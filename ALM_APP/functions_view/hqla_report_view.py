# ALM_APP/functions_view/hqla_report_view.py

from django.shortcuts import render
from ALM_APP.models import HQLAStock
from django.shortcuts import render
from ALM_APP.models import HQLAStockOutflow

def hqla_report_view(request):
    mis_date_param = request.GET.get('fic_mis_date')
    currency_param = request.GET.get('currency')

    # 1) Base QuerySet
    stocks = HQLAStock.objects.all()

    # 2) Gather distinct FIC MIS dates (order by date ascending)
    all_mis_dates = (
        HQLAStock.objects.values_list('fic_mis_date', flat=True)
                        .distinct()
                        .order_by('fic_mis_date')
    )

    # 3) Gather distinct Currencies
    all_currencies = (
        HQLAStock.objects.values_list('v_ccy_code', flat=True)
                        .distinct()
                        .order_by('v_ccy_code')
    )

    # 4) Apply filters if provided
    if mis_date_param:
        stocks = stocks.filter(fic_mis_date=mis_date_param)
    if currency_param:
        stocks = stocks.filter(v_ccy_code=currency_param)

    # 5) Determine the filtered currencies present in the final result
    currencies = list(stocks.values_list('v_ccy_code', flat=True).distinct())

    # 6) Build your dictionary groupings (Level 1, Level 2A, etc.)
    # (same grouping logic as before...)

    # For example:
    level_1_assets = {}
    level_2a_assets = {}
    level_2b_assets = {}
    hqla_totals = {}

    for ccy in currencies:
        currency_stocks = stocks.filter(v_ccy_code=ccy)

        l1_all = currency_stocks.filter(hqla_level="Level 1")
        l1_totals = l1_all.filter(v_prod_type__startswith="Total Level 1")
        l1_items = l1_all.exclude(v_prod_type__startswith="Total Level 1")

        l2a_all = currency_stocks.filter(hqla_level="Level 2A")
        l2a_totals = l2a_all.filter(v_prod_type__icontains="Level 2A")
        l2a_items = l2a_all.exclude(v_prod_type__icontains="Level 2A")

        l2b_all = currency_stocks.filter(hqla_level="Level 2B")
        l2b_totals = l2b_all.filter(v_prod_type__icontains="Level 2B")
        l2b_items = l2b_all.exclude(v_prod_type__icontains="Level 2B")

        currency_totals = currency_stocks.filter(v_prod_code__startswith="HQLA_TOTAL_")

        level_1_assets[ccy] = {"items": l1_items, "totals": l1_totals}
        level_2a_assets[ccy] = {"items": l2a_items, "totals": l2a_totals}
        level_2b_assets[ccy] = {"items": l2b_items, "totals": l2b_totals}
        hqla_totals[ccy]     = currency_totals

    # 7) Build context for the template
    context = {
        "fic_mis_date_selected": mis_date_param,
        "currency_selected": currency_param,
        "all_mis_dates": all_mis_dates,       # For the dropdown
        "all_currencies": all_currencies,     # For the dropdown
        "currencies": currencies,
        "level_1_assets": level_1_assets,
        "level_2a_assets": level_2a_assets,
        "level_2b_assets": level_2b_assets,
        "hqla_totals": hqla_totals,
    }
    return render(request, "LRM_APP/lcr/hqla_report.html", context)



#####################################################3##########################
from django.shortcuts import render
from ALM_APP.models import HQLAStockOutflow

def lcr_outflows_view(request):
    """
    Displays LCR Outflows as stored by the classification function.
    The records are organized into a structured dictionary as follows:
      - Top-level keys: each distinct currency (v_ccy_code).
      - For each currency, two keys:
          "hqla_levels": a dict keyed by hqla_level (e.g., Retail Deposits, Wholesale Funding)
                        Each hqla_level contains:
                           • "aggregated": a dict of detail rows (those NOT starting with "Total")
                              grouped by secondary_grouping; each secondary group is a dict
                              keyed by product type (v_prod_type) with aggregated sums:
                                  - n_amount
                                  - weighted_amount
                                  - adjusted_amount
                                  - risk_weight (assumed constant for that product type)
                           • "total": the pre‐calculated total row for that hqla_level 
                              (record whose v_prod_type starts with "Total")
      - "overall_total": the overall total row for the currency (record with v_prod_type starting with "Total Cash Outflows")
    """
    fic_mis_date_selected = request.GET.get("fic_mis_date", "")
    currency_selected = request.GET.get("currency", "")

    qs = HQLAStockOutflow.objects.all()
    if fic_mis_date_selected:
        qs = qs.filter(fic_mis_date=fic_mis_date_selected)
    if currency_selected:
        qs = qs.filter(v_ccy_code=currency_selected)

    # For dropdown menus
    all_mis_dates = HQLAStockOutflow.objects.values_list("fic_mis_date", flat=True).distinct()
    all_currencies = HQLAStockOutflow.objects.values_list("v_ccy_code", flat=True).distinct()

    structured_data = {}

    for record in qs:
        currency = record.v_ccy_code
        if currency not in structured_data:
            structured_data[currency] = {"hqla_levels": {}, "overall_total": None}

        # Identify overall total record (Total Cash Outflows)
        if record.v_prod_type.startswith("Total Cash Outflows"):
            structured_data[currency]["overall_total"] = record

        # Identify per-level total rows (those with v_prod_type starting with "Total")
        elif record.v_prod_type.startswith("Total"):
            hqla_level = record.hqla_level or "Undefined"
            if hqla_level not in structured_data[currency]["hqla_levels"]:
                structured_data[currency]["hqla_levels"][hqla_level] = {"aggregated": {}, "total": None}
            structured_data[currency]["hqla_levels"][hqla_level]["total"] = record

        # Detail rows: aggregate by hqla_level and secondary_grouping, then by product type
        else:
            hqla_level = record.hqla_level or "Undefined"
            secondary = record.secondary_grouping or ""
            if hqla_level not in structured_data[currency]["hqla_levels"]:
                structured_data[currency]["hqla_levels"][hqla_level] = {"aggregated": {}, "total": None}
            agg = structured_data[currency]["hqla_levels"][hqla_level]["aggregated"]
            if secondary not in agg:
                agg[secondary] = {}
            prod_type = record.v_prod_type
            if prod_type not in agg[secondary]:
                agg[secondary][prod_type] = {
                    "n_amount": 0,
                    "risk_weight": record.risk_weight,  # assumed constant for a product type
                    "weighted_amount": 0,
                    "adjusted_amount": 0,
                }
            agg[secondary][prod_type]["n_amount"] += record.n_amount
            agg[secondary][prod_type]["weighted_amount"] += record.weighted_amount
            agg[secondary][prod_type]["adjusted_amount"] += record.adjusted_amount

    context = {
        "structured_data": structured_data,
        "all_mis_dates": all_mis_dates,
        "all_currencies": all_currencies,
        "fic_mis_date_selected": fic_mis_date_selected,
        "currency_selected": currency_selected,
    }
    return render(request, "LRM_APP/lcr/lcr_outflows.html", context)



######################################################################################################

from django.shortcuts import render
from ALM_APP.models import HQLAStockInflow

def lcr_inflows_view(request):
    """
    Displays LCR Inflows as stored by the classification function.
    The records are organized into a structured dictionary as follows:
      - Top-level keys: each distinct currency (`v_ccy_code`).
      - For each currency, two keys:
          "hqla_levels": a dict keyed by `hqla_level` (e.g., Loan Repayments, Depositor Inflows)
                        Each `hqla_level` contains:
                           • "aggregated": a dict of detail rows (those NOT starting with "Total")
                              grouped by `secondary_grouping`; each secondary group is a dict
                              keyed by product type (`v_prod_type`) with aggregated sums:
                                  - `n_amount`
                                  - `weighted_amount`
                                  - `adjusted_amount`
                                  - `risk_weight` (assumed constant for that product type)
                           • "total": the pre‐calculated total row for that `hqla_level` 
                              (record whose `v_prod_type` starts with "Total")
      - "overall_total": the overall total row for the currency (record with `v_prod_type` starting with "Total Cash Inflows")
    """
    fic_mis_date_selected = request.GET.get("fic_mis_date", "")
    currency_selected = request.GET.get("currency", "")

    qs = HQLAStockInflow.objects.all()
    if fic_mis_date_selected:
        qs = qs.filter(fic_mis_date=fic_mis_date_selected)
    if currency_selected:
        qs = qs.filter(v_ccy_code=currency_selected)

    # For dropdown menus
    all_mis_dates = HQLAStockInflow.objects.values_list("fic_mis_date", flat=True).distinct()
    all_currencies = HQLAStockInflow.objects.values_list("v_ccy_code", flat=True).distinct()

    structured_data = {}

    for record in qs:
        currency = record.v_ccy_code
        if currency not in structured_data:
            structured_data[currency] = {"hqla_levels": {}, "overall_total": None}

        # Identify overall total record (Total Cash Inflows)
        if record.v_prod_type.startswith("Total Cash Inflows"):
            structured_data[currency]["overall_total"] = record

        # Identify per-level total rows (those with v_prod_type starting with "Total")
        elif record.v_prod_type.startswith("Total"):
            hqla_level = record.hqla_level or "Undefined"
            if hqla_level not in structured_data[currency]["hqla_levels"]:
                structured_data[currency]["hqla_levels"][hqla_level] = {"aggregated": {}, "total": None}
            structured_data[currency]["hqla_levels"][hqla_level]["total"] = record

        # Detail rows: aggregate by hqla_level and secondary_grouping, then by product type
        else:
            hqla_level = record.hqla_level or "Undefined"
            secondary = record.secondary_grouping or ""
            if hqla_level not in structured_data[currency]["hqla_levels"]:
                structured_data[currency]["hqla_levels"][hqla_level] = {"aggregated": {}, "total": None}
            agg = structured_data[currency]["hqla_levels"][hqla_level]["aggregated"]
            if secondary not in agg:
                agg[secondary] = {}
            prod_type = record.v_prod_type
            if prod_type not in agg[secondary]:
                agg[secondary][prod_type] = {
                    "n_amount": 0,
                    "risk_weight": record.risk_weight,  # assumed constant for a product type
                    "weighted_amount": 0,
                    "adjusted_amount": 0,
                }
            agg[secondary][prod_type]["n_amount"] += record.n_amount
            agg[secondary][prod_type]["weighted_amount"] += record.weighted_amount
            agg[secondary][prod_type]["adjusted_amount"] += record.adjusted_amount

    context = {
        "structured_data": structured_data,
        "all_mis_dates": all_mis_dates,
        "all_currencies": all_currencies,
        "fic_mis_date_selected": fic_mis_date_selected,
        "currency_selected": currency_selected,
    }
    return render(request, "LRM_APP/lcr/lcr_inflows.html", context)




##################################################################################################

from django.shortcuts import render
from ALM_APP.models import LCRCalculation

def lcr_report_view(request):
    """
    Displays LCR Calculation results grouped by currency and then by category.
    
    The table has three columns:
      - CATEGORY (displayed as a header for that category)
      - SUB-CATEGORY (the record’s v_product_name)
      - TOTAL WEIGHTED VALUE (average), which is:
            • adjusted_amount for HQLA, CASH OUTFLOWS, and CASH INFLOWS;
            • net_cash_outflows for NET CASH OUTFLOWS;
            • lcr_ratio (formatted as a percentage) for LCR RATIO.
    
    For each currency and category:
      - All level records (those with total_type "level" or not flagged as overall) are listed first.
      - Then, all overall total records (those whose total_type is "overall_after" or "overall",
        or whose v_prod_type starts with "Total") are displayed below.
    
    Fixed category order:
      1. HIGH-QUALITY LIQUID ASSETS
      2. CASH OUTFLOWS
      3. CASH INFLOWS
      4. NET CASH OUTFLOWS
      5. LCR RATIO
    """
    fic_mis_date = request.GET.get("fic_mis_date", "").strip()
    currency_selected = request.GET.get("currency", "").strip()
    
    qs = LCRCalculation.objects.all()
    if fic_mis_date:
        qs = qs.filter(fic_mis_date=fic_mis_date)
    if currency_selected:
        qs = qs.filter(v_ccy_code=currency_selected)
    
    category_order = [
        "HIGH-QUALITY LIQUID ASSETS",
        "CASH OUTFLOWS",
        "CASH INFLOWS",
        "NET CASH OUTFLOWS",
        "LCR RATIO"
    ]
    
    # Group records by currency and then by category.
    # For each category, we create two lists:
    # "level": all detail records (typically with total_type "level")
    # "overall": records whose total_type is "overall_after" or "overall", or whose v_prod_type starts with "Total"
    structured_data = {}
    for rec in qs:
        cur = rec.v_ccy_code
        if cur not in structured_data:
            structured_data[cur] = {cat: {"level": [], "overall": []} for cat in category_order}
        cat = rec.category
        if cat not in category_order:
            continue
        if (rec.total_type and rec.total_type.lower() in ["overall_after", "overall"]) or rec.v_prod_type.startswith("Total"):
            structured_data[cur][cat]["overall"].append(rec)
        else:
            structured_data[cur][cat]["level"].append(rec)
    
    # For dropdown menus: get distinct MIS dates and currencies from qs.
    all_mis_dates = qs.order_by("fic_mis_date").values_list("fic_mis_date", flat=True).distinct()
    all_currencies = qs.order_by("v_ccy_code").values_list("v_ccy_code", flat=True).distinct()
    
    context = {
        "fic_mis_date": fic_mis_date,
        "currency_selected": currency_selected,
        "structured_data": structured_data,
        "category_order": category_order,
        "all_mis_dates": all_mis_dates,
        "all_currencies": all_currencies,
    }
    return render(request, "LRM_APP/lcr/lcr_report.html", context)

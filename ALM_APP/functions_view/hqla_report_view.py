# ALM_APP/functions_view/hqla_report_view.py

from django.shortcuts import render
from ALM_APP.models import HQLAStock

def hqla_report_view(request):
    # OPTIONAL filters
    mis_date_param = request.GET.get('fic_mis_date')  # e.g. "2023-01-15"
    currency_param = request.GET.get('currency')      # e.g. "USD"

    # Base QuerySet
    stocks = HQLAStock.objects.all()

    # Apply filters if provided
    if mis_date_param:
        stocks = stocks.filter(fic_mis_date=mis_date_param)
    if currency_param:
        stocks = stocks.filter(v_ccy_code=currency_param)

    # Distinct currencies from the filtered set
    currencies = list(stocks.values_list('v_ccy_code', flat=True).distinct())

    level_1_assets = {}
    level_2a_assets = {}
    level_2b_assets = {}
    hqla_totals = {}

    for ccy in currencies:
        currency_stocks = stocks.filter(v_ccy_code=ccy)

        # ---------------------------
        # Level 1
        # ---------------------------
        l1_all = currency_stocks.filter(hqla_level="Level 1")
        # Identify total rows by checking if they start with "Total Level 1" or any known pattern
        l1_totals = l1_all.filter(v_prod_type__startswith="Total Level 1")
        l1_items = l1_all.exclude(v_prod_type__startswith="Total Level 1")

        # ---------------------------
        # Level 2A
        # ---------------------------
        l2a_all = currency_stocks.filter(hqla_level="Level 2A")
        l2a_totals = l2a_all.filter(v_prod_type__icontains="Level 2A")
        l2a_items = l2a_all.exclude(v_prod_type__icontains="Level 2A")

        # ---------------------------
        # Level 2B
        # ---------------------------
        l2b_all = currency_stocks.filter(hqla_level="Level 2B")
        l2b_totals = l2b_all.filter(v_prod_type__icontains="Level 2B")
        l2b_items = l2b_all.exclude(v_prod_type__icontains="Level 2B")

        # If you have an overall "Total HQLA" row for the currency (e.g. "HQLA_TOTAL_"),
        # you can keep that separate.
        currency_totals = currency_stocks.filter(v_prod_code__startswith="HQLA_TOTAL_")

        # Now store them in dictionaries
        level_1_assets[ccy] = {
            "items":  l1_items,
            "totals": l1_totals,
        }
        level_2a_assets[ccy] = {
            "items":  l2a_items,
            "totals": l2a_totals,
        }
        level_2b_assets[ccy] = {
            "items":  l2b_items,
            "totals": l2b_totals,
        }
        hqla_totals[ccy] = currency_totals

    context = {
        "fic_mis_date_selected": mis_date_param,
        "currency_selected": currency_param,
        "currencies": currencies,
        "level_1_assets": level_1_assets,
        "level_2a_assets": level_2a_assets,
        "level_2b_assets": level_2b_assets,
        "hqla_totals": hqla_totals,
    }
    return render(request, "LRM_APP/lcr/hqla_report.html", context)

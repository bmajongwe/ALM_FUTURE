from django.db import transaction
from decimal import Decimal
from ALM_APP.models import NSFRStock, NSFRStockSummary

def populate_nsfr_stock_summary(fic_mis_date):
    """
    Populates NSFRStockSummary for the given reporting date.
    
    For each funding type:
      1. Level_total rows:
         - For each NSFRStock row with row_category = "level_total", compute n_amount as the sum of
           amount_less_6_months, amount_6_to_12_months, and amount_greater_1_year.
         - Copy total_calculated_sf into total_available_sf (if v_nsfr_type is "AVAILABLE STABLE FUNDING")
           or into total_required_sf (if v_nsfr_type is "REQUIRED STABLE FUNDING").
         - Preserve v_nsfr_type, v_prod_type_level, and v_ccy_code.
         
      2. Overall_total rows:
         - Group NSFRStock overall_total rows by their actual currency (v_ccy_code) and sum the
           corresponding n_amount and total_calculated_sf fields.
         - Insert one overall_total record per currency for each funding type.
         
      3. NSFR Ratio:
         - For each currency overall group, compute the NSFR ratio as:
               (overall total_available_sf / overall total_required_sf) * 100
         - Instead of updating the overall_total rows, create a separate summary record (with
           v_nsfr_type = "NSFR RATIO" and v_prod_type_level = "NSFR RATIO", row_category = "ratio")
           that contains the computed ratio.
           
    Column naming in NSFRStockSummary:
      - fic_mis_date: Reporting Date
      - v_nsfr_type: Funding Type ("AVAILABLE STABLE FUNDING" / "REQUIRED STABLE FUNDING" or "NSFR RATIO")
      - v_prod_type_level: Product Level (or "OVERALL TOTAL" for overall rows, "NSFR RATIO" for ratio record)
      - v_ccy_code: Currency Code (preserved from NSFRStock)
      - n_amount: Sum of the three amount fields from NSFRStock (for level_total/overall_total)
      - total_calculated_sf: The stable funding value from NSFRStock
      - total_available_sf / total_required_sf: Mapped from total_calculated_sf (based on funding type)
      - nsfr_ratio: The computed NSFR percentage (in a separate ratio record)
      - row_category: "level_total", "overall_total", or "ratio"
    """
    try:
        # Delete existing summary records for the reporting date.
        NSFRStockSummary.objects.filter(fic_mis_date=fic_mis_date).delete()
        
        summary_entries = []
        
        # --- Process AVAILABLE STABLE FUNDING ---
        avail_level_qs = NSFRStock.objects.filter(
            fic_mis_date=fic_mis_date,
            v_nsfr_type="AVAILABLE STABLE FUNDING",
            row_category="level_total"
        )
        for rec in avail_level_qs:
            n_amt = (rec.amount_less_6_months or Decimal("0.00")) + \
                    (rec.amount_6_to_12_months or Decimal("0.00")) + \
                    (rec.amount_greater_1_year or Decimal("0.00"))
            summary_entries.append(NSFRStockSummary(
                fic_mis_date = fic_mis_date,
                v_nsfr_type = rec.v_nsfr_type,              # "AVAILABLE STABLE FUNDING"
                v_prod_type_level = rec.v_prod_type_level,    # as in NSFRStock
                v_ccy_code = rec.v_ccy_code,                  # actual currency
                row_category = rec.row_category,              # "level_total"
                n_amount = n_amt,
                total_calculated_sf = rec.total_calculated_sf,
                total_available_sf = rec.total_calculated_sf   # mapped to available
            ))
        
        # Process overall_total rows for AVAILABLE STABLE FUNDING, grouping by actual currency.
        overall_avail = {}
        avail_overall_qs = NSFRStock.objects.filter(
            fic_mis_date=fic_mis_date,
            v_nsfr_type="AVAILABLE STABLE FUNDING",
            row_category="overall_total"
        )
        for rec in avail_overall_qs:
            currency = rec.v_ccy_code
            n_amt = (rec.amount_less_6_months or Decimal("0.00")) + \
                    (rec.amount_6_to_12_months or Decimal("0.00")) + \
                    (rec.amount_greater_1_year or Decimal("0.00"))
            if currency not in overall_avail:
                overall_avail[currency] = {
                    "n_amount": n_amt,
                    "total_calculated_sf": rec.total_calculated_sf
                }
            else:
                overall_avail[currency]["n_amount"] += n_amt
                overall_avail[currency]["total_calculated_sf"] += rec.total_calculated_sf
        
        for currency, agg in overall_avail.items():
            summary_entries.append(NSFRStockSummary(
                fic_mis_date = fic_mis_date,
                v_nsfr_type = "AVAILABLE STABLE FUNDING",
                v_prod_type_level = "OVERALL TOTAL",
                v_ccy_code = currency,  # preserve actual currency
                row_category = "overall_total",
                n_amount = agg["n_amount"],
                total_calculated_sf = agg["total_calculated_sf"],
                total_available_sf = agg["total_calculated_sf"]
            ))
        
        # --- Process REQUIRED STABLE FUNDING ---
        req_level_qs = NSFRStock.objects.filter(
            fic_mis_date=fic_mis_date,
            v_nsfr_type="REQUIRED STABLE FUNDING",
            row_category="level_total"
        )
        for rec in req_level_qs:
            n_amt = (rec.amount_less_6_months or Decimal("0.00")) + \
                    (rec.amount_6_to_12_months or Decimal("0.00")) + \
                    (rec.amount_greater_1_year or Decimal("0.00"))
            summary_entries.append(NSFRStockSummary(
                fic_mis_date = fic_mis_date,
                v_nsfr_type = rec.v_nsfr_type,              # "REQUIRED STABLE FUNDING"
                v_prod_type_level = rec.v_prod_type_level,    # as in NSFRStock
                v_ccy_code = rec.v_ccy_code,                  # actual currency
                row_category = rec.row_category,              # "level_total"
                n_amount = n_amt,
                total_calculated_sf = rec.total_calculated_sf,
                total_required_sf = rec.total_calculated_sf   # mapped to required
            ))
        
        overall_req = {}
        req_overall_qs = NSFRStock.objects.filter(
            fic_mis_date=fic_mis_date,
            v_nsfr_type="REQUIRED STABLE FUNDING",
            row_category="overall_total"
        )
        for rec in req_overall_qs:
            currency = rec.v_ccy_code
            n_amt = (rec.amount_less_6_months or Decimal("0.00")) + \
                    (rec.amount_6_to_12_months or Decimal("0.00")) + \
                    (rec.amount_greater_1_year or Decimal("0.00"))
            if currency not in overall_req:
                overall_req[currency] = {
                    "n_amount": n_amt,
                    "total_calculated_sf": rec.total_calculated_sf
                }
            else:
                overall_req[currency]["n_amount"] += n_amt
                overall_req[currency]["total_calculated_sf"] += rec.total_calculated_sf
        
        for currency, agg in overall_req.items():
            summary_entries.append(NSFRStockSummary(
                fic_mis_date = fic_mis_date,
                v_nsfr_type = "REQUIRED STABLE FUNDING",
                v_prod_type_level = "OVERALL TOTAL",
                v_ccy_code = currency,  # preserve actual currency
                row_category = "overall_total",
                n_amount = agg["n_amount"],
                total_calculated_sf = agg["total_calculated_sf"],
                total_required_sf = agg["total_calculated_sf"]
            ))
        
        # Bulk insert all summary entries
        with transaction.atomic():
            if summary_entries:
                NSFRStockSummary.objects.bulk_create(summary_entries)
                print(f"✅ Inserted {len(summary_entries)} NSFRStockSummary records for {fic_mis_date}.")
            else:
                print(f"⚠️ No NSFRStockSummary records created for {fic_mis_date}.")
        
        # --- Calculate NSFR Ratio as a stand-alone record ---
        # For each currency overall group, compute the NSFR ratio:
        #     ratio = (overall total_available_sf) / (overall total_required_sf) * 100
        # Create a separate NSFRStockSummary record (row_category="ratio")
        # with v_nsfr_type and v_prod_type_level set to "NSFR RATIO".
        overall_currencies = NSFRStockSummary.objects.filter(
            fic_mis_date=fic_mis_date,
            row_category="overall_total"
        ).values_list('v_ccy_code', flat=True).distinct()
        
        ratio_entries = []
        for currency in overall_currencies:
            avail_row = NSFRStockSummary.objects.filter(
                fic_mis_date=fic_mis_date,
                row_category="overall_total",
                v_nsfr_type="AVAILABLE STABLE FUNDING",
                v_ccy_code=currency
            ).first()
            req_row = NSFRStockSummary.objects.filter(
                fic_mis_date=fic_mis_date,
                row_category="overall_total",
                v_nsfr_type="REQUIRED STABLE FUNDING",
                v_ccy_code=currency
            ).first()
            if avail_row and req_row and req_row.total_required_sf and req_row.total_required_sf != Decimal("0.00"):
                ratio = (avail_row.total_available_sf / req_row.total_required_sf) * Decimal("100.00")
                ratio_entries.append(NSFRStockSummary(
                    fic_mis_date = fic_mis_date,
                    v_nsfr_type = "NSFR RATIO",
                    v_prod_type_level = "NSFR RATIO",
                    v_ccy_code = currency,
                    row_category = "ratio",
                    n_amount = Decimal("0.00"),
                    total_calculated_sf = Decimal("0.00"),
                    total_available_sf = Decimal("0.00"),
                    total_required_sf = Decimal("0.00"),
                    nsfr_ratio = ratio
                ))
                desc = "NSFR Met" if ratio >= Decimal("100.00") else "NSFR Not Met"
                print(f"For currency {currency}, NSFR Ratio = {ratio:.2f} ({desc}).")
            else:
                print(f"Insufficient data to calculate NSFR Ratio for currency {currency}.")
        
        # Bulk insert ratio entries
        with transaction.atomic():
            if ratio_entries:
                NSFRStockSummary.objects.bulk_create(ratio_entries)
                print(f"✅ Inserted {len(ratio_entries)} NSFR RATIO records for {fic_mis_date}.")
            else:
                print(f"⚠️ No NSFR RATIO records created for {fic_mis_date}.")
                
    except Exception as e:
        print(f"❌ Error in populate_nsfr_stock_summary: {e}")

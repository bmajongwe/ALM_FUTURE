from collections import defaultdict
from django.db import transaction
from decimal import Decimal
from ALM_APP.models import (
    ExtractedNsfrData,
    NSFRClassification,
    NSFRStock
)

def populate_nsfr_stock(fic_mis_date):
    """
    Populates NSFRStock by:
      1) Aggregating ExtractedNsfrData by v_prod_type and currency (v_ccy_code)
         for different time horizons.
      2) Looking up NSFRClassification to apply ASF/RSF factors.
      3) Creating one NSFRStock row per product type and currency.
      4) Creating aggregated total rows for each v_prod_type_level per currency.
      5) Creating an overall total row for each v_nsfr_type per currency.

    Final structure:
      - Normal rows: (v_prod_type, v_prod_type_level, v_nsfr_type, v_ccy_code) with row_category "normal"
      - "TOTAL for {v_prod_type_level}" rows with row_category "level_total"
      - "OVERALL TOTAL for {v_nsfr_type}" rows with row_category "overall_total"
    """
    try:
        print(f"🔍 Starting NSFR Stock population (aggregated) on date {fic_mis_date}")

        # 1️⃣ Delete old NSFRStock records for this date
        deleted_count = NSFRStock.objects.filter(fic_mis_date=fic_mis_date).delete()
        print(f"🗑️ Deleted {deleted_count[0]} old NSFRStock records for {fic_mis_date}")

        # 2️⃣ Retrieve relevant extracted data
        nsfr_extracted = ExtractedNsfrData.objects.filter(fic_mis_date=fic_mis_date)
        print(f"🔹 Found {nsfr_extracted.count()} ExtractedNsfrData records for date {fic_mis_date}")

        # Aggregator for product types: keyed by (prod_type, currency)
        aggregator_pt = defaultdict(lambda: {
            "amount_less_6m": Decimal("0.00"),
            "amount_6_12m": Decimal("0.00"),
            "amount_greater_1y": Decimal("0.00")
        })

        # Aggregator for product type levels: keyed by (nsfr_type, prod_level, currency)
        aggregator_lvl = defaultdict(lambda: {
            "amount_less_6m": Decimal("0.00"),
            "amount_6_12m": Decimal("0.00"),
            "amount_greater_1y": Decimal("0.00"),
            "calculated_sf_less_6m": Decimal("0.00"),
            "calculated_sf_6_12m": Decimal("0.00"),
            "calculated_sf_greater_1y": Decimal("0.00"),
            "total_calculated_sf": Decimal("0.00")
        })

        # Aggregator for overall NSFR type totals: keyed by (nsfr_type, currency)
        aggregator_type = defaultdict(lambda: {
            "amount_less_6m": Decimal("0.00"),
            "amount_6_12m": Decimal("0.00"),
            "amount_greater_1y": Decimal("0.00"),
            "calculated_sf_less_6m": Decimal("0.00"),
            "calculated_sf_6_12m": Decimal("0.00"),
            "calculated_sf_greater_1y": Decimal("0.00"),
            "total_calculated_sf": Decimal("0.00")
        })

        nsfr_stock_records = []
        skipped_count = 0

        with transaction.atomic():
            # 3️⃣ Aggregate amounts by horizon per product type and currency
            for record in nsfr_extracted:
                prod_type = record.v_prod_type
                currency = record.v_ccy_code  # ensure this field exists on ExtractedNsfrData
                horizon_label = (record.time_horizon_label or "").strip()
                amt_value = Decimal(record.n_total_cash_flow_amount or "0")

                key = (prod_type, currency)
                if horizon_label == "< 6 months":
                    aggregator_pt[key]["amount_less_6m"] += amt_value
                elif horizon_label == "≥ 6 months to < 1 year":
                    aggregator_pt[key]["amount_6_12m"] += amt_value
                elif horizon_label == "≥ 1 year":
                    aggregator_pt[key]["amount_greater_1y"] += amt_value
                else:
                    # If horizon label is unexpected, skip or log
                    pass

            print(f"🔹 Aggregated data for {len(aggregator_pt)} unique product and currency combinations")

            # 4️⃣ Build normal product-level rows (grouped by product type and currency)
            for (prod_type, currency), data_dict in aggregator_pt.items():
                classification = NSFRClassification.objects.filter(v_prod_type=prod_type).first()
                if not classification:
                    print(f"⚠️ No NSFRClassification for prod_type={prod_type}. Skipping.")
                    skipped_count += 1
                    continue

                # a) Identify amounts
                less_6m_amt = data_dict["amount_less_6m"]
                six_12m_amt = data_dict["amount_6_12m"]
                greater_1y_amt = data_dict["amount_greater_1y"]

                # b) Get classification factors
                factor_less_6m = classification.funding_factor_less_6_months
                factor_6_12m = classification.funding_factor_6_to_12_months
                factor_greater_1y = classification.funding_factor_greater_1_year

                # c) Calculate SF values per horizon
                calc_less_6m = less_6m_amt * (factor_less_6m / Decimal("100"))
                calc_6_12m = six_12m_amt * (factor_6_12m / Decimal("100"))
                calc_greater_1y = greater_1y_amt * (factor_greater_1y / Decimal("100"))
                total_calc = calc_less_6m + calc_6_12m + calc_greater_1y

                # d) Insert normal product row with currency
                nsfr_stock_records.append(NSFRStock(
                    fic_mis_date=fic_mis_date,
                    v_nsfr_type=classification.v_nsfr_type,
                    v_prod_type_level=classification.v_prod_type_level,
                    v_prod_type=prod_type,
                    v_ccy_code=currency,
                    amount_less_6_months=less_6m_amt,
                    amount_6_to_12_months=six_12m_amt,
                    amount_greater_1_year=greater_1y_amt,
                    funding_factor_less_6_months=factor_less_6m,
                    funding_factor_6_to_12_months=factor_6_12m,
                    funding_factor_greater_1_year=factor_greater_1y,
                    calculated_sf_less_6_months=calc_less_6m,
                    calculated_sf_6_to_12_months=calc_6_12m,
                    calculated_sf_greater_1_year=calc_greater_1y,
                    total_calculated_sf=total_calc,
                    row_category="normal"
                ))

                # e) Aggregate into level and overall totals (including currency)
                nsfr_type = classification.v_nsfr_type
                prod_level = classification.v_prod_type_level
                lvl_key = (nsfr_type, prod_level, currency)
                type_key = (nsfr_type, currency)

                aggregator_lvl[lvl_key]["amount_less_6m"] += less_6m_amt
                aggregator_lvl[lvl_key]["amount_6_12m"] += six_12m_amt
                aggregator_lvl[lvl_key]["amount_greater_1y"] += greater_1y_amt
                aggregator_lvl[lvl_key]["calculated_sf_less_6m"] += calc_less_6m
                aggregator_lvl[lvl_key]["calculated_sf_6_12m"] += calc_6_12m
                aggregator_lvl[lvl_key]["calculated_sf_greater_1y"] += calc_greater_1y
                aggregator_lvl[lvl_key]["total_calculated_sf"] += total_calc

                aggregator_type[type_key]["amount_less_6m"] += less_6m_amt
                aggregator_type[type_key]["amount_6_12m"] += six_12m_amt
                aggregator_type[type_key]["amount_greater_1y"] += greater_1y_amt
                aggregator_type[type_key]["calculated_sf_less_6m"] += calc_less_6m
                aggregator_type[type_key]["calculated_sf_6_12m"] += calc_6_12m
                aggregator_type[type_key]["calculated_sf_greater_1y"] += calc_greater_1y
                aggregator_type[type_key]["total_calculated_sf"] += total_calc

            # 5️⃣ Build total rows for each v_prod_type_level per currency
            for (nsfr_type, prod_level, currency), agg_dict in aggregator_lvl.items():
                amt_less_6m = agg_dict["amount_less_6m"]
                amt_6_12m = agg_dict["amount_6_12m"]
                amt_greater_1y = agg_dict["amount_greater_1y"]
                calc_less_6m = agg_dict["calculated_sf_less_6m"]
                calc_6_12m = agg_dict["calculated_sf_6_12m"]
                calc_greater_1y = agg_dict["calculated_sf_greater_1y"]
                total_calc = agg_dict["total_calculated_sf"]

                nsfr_stock_records.append(NSFRStock(
                    fic_mis_date=fic_mis_date,
                    v_nsfr_type=nsfr_type,
                    v_prod_type_level=prod_level,
                    v_prod_type=f"TOTAL for {prod_level}",
                    v_ccy_code=currency,
                    amount_less_6_months=amt_less_6m,
                    amount_6_to_12_months=amt_6_12m,
                    amount_greater_1_year=amt_greater_1y,
                    funding_factor_less_6_months=Decimal("0"),
                    funding_factor_6_to_12_months=Decimal("0"),
                    funding_factor_greater_1_year=Decimal("0"),
                    calculated_sf_less_6_months=calc_less_6m,
                    calculated_sf_6_to_12_months=calc_6_12m,
                    calculated_sf_greater_1_year=calc_greater_1y,
                    total_calculated_sf=total_calc,
                    row_category="level_total"
                ))

            # 6️⃣ Build overall total rows for each v_nsfr_type per currency
            for (nsfr_type, currency), agg_dict in aggregator_type.items():
                amt_less_6m = agg_dict["amount_less_6m"]
                amt_6_12m = agg_dict["amount_6_12m"]
                amt_greater_1y = agg_dict["amount_greater_1y"]
                calc_less_6m = agg_dict["calculated_sf_less_6m"]
                calc_6_12m = agg_dict["calculated_sf_6_12m"]
                calc_greater_1y = agg_dict["calculated_sf_greater_1y"]
                total_calc = agg_dict["total_calculated_sf"]

                nsfr_stock_records.append(NSFRStock(
                    fic_mis_date=fic_mis_date,
                    v_nsfr_type=nsfr_type,
                    v_prod_type_level=f"TOTAL_{nsfr_type}",
                    v_prod_type=f"OVERALL TOTAL for {nsfr_type}",
                    v_ccy_code=currency,
                    amount_less_6_months=amt_less_6m,
                    amount_6_to_12_months=amt_6_12m,
                    amount_greater_1_year=amt_greater_1y,
                    funding_factor_less_6_months=Decimal("0"),
                    funding_factor_6_to_12_months=Decimal("0"),
                    funding_factor_greater_1_year=Decimal("0"),
                    calculated_sf_less_6_months=calc_less_6m,
                    calculated_sf_6_to_12_months=calc_6_12m,
                    calculated_sf_greater_1_year=calc_greater_1y,
                    total_calculated_sf=total_calc,
                    row_category="overall_total"
                ))

            # 7️⃣ Bulk insert all data
            if nsfr_stock_records:
                NSFRStock.objects.bulk_create(nsfr_stock_records)
                print(f"✅ Inserted {len(nsfr_stock_records)} NSFRStock records for {fic_mis_date}.")
            else:
                print(f"⚠️ No NSFRStock records created for {fic_mis_date}. Skipped {skipped_count} product types.")

    except Exception as e:
        print(f"❌ Error in populate_nsfr_stock: {e}")

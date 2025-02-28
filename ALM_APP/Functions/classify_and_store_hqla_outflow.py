from collections import defaultdict
from django.db import transaction
from decimal import Decimal
from ALM_APP.models import (
    ExtractedLiquidityData, 
    HQLAInflowOutflowClassification, 
    HQLAStockOutflow
)

def classify_and_store_hqla_outflow_ccy(fic_mis_date):
    """
    Classifies extracted liquidity data into HQLA outflows for LCR purposes.
    Processes only **outflows** and applies risk weight as the outflow rate.
    Inserts one total per `hqla_level` (e.g., Retail Deposits, Wholesale Funding) and an
    overall total for cash outflows. Summary rows are flagged using `is_total` and `total_type`.
    """
    try:
        print(f"🔍 Starting multi-currency LCR Outflow classification for {fic_mis_date}")

        # 1️⃣ Delete old outflow records for this date
        deleted_count = HQLAStockOutflow.objects.filter(fic_mis_date=fic_mis_date).delete()
        print(f"🗑️ Deleted {deleted_count[0]} old LCR outflow records for {fic_mis_date}")

        # 2️⃣ Retrieve **only outflows** from ExtractedLiquidityData
        extracted_outflows = ExtractedLiquidityData.objects.filter(
            fic_mis_date=fic_mis_date,
            account_type="Outflow"
        )
        classifications = HQLAInflowOutflowClassification.objects.filter(is_outflow="Y")  # Only pick outflows

        print(f"🔹 Found {extracted_outflows.count()} extracted outflow records to classify.")

        # (A) Group data by (prod_type, prod_code, ccy)
        grouped_data = defaultdict(Decimal)   # (prod_type, prod_code, ccy) -> sum of original amounts
        detail_rows = {}                      # Store a sample row (for name, etc.)

        for record in extracted_outflows:
            key = (record.v_prod_type, record.v_prod_code, record.v_ccy_code)
            grouped_data[key] += Decimal(record.n_total_cash_flow_amount)
            detail_rows[key] = record  # Keep reference for product_name, etc.

        print(f"🔹 Grouped into {len(grouped_data)} unique product-currency combos.")

        # Summed outflow amounts per currency (for adjusted amounts)
        total_adjusted_outflows = defaultdict(Decimal)
        # Store detailed (non-total) entries per currency.
        currency_to_outflow_entries = defaultdict(list)
        skipped_records = 0

        with transaction.atomic():
            # 3️⃣ Summarize each group, classify
            for (prod_type, prod_code, ccy), original_sum_amt in grouped_data.items():
                classification = classifications.filter(v_prod_type=prod_type).first()
                if not classification:
                    skipped_records += 1
                    print(f"⚠️ No classification for prod_type={prod_type}, skipping.")
                    continue

                sample_row = detail_rows[(prod_type, prod_code, ccy)]
                risk_weight = Decimal(classification.risk_weight) / Decimal('100')  # Used as outflow rate

                # Weighted amount (apply risk weight)
                weighted_amount = original_sum_amt * (Decimal('1') - risk_weight)
                # Adjusted amount is the same as weighted amount
                adjusted_amount = weighted_amount  

                # Sum total adjusted outflows per currency
                total_adjusted_outflows[ccy] += adjusted_amount  

                # Store line-by-line detail (non-total entries)
                currency_to_outflow_entries[ccy].append(HQLAStockOutflow(
                    fic_mis_date=sample_row.fic_mis_date,
                    v_prod_type=prod_type,
                    v_prod_code=prod_code,
                    v_product_name=sample_row.v_product_name,
                    ratings=classification.ratings,
                    hqla_level=classification.hqla_level,  # Main grouping (e.g., Retail Deposits)
                    secondary_grouping=classification.secondary_grouping,  # Stored but not totaled separately
                    n_amount=original_sum_amt,  # Original amount remains unchanged
                    v_ccy_code=ccy,
                    risk_weight=classification.risk_weight,
                    weighted_amount=weighted_amount,
                    adjusted_amount=adjusted_amount
                ))

            # 4️⃣ Build the output per currency with detail rows first and totals at the bottom.
            all_insertable_rows = []
            for ccy, entries in currency_to_outflow_entries.items():
                # First add the detailed (non-total) product entries.
                all_insertable_rows.extend(entries)
                
                # Then, for each distinct hqla_level total:
                unique_hqla_levels = set(entry.hqla_level for entry in entries)
                for main_group in unique_hqla_levels:
                    total_original_amt = sum(entry.n_amount for entry in entries if entry.hqla_level == main_group)
                    total_adj_amt = sum(entry.adjusted_amount for entry in entries if entry.hqla_level == main_group)
                    all_insertable_rows.append(HQLAStockOutflow(
                        fic_mis_date=fic_mis_date,
                        v_prod_type=f"Total {main_group} ({ccy})",
                        v_prod_code=f"{main_group}_TOTAL_{ccy}",
                        v_product_name=f"Total {main_group} LCR Outflow",
                        hqla_level=main_group,
                        n_amount=total_original_amt,  # Sum of original amounts
                        v_ccy_code=ccy,
                        weighted_amount=total_adj_amt,
                        adjusted_amount=total_adj_amt,
                        risk_weight=0,  # No further risk adjustment
                        is_total=True,
                        total_type="level"
                    ))
    
                # Then, for the overall cash outflows per currency:
                total_original_cash_outflow = sum(entry.n_amount for entry in entries)
                total_adj_cash_outflow = total_adjusted_outflows[ccy]
                all_insertable_rows.append(HQLAStockOutflow(
                    fic_mis_date=fic_mis_date,
                    v_prod_type=f"Total Cash Outflows ({ccy})",
                    v_prod_code=f"CASH_OUTFLOW_TOTAL_{ccy}",
                    v_product_name="Total Cash Outflows for LCR",
                    hqla_level="Total Cash Outflows",
                    n_amount=total_original_cash_outflow,  # Sum of original amounts
                    v_ccy_code=ccy,
                    weighted_amount=total_adj_cash_outflow,
                    adjusted_amount=total_adj_cash_outflow,
                    risk_weight=0,  # No risk adjustment for totals
                    is_total=True,
                    total_type="overall"
                ))
    
            # 5️⃣ Bulk insert everything
            HQLAStockOutflow.objects.bulk_create(all_insertable_rows)
    
            inserted_count = len(all_insertable_rows)
            print(f"✅ Successfully classified {inserted_count} LCR outflow records across currencies.")
            if skipped_records > 0:
                print(f"⚠️ Skipped {skipped_records} records with no classification.")
    
    except Exception as e:
        print(f"❌ Error in classify_and_store_hqla_outflow_ccy: {e}")

from collections import defaultdict
from django.db import transaction
from decimal import Decimal
from ALM_APP.models import (
    ExtractedLiquidityData, 
    HQLAClassification, 
    HQLAStock, 
    HQLAConfig
)

def classify_and_store_hqla_multi_ccy(fic_mis_date):
    """
    Classifies extracted liquidity data into HQLA levels and stores the computed HQLA stock,
    processing each currency separately (no mixing of currencies).

    Removes any references to `max_hqla_percentage`, simplifying the final HQLAStock entries.
    """

    try:
        print(f"🔍 Starting multi-currency HQLA classification for {fic_mis_date}")

        # 1) Fetch Haircuts & Caps from HQLAConfig
        hqla_config = HQLAConfig.objects.filter(label="HQLA_Default").first()
        if not hqla_config:
            print("⚠️ No HQLA config found! Using default values.")
            level_2a_haircut = Decimal('0.15')  # 15%
            level_2b_haircut = Decimal('0.50')  # 50%
            level_2a_cap = Decimal('0.40')      # 40%
            level_2b_cap = Decimal('0.15')      # 15%
        else:
            level_2a_haircut = Decimal(hqla_config.level_2a_haircut) / Decimal('100')
            level_2b_haircut = Decimal(hqla_config.level_2b_haircut) / Decimal('100')
            level_2a_cap = Decimal(hqla_config.level_2a_cap) / Decimal('100')
            level_2b_cap = Decimal(hqla_config.level_2b_cap) / Decimal('100')

        print(f"✅ Using haircuts: L2A={level_2a_haircut*100}%, L2B={level_2b_haircut*100}%")
        print(f"✅ Using caps: L2A ≤ {level_2a_cap*100}%, L2B ≤ {level_2b_cap*100}%")

        # 2) Delete old HQLA records for this date
        deleted_count = HQLAStock.objects.filter(fic_mis_date=fic_mis_date).delete()
        print(f"🗑️ Deleted {deleted_count[0]} old HQLA records for {fic_mis_date}")

        # 3) Retrieve extracted data & classification
        extracted_data = ExtractedLiquidityData.objects.filter(fic_mis_date=fic_mis_date)
        classifications = HQLAClassification.objects.all()

        print(f"🔹 Found {extracted_data.count()} extracted records to classify.")

        # Group data by (v_prod_type, v_prod_code, v_ccy_code) to sum amounts
        from collections import defaultdict
        grouped_data = defaultdict(Decimal)  # (prod_type, prod_code, ccy) -> sum
        detail_rows = {}

        for record in extracted_data:
            key = (record.v_prod_type, record.v_prod_code, record.v_ccy_code)
            grouped_data[key] += Decimal(record.n_total_cash_flow_amount)
            detail_rows[key] = record  # store a sample row for name/ratings

        print(f"🔹 Grouped into {len(grouped_data)} unique product-currency combos.")

        # Summation of weighted amounts by currency
        level_1_sums = defaultdict(Decimal)
        level_2a_sums = defaultdict(Decimal)
        level_2b_sums = defaultdict(Decimal)

        # Store line-level entries
        currency_to_hqla_entries = defaultdict(list)
        skipped_records = 0

        with transaction.atomic():
            # 4) Summarize each group, then classify
            for (prod_type, prod_code, ccy), total_amt in grouped_data.items():
                classification = classifications.filter(v_prod_type=prod_type).first()
                if not classification:
                    skipped_records += 1
                    print(f"⚠️ No classification for prod_type={prod_type}, skipping.")
                    continue

                sample_row = detail_rows[(prod_type, prod_code, ccy)]
                original_amount = total_amt
                risk_weight = Decimal(classification.risk_weight) / Decimal('100')
                weighted_amount = original_amount * (Decimal('1') - risk_weight)

                # Sum by level
                if classification.hqla_level == "Level 1":
                    level_1_sums[ccy] += weighted_amount
                elif classification.hqla_level == "Level 2A":
                    level_2a_sums[ccy] += weighted_amount
                elif classification.hqla_level == "Level 2B":
                    level_2b_sums[ccy] += weighted_amount

                # Add line-level detail
                currency_to_hqla_entries[ccy].append(
                    HQLAStock(
                        fic_mis_date=sample_row.fic_mis_date,
                        v_prod_type=prod_type,
                        v_prod_code=prod_code,
                        v_product_name=sample_row.v_product_name,
                        ratings=classification.ratings,
                        hqla_level=classification.hqla_level,
                        n_amount=original_amount,
                        v_ccy_code=ccy,
                        risk_weight=classification.risk_weight,
                        weighted_amount=weighted_amount,
                        adjusted_amount=Decimal('0')
                    )
                )

            # 5) Apply haircuts & caps per currency
            all_insertable_rows = []

            for ccy, entries in currency_to_hqla_entries.items():
                l1_total = level_1_sums[ccy]
                l2a_total = level_2a_sums[ccy]
                l2b_total = level_2b_sums[ccy]

                # a) "Before Cap": apply haircuts
                l2a_haircut_str = f"{level_2a_haircut*100}%"  # e.g. "15%"
                l2b_haircut_str = f"{level_2b_haircut*100}%"  # e.g. "50%"

                l2a_adjusted = l2a_total * (Decimal('1') - level_2a_haircut)
                l2b_adjusted = l2b_total * (Decimal('1') - level_2b_haircut)

                total_before_caps = l1_total + l2a_adjusted + l2b_adjusted

                # b) L2A Cap
                l2a_capped = min(
                    l2a_adjusted,
                    (level_2a_cap / (Decimal('1') - level_2a_cap)) * l1_total - l2b_adjusted
                )
                l2a_capped = max(l2a_capped, Decimal('0'))

                # c) Preliminary HQLA
                prelim_hqla = max(l1_total + l2a_capped + l2b_adjusted, Decimal('0'))

                # d) L2B Cap
                l2b_capped = min(
                    l2b_adjusted,
                    level_2b_cap * (l1_total + l2a_capped + l2b_adjusted)
                )
                l2b_capped = max(l2b_capped, Decimal('0'))

                # e) Final HQLA after caps
                final_hqla_after_caps = max(l1_total + l2a_capped + l2b_capped, Decimal('0'))

                # f) Insert "Before Caps" and "After Caps" totals + L1, L2A, L2B
                all_insertable_rows.append(HQLAStock(
                    fic_mis_date=fic_mis_date,
                    v_prod_type=f"Total HQLA Before Caps ({ccy})",
                    v_prod_code=f"HQLA_TOTAL_BEFORE_{ccy}",
                    v_product_name="Total High-Quality Liquid Assets (Before Caps)",
                    hqla_level="HQLA",
                    weighted_amount=total_before_caps,
                    adjusted_amount=total_before_caps,
                    v_ccy_code=ccy
                ))
                all_insertable_rows.append(HQLAStock(
                    fic_mis_date=fic_mis_date,
                    v_prod_type=f"Total HQLA After Caps ({ccy})",
                    v_prod_code=f"HQLA_TOTAL_AFTER_{ccy}",
                    v_product_name="Total High-Quality Liquid Assets (After Caps)",
                    hqla_level="HQLA",
                    weighted_amount=final_hqla_after_caps,
                    adjusted_amount=final_hqla_after_caps,
                    v_ccy_code=ccy
                ))

                # Level 1 total
                all_insertable_rows.append(HQLAStock(
                    fic_mis_date=fic_mis_date,
                    v_prod_type=f"Total Level 1 HQLA ({ccy})",
                    v_prod_code=f"L1_TOTAL_{ccy}",
                    v_product_name="Total Level 1 HQLA",
                    hqla_level="Level 1",
                    weighted_amount=l1_total,
                    adjusted_amount=l1_total,
                    v_ccy_code=ccy
                ))

                # Level 2A "Before" vs. "After Cap"
                all_insertable_rows.append(HQLAStock(
                    fic_mis_date=fic_mis_date,
                    v_prod_type=f"Total Level 2A HQLA Before Cap ({ccy})",
                    v_prod_code=f"L2A_TOTAL_BEFORE_{ccy}",
                    v_product_name=f"Total Level 2A HQLA Before (Haircut {l2a_haircut_str})",
                    hqla_level="Level 2A",
                    weighted_amount=l2a_total,
                    adjusted_amount=l2a_adjusted,
                    v_ccy_code=ccy
                ))
                all_insertable_rows.append(HQLAStock(
                    fic_mis_date=fic_mis_date,
                    v_prod_type=f"Total Level 2A HQLA After Cap ({ccy})",
                    v_prod_code=f"L2A_TOTAL_CAP_{ccy}",
                    v_product_name=f"Total Level 2A HQLA After Cap ({level_2a_cap*100}% cap)",
                    hqla_level="Level 2A",
                    weighted_amount=l2a_adjusted,
                    adjusted_amount=l2a_capped,
                    v_ccy_code=ccy
                ))

                # Level 2B "Before" vs. "After Cap"
                all_insertable_rows.append(HQLAStock(
                    fic_mis_date=fic_mis_date,
                    v_prod_type=f"Total Level 2B HQLA Before Cap ({ccy})",
                    v_prod_code=f"L2B_TOTAL_BEFORE_{ccy}",
                    v_product_name=f"Total Level 2B HQLA Before (Haircut {l2b_haircut_str})",
                    hqla_level="Level 2B",
                    weighted_amount=l2b_total,
                    adjusted_amount=l2b_adjusted,
                    v_ccy_code=ccy
                ))
                all_insertable_rows.append(HQLAStock(
                    fic_mis_date=fic_mis_date,
                    v_prod_type=f"Total Level 2B HQLA After Cap ({ccy})",
                    v_prod_code=f"L2B_TOTAL_CAP_{ccy}",
                    v_product_name=f"Total Level 2B HQLA After Cap ({level_2b_cap*100}% cap)",
                    hqla_level="Level 2B",
                    weighted_amount=l2b_adjusted,
                    adjusted_amount=l2b_capped,
                    v_ccy_code=ccy
                ))

                # Finally, add the line-by-line product detail
                all_insertable_rows.extend(entries)

            # 6) Bulk insert all rows
            HQLAStock.objects.bulk_create(all_insertable_rows)

            inserted_count = len(all_insertable_rows)
            print(f"✅ Successfully classified {inserted_count} HQLA records across currencies.")
            if skipped_records > 0:
                print(f"⚠️ Skipped {skipped_records} records with no classification.")

    except Exception as e:
        print(f"❌ Error in classify_and_store_hqla_multi_ccy: {e}")

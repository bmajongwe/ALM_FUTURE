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

    IMPROVEMENTS:
    - Aggregates records at the product-type level (grouping by (v_prod_type, v_ccy_code)).
    - Uses HQLAClassification (lookup by v_prod_type) to determine the hqla_level (Level 1, Level 2A or Level 2B)
      and to populate the v_prod_type_level field.
    - For detail rows, v_prod_code is set to blank and v_product_name is set to an empty string (to satisfy the not-null constraint).
    - If any required field is missing (or if hqla_level is not one of the expected values), a message is printed and that record is skipped.
    - The records are output grouped by level (Level 1, then Level 2A, then Level 2B) with summary rows following each group,
      and overall summary rows (Before Caps and After Caps) are added per currency.
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

        # 2) Delete old HQLA records for this reporting date
        deleted_count = HQLAStock.objects.filter(fic_mis_date=fic_mis_date).delete()
        print(f"🗑️ Deleted {deleted_count[0]} old HQLA records for {fic_mis_date}")

        # 3) Retrieve extracted data & classification
        extracted_data = ExtractedLiquidityData.objects.filter(fic_mis_date=fic_mis_date)
        if not extracted_data.exists():
            print("⚠️ No extracted data found for this date. Exiting.")
            return

        classifications = HQLAClassification.objects.all()
        if not classifications.exists():
            print("⚠️ No HQLA classifications available. Exiting.")
            return

        print(f"🔹 Found {extracted_data.count()} extracted records to classify.")

        # Group data by (v_prod_type, v_ccy_code) to sum original amounts.
        grouped_data = defaultdict(Decimal)   # key: (prod_type, ccy) -> sum of original amounts
        detail_rows = {}                      # store one sample record per group

        for record in extracted_data:
            if record.n_total_cash_flow_amount is None:
                print(f"⚠️ Record with product type '{record.v_prod_type}' in currency '{record.v_ccy_code}' missing cash flow amount; skipping.")
                continue
            key = (record.v_prod_type, record.v_ccy_code)
            grouped_data[key] += Decimal(record.n_total_cash_flow_amount)
            detail_rows[key] = record

        print(f"🔹 Grouped into {len(grouped_data)} unique product type-currency combos.")

        # Dictionaries to accumulate weighted and original sums per currency and per level
        level_1_sums = defaultdict(Decimal)
        level_2a_sums = defaultdict(Decimal)
        level_2b_sums = defaultdict(Decimal)
        level_1_orig_sums = defaultdict(Decimal)
        level_2a_orig_sums = defaultdict(Decimal)
        level_2b_orig_sums = defaultdict(Decimal)

        # Structure to store detail rows by currency and hqla_level.
        # For each currency, the keys are the expected levels: "Level 1", "Level 2A", "Level 2B"
        currency_to_hqla_entries = defaultdict(lambda: {"Level 1": [], "Level 2A": [], "Level 2B": []})
        skipped_records = 0

        with transaction.atomic():
            # Process each aggregated group.
            for (prod_type, ccy), original_sum_amt in grouped_data.items():
                classification = classifications.filter(v_prod_type=prod_type).first()
                if not classification:
                    skipped_records += 1
                    print(f"⚠️ No classification found for product type '{prod_type}'; skipping this group.")
                    continue

                # Check if the classification.hqla_level is one of the expected values.
                if classification.hqla_level not in ("Level 1", "Level 2A", "Level 2B"):
                    print(f"⚠️ Unexpected hqla_level '{classification.hqla_level}' for product type '{prod_type}'; skipping.")
                    skipped_records += 1
                    continue

                risk_weight = Decimal(classification.risk_weight) / Decimal('100')
                weighted_amount = original_sum_amt * (Decimal('1') - risk_weight)

                # Accumulate totals by level.
                if classification.hqla_level == "Level 1":
                    level_1_sums[ccy] += weighted_amount
                    level_1_orig_sums[ccy] += original_sum_amt
                elif classification.hqla_level == "Level 2A":
                    level_2a_sums[ccy] += weighted_amount
                    level_2a_orig_sums[ccy] += original_sum_amt
                elif classification.hqla_level == "Level 2B":
                    level_2b_sums[ccy] += weighted_amount
                    level_2b_orig_sums[ccy] += original_sum_amt

                # Create a detail row; v_product_name is set to an empty string to satisfy not-null constraint.
                detail = HQLAStock(
                    fic_mis_date=detail_rows[(prod_type, ccy)].fic_mis_date,
                    v_prod_type=prod_type,
                    v_prod_type_level=classification.v_prod_type_level,
                    v_prod_code="",              # Aggregation at product type level.
                    v_product_name="",           # Set to empty string instead of null.
                    ratings=classification.ratings,
                    hqla_level=classification.hqla_level,
                    n_amount=original_sum_amt,
                    v_ccy_code=ccy,
                    risk_weight=classification.risk_weight,
                    weighted_amount=weighted_amount,
                    adjusted_amount=Decimal('0')
                )
                currency_to_hqla_entries[ccy][classification.hqla_level].append(detail)

            # For each currency, build level-wise outputs.
            all_insertable_rows = []
            for ccy in currency_to_hqla_entries.keys():
                # --- Level 1 ---
                all_insertable_rows.extend(currency_to_hqla_entries[ccy]["Level 1"])
                if level_1_orig_sums[ccy] != 0:
                    summary_level1 = HQLAStock(
                        fic_mis_date=fic_mis_date,
                        v_prod_type=f"Total Level 1 HQLA ({ccy})",
                        v_prod_type_level="",
                        v_prod_code=f"L1_TOTAL_{ccy}",
                        v_product_name="Total Level 1 HQLA",
                        hqla_level="Level 1",
                        n_amount=level_1_orig_sums[ccy],
                        v_ccy_code=ccy,
                        weighted_amount=level_1_sums[ccy],
                        adjusted_amount=level_1_sums[ccy],
                        risk_weight=0,
                        is_total=True,
                        total_type="level1"
                    )
                    all_insertable_rows.append(summary_level1)

                # --- Level 2A ---
                all_insertable_rows.extend(currency_to_hqla_entries[ccy]["Level 2A"])
                if level_2a_orig_sums[ccy] != 0:
                    l2a_weighted = level_2a_sums[ccy]
                    l2a_orig = level_2a_orig_sums[ccy]
                    l2a_adjusted = l2a_weighted * (Decimal('1') - level_2a_haircut)
                    summary_level2a_before = HQLAStock(
                        fic_mis_date=fic_mis_date,
                        v_prod_type=f"Total Level 2A HQLA Before Cap ({ccy})",
                        v_prod_type_level="",
                        v_prod_code=f"L2A_TOTAL_BEFORE_{ccy}",
                        v_product_name=f"Total Level 2A HQLA Before Cap (Haircut {level_2a_haircut*100}%)",
                        hqla_level="Level 2A",
                        n_amount=l2a_orig,
                        v_ccy_code=ccy,
                        weighted_amount=l2a_weighted,
                        adjusted_amount=l2a_adjusted,
                        risk_weight=0,
                        is_total=True,
                        total_type="level2a_before"
                    )
                    all_insertable_rows.append(summary_level2a_before)

                # --- Level 2B ---
                all_insertable_rows.extend(currency_to_hqla_entries[ccy]["Level 2B"])
                if level_2b_orig_sums[ccy] != 0:
                    l2b_weighted = level_2b_sums[ccy]
                    l2b_orig = level_2b_orig_sums[ccy]
                    l2b_adjusted = l2b_weighted * (Decimal('1') - level_2b_haircut)
                    summary_level2b_before = HQLAStock(
                        fic_mis_date=fic_mis_date,
                        v_prod_type=f"Total Level 2B HQLA Before Cap ({ccy})",
                        v_prod_type_level="",
                        v_prod_code=f"L2B_TOTAL_BEFORE_{ccy}",
                        v_product_name=f"Total Level 2B HQLA Before Cap (Haircut {level_2b_haircut*100}%)",
                        hqla_level="Level 2B",
                        n_amount=l2b_orig,
                        v_ccy_code=ccy,
                        weighted_amount=l2b_weighted,
                        adjusted_amount=l2b_adjusted,
                        risk_weight=0,
                        is_total=True,
                        total_type="level2b_before"
                    )
                    all_insertable_rows.append(summary_level2b_before)

                # --- Overall Adjustments ---
                l1_weighted = level_1_sums[ccy]
                l2a_weighted = level_2a_sums[ccy]
                l2b_weighted = level_2b_sums[ccy]
                l2a_adjusted = l2a_weighted * (Decimal('1') - level_2a_haircut)
                l2b_adjusted = l2b_weighted * (Decimal('1') - level_2b_haircut)
                total_before_caps = l1_weighted + l2a_adjusted + l2b_adjusted

                l2a_capped = min(
                    l2a_adjusted,
                    (level_2a_cap / (Decimal('1') - level_2a_cap)) * l1_weighted - l2b_adjusted
                )
                l2a_capped = max(l2a_capped, Decimal('0'))
                l2b_capped = min(
                    l2b_adjusted,
                    level_2b_cap * (l1_weighted + l2a_capped + l2b_adjusted)
                )
                l2b_capped = max(l2b_capped, Decimal('0'))
                final_hqla_after_caps = l1_weighted + l2a_capped + l2b_capped

                if level_2a_orig_sums[ccy] != 0:
                    summary_level2a_after = HQLAStock(
                        fic_mis_date=fic_mis_date,
                        v_prod_type=f"Total Level 2A HQLA After Cap ({ccy})",
                        v_prod_type_level="",
                        v_prod_code=f"L2A_TOTAL_CAP_{ccy}",
                        v_product_name=f"Total Level 2A HQLA After Cap ({level_2a_cap*100}% cap)",
                        hqla_level="Level 2A",
                        n_amount=level_2a_orig_sums[ccy],
                        v_ccy_code=ccy,
                        weighted_amount=l2a_adjusted,
                        adjusted_amount=l2a_capped,
                        risk_weight=0,
                        is_total=True,
                        total_type="level2a_after"
                    )
                    all_insertable_rows.append(summary_level2a_after)

                if level_2b_orig_sums[ccy] != 0:
                    summary_level2b_after = HQLAStock(
                        fic_mis_date=fic_mis_date,
                        v_prod_type=f"Total Level 2B HQLA After Cap ({ccy})",
                        v_prod_type_level="",
                        v_prod_code=f"L2B_TOTAL_CAP_{ccy}",
                        v_product_name=f"Total Level 2B HQLA After Cap ({level_2b_cap*100}% cap)",
                        hqla_level="Level 2B",
                        n_amount=level_2b_orig_sums[ccy],
                        v_ccy_code=ccy,
                        weighted_amount=l2b_adjusted,
                        adjusted_amount=l2b_capped,
                        risk_weight=0,
                        is_total=True,
                        total_type="level2b_after"
                    )
                    all_insertable_rows.append(summary_level2b_after)

                overall_before = HQLAStock(
                    fic_mis_date=fic_mis_date,
                    v_prod_type=f"Total HQLA Before Caps ({ccy})",
                    v_prod_type_level="",
                    v_prod_code=f"HQLA_TOTAL_BEFORE_{ccy}",
                    v_product_name="Total High-Quality Liquid Assets (Before Caps)",
                    hqla_level="HQLA",
                    n_amount=level_1_orig_sums[ccy] + level_2a_orig_sums[ccy] + level_2b_orig_sums[ccy],
                    v_ccy_code=ccy,
                    weighted_amount=total_before_caps,
                    adjusted_amount=total_before_caps,
                    risk_weight=0,
                    is_total=True,
                    total_type="overall_before"
                )
                overall_after = HQLAStock(
                    fic_mis_date=fic_mis_date,
                    v_prod_type=f"Total HQLA After Caps ({ccy})",
                    v_prod_type_level="",
                    v_prod_code=f"HQLA_TOTAL_AFTER_{ccy}",
                    v_product_name="Total High-Quality Liquid Assets (After Caps)",
                    hqla_level="HQLA",
                    n_amount=level_1_orig_sums[ccy] + level_2a_orig_sums[ccy] + level_2b_orig_sums[ccy],
                    v_ccy_code=ccy,
                    weighted_amount=final_hqla_after_caps,
                    adjusted_amount=final_hqla_after_caps,
                    risk_weight=0,
                    is_total=True,
                    total_type="overall_after"
                )
                all_insertable_rows.append(overall_before)
                all_insertable_rows.append(overall_after)

            # Bulk insert all records.
            HQLAStock.objects.bulk_create(all_insertable_rows)

            inserted_count = len(all_insertable_rows)
            print(f"✅ Successfully classified {inserted_count} HQLA records across currencies.")
            if skipped_records > 0:
                print(f"⚠️ Skipped {skipped_records} records due to missing data or classification issues.")

    except Exception as e:
        print(f"❌ Error in classify_and_store_hqla_multi_ccy: {e}")

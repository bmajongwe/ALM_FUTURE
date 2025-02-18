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
    
    IMPROVEMENT:
    - Groups records by (v_prod_type, v_prod_code, v_ccy_code) to sum total amounts (original).
    - Also stores the original sum in n_amount for each total row (Level 1, 2A, 2B).
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

        # 2) Delete old HQLA records
        deleted_count = HQLAStock.objects.filter(fic_mis_date=fic_mis_date).delete()
        print(f"🗑️ Deleted {deleted_count[0]} old HQLA records for {fic_mis_date}")

        # 3) Retrieve extracted data & classification
        extracted_data = ExtractedLiquidityData.objects.filter(fic_mis_date=fic_mis_date)
        classifications = HQLAClassification.objects.all()

        print(f"🔹 Found {extracted_data.count()} extracted records to classify.")

        # (A) Group data by (v_prod_type, v_prod_code, v_ccy_code) to sum original amounts
        grouped_data = defaultdict(Decimal)   # (prod_type, prod_code, ccy) -> sum of original amounts
        detail_rows = {}                     # store a sample row (for name, etc.)

        for record in extracted_data:
            key = (record.v_prod_type, record.v_prod_code, record.v_ccy_code)
            grouped_data[key] += Decimal(record.n_total_cash_flow_amount)
            detail_rows[key] = record  # keep reference for product_name, etc.

        print(f"🔹 Grouped into {len(grouped_data)} unique product-currency combos.")

        # Weighted sums (before haircuts) per currency
        level_1_sums = defaultdict(Decimal)
        level_2a_sums = defaultdict(Decimal)
        level_2b_sums = defaultdict(Decimal)

        # Also store sum of original amounts (for summary rows)
        level_1_orig_sums = defaultdict(Decimal)
        level_2a_orig_sums = defaultdict(Decimal)
        level_2b_orig_sums = defaultdict(Decimal)

        currency_to_hqla_entries = defaultdict(list)
        skipped_records = 0

        with transaction.atomic():
            # 4) Summarize each group, classify
            for (prod_type, prod_code, ccy), original_sum_amt in grouped_data.items():
                classification = classifications.filter(v_prod_type=prod_type).first()
                if not classification:
                    skipped_records += 1
                    print(f"⚠️ No classification for prod_type={prod_type}, skipping.")
                    continue

                sample_row = detail_rows[(prod_type, prod_code, ccy)]
                risk_weight = Decimal(classification.risk_weight) / Decimal('100')

                # Weighted amount (after risk weight is applied)
                weighted_amount = original_sum_amt * (Decimal('1') - risk_weight)

                # Accumulate sums by level
                if classification.hqla_level == "Level 1":
                    level_1_sums[ccy] += weighted_amount
                    level_1_orig_sums[ccy] += original_sum_amt
                elif classification.hqla_level == "Level 2A":
                    level_2a_sums[ccy] += weighted_amount
                    level_2a_orig_sums[ccy] += original_sum_amt
                elif classification.hqla_level == "Level 2B":
                    level_2b_sums[ccy] += weighted_amount
                    level_2b_orig_sums[ccy] += original_sum_amt

                # Line-level detail for each aggregated group
                currency_to_hqla_entries[ccy].append(HQLAStock(
                    fic_mis_date=sample_row.fic_mis_date,
                    v_prod_type=prod_type,
                    v_prod_code=prod_code,
                    v_product_name=sample_row.v_product_name,
                    ratings=classification.ratings,
                    hqla_level=classification.hqla_level,
                    n_amount=original_sum_amt,  # Sum of the original amounts for that group
                    v_ccy_code=ccy,
                    risk_weight=classification.risk_weight,  # Keep original risk weight here
                    weighted_amount=weighted_amount,
                    adjusted_amount=Decimal('0')
                ))

            # 5) Apply haircuts & caps per currency and insert summary rows
            all_insertable_rows = []

            for ccy, entries in currency_to_hqla_entries.items():
                # Weighted totals
                l1_weighted = level_1_sums[ccy]
                l2a_weighted = level_2a_sums[ccy]
                l2b_weighted = level_2b_sums[ccy]

                # Original sums
                l1_orig = level_1_orig_sums[ccy]
                l2a_orig = level_2a_orig_sums[ccy]
                l2b_orig = level_2b_orig_sums[ccy]

                # Haircut strings for naming
                l2a_haircut_str = f"{level_2a_haircut*100}%"  # e.g. "15%"
                l2b_haircut_str = f"{level_2b_haircut*100}%"  # e.g. "50%"

                # a) "Before Cap": apply haircuts
                # (l1 is not subject to a haircut)
                l2a_adjusted = l2a_weighted * (Decimal('1') - level_2a_haircut)
                l2b_adjusted = l2b_weighted * (Decimal('1') - level_2b_haircut)

                total_before_caps = l1_weighted + l2a_adjusted + l2b_adjusted

                # b) L2A Cap
                l2a_capped = min(
                    l2a_adjusted,
                    (level_2a_cap / (Decimal('1') - level_2a_cap)) * l1_weighted - l2b_adjusted
                )
                l2a_capped = max(l2a_capped, Decimal('0'))

                # c) Preliminary HQLA (before L2B cap)
                preliminary_hqla = max(l1_weighted + l2a_capped + l2b_adjusted, Decimal('0'))

                # d) L2B Cap
                l2b_capped = min(
                    l2b_adjusted,
                    level_2b_cap * (l1_weighted + l2a_capped + l2b_adjusted)
                )
                l2b_capped = max(l2b_capped, Decimal('0'))

                # e) Final HQLA after caps
                final_hqla_after_caps = max(l1_weighted + l2a_capped + l2b_capped, Decimal('0'))

                # Insert summary rows with risk_weight set to 0 and n_amount as the original sum

                # "Before Caps" total
                all_insertable_rows.append(HQLAStock(
                    fic_mis_date=fic_mis_date,
                    v_prod_type=f"Total HQLA Before Caps ({ccy})",
                    v_prod_code=f"HQLA_TOTAL_BEFORE_{ccy}",
                    v_product_name="Total High-Quality Liquid Assets (Before Caps)",
                    hqla_level="HQLA",
                    n_amount=l1_orig + l2a_orig + l2b_orig,
                    v_ccy_code=ccy,
                    weighted_amount=total_before_caps,
                    adjusted_amount=total_before_caps,
                    risk_weight=0  # Totals not subject to further risk weighting
                ))

                # "After Caps" total
                all_insertable_rows.append(HQLAStock(
                    fic_mis_date=fic_mis_date,
                    v_prod_type=f"Total HQLA After Caps ({ccy})",
                    v_prod_code=f"HQLA_TOTAL_AFTER_{ccy}",
                    v_product_name="Total High-Quality Liquid Assets (After Caps)",
                    hqla_level="HQLA",
                    n_amount=l1_orig + l2a_orig + l2b_orig,
                    v_ccy_code=ccy,
                    weighted_amount=final_hqla_after_caps,
                    adjusted_amount=final_hqla_after_caps,
                    risk_weight=0
                ))

                # Level 1 total
                all_insertable_rows.append(HQLAStock(
                    fic_mis_date=fic_mis_date,
                    v_prod_type=f"Total Level 1 HQLA ({ccy})",
                    v_prod_code=f"L1_TOTAL_{ccy}",
                    v_product_name="Total Level 1 HQLA",
                    hqla_level="Level 1",
                    n_amount=l1_orig,
                    v_ccy_code=ccy,
                    weighted_amount=l1_weighted,
                    adjusted_amount=l1_weighted,
                    risk_weight=0
                ))

                # Level 2A before cap total
                all_insertable_rows.append(HQLAStock(
                    fic_mis_date=fic_mis_date,
                    v_prod_type=f"Total Level 2A HQLA Before Cap ({ccy})",
                    v_prod_code=f"L2A_TOTAL_BEFORE_{ccy}",
                    v_product_name=f"Total Level 2A HQLA Before Cap (Haircut {l2a_haircut_str})",
                    hqla_level="Level 2A",
                    n_amount=l2a_orig,
                    v_ccy_code=ccy,
                    weighted_amount=l2a_weighted,
                    adjusted_amount=l2a_adjusted,
                    risk_weight=0
                ))
                # Level 2A after cap total
                all_insertable_rows.append(HQLAStock(
                    fic_mis_date=fic_mis_date,
                    v_prod_type=f"Total Level 2A HQLA After Cap ({ccy})",
                    v_prod_code=f"L2A_TOTAL_CAP_{ccy}",
                    v_product_name=f"Total Level 2A HQLA After Cap ({level_2a_cap*100}% cap)",
                    hqla_level="Level 2A",
                    n_amount=l2a_orig,
                    v_ccy_code=ccy,
                    weighted_amount=l2a_adjusted,
                    adjusted_amount=l2a_capped,
                    risk_weight=0
                ))

                # Level 2B before cap total
                all_insertable_rows.append(HQLAStock(
                    fic_mis_date=fic_mis_date,
                    v_prod_type=f"Total Level 2B HQLA Before Cap ({ccy})",
                    v_prod_code=f"L2B_TOTAL_BEFORE_{ccy}",
                    v_product_name=f"Total Level 2B HQLA Before Cap (Haircut {l2b_haircut_str})",
                    hqla_level="Level 2B",
                    n_amount=l2b_orig,
                    v_ccy_code=ccy,
                    weighted_amount=l2b_weighted,
                    adjusted_amount=l2b_adjusted,
                    risk_weight=0
                ))
                # Level 2B after cap total
                all_insertable_rows.append(HQLAStock(
                    fic_mis_date=fic_mis_date,
                    v_prod_type=f"Total Level 2B HQLA After Cap ({ccy})",
                    v_prod_code=f"L2B_TOTAL_CAP_{ccy}",
                    v_product_name=f"Total Level 2B HQLA After Cap ({level_2b_cap*100}% cap)",
                    hqla_level="Level 2B",
                    n_amount=l2b_orig,
                    v_ccy_code=ccy,
                    weighted_amount=l2b_adjusted,
                    adjusted_amount=l2b_capped,
                    risk_weight=0
                ))

                # Finally, add the line-by-line product detail entries
                all_insertable_rows.extend(entries)

            # 6) Bulk insert everything
            HQLAStock.objects.bulk_create(all_insertable_rows)

            inserted_count = len(all_insertable_rows)
            print(f"✅ Successfully classified {inserted_count} HQLA records across currencies.")
            if skipped_records > 0:
                print(f"⚠️ Skipped {skipped_records} records with no classification.")

    except Exception as e:
        print(f"❌ Error in classify_and_store_hqla_multi_ccy: {e}")






























# from collections import defaultdict
# from django.db import transaction
# from decimal import Decimal
# from ALM_APP.models import (
#     ExtractedLiquidityData,
#     HQLAClassification,
#     HQLAStock,
#     HQLAConfig
# )

# def classify_and_store_hqla_multi_ccy(fic_mis_date):
#     """
#     Classifies extracted liquidity data into HQLA levels and stores the computed HQLA stock,
#     processing each currency separately (no mixing of currencies).
    
#     IMPROVEMENT:
#     - Groups records by (v_prod_type, v_prod_code, v_ccy_code) to sum total amounts (original).
#     - Also stores the original sum in n_amount for each total row (Level 1, 2A, 2B).
#     """

#     try:
#         print(f"🔍 Starting multi-currency HQLA classification for {fic_mis_date}")

#         # 1) Fetch Haircuts & Caps from HQLAConfig
#         hqla_config = HQLAConfig.objects.filter(label="HQLA_Default").first()
#         if not hqla_config:
#             print("⚠️ No HQLA config found! Using default values.")
#             level_2a_haircut = Decimal('0.15')  # 15%
#             level_2b_haircut = Decimal('0.50')  # 50%
#             level_2a_cap = Decimal('0.40')      # 40%
#             level_2b_cap = Decimal('0.15')      # 15%
#         else:
#             level_2a_haircut = Decimal(hqla_config.level_2a_haircut) / Decimal('100')
#             level_2b_haircut = Decimal(hqla_config.level_2b_haircut) / Decimal('100')
#             level_2a_cap = Decimal(hqla_config.level_2a_cap) / Decimal('100')
#             level_2b_cap = Decimal(hqla_config.level_2b_cap) / Decimal('100')

#         print(f"✅ Using haircuts: L2A={level_2a_haircut*100}%, L2B={level_2b_haircut*100}%")
#         print(f"✅ Using caps: L2A ≤ {level_2a_cap*100}%, L2B ≤ {level_2b_cap*100}%")

#         # 2) Delete old HQLA records
#         deleted_count = HQLAStock.objects.filter(fic_mis_date=fic_mis_date).delete()
#         print(f"🗑️ Deleted {deleted_count[0]} old HQLA records for {fic_mis_date}")

#         # 3) Retrieve extracted data & classification
#         extracted_data = ExtractedLiquidityData.objects.filter(fic_mis_date=fic_mis_date)
#         classifications = HQLAClassification.objects.all()

#         print(f"🔹 Found {extracted_data.count()} extracted records to classify.")

#         # (A) Group data by (v_prod_type, v_prod_code, v_ccy_code) to sum original amounts
#         grouped_data = defaultdict(Decimal)   # (prod_type, prod_code, ccy) -> sum of original
#         detail_rows = {}                     # store a sample row (for name, etc.)

#         for record in extracted_data:
#             key = (record.v_prod_type, record.v_prod_code, record.v_ccy_code)
#             grouped_data[key] += Decimal(record.n_total_cash_flow_amount)
#             detail_rows[key] = record  # keep reference for product_name, etc.

#         print(f"🔹 Grouped into {len(grouped_data)} unique product-currency combos.")

#         # Weighted sums (before haircuts) per currency
#         level_1_sums = defaultdict(Decimal)
#         level_2a_sums = defaultdict(Decimal)
#         level_2b_sums = defaultdict(Decimal)

#         # Also store sum of original amounts (for summary rows)
#         level_1_orig_sums = defaultdict(Decimal)
#         level_2a_orig_sums = defaultdict(Decimal)
#         level_2b_orig_sums = defaultdict(Decimal)

#         currency_to_hqla_entries = defaultdict(list)
#         skipped_records = 0

#         with transaction.atomic():
#             # 4) Summarize each group, classify
#             for (prod_type, prod_code, ccy), original_sum_amt in grouped_data.items():
#                 classification = classifications.filter(v_prod_type=prod_type).first()
#                 if not classification:
#                     skipped_records += 1
#                     print(f"⚠️ No classification for prod_type={prod_type}, skipping.")
#                     continue

#                 sample_row = detail_rows[(prod_type, prod_code, ccy)]
#                 risk_weight = Decimal(classification.risk_weight) / Decimal('100')

#                 # Weighted amount
#                 weighted_amount = original_sum_amt * (Decimal('1') - risk_weight)

#                 # Accumulate sums by level
#                 if classification.hqla_level == "Level 1":
#                     level_1_sums[ccy] += weighted_amount
#                     level_1_orig_sums[ccy] += original_sum_amt
#                 elif classification.hqla_level == "Level 2A":
#                     level_2a_sums[ccy] += weighted_amount
#                     level_2a_orig_sums[ccy] += original_sum_amt
#                 elif classification.hqla_level == "Level 2B":
#                     level_2b_sums[ccy] += weighted_amount
#                     level_2b_orig_sums[ccy] += original_sum_amt

#                 # line-level detail for each aggregated group
#                 currency_to_hqla_entries[ccy].append(HQLAStock(
#                     fic_mis_date=sample_row.fic_mis_date,
#                     v_prod_type=prod_type,
#                     v_prod_code=prod_code,
#                     v_product_name=sample_row.v_product_name,
#                     ratings=classification.ratings,
#                     hqla_level=classification.hqla_level,
#                     n_amount=original_sum_amt,  # sum of the original amounts for that group
#                     v_ccy_code=ccy,
#                     risk_weight=classification.risk_weight,
#                     weighted_amount=weighted_amount,
#                     adjusted_amount=Decimal('0')
#                 ))

#             # 5) Haircuts & caps per currency
#             all_insertable_rows = []

#             for ccy, entries in currency_to_hqla_entries.items():
#                 # Weighted totals
#                 l1_weighted = level_1_sums[ccy]
#                 l2a_weighted = level_2a_sums[ccy]
#                 l2b_weighted = level_2b_sums[ccy]

#                 # Original sums
#                 l1_orig = level_1_orig_sums[ccy]
#                 l2a_orig = level_2a_orig_sums[ccy]
#                 l2b_orig = level_2b_orig_sums[ccy]

#                 # Haircut strings for naming
#                 l2a_haircut_str = f"{level_2a_haircut*100}%"  # e.g. "15%"
#                 l2b_haircut_str = f"{level_2b_haircut*100}%"  # e.g. "50%"

#                 # a) "Before Cap": apply haircuts
#                 l2a_adjusted = l2a_weighted
#                 l2b_adjusted = l2b_weighted

#                 # Because we already applied the risk weight, but not the *haircut*,
#                 # let's do that now:
#                 # Actually, the function above lumps risk_weight + haircut in one step.
#                 # But if you want haircuts separate, do:
#                 l2a_adjusted = l2a_weighted * (Decimal('1') - level_2a_haircut)
#                 l2b_adjusted = l2b_weighted * (Decimal('1') - level_2b_haircut)

#                 total_before_caps = l1_weighted + l2a_adjusted + l2b_adjusted

#                 # b) L2A Cap
#                 l2a_capped = min(
#                     l2a_adjusted,
#                     (level_2a_cap / (Decimal('1') - level_2a_cap)) * l1_weighted - l2b_adjusted
#                 )
#                 l2a_capped = max(l2a_capped, Decimal('0'))

#                 # c) Preliminary
#                 preliminary_hqla = max(l1_weighted + l2a_capped + l2b_adjusted, Decimal('0'))

#                 # d) L2B Cap
#                 l2b_capped = min(
#                     l2b_adjusted,
#                     level_2b_cap * (l1_weighted + l2a_capped + l2b_adjusted)
#                 )
#                 l2b_capped = max(l2b_capped, Decimal('0'))

#                 # e) Final HQLA after caps
#                 final_hqla_after_caps = max(l1_weighted + l2a_capped + l2b_capped, Decimal('0'))

#                 # Insert summary rows now, with n_amount as the "original sum"
#                 # for that level or combination.

#                 # "Before Caps" total
#                 all_insertable_rows.append(HQLAStock(
#                     fic_mis_date=fic_mis_date,
#                     v_prod_type=f"Total HQLA Before Caps ({ccy})",
#                     v_prod_code=f"HQLA_TOTAL_BEFORE_{ccy}",
#                     v_product_name="Total High-Quality Liquid Assets (Before Caps)",
#                     hqla_level="HQLA",
#                     # n_amount => sum of all original (Level1+Level2A+Level2B) for that currency
#                     n_amount=l1_orig + l2a_orig + l2b_orig,
#                     v_ccy_code=ccy,
#                     weighted_amount=total_before_caps,
#                     adjusted_amount=total_before_caps
#                 ))

#                 # "After Caps" total
#                 all_insertable_rows.append(HQLAStock(
#                     fic_mis_date=fic_mis_date,
#                     v_prod_type=f"Total HQLA After Caps ({ccy})",
#                     v_prod_code=f"HQLA_TOTAL_AFTER_{ccy}",
#                     v_product_name="Total High-Quality Liquid Assets (After Caps)",
#                     hqla_level="HQLA",
#                     n_amount=l1_orig + l2a_orig + l2b_orig,  # same original sum
#                     v_ccy_code=ccy,
#                     weighted_amount=final_hqla_after_caps,
#                     adjusted_amount=final_hqla_after_caps
#                 ))

#                 # Level 1
#                 all_insertable_rows.append(HQLAStock(
#                     fic_mis_date=fic_mis_date,
#                     v_prod_type=f"Total Level 1 HQLA ({ccy})",
#                     v_prod_code=f"L1_TOTAL_{ccy}",
#                     v_product_name="Total Level 1 HQLA",
#                     hqla_level="Level 1",
#                     n_amount=l1_orig,
#                     v_ccy_code=ccy,
#                     weighted_amount=l1_weighted,
#                     adjusted_amount=l1_weighted
#                 ))

#                 # Level 2A before vs after cap
#                 all_insertable_rows.append(HQLAStock(
#                     fic_mis_date=fic_mis_date,
#                     v_prod_type=f"Total Level 2A HQLA Before Cap ({ccy})",
#                     v_prod_code=f"L2A_TOTAL_BEFORE_{ccy}",
#                     v_product_name=f"Total Level 2A HQLA Before Cap (Haircut {l2a_haircut_str})",
#                     hqla_level="Level 2A",
#                     n_amount=l2a_orig,
#                     v_ccy_code=ccy,
#                     weighted_amount=l2a_weighted,
#                     adjusted_amount=l2a_adjusted
#                 ))
#                 all_insertable_rows.append(HQLAStock(
#                     fic_mis_date=fic_mis_date,
#                     v_prod_type=f"Total Level 2A HQLA After Cap ({ccy})",
#                     v_prod_code=f"L2A_TOTAL_CAP_{ccy}",
#                     v_product_name=f"Total Level 2A HQLA After Cap ({level_2a_cap*100}% cap)",
#                     hqla_level="Level 2A",
#                     n_amount=l2a_orig,
#                     v_ccy_code=ccy,
#                     weighted_amount=l2a_adjusted,
#                     adjusted_amount=l2a_capped
#                 ))

#                 # Level 2B before vs after cap
#                 all_insertable_rows.append(HQLAStock(
#                     fic_mis_date=fic_mis_date,
#                     v_prod_type=f"Total Level 2B HQLA Before Cap ({ccy})",
#                     v_prod_code=f"L2B_TOTAL_BEFORE_{ccy}",
#                     v_product_name=f"Total Level 2B HQLA Before Cap (Haircut {l2b_haircut_str})",
#                     hqla_level="Level 2B",
#                     n_amount=l2b_orig,
#                     v_ccy_code=ccy,
#                     weighted_amount=l2b_weighted,
#                     adjusted_amount=l2b_adjusted
#                 ))
#                 all_insertable_rows.append(HQLAStock(
#                     fic_mis_date=fic_mis_date,
#                     v_prod_type=f"Total Level 2B HQLA After Cap ({ccy})",
#                     v_prod_code=f"L2B_TOTAL_CAP_{ccy}",
#                     v_product_name=f"Total Level 2B HQLA After Cap ({level_2b_cap*100}% cap)",
#                     hqla_level="Level 2B",
#                     n_amount=l2b_orig,
#                     v_ccy_code=ccy,
#                     weighted_amount=l2b_adjusted,
#                     adjusted_amount=l2b_capped
#                 ))

#                 # Finally, add the line-by-line product detail
#                 all_insertable_rows.extend(entries)

#             # 6) Bulk insert everything
#             HQLAStock.objects.bulk_create(all_insertable_rows)

#             inserted_count = len(all_insertable_rows)
#             print(f"✅ Successfully classified {inserted_count} HQLA records across currencies.")
#             if skipped_records > 0:
#                 print(f"⚠️ Skipped {skipped_records} records with no classification.")

#     except Exception as e:
#         print(f"❌ Error in classify_and_store_hqla_multi_ccy: {e}")

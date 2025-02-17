from django.db import transaction
from decimal import Decimal
from ALM_APP.models import ExtractedLiquidityData, HQLAClassification, HQLAStock, HQLAConfig

def classify_and_store_hqla(fic_mis_date):
    """
    Classifies extracted liquidity data into HQLA levels and stores the computed HQLA stock.
    Applies risk weights per product, then calculates weighted amounts before applying haircuts.
    Ensures adjustments for Level 2A & Level 2B caps are enforced correctly.
    Uses the correct formulas to prevent negative values.
    """

    try:
        print(f"🔍 Starting HQLA classification for {fic_mis_date}")

        # 1️⃣ Fetch Haircuts & Caps from HQLAConfig Table
        hqla_config = HQLAConfig.objects.filter(label="HQLA_Default").first()

        if not hqla_config:
            print("⚠️ No HQLA config found! Using default values.")
            level_2a_haircut = Decimal(15) / Decimal(100)  # Default 15%
            level_2b_haircut = Decimal(50) / Decimal(100)  # Default 50%
            level_2a_cap = Decimal(40) / Decimal(100)  # Default 40%
            level_2b_cap = Decimal(15) / Decimal(100)  # Default 15%
        else:
            level_2a_haircut = Decimal(hqla_config.level_2a_haircut) / Decimal(100)
            level_2b_haircut = Decimal(hqla_config.level_2b_haircut) / Decimal(100)
            level_2a_cap = Decimal(hqla_config.level_2a_cap) / Decimal(100)
            level_2b_cap = Decimal(hqla_config.level_2b_cap) / Decimal(100)

        print(f"✅ Using haircuts: Level 2A = {level_2a_haircut*100}%, Level 2B = {level_2b_haircut*100}%")
        print(f"✅ Using caps: Level 2A ≤ {level_2a_cap*100}%, Level 2B ≤ {level_2b_cap*100}%")

        # 2️⃣ Remove old records for the same reporting date
        deleted_count = HQLAStock.objects.filter(fic_mis_date=fic_mis_date).delete()
        print(f"🗑️ Deleted {deleted_count[0]} old HQLA records for {fic_mis_date}")

        # 3️⃣ Retrieve extracted liquidity data for classification
        extracted_data = ExtractedLiquidityData.objects.filter(fic_mis_date=fic_mis_date)
        classifications = HQLAClassification.objects.all()

        print(f"🔹 Found {extracted_data.count()} extracted records to classify")

        hqla_entries = []
        level_1_weighted_total = Decimal(0)
        level_2a_weighted_total = Decimal(0)
        level_2b_weighted_total = Decimal(0)
        skipped_records = 0

        with transaction.atomic():
            for record in extracted_data:
                # 4️⃣ Find the corresponding HQLA classification
                classification = classifications.filter(v_prod_type=record.v_prod_type).first()

                if classification:
                    # 5️⃣ Apply Risk Weight per product
                    weighted_amount = Decimal(record.n_total_cash_flow_amount) * (Decimal(1) - (Decimal(classification.risk_weight) / Decimal(100)))

                    # 6️⃣ Track weighted amounts before applying haircuts
                    if classification.hqla_level == "Level 1":
                        level_1_weighted_total += weighted_amount  # No haircut applied
                    elif classification.hqla_level == "Level 2A":
                        level_2a_weighted_total += weighted_amount  # Haircut applied later
                    elif classification.hqla_level == "Level 2B":
                        level_2b_weighted_total += weighted_amount  # Haircut applied later

                    # 7️⃣ Append the HQLA record (NO haircut applied yet)
                    hqla_entries.append(HQLAStock(
                        fic_mis_date=record.fic_mis_date,
                        v_prod_type=record.v_prod_type,
                        v_prod_code=record.v_prod_code,
                        v_product_name=record.v_product_name,
                        ratings=classification.ratings,
                        hqla_level=classification.hqla_level,
                        n_amount=record.n_total_cash_flow_amount,
                        v_ccy_code=record.v_ccy_code,
                        risk_weight=classification.risk_weight,
                        weighted_amount=weighted_amount,  # Risk weight applied
                        adjusted_amount=Decimal(0)  # Will be updated after haircuts
                    ))

                else:
                    skipped_records += 1
                    print(f"⚠️ No HQLA classification found for {record.v_prod_type}, skipping...")

            # 8️⃣ Apply Haircuts to Level 2A and Level 2B AFTER summing weighted amounts
            adjusted_level_2b = level_2b_weighted_total * (Decimal(1) - level_2b_haircut)  # Uses dynamic haircut
            adjusted_level_2a = min(
                level_2a_weighted_total * (Decimal(1) - level_2a_haircut),  # Uses dynamic haircut
                (level_2a_cap / (Decimal(1) - level_2a_cap)) * level_1_weighted_total - adjusted_level_2b  # 40% cap enforcement
            )

            adjusted_level_2a = max(adjusted_level_2a, Decimal(0))  # Ensure non-negative

            # 9️⃣ Compute Total HQLA
            total_hqla = max(level_1_weighted_total + adjusted_level_2a + adjusted_level_2b, Decimal(0))

            # 🔟 Apply Level 2B Cap (15% of Total HQLA)
            adjusted_level_2b_after_cap = min(
                adjusted_level_2b,
                level_2b_cap * (level_1_weighted_total + adjusted_level_2a + adjusted_level_2b)
            )
            adjusted_level_2b_after_cap = max(adjusted_level_2b_after_cap, Decimal(0))  # Ensure non-negative

            # 🔟 Store **Total Level 1, Level 2A & Level 2B Weighted Amounts**
            hqla_entries.append(HQLAStock(
                fic_mis_date=fic_mis_date,
                v_prod_type="Total HQLA",
                v_prod_code="HQLA_TOTAL",
                v_product_name="Total High-Quality Liquid Assets",
                hqla_level="HQLA",
                weighted_amount=total_hqla,
                adjusted_amount=total_hqla
            ))

            hqla_entries.append(HQLAStock(
                fic_mis_date=fic_mis_date,
                v_prod_type="Total Level 1 HQLA",
                v_prod_code="L1_TOTAL",
                v_product_name="Total Level 1 HQLA",
                hqla_level="Level 1",
                weighted_amount=level_1_weighted_total,
                adjusted_amount=level_1_weighted_total
            ))

            hqla_entries.append(HQLAStock(
                fic_mis_date=fic_mis_date,
                v_prod_type="Total Level 2A HQLA",
                v_prod_code="L2A_TOTAL",
                v_product_name="Total Level 2A HQLA Before Cap",
                hqla_level="Level 2A",
                weighted_amount=level_2a_weighted_total,
                adjusted_amount=adjusted_level_2a
            ))

            hqla_entries.append(HQLAStock(
                fic_mis_date=fic_mis_date,
                v_prod_type="Total Level 2B HQLA",
                v_prod_code="L2B_TOTAL",
                v_product_name="Total Level 2B HQLA Before Cap",
                hqla_level="Level 2B",
                weighted_amount=level_2b_weighted_total,
                adjusted_amount=adjusted_level_2b
            ))

            # 🔟 Store **Total Level 2A After Cap**
            hqla_entries.append(HQLAStock(
                fic_mis_date=fic_mis_date,
                v_prod_type="Total Level 2A HQLA After Cap",
                v_prod_code="L2A_TOTAL_CAP",
                v_product_name="Total Level 2A HQLA After Cap",
                hqla_level="Level 2A",
                weighted_amount=adjusted_level_2a,
                adjusted_amount=adjusted_level_2a
            ))

            # 🔟 Store **Total Level 2B After Cap**
            hqla_entries.append(HQLAStock(
                fic_mis_date=fic_mis_date,
                v_prod_type="Total Level 2B HQLA After Cap",
                v_prod_code="L2B_TOTAL_CAP",
                v_product_name="Total Level 2B HQLA After Cap",
                hqla_level="Level 2B",
                weighted_amount=adjusted_level_2b,
                adjusted_amount=adjusted_level_2b_after_cap
            ))

            # 🔟 Bulk insert classified HQLA data
            HQLAStock.objects.bulk_create(hqla_entries)
            print(f"✅ Successfully classified {len(hqla_entries)} records into HQLA stock.")

    except Exception as e:
        print(f"❌ Error in classify_and_store_hqla: {e}")

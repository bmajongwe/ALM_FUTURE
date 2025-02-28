from django.db import transaction
from datetime import datetime
from ALM_APP.models import (
    ExtractedLiquidityData, LiquidityGapResultsBase, LrmSelectionConfig
)

def transfer_lrm_data(fic_mis_date, selection_purpose="LCR"):
    """
    Transfers ALM data for LCR based on configured selection criteria.
    Filters records by process names, product types, and time horizons defined in `LrmSelectionConfig`.
    Deletes existing data for the date before inserting new records.
    """

    try:
        print(f"🔍 Starting data transfer for {selection_purpose} on {fic_mis_date}")

        # 1️⃣ Ensure fic_mis_date is a proper date object
        if isinstance(fic_mis_date, str):
            fic_mis_date = datetime.strptime(fic_mis_date, "%Y-%m-%d").date()

        # 2️⃣ Get active LCR selection configuration
        selection = LrmSelectionConfig.objects.filter(selection_purpose=selection_purpose).first()
        if not selection:
            print(f"⚠️ No active {selection_purpose} selection found. Skipping data transfer.")
            return

        print(f"✅ Found selection config for {selection_purpose}")

        # 3️⃣ Retrieve filter criteria from the selection
        selected_processes = selection.selected_process_names  # e.g., ["contractual"]
        selected_products = selection.selected_product_types  # e.g., ["Business loans and Overdrafts"]
        selected_time_horizons = selection.selected_time_horizons  # e.g., ["1-30 Days"]

        print(f"🔹 Selected Processes: {selected_processes}")
        print(f"🔹 Selected Products: {selected_products}")
        print(f"🔹 Selected Time Horizons: {selected_time_horizons}")

        # 4️⃣ Convert selected time horizon into day range (include 0 days)
        time_ranges = []
        for time_horizon in selected_time_horizons:
            if time_horizon == "1-30 Days":
                start_days, end_days = 0, 30  # **Include 0 days**
            else:
                continue  # Skip if it's not in the expected LCR range
            time_ranges.append((start_days, end_days))

        print(f"🔹 Time Ranges Calculated: {time_ranges}")

        with transaction.atomic():
            # 5️⃣ Remove old extracted data for the same date
            deleted_count = ExtractedLiquidityData.objects.filter(fic_mis_date=fic_mis_date).delete()
            print(f"🗑️ Deleted {deleted_count[0]} old extracted records for {fic_mis_date}")

            # 6️⃣ Retrieve ALM records matching filter criteria
            alm_records = LiquidityGapResultsBase.objects.filter(
                fic_mis_date=fic_mis_date,
                process_name__in=selected_processes,  # Match process names
                v_prod_type__in=selected_products  # Match product types
            )

            print(f"🔍 Found {alm_records.count()} matching ALM records")

            extracted_data = []
            skipped_records = 0

            for record in alm_records:
                # 7️⃣ Ensure `bucket_start_date` is converted to a date object
                if isinstance(record.bucket_start_date, str):
                    record_start_date = datetime.strptime(record.bucket_start_date, "%Y-%m-%d").date()
                else:
                    record_start_date = record.bucket_start_date  # Already a date

                # 8️⃣ Apply time horizon filtering
                record_days = (record_start_date - fic_mis_date).days
                match_found = False

                for start_days, end_days in time_ranges:
                    if start_days <= record_days <= end_days:
                        match_found = True
                        # 9️⃣ Append filtered records to insert list
                        extracted_data.append(ExtractedLiquidityData(
                            fic_mis_date=record.fic_mis_date,
                            bucket_start_date=record.bucket_start_date,
                            bucket_end_date=record.bucket_end_date,
                            account_type=record.account_type,
                            v_prod_type=record.v_prod_type,
                            v_prod_code=record.v_prod_code,
                            v_product_name=record.v_product_name,
                            v_product_splits=record.v_product_splits,
                            v_prod_type_desc=record.v_prod_type_desc,
                            v_ccy_code=record.v_ccy_code,
                            inflows=record.inflows,
                            outflows=record.outflows,
                            n_total_cash_flow_amount=record.n_total_cash_flow_amount,
                            n_total_principal_payment=record.n_total_principal_payment,
                            n_total_interest_payment=record.n_total_interest_payment,
                            time_horizon_label=f"{start_days}-{end_days} days"
                        ))
                        break  # Stop checking further time ranges

                if not match_found:
                    skipped_records += 1
                    print(f"⚠️ Skipped Record: {record.v_prod_code} (Days: {record_days}) - Outside selected time range")

            # 🔟 Insert extracted data efficiently
            if extracted_data:
                ExtractedLiquidityData.objects.bulk_create(extracted_data)
                print(f"✅ Successfully transferred {len(extracted_data)} records for {selection_purpose}.")
            else:
                print(f"⚠️ No matching records found for {selection_purpose}.")

            print(f"🔹 Skipped {skipped_records} records due to time range mismatch")

    except Exception as e:
        print(f"❌ Error in transfer_lrm_data: {e}")

from django.db import transaction
from datetime import datetime
from decimal import Decimal
from ALM_APP.models import (
    ExtractedNsfrData,
    LiquidityGapResultsBase,
    LrmSelectionConfig
)

def transfer_nsfr_data(fic_mis_date, selection_purpose="NSFR"):
    """
    Transfers ALM data for NSFR based on configured selection criteria.
    Groups day ranges as follows:
      < 6 months → 0 - 179 days
      ≥ 6 months to < 1 year → 180 - 364 days
      ≥ 1 year → 365 - 99999 days
    """

    try:
        print(f"🔍 Starting data transfer for {selection_purpose} on {fic_mis_date}")

        # 1️⃣ Ensure fic_mis_date is a proper date object
        if isinstance(fic_mis_date, str):
            fic_mis_date = datetime.strptime(fic_mis_date, "%Y-%m-%d").date()

        # 2️⃣ Get active NSFR selection configuration
        selection = LrmSelectionConfig.objects.filter(selection_purpose=selection_purpose).first()
        if not selection:
            print(f"⚠️ No active {selection_purpose} selection found. Skipping data transfer.")
            return

        print(f"✅ Found selection config for {selection_purpose}")

        # 3️⃣ Retrieve filter criteria from the selection
        selected_processes = selection.selected_process_names
        selected_products = selection.selected_product_types
        selected_time_horizons = selection.selected_time_horizons

        print(f"🔹 Selected Processes: {selected_processes}")
        print(f"🔹 Selected Products: {selected_products}")
        print(f"🔹 Selected Time Horizons: {selected_time_horizons}")

        # 4️⃣ Convert selected time horizon into day ranges
        time_ranges = []
        for time_horizon in selected_time_horizons:
            if time_horizon == "< 6 months":
                start_days, end_days = 0, 179
            elif time_horizon == "≥ 6 months to < 1 year":
                start_days, end_days = 180, 364
            elif time_horizon == "≥ 1 year":
                start_days, end_days = 365, 99999
            else:
                continue
            time_ranges.append((time_horizon, start_days, end_days))

        print(f"🔹 Time Ranges Calculated: {time_ranges}")

        with transaction.atomic():
            # 5️⃣ Remove old extracted data for the same date
            deleted_count = ExtractedNsfrData.objects.filter(fic_mis_date=fic_mis_date).delete()
            print(f"🗑️ Deleted {deleted_count[0]} old extracted NSFR records for {fic_mis_date}")

            # 6️⃣ Retrieve ALM records matching filter criteria
            alm_records = LiquidityGapResultsBase.objects.filter(
                fic_mis_date=fic_mis_date,
                process_name__in=selected_processes,
                v_prod_type__in=selected_products
            )

            print(f"🔍 Found {alm_records.count()} matching ALM records for NSFR transfer")

            extracted_data = []
            skipped_records = 0

            for record in alm_records:
                # 7️⃣ Ensure `bucket_start_date` is date
                if isinstance(record.bucket_start_date, str):
                    record_start_date = datetime.strptime(record.bucket_start_date, "%Y-%m-%d").date()
                else:
                    record_start_date = record.bucket_start_date

                record_days = (record_start_date - fic_mis_date).days
                match_found = False

                for (label, start_days, end_days) in time_ranges:
                    if start_days <= record_days <= end_days:
                        # 8️⃣ Add to extracted data if within range
                        match_found = True
                        extracted_data.append(ExtractedNsfrData(
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
                            time_horizon_label=label
                        ))
                        break

                if not match_found:
                    skipped_records += 1
                    print(f"⚠️ Skipped record: {record.v_prod_code} (Days: {record_days}) outside time range.")

            # 9️⃣ Bulk insert the new data
            if extracted_data:
                ExtractedNsfrData.objects.bulk_create(extracted_data)
                print(f"✅ Successfully transferred {len(extracted_data)} records for {selection_purpose}.")
            else:
                print(f"⚠️ No matching NSFR records found for {selection_purpose}.")

            print(f"🔹 Skipped {skipped_records} records due to time horizon mismatch")

    except Exception as e:
        print(f"❌ Error in transfer_nsfr_data: {e}")

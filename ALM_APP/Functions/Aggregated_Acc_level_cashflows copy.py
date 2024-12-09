from datetime import timedelta, datetime
from dateutil.relativedelta import relativedelta  # To handle months and years
from django.db.models import Sum
from ..models import *


def calculate_time_buckets_and_spread(process_name, fic_mis_date):
    """
    Aggregate cashflow data from product_level_cashflows table and spread amounts across time buckets.
    fic_mis_date serves as the starting point, and d_cashflow_date is used for determining bucket placement.
    Before running, existing data for the same fic_mis_date is deleted to avoid duplicates.
    """

    # Step 1: Convert fic_mis_date from string to date object
    if isinstance(fic_mis_date, str):
        fic_mis_date = datetime.strptime(fic_mis_date, "%Y-%m-%d").date()

    # Step 2: Fetch process information
    try:
        process = Process.objects.get(name=process_name)
    except Process.DoesNotExist:
        print(f"Process '{process_name}' does not exist.")
        return

    # Step 3: Delete existing data for the same fic_mis_date and process_name in relevant tables
    AggregatedCashflowByBuckets.objects.filter(fic_mis_date=fic_mis_date, process_name=process_name).delete()
    TimeBucketMaster.objects.filter(process_name=process_name).delete()

    # Step 4: Fetch the TimeBuckets (neutral, not process specific)
    time_buckets = TimeBuckets.objects.all().order_by('serial_number')
    
    if not time_buckets.exists():
        print(f"No time buckets found.")
        return

    # Step 5: Fetch the product level cashflows for the given fic_mis_date
    cashflows = product_level_cashflows.objects.filter(fic_mis_date=fic_mis_date)

    if not cashflows.exists():
        print(f"No cashflows found for fic_mis_date: {fic_mis_date}")
        return

    # Step 6: Iterate over each account in product_level_cashflows and spread its data into the buckets
    for cashflow in cashflows:
        account_number = cashflow.v_account_number
        product_code = cashflow.v_prod_code
        currency_code = cashflow.v_ccy_code

        # Step 7: Aggregate for each financial element (cashflow amount, principal, interest)
        financial_elements = ['n_total_cash_flow_amount', 'n_total_principal_payment', 'n_total_interest_payment']

        for element in financial_elements:
            # Initialize an empty dictionary to store bucket values for this account/element
            bucket_data = {f"bucket_{i+1}": 0 for i in range(len(time_buckets))}

            # Step 8: Iterate through time buckets and calculate bucket start and end dates based on fic_mis_date
            bucket_start_date = fic_mis_date  # Start with fic_mis_date as the base

            for idx, bucket in enumerate(time_buckets):
                # Calculate the start and end dates dynamically based on the multiplier (Days, Months, Years)
                if bucket.multiplier == 'Days':
                    bucket_end_date = bucket_start_date + timedelta(days=bucket.frequency)
                elif bucket.multiplier == 'Months':
                    bucket_end_date = bucket_start_date + relativedelta(months=bucket.frequency)
                elif bucket.multiplier == 'Years':
                    bucket_end_date = bucket_start_date + relativedelta(years=bucket.frequency)
                else:
                    raise ValueError(f"Unsupported multiplier: {bucket.multiplier}")

                # Filter cashflows within the calculated bucket range based on d_cashflow_date
                cashflows_in_bucket = cashflows.filter(
                    v_account_number=account_number,
                    d_cashflow_date__gte=bucket_start_date,  # Compare to actual cashflow date
                    d_cashflow_date__lte=bucket_end_date
                )

                # Step 9: Aggregate the values for each element (cash_flow_amount, principal_payment, interest_payment)
                cashflows_aggregated = cashflows_in_bucket.aggregate(Sum(element))

                # Sum the values and spread them across the buckets
                bucket_data[f"bucket_{idx+1}"] += cashflows_aggregated[f"{element}__sum"] or 0

                # Store the bucket range in TimeBucketMaster (optional, for record-keeping)
                TimeBucketMaster.objects.update_or_create(
                    process_name=process_name,  # Process is still linked for record-keeping
                    bucket_number=idx+1,
                    defaults={
                        'start_date': bucket_start_date,  # Adjusted start date based on fic_mis_date
                        'end_date': bucket_end_date,      # Adjusted end date based on fic_mis_date
                    }
                )

                # Move to the next bucket, where the end date of the current bucket becomes the start date for the next bucket
                bucket_start_date = bucket_end_date + timedelta(days=1)

            # Step 10: Store aggregated values in AggregatedCashflowByBuckets with foreign key reference to TimeBucketMaster
            time_bucket_master = TimeBucketMaster.objects.filter(
                process_name=process_name
            ).first()

            AggregatedCashflowByBuckets.objects.update_or_create(
                fic_mis_date=fic_mis_date,
                process_name=process_name,  # Process filter helps identify records
                v_account_number=account_number,
                v_prod_code=product_code,
                v_ccy_code=currency_code,
                financial_element=element,
                defaults={
                    **bucket_data,  # Save all the bucket sums dynamically
                    'time_bucket_master': time_bucket_master  # Foreign key to TimeBucketMaster
                }
            )

    print(f"Successfully aggregated cashflows for process '{process_name}' and fic_mis_date {fic_mis_date}.")

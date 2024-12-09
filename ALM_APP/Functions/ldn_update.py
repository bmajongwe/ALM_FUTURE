from django.db.models import F
from datetime import timedelta
from ..models import Ldn_Financial_Instrument, Dim_Product

def update_date(fic_mis_date):
    """
    Updates D_MATURITY_DATE and D_NEXT_PAYMENT_DATE for records in the Ldn_Financial_Instrument table
    based on a specific FIC_MIS_DATE and product group descriptions in various time buckets.

    Args:
    fic_mis_date (datetime.date): The FIC_MIS_DATE to filter records by.
    
    Each product group description sets D_MATURITY_DATE based on a specified duration.
    D_NEXT_PAYMENT_DATE is set to one day before D_MATURITY_DATE.
    """
    # Define the duration mappings in days
    duration_mapping = {
        'FIX TO DAY 1 BUCKET': 1,
        'FIX TO 1 DAY BUCKET': 1,
        'FIX TO 0-7 DAY BUCKET': 7,
        'FIX TO 30 DAY BUCKET': 30,
        'FIX TO 1-30 DAYS BUCKET': 30,
        'FIX TO 31-60 DAYS BUCKET': 60,
        'FIX TO 61-90 DAYS BUCKET': 90,
        'FIX TO 91-180 DAYS BUCKET': 180,
        'FIX TO 181-365 DAYS BUCKET': 365,
        'FIX TO 6-12 MONTHS BUCKET': 365,
        '1 YEAR TO 3 YEARS BUCKET': 3 * 365,
        '3 YEARS TO 5 YEARS BUCKET': 5 * 365,
        '5 YEARS TO 10 YEARS BUCKET': 10 * 365,
        'FIX TO 99 YEAR BUCKET': 99 * 365,
        'FIX TO LAST BUCKET': 99 * 365  # Assuming "last bucket" is also 99 years
    }

    try:
        # Loop through each duration and apply the update for each matching bucket description
        for bucket, days in duration_mapping.items():
            # Retrieve eligible V_PROD_CODEs for the current bucket
            eligible_prod_codes = Dim_Product.objects.filter(
                v_prod_group_desc=bucket
            ).values_list('v_prod_code', flat=True)
            
            # Debugging output for eligible product codes
            print(f"Updating bucket '{bucket}' with duration {days} days.")
            print("Eligible Product Codes:", list(eligible_prod_codes))

            # Filter Ldn_Financial_Instrument records for updating
            matching_records = Ldn_Financial_Instrument.objects.filter(
                v_prod_code__in=eligible_prod_codes,
                fic_mis_date=fic_mis_date
            )
            
            # Debugging output for matching records count
            print("Matching Records Count:", matching_records.count())

            # Update D_MATURITY_DATE based on bucket duration
            updated_records = matching_records.update(
                d_maturity_date=F('fic_mis_date') + timedelta(days=days)
            )

            # Update D_NEXT_PAYMENT_DATE to be one day before D_MATURITY_DATE
            updated_next_payment_date = matching_records.update(
                d_next_payment_date=F('d_maturity_date') - timedelta(days=1)
            )

            # Output the count of updated records for each bucket
            print(f"{updated_records} records were updated for D_MATURITY_DATE in bucket '{bucket}'.")
            print(f"{updated_next_payment_date} records were updated for D_NEXT_PAYMENT_DATE in bucket '{bucket}'.")

    except Exception as e:
        print(f"An error occurred: {e}")

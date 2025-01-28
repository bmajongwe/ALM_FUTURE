
from datetime import timedelta, datetime
from decimal import Decimal
from dateutil.relativedelta import relativedelta  # To handle months and years
from django.db.models import Sum, Max
from django.db import transaction
from ..models import *
import logging
from django.core.exceptions import ObjectDoesNotExist
import traceback


logger = logging.getLogger(__name__)

def filter_products(process_name, fic_mis_date):
    """
    Retrieve products from Ldn_Product_Master based on filters associated with the process.
    Consider the highest fic_mis_date for each product code, then apply filters on f_prod_rate_sensitivity.
    This function now checks both Process and Process_Rn tables for the process.
    """

    try:
        # Step 1: Retrieve the process and associated filters
        try:
            process = Process.objects.get(name=process_name)
            filters = process.filters.all()
            logger.info(f"Retrieved filters from Process table for process '{process_name}'.")
        except Process.DoesNotExist:
            try:
                process = Process_Rn.objects.get(process_name=process_name)
                filters = process.filters.all()
                logger.info(f"Retrieved filters from Process_Rn table for process '{process_name}'.")
            except Process_Rn.DoesNotExist:
                error_message = f"Process '{process_name}' does not exist in either Process or Process_Rn tables."
                logger.error(error_message)
                Log.objects.create(
                    function_name='filter_products',
                    log_level='ERROR',
                    message=error_message,
                    detailed_error=traceback.format_exc(),
                    status='FAILURE'
                )
                return []

        if not filters.exists():
            info_message = f"No filters found for process '{process_name}'."
            logger.info(info_message)
            Log.objects.create(
                function_name='filter_products',
                log_level='INFO',
                message=info_message,
                status='SUCCESS'
            )
            return []

        logger.info(f"Filters for process '{process_name}': {[f'{f.field_name} {f.condition} {f.value}' for f in filters]}")

        # Step 2: Get the latest fic_mis_date per product code
        latest_dates_subquery = (
            Ldn_Product_Master.objects
            .values('v_prod_code')
            .annotate(max_fic_mis_date=Max('fic_mis_date'))
        )
        logger.info(f"Fetched latest fic_mis_date for each product code for process '{process_name}' and fic_mis_date '{fic_mis_date}'.")

        # Step 3: Use this subquery to get the latest entries for each product code
        latest_products = Ldn_Product_Master.objects.filter(
            v_prod_code__in=[item['v_prod_code'] for item in latest_dates_subquery],
            fic_mis_date__in=[item['max_fic_mis_date'] for item in latest_dates_subquery]
        )
        logger.info(f"Retrieved latest product entries for process '{process_name}' and fic_mis_date '{fic_mis_date}'.")

        if not latest_products.exists():
            info_message = f"No latest products found for process '{process_name}' and fic_mis_date '{fic_mis_date}'."
            logger.info(info_message)
            Log.objects.create(
                function_name='filter_products',
                log_level='INFO',
                message=info_message,
                status='SUCCESS'
            )
            return []

        # Step 4: Apply the process-specific filters
        filtered_products = latest_products
        for filter in filters:
            field = filter.field_name
            condition = filter.condition
            value = filter.value

            logger.info(f"Applying filter - Field: {field}, Condition: {condition}, Value: {value}")

            if condition == 'equals':
                filtered_products = filtered_products.filter(**{f"{field}__iexact": value})
            elif condition == 'contains':
                filtered_products = filtered_products.filter(**{f"{field}__icontains": value})
            elif condition == 'greater_than':
                filtered_products = filtered_products.filter(**{f"{field}__gt": value})
            elif condition == 'less_than':
                filtered_products = filtered_products.filter(**{f"{field}__lt": value})
            else:
                error_message = f"Unknown condition '{condition}' in filter for field '{field}'."
                logger.error(error_message)
                Log.objects.create(
                    function_name='filter_products',
                    log_level='ERROR',
                    message=error_message,
                    detailed_error=traceback.format_exc(),
                    status='FAILURE'
                )
                return []

        logger.info(f"Filtered products after applying all filters: {list(filtered_products.values_list('v_prod_code', flat=True))}")

        # Step 5: Match these products in product_level_cashflows
        final_product_codes = product_level_cashflows.objects.filter(
            fic_mis_date=fic_mis_date,
            v_prod_code__in=filtered_products.values_list('v_prod_code', flat=True)
        ).values_list('v_prod_code', flat=True).distinct()

        final_product_codes_list = list(final_product_codes)
        logger.info(f"Filtered product codes with highest fic_mis_date where conditions are met: {final_product_codes_list}")

        # Log the successful execution
        success_message = f"Successfully filtered products for process '{process_name}' and fic_mis_date '{fic_mis_date}'."
        logger.info(success_message)
        Log.objects.create(
            function_name='filter_products',
            log_level='INFO',
            message=success_message,
            status='SUCCESS'
        )

        return final_product_codes_list

    except TypeError as e:
        error_message = f"TypeError in filter_products: {str(e)}"
        logger.error(error_message)
        Log.objects.create(
            function_name='filter_products',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        return []

    except Exception as e:
        error_message = f"Unexpected error in filter_products for process '{process_name}' and fic_mis_date '{fic_mis_date}': {str(e)}"
        logger.error(error_message)
        Log.objects.create(
            function_name='filter_products',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        return []





####################################################################################################################


logger = logging.getLogger(__name__)

def calculate_time_buckets_and_spread(process_name, fic_mis_date):
    """
    Aggregate cashflow data from product_level_cashflows table and spread amounts across time buckets.
    This function checks both Process and Process_Rn tables for the process and handles scenarios
    where filters are applied or not.
    """
    logger.info(f"Function 'calculate_time_buckets_and_spread' started with process_name='{process_name}' and fic_mis_date='{fic_mis_date}'.")

    # Convert fic_mis_date if it's a string
    try:
        if isinstance(fic_mis_date, str):
            fic_mis_date = datetime.strptime(fic_mis_date, "%Y-%m-%d").date()
            logger.info(f"Converted fic_mis_date to date object: {fic_mis_date}")
            Log.objects.create(
                function_name='calculate_time_buckets_and_spread',
                log_level='INFO',
                message=f"Converted fic_mis_date to date object: {fic_mis_date}",
                status='SUCCESS'
            )
    except Exception as e:
        error_message = f"Error converting fic_mis_date: {e}"
        logger.error(error_message)
        Log.objects.create(
            function_name='calculate_time_buckets_and_spread',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        return 0

    # Step 1: Reset the record_count for all rows in product_level_cashflows for the given fic_mis_date
    try:
        reset_count = product_level_cashflows.objects.filter(fic_mis_date=fic_mis_date).update(record_count=0)
        logger_message = f"Reset 'record_count' for {reset_count} rows in product_level_cashflows for fic_mis_date {fic_mis_date}"
        logger.info(logger_message)
        Log.objects.create(
            function_name='calculate_time_buckets_and_spread',
            log_level='INFO',
            message=logger_message,
            status='SUCCESS'
        )
    except Exception as e:
        error_message = f"Error resetting record_count: {e}"
        logger.error(error_message)
        Log.objects.create(
            function_name='calculate_time_buckets_and_spread',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        return 0

    # Step 2: Get filtered product codes
    try:
        filtered_product_codes = filter_products(process_name, fic_mis_date)
        if not filtered_product_codes:
            logger.info("No filters applied. Processing all product codes.")
            Log.objects.create(
                function_name='calculate_time_buckets_and_spread',
                log_level='INFO',
                message="No filters applied. Processing all product codes.",
                status='SUCCESS'
            )
            # Fetch all product codes since no filters are applied
            filtered_product_codes = list(Ldn_Product_Master.objects.values_list('v_prod_code', flat=True))
            logger_message = f"Using all product codes: {filtered_product_codes}"
            logger.info(logger_message)
            Log.objects.create(
                function_name='calculate_time_buckets_and_spread',
                log_level='INFO',
                message=f"Using all product codes: {filtered_product_codes}",
                status='SUCCESS'
            )
        else:
            logger_message = f"Filtered product codes: {filtered_product_codes}"
            logger.info(logger_message)
            Log.objects.create(
                function_name='calculate_time_buckets_and_spread',
                log_level='INFO',
                message=logger_message,
                status='SUCCESS'
            )
    except Exception as e:
        error_message = f"Error filtering product codes: {e}"
        logger.error(error_message)
        Log.objects.create(
            function_name='filter_products',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        return 0

    # Step 3: Update product_level_cashflows based on filtered product codes
    try:
        updated_rows = product_level_cashflows.objects.filter(
            fic_mis_date=fic_mis_date,
            v_prod_code__in=filtered_product_codes
        ).update(record_count=1)
        logger_message = f"Updated 'record_count' for {updated_rows} rows in product_level_cashflows for fic_mis_date {fic_mis_date}"
        logger.info(logger_message)
        Log.objects.create(
            function_name='calculate_time_buckets_and_spread',
            log_level='INFO',
            message=logger_message,
            status='SUCCESS'
        )
    except Exception as e:
        error_message = f"Error updating record_count: {e}"
        logger.error(error_message)
        Log.objects.create(
            function_name='calculate_time_buckets_and_spread',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        return 0

    # Step 4: Fetch process information and delete existing data
    try:
        try:
            process = Process.objects.get(name=process_name)
            logger.info(f"Retrieved process '{process_name}' from Process table.")
            Log.objects.create(
                function_name='calculate_time_buckets_and_spread',
                log_level='INFO',
                message=f"Retrieved process '{process_name}' from Process table.",
                status='SUCCESS'
            )
        except Process.DoesNotExist:
            process = Process_Rn.objects.get(process_name=process_name)
            logger.info(f"Retrieved process '{process_name}' from Process_Rn table.")
            Log.objects.create(
                function_name='calculate_time_buckets_and_spread',
                log_level='INFO',
                message=f"Retrieved process '{process_name}' from Process_Rn table.",
                status='SUCCESS'
            )

        AggregatedCashflowByBuckets.objects.filter(fic_mis_date=fic_mis_date, process_name=process_name).delete()
        TimeBucketMaster.objects.filter(process_name=process_name).delete()
        logger_message = f"Deleted existing records for process '{process_name}' and fic_mis_date {fic_mis_date}"
        logger.info(logger_message)
        Log.objects.create(
            function_name='calculate_time_buckets_and_spread',
            log_level='INFO',
            message=logger_message,
            status='SUCCESS'
        )
    except Process_Rn.DoesNotExist:
        error_message = f"Process '{process_name}' does not exist in either Process or Process_Rn tables."
        logger.error(error_message)
        Log.objects.create(
            function_name='calculate_time_buckets_and_spread',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        return 0
    except Exception as e:
        error_message = f"Error deleting existing records: {e}"
        logger.error(error_message)
        Log.objects.create(
            function_name='calculate_time_buckets_and_spread',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        return 0

    # Step 5: Fetch TimeBuckets and product level cashflows
    try:
        time_buckets = TimeBuckets.objects.all().order_by('serial_number')
        if not time_buckets.exists():
            logger_message = "No time buckets found."
            logger.info(logger_message)
            Log.objects.create(
                function_name='calculate_time_buckets_and_spread',
                log_level='INFO',
                message=logger_message,
                status='SUCCESS'
            )
            return 0
        total_time_buckets = time_buckets.count()
        logger.info(f"Fetched {total_time_buckets} time buckets.")
        Log.objects.create(
            function_name='calculate_time_buckets_and_spread',
            log_level='INFO',
            message=f"Fetched {total_time_buckets} time buckets.",
            status='SUCCESS'
        )
    except Exception as e:
        error_message = f"Error fetching time buckets: {e}"
        logger.error(error_message)
        Log.objects.create(
            function_name='calculate_time_buckets_and_spread',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        return 0

    # Only process cashflows with record_count set to 1
    try:
        cashflows = product_level_cashflows.objects.filter(
            fic_mis_date=fic_mis_date,
            v_prod_code__in=filtered_product_codes,
            record_count=1
        )
        if not cashflows.exists():
            logger_message = f"No cashflows found for fic_mis_date: {fic_mis_date}"
            logger.info(logger_message)
            Log.objects.create(
                function_name='calculate_time_buckets_and_spread',
                log_level='INFO',
                message=logger_message,
                status='SUCCESS'
            )
            return 0
        logger.info(f"Processing {cashflows.count()} cashflows.")
        Log.objects.create(
            function_name='calculate_time_buckets_and_spread',
            log_level='INFO',
            message=f"Processing {cashflows.count()} cashflows.",
            status='SUCCESS'
        )
    except Exception as e:
        error_message = f"Error filtering cashflows: {e}"
        logger.error(error_message)
        Log.objects.create(
            function_name='calculate_time_buckets_and_spread',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        return 0

    # Process each cashflow item
    for cashflow in cashflows:
        account_number = cashflow.v_account_number
        product_code = cashflow.v_prod_code
        currency_code = cashflow.v_ccy_code
        v_loan_type = cashflow.v_loan_type
        v_party_type_code = cashflow.v_party_type_code

        financial_elements = ['n_total_cash_flow_amount', 'n_total_principal_payment', 'n_total_interest_payment']

        for element in financial_elements:
            bucket_data = {f"bucket_{i+1}": 0 for i in range(len(time_buckets))}
            bucket_start_date = fic_mis_date

            for idx, bucket in enumerate(time_buckets):
                try:
                    if bucket.multiplier == 'Days':
                        bucket_end_date = bucket_start_date + timedelta(days=bucket.frequency)
                    elif bucket.multiplier == 'Months':
                        bucket_end_date = bucket_start_date + relativedelta(months=bucket.frequency)
                    elif bucket.multiplier == 'Years':
                        bucket_end_date = bucket_start_date + relativedelta(years=bucket.frequency)
                    else:
                        raise ValueError(f"Unsupported multiplier: {bucket.multiplier}")

                    cashflows_in_bucket = cashflows.filter(
                        v_account_number=account_number,
                        d_cashflow_date__gte=bucket_start_date,
                        d_cashflow_date__lte=bucket_end_date
                    )
                    cashflows_aggregated = cashflows_in_bucket.aggregate(Sum(element))
                    bucket_sum = cashflows_aggregated.get(f"{element}__sum", 0) or 0
                    bucket_data[f"bucket_{idx+1}"] += bucket_sum

                    # Update TimeBucketMaster for reference
                    TimeBucketMaster.objects.update_or_create(
                        process_name=process_name,
                        bucket_number=idx+1,
                        defaults={
                            'start_date': bucket_start_date,
                            'end_date': bucket_end_date,
                        }
                    )
                    # Removed logging statements related to TimeBucketMaster update
                    bucket_start_date = bucket_end_date + timedelta(days=1)
                except Exception as e:
                    error_message = f"Error processing bucket {idx+1} for element '{element}': {e}"
                    logger.error(error_message)
                    Log.objects.create(
                        function_name='calculate_time_buckets_and_spread',
                        log_level='ERROR',
                        message=error_message,
                        detailed_error=traceback.format_exc(),
                        status='FAILURE'
                    )
                    return 0

            try:
                # Store the aggregated bucket data
                time_bucket_master = TimeBucketMaster.objects.filter(process_name=process_name).first()
                AggregatedCashflowByBuckets.objects.update_or_create(
                    fic_mis_date=fic_mis_date,
                    process_name=process_name,
                    v_account_number=account_number,
                    v_prod_code=product_code,
                    v_ccy_code=currency_code,
                    v_loan_type=v_loan_type,
                    v_party_type_code=v_party_type_code,
                    financial_element=element,
                    defaults={
                        **bucket_data,
                        'time_bucket_master': time_bucket_master
                    }
                )
                # Removed logging statements related to AggregatedCashflowByBuckets update
            except Exception as e:
                error_message = f"Error inserting AggregatedCashflowByBuckets for product '{product_code}' and element '{element}': {e}"
                logger.error(error_message)
                Log.objects.create(
                    function_name='calculate_time_buckets_and_spread',
                    log_level='ERROR',
                    message=error_message,
                    detailed_error=traceback.format_exc(),
                    status='FAILURE'
                )
                return 0

    # Final Success Log
    try:
        logger_message = f"Successfully aggregated cashflows for process '{process_name}' and fic_mis_date {fic_mis_date}."
        logger.info(logger_message)
        Log.objects.create(
            function_name='calculate_time_buckets_and_spread',
            log_level='INFO',
            message=logger_message,
            status='SUCCESS'
        )
        return 1
    except Exception as e:
        error_message = f"Error logging success message: {e}"
        logger.error(error_message)
        Log.objects.create(
            function_name='calculate_time_buckets_and_spread',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        return 0



    






    ##############################################################################################



logger = logging.getLogger(__name__)

def calculate_behavioral_pattern_distribution(process_name, fic_mis_date):
    """
    Distribute amounts across time buckets based on behavioral patterns.
    Deletes previous entries if the process is rerun for the same fic_mis_date.
    This function now checks both Process and Process_Rn tables for the process.
    """
    logger.info(f"Function 'calculate_behavioral_pattern_distribution' started with process_name='{process_name}' and fic_mis_date='{fic_mis_date}'.")

    # Convert fic_mis_date if it's a string
    try:
        if isinstance(fic_mis_date, str):
            fic_mis_date = datetime.strptime(fic_mis_date, "%Y-%m-%d").date()
            logger.info(f"Converted fic_mis_date to date object: {fic_mis_date}")
            Log.objects.create(
                function_name='calculate_behavioral_pattern_distribution',
                log_level='INFO',
                message=f"Converted fic_mis_date to date object: {fic_mis_date}",
                status='SUCCESS'
            )
    except Exception as e:
        error_message = f"Error converting fic_mis_date: {e}"
        logger.error(error_message)
        Log.objects.create(
            function_name='calculate_behavioral_pattern_distribution',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        return 0

    # Step 1: Delete previous entries for the process_name and fic_mis_date
    try:
        AggregatedCashflowByBuckets.objects.filter(
            process_name=process_name, 
            fic_mis_date=fic_mis_date
        ).delete()
        logger_message = f"Deleted existing records for process '{process_name}' and fic_mis_date {fic_mis_date}"
        logger.info(logger_message)
        Log.objects.create(
            function_name='calculate_behavioral_pattern_distribution',
            log_level='INFO',
            message=logger_message,
            status='SUCCESS'
        )
    except Exception as e:
        error_message = f"Error deleting previous entries: {e}"
        logger.error(error_message)
        Log.objects.create(
            function_name='calculate_behavioral_pattern_distribution',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        return 0

    # Step 2: Fetch the process from both Process and Process_Rn tables
    try:
        try:
            process = Process.objects.get(name=process_name)
            logger.info(f"Retrieved process '{process_name}' from Process table.")
            Log.objects.create(
                function_name='calculate_behavioral_pattern_distribution',
                log_level='INFO',
                message=f"Retrieved process '{process_name}' from Process table.",
                status='SUCCESS'
            )
        except Process.DoesNotExist:
            process = Process_Rn.objects.get(process_name=process_name)
            logger.info(f"Retrieved process '{process_name}' from Process_Rn table.")
            Log.objects.create(
                function_name='calculate_behavioral_pattern_distribution',
                log_level='INFO',
                message=f"Retrieved process '{process_name}' from Process_Rn table.",
                status='SUCCESS'
            )
    except Process_Rn.DoesNotExist:
        error_message = f"Process '{process_name}' does not exist in either Process or Process_Rn tables."
        logger.error(error_message)
        Log.objects.create(
            function_name='calculate_behavioral_pattern_distribution',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        return 0
    except Exception as e:
        error_message = f"Error fetching process information: {e}"
        logger.error(error_message)
        Log.objects.create(
            function_name='calculate_behavioral_pattern_distribution',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        return 0

    # Step 3: Fetch behavioral patterns
    try:
        behavioral_patterns = BehavioralPatternConfig.objects.all()
        if not behavioral_patterns.exists():
            logger_message = "No behavioral patterns found."
            logger.info(logger_message)
            Log.objects.create(
                function_name='calculate_behavioral_pattern_distribution',
                log_level='INFO',
                message=logger_message,
                status='SUCCESS'
            )
            return 1
        logger.info(f"Fetched {behavioral_patterns.count()} behavioral patterns.")
        Log.objects.create(
            function_name='calculate_behavioral_pattern_distribution',
            log_level='INFO',
            message=f"Fetched {behavioral_patterns.count()} behavioral patterns.",
            status='SUCCESS'
        )
    except Exception as e:
        error_message = f"Error fetching behavioral patterns: {e}"
        logger.error(error_message)
        Log.objects.create(
            function_name='calculate_behavioral_pattern_distribution',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        return 0

    # Step 4: Fetch the time buckets associated with the process
    try:
        time_buckets = TimeBuckets.objects.all().order_by('serial_number')
        if not time_buckets.exists():
            logger_message = "No time buckets found."
            logger.info(logger_message)
            Log.objects.create(
                function_name='calculate_behavioral_pattern_distribution',
                log_level='INFO',
                message=logger_message,
                status='SUCCESS'
            )
            return 0
        total_time_buckets = time_buckets.count()
        logger.info(f"Fetched {total_time_buckets} time buckets.")
        Log.objects.create(
            function_name='calculate_behavioral_pattern_distribution',
            log_level='INFO',
            message=f"Fetched {total_time_buckets} time buckets.",
            status='SUCCESS'
        )
    except Exception as e:
        error_message = f"Error fetching time buckets: {e}"
        logger.error(error_message)
        Log.objects.create(
            function_name='calculate_behavioral_pattern_distribution',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        return 0

    # Step 5: Iterate through each behavioral pattern
    for pattern in behavioral_patterns:
        try:
            logger.info(f"Applying behavioral pattern for product type '{pattern.v_prod_type}'.")
            Log.objects.create(
                function_name='calculate_behavioral_pattern_distribution',
                log_level='INFO',
                message=f"Applying behavioral pattern for product type '{pattern.v_prod_type}'.",
                status='SUCCESS'
            )

            # Fetch the entries associated with this pattern
            entries = BehavioralPatternEntry.objects.filter(pattern_id=pattern.id).order_by('order')
            total_entries = entries.count()

            # Check if the number of behavioral entries matches the number of time buckets
            if total_entries != total_time_buckets:
                logger_message = f"Mismatch between behavioral entries ({total_entries}) and time buckets ({total_time_buckets}). Skipping pattern '{pattern.v_prod_type}'."
                logger.warning(logger_message)
                Log.objects.create(
                    function_name='calculate_behavioral_pattern_distribution',
                    log_level='WARNING',
                    message=logger_message,
                    status='SUCCESS'
                )
                continue  # Skip this pattern since it doesn't match the time buckets

            # Fetch product level cashflows that match the product type
            try:
                product_codes = Ldn_Product_Master.objects.filter(v_prod_type=pattern.v_prod_type).values_list('v_prod_code', flat=True)
                cashflows = product_level_cashflows.objects.filter(
                    fic_mis_date=fic_mis_date,
                    v_prod_code__in=product_codes
                )
                if not cashflows.exists():
                    logger_message = f"No cashflows found for fic_mis_date: {fic_mis_date} and product type: {pattern.v_prod_type}"
                    logger.info(logger_message)
                    Log.objects.create(
                        function_name='calculate_behavioral_pattern_distribution',
                        log_level='INFO',
                        message=logger_message,
                        status='SUCCESS'
                    )
                    continue
                logger.info(f"Processing {cashflows.count()} cashflows for product type '{pattern.v_prod_type}'.")
                Log.objects.create(
                    function_name='calculate_behavioral_pattern_distribution',
                    log_level='INFO',
                    message=f"Processing {cashflows.count()} cashflows for product type '{pattern.v_prod_type}'.",
                    status='SUCCESS'
                )
            except Exception as e:
                error_message = f"Error fetching cashflows for product type '{pattern.v_prod_type}': {e}"
                logger.error(error_message)
                Log.objects.create(
                    function_name='calculate_behavioral_pattern_distribution',
                    log_level='ERROR',
                    message=error_message,
                    detailed_error=traceback.format_exc(),
                    status='FAILURE'
                )
                continue

            # Process each cashflow item and distribute amounts based on percentage
            for cashflow in cashflows:
                account_number = cashflow.v_account_number
                product_code = cashflow.v_prod_code
                currency_code = cashflow.v_ccy_code
                v_loan_type = cashflow.v_loan_type
                v_party_type_code = cashflow.v_party_type_code

                financial_elements = ['n_total_cash_flow_amount', 'n_total_principal_payment', 'n_total_interest_payment']

                for element in financial_elements:
                    try:
                        total_value = getattr(cashflow, element)

                        # Edge case: skip if total_value is None or zero
                        if total_value is None or total_value == 0:
                            logger.debug(f"Skipping element '{element}' for cashflow ID '{cashflow.id}' due to zero or None value.")
                            continue

                        # Distribute across the entries based on percentage
                        for entry, time_bucket in zip(entries, time_buckets):
                            percentage = entry.percentage / Decimal(100.0)  # Convert percentage to a ratio
                            distributed_value = total_value * percentage

                            # Store the distribution in TimeBucketMaster (optional for record keeping)
                            try:
                                time_bucket_master, created = TimeBucketMaster.objects.update_or_create(
                                    process_name=process_name,
                                    bucket_number=time_bucket.serial_number,  # Use 'serial_number' from time buckets
                                    defaults={
                                        'start_date': time_bucket.start_date,
                                        'end_date': time_bucket.end_date,
                                    }
                                )
                                if created:
                                    logger.debug(f"Created TimeBucketMaster for bucket_number={time_bucket.serial_number}.")
                                else:
                                    logger.debug(f"Updated TimeBucketMaster for bucket_number={time_bucket.serial_number}.")
                            except Exception as e:
                                error_message = f"Error updating TimeBucketMaster for bucket_number={time_bucket.serial_number}: {e}"
                                logger.error(error_message)
                                Log.objects.create(
                                    function_name='calculate_behavioral_pattern_distribution',
                                    log_level='ERROR',
                                    message=error_message,
                                    detailed_error=traceback.format_exc(),
                                    status='FAILURE'
                                )
                                return 0

                            # Fetch existing value in the bucket and accumulate
                            try:
                                aggregated_entry, created = AggregatedCashflowByBuckets.objects.get_or_create(
                                    fic_mis_date=fic_mis_date,
                                    process_name=process_name,
                                    v_account_number=account_number,
                                    v_prod_code=product_code,
                                    v_ccy_code=currency_code,
                                    v_loan_type=v_loan_type,
                                    v_party_type_code=v_party_type_code,
                                    financial_element=element,
                                )

                                # Fetch the current value, and default to Decimal(0) if it is None
                                current_value = getattr(aggregated_entry, f'bucket_{time_bucket.serial_number}', None)
                                if current_value is None:
                                    current_value = Decimal(0)

                                # Accumulate the value in the bucket
                                new_value = current_value + distributed_value
                                setattr(aggregated_entry, f'bucket_{time_bucket.serial_number}', new_value)
                                aggregated_entry.time_bucket_master = time_bucket_master  # Correctly assign the TimeBucketMaster instance
                                aggregated_entry.save()
                                logger.debug(f"Accumulated {distributed_value} in bucket_{time_bucket.serial_number} for aggregated_entry ID '{aggregated_entry.id}'.")
                            except Exception as e:
                                error_message = f"Error updating AggregatedCashflowByBuckets for product '{product_code}' and element '{element}': {e}"
                                logger.error(error_message)
                                Log.objects.create(
                                    function_name='calculate_behavioral_pattern_distribution',
                                    log_level='ERROR',
                                    message=error_message,
                                    detailed_error=traceback.format_exc(),
                                    status='FAILURE'
                                )
                                return 0
                    except Exception as e:
                        error_message = f"Error processing element '{element}' for cashflow ID '{cashflow.id}': {e}"
                        logger.error(error_message)
                        Log.objects.create(
                            function_name='calculate_behavioral_pattern_distribution',
                            log_level='ERROR',
                            message=error_message,
                            detailed_error=traceback.format_exc(),
                            status='FAILURE'
                        )
                        return 0

        except Exception as e:
            error_message = f"Unexpected error in applying behavioral pattern '{pattern.v_prod_type}': {e}"
            logger.error(error_message)
            Log.objects.create(
                function_name='calculate_behavioral_pattern_distribution',
                log_level='ERROR',
                message=error_message,
                detailed_error=traceback.format_exc(),
                status='FAILURE'
            )
            return 0

    try:
        logger_message = f"Successfully distributed amounts using behavioral patterns for process '{process_name}' and fic_mis_date {fic_mis_date}."
        logger.info(logger_message)
        Log.objects.create(
            function_name='calculate_behavioral_pattern_distribution',
            log_level='INFO',
            message=logger_message,
            status='SUCCESS'
        )
        return 1
    except Exception as e:
        error_message = f"Error logging success message: {e}"
        logger.error(error_message)
        Log.objects.create(
            function_name='calculate_behavioral_pattern_distribution',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        return 0



# from datetime import timedelta, datetime
# from decimal import Decimal
# from dateutil.relativedelta import relativedelta  # To handle months and years
# from django.db.models import Sum, Max
# from ..models import *

# def filter_products(process_name, fic_mis_date):
#     """
#     Retrieve products from Ldn_Product_Master based on filters associated with the process.
#     Consider the highest fic_mis_date for each product code, then apply filters on f_prod_rate_sensitivity.
#     """
#     # Get the process and associated filters
#     try:
#         process = Process.objects.get(name=process_name)
#         filters = process.filters.all()
#         print(f"Filters for process '{process_name}': {[f'{f.field_name} {f.condition} {f.value}' for f in filters]}")
#     except Process.DoesNotExist:
#         print(f"Process '{process_name}' does not exist.")
#         return []

#     # Step 1: Get the latest fic_mis_date per product code
#     latest_dates_subquery = (
#         Ldn_Product_Master.objects
#         .values('v_prod_code')
#         .annotate(max_fic_mis_date=Max('fic_mis_date'))
#     )

#     # Step 2: Use this subquery to get the latest entries for each product code
#     latest_products = Ldn_Product_Master.objects.filter(
#         v_prod_code__in=[item['v_prod_code'] for item in latest_dates_subquery],
#         fic_mis_date__in=[item['max_fic_mis_date'] for item in latest_dates_subquery]
#     )

#     # Step 3: Apply the process-specific filter on f_prod_rate_sensitivity and other fields
#     filtered_products = latest_products
#     for filter in filters:
#         field = filter.field_name
#         condition = filter.condition
#         value = filter.value

#         print(f"Applying filter - Field: {field}, Condition: {condition}, Value: {value}")

#         if condition == 'equals':
#             filtered_products = filtered_products.filter(**{f"{field}__iexact": value})
#         elif condition == 'contains':
#             filtered_products = filtered_products.filter(**{f"{field}__icontains": value})
#         elif condition == 'greater_than':
#             filtered_products = filtered_products.filter(**{f"{field}__gt": value})
#         elif condition == 'less_than':
#             filtered_products = filtered_products.filter(**{f"{field}__lt": value})

#     # Step 4: Match these products in product_level_cashflows
#     final_product_codes = product_level_cashflows.objects.filter(
#         fic_mis_date=fic_mis_date,
#         v_prod_code__in=filtered_products.values_list('v_prod_code', flat=True)
#     ).values_list('v_prod_code', flat=True).distinct()

#     print(f"Filtered product codes with highest fic_mis_date where conditions are met: {list(final_product_codes)}")
#     return final_product_codes



# def calculate_time_buckets_and_spread(process_name, fic_mis_date):
#     """
#     Aggregate cashflow data from product_level_cashflows table and spread amounts across time buckets.
#     """
#     if isinstance(fic_mis_date, str):
#         fic_mis_date = datetime.strptime(fic_mis_date, "%Y-%m-%d").date()

#     # Step 1: Reset the record_count for all rows in product_level_cashflows for the given fic_mis_date
#     reset_count = product_level_cashflows.objects.filter(fic_mis_date=fic_mis_date).update(record_count=0)
#     print(f"Reset 'record_count' for {reset_count} rows in product_level_cashflows for fic_mis_date {fic_mis_date}")

#     # Step 2: Get filtered product codes
#     filtered_product_codes = filter_products(process_name, fic_mis_date)
    
#     # Step 3: Update product_level_cashflows based on filtered product codes
#     updated_rows = product_level_cashflows.objects.filter(
#         fic_mis_date=fic_mis_date,
#         v_prod_code__in=filtered_product_codes
#     ).update(record_count=1)
#     print(f"Updated 'record_count' for {updated_rows} rows in product_level_cashflows for fic_mis_date {fic_mis_date}")

#     # Step 4: Fetch process information and delete existing data
#     try:
#         process = Process.objects.get(name=process_name)
#     except Process.DoesNotExist:
#         print(f"Process '{process_name}' does not exist.")
#         return

#     AggregatedCashflowByBuckets.objects.filter(fic_mis_date=fic_mis_date, process_name=process_name).delete()
#     TimeBucketMaster.objects.filter(process_name=process_name).delete()
#     print(f"Deleted existing records for process '{process_name}' and fic_mis_date {fic_mis_date}")

#     # Step 5: Fetch TimeBuckets and product level cashflows
#     time_buckets = TimeBuckets.objects.all().order_by('serial_number')
#     if not time_buckets.exists():
#         print("No time buckets found.")
#         return

#     # Only process cashflows with record_count set to 1
#     cashflows = product_level_cashflows.objects.filter(
#         fic_mis_date=fic_mis_date,
#         v_prod_code__in=filtered_product_codes,
#         record_count=1
#     )
#     if not cashflows.exists():
#         print(f"No cashflows found for fic_mis_date: {fic_mis_date}")
#         return

#     # Process each cashflow item
#     for cashflow in cashflows:
#         account_number = cashflow.v_account_number
#         product_code = cashflow.v_prod_code
#         currency_code = cashflow.v_ccy_code
#         v_loan_type=cashflow.v_loan_type
#         v_party_type_code=cashflow.v_party_type_code

#         financial_elements = ['n_total_cash_flow_amount', 'n_total_principal_payment', 'n_total_interest_payment']

#         for element in financial_elements:
#             bucket_data = {f"bucket_{i+1}": 0 for i in range(len(time_buckets))}
#             bucket_start_date = fic_mis_date

#             for idx, bucket in enumerate(time_buckets):
#                 if bucket.multiplier == 'Days':
#                     bucket_end_date = bucket_start_date + timedelta(days=bucket.frequency)
#                 elif bucket.multiplier == 'Months':
#                     bucket_end_date = bucket_start_date + relativedelta(months=bucket.frequency)
#                 elif bucket.multiplier == 'Years':
#                     bucket_end_date = bucket_start_date + relativedelta(years=bucket.frequency)
#                 else:
#                     raise ValueError(f"Unsupported multiplier: {bucket.multiplier}")

#                 cashflows_in_bucket = cashflows.filter(
#                     v_account_number=account_number,
#                     d_cashflow_date__gte=bucket_start_date,
#                     d_cashflow_date__lte=bucket_end_date
#                 )
#                 cashflows_aggregated = cashflows_in_bucket.aggregate(Sum(element))
#                 bucket_data[f"bucket_{idx+1}"] += cashflows_aggregated[f"{element}__sum"] or 0

#                 # Update TimeBucketMaster for reference
#                 TimeBucketMaster.objects.update_or_create(
#                     process_name=process_name,
#                     bucket_number=idx+1,
#                     defaults={
#                         'start_date': bucket_start_date,
#                         'end_date': bucket_end_date,
#                     }
#                 )
#                 bucket_start_date = bucket_end_date + timedelta(days=1)

#             # Store the aggregated bucket data
#             time_bucket_master = TimeBucketMaster.objects.filter(process_name=process_name).first()
#             AggregatedCashflowByBuckets.objects.update_or_create(
#                 fic_mis_date=fic_mis_date,
#                 process_name=process_name,
#                 v_account_number=account_number,
#                 v_prod_code=product_code,
#                 v_ccy_code=currency_code,
#                 v_loan_type=v_loan_type,
#                 v_party_type_code=v_party_type_code,
#                 financial_element=element,
#                 defaults={
#                     **bucket_data,
#                     'time_bucket_master': time_bucket_master
#                 }
#             )

#     print(f"Successfully aggregated cashflows for process '{process_name}' and fic_mis_date {fic_mis_date}.")








# def calculate_behavioral_pattern_distribution(process_name, fic_mis_date):
#     """
#     Distribute amounts across time buckets based on behavioral patterns.
#     Deletes previous entries if the process is rerun for the same fic_mis_date.
#     """
#     if isinstance(fic_mis_date, str):
#         fic_mis_date = datetime.strptime(fic_mis_date, "%Y-%m-%d").date()

#     # Step 1: Delete previous entries for the process_name and fic_mis_date
#     AggregatedCashflowByBuckets.objects.filter(
#         process_name=process_name, 
#         fic_mis_date=fic_mis_date
#     ).delete()

#     print(f"Deleted existing records for process '{process_name}' and fic_mis_date {fic_mis_date}")

#     # Fetch behavioral patterns
#     behavioral_patterns = BehavioralPatternConfig.objects.all()

#     if not behavioral_patterns.exists():
#         print("No behavioral patterns found.")
#         return

#     # Fetch the time buckets associated with the process
#     time_buckets = TimeBuckets.objects.all().order_by('serial_number')

#     if not time_buckets.exists():
#         print("No time buckets found.")
#         return

#     total_time_buckets = time_buckets.count()

#     for pattern in behavioral_patterns:
#         print(f"Applying behavioral pattern for product type '{pattern.v_prod_type}'.")

#         # Fetch the entries associated with this pattern
#         entries = BehavioralPatternEntry.objects.filter(pattern_id=pattern.id).order_by('order')

#         total_entries = entries.count()

#         # Check if the number of behavioral entries matches the number of time buckets
#         if total_entries != total_time_buckets:
#             print(f"Mismatch between behavioral entries ({total_entries}) and time buckets ({total_time_buckets}). Skipping pattern '{pattern.v_prod_type}'.")
#             continue  # Skip this pattern since it doesn't match the time buckets

#         # Fetch product level cashflows that match the product type
#         cashflows = product_level_cashflows.objects.filter(
#             fic_mis_date=fic_mis_date,
#             v_prod_code__in=Ldn_Product_Master.objects.filter(v_prod_type=pattern.v_prod_type).values_list('v_prod_code', flat=True)
#         )

#         if not cashflows.exists():
#             print(f"No cashflows found for fic_mis_date: {fic_mis_date} and product type: {pattern.v_prod_type}")
#             continue

#         # Process each cashflow item and distribute amounts based on percentage
#         for cashflow in cashflows:
#             account_number = cashflow.v_account_number
#             product_code = cashflow.v_prod_code
#             currency_code = cashflow.v_ccy_code
#             v_loan_type=cashflow.v_loan_type
#             v_party_type_code=cashflow.v_party_type_code

#             financial_elements = ['n_total_cash_flow_amount', 'n_total_principal_payment', 'n_total_interest_payment']

#             for element in financial_elements:
#                 total_value = getattr(cashflow, element)

#                 # Edge case: skip if total_value is None or zero
#                 if total_value is None or total_value == 0:
#                     continue

#                 # Distribute across the entries based on percentage
#                 for entry, time_bucket in zip(entries, time_buckets):
#                     percentage = entry.percentage / Decimal(100.0)  # Convert percentage to a ratio
#                     distributed_value = total_value * percentage

#                     # Store the distribution in TimeBucketMaster (optional for record keeping)
#                     time_bucket_master, _ = TimeBucketMaster.objects.update_or_create(
#                         process_name=process_name,
#                         bucket_number=time_bucket.serial_number,  # Use 'serial_number' from time buckets
#                         defaults={
#                             'start_date': time_bucket.start_date,
#                             'end_date': time_bucket.end_date,
#                         }
#                     )

#                     # Fetch existing value in the bucket and accumulate
#                     aggregated_entry, created = AggregatedCashflowByBuckets.objects.get_or_create(
#                         fic_mis_date=fic_mis_date,
#                         process_name=process_name,
#                         v_account_number=account_number,
#                         v_prod_code=product_code,
#                         v_ccy_code=currency_code,
#                         v_loan_type=v_loan_type,
#                         v_party_type_code=v_party_type_code,
#                         financial_element=element,
#                     )

#                     # Fetch the current value, and default to Decimal(0) if it is None
#                     current_value = getattr(aggregated_entry, f'bucket_{time_bucket.serial_number}', None)
#                     if current_value is None:
#                         current_value = Decimal(0)

#                     # Accumulate the value in the bucket
#                     new_value = current_value + distributed_value

#                     # Update the entry with the new accumulated value
#                     setattr(aggregated_entry, f'bucket_{time_bucket.serial_number}', new_value)
#                     aggregated_entry.time_bucket_master = time_bucket_master  # Correctly assign the TimeBucketMaster instance
#                     aggregated_entry.save()

#     print(f"Successfully distributed amounts using behavioral patterns for process '{process_name}' and fic_mis_date {fic_mis_date}.")

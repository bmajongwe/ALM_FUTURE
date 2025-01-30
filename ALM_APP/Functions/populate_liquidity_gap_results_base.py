from django.db.models import Sum
from django.db import transaction
from django.core.cache import cache
from ..models import Aggregated_Prod_Cashflow_Base, TimeBucketMaster, Dim_Product, LiquidityGapResultsBase, Log
import logging
import traceback

logger = logging.getLogger(__name__)

def populate_liquidity_gap_results_base(fic_mis_date, process_name):
    """
    Fetches aggregated data from Aggregated_Prod_Cashflow_Base, groups by product and party type,
    retrieves product details based on v_prod_code and v_product_splits based on both v_prod_code and v_party_type_code,
    then stores separated results in LiquidityGapResultsBase.
    If no matching product info is found, uses default values and continues processing.
    """
    try:
        with transaction.atomic():
            # Step 1: Delete existing records
            deleted_count = LiquidityGapResultsBase.objects.filter(
                fic_mis_date=fic_mis_date, process_name=process_name
            ).delete()[0]
            logger_message = f"Deleted {deleted_count} records for {fic_mis_date}, {process_name}"
            logger.info(logger_message)
            print(logger_message)
            Log.objects.create(
                function_name='populate_liquidity_gap_results_base',
                log_level='INFO',
                message=logger_message,
                status='SUCCESS'
            )

            # Step 2: Fetch and cache product data with party type info
            cache_key = f"product_lookup_{fic_mis_date}"
            cache_data = cache.get(cache_key)
            if not cache_data:
                try:
                    products = Dim_Product.objects.filter(fic_mis_date=fic_mis_date).values(
                        'v_prod_code', 'v_prod_type', 'v_flow_type', 
                        'v_product_name', 'v_prod_type_desc', 
                        'v_party_type_code', 'v_product_splits'
                    )
                    product_info_lookup = {}
                    product_splits_lookup = {}
                    for prod in products:
                        code = prod['v_prod_code']
                        ptc = prod['v_party_type_code']
                        # Store first occurrence of product info based on v_prod_code
                        if code not in product_info_lookup:
                            product_info_lookup[code] = prod
                        # Map (v_prod_code, v_party_type_code) to v_product_splits
                        product_splits_lookup[(code, ptc)] = prod['v_product_splits']
                    cache_data = {
                        'product_info_lookup': product_info_lookup,
                        'product_splits_lookup': product_splits_lookup
                    }
                    cache.set(cache_key, cache_data, timeout=3600)
                    logger_message = f"Cached product data with {len(product_info_lookup)} entries"
                    logger.info(logger_message)
                    print(logger_message)
                    Log.objects.create(
                        function_name='populate_liquidity_gap_results_base',
                        log_level='INFO',
                        message=logger_message,
                        status='SUCCESS'
                    )
                except Exception as e:
                    error_message = f"Error fetching product data: {e}"
                    logger.error(error_message)
                    print(error_message)
                    Log.objects.create(
                        function_name='populate_liquidity_gap_results_base',
                        log_level='ERROR',
                        message=error_message,
                        detailed_error=traceback.format_exc(),
                        status='FAILURE'
                    )
                    return 0
            else:
                product_info_lookup = cache_data['product_info_lookup']
                product_splits_lookup = cache_data['product_splits_lookup']

            # Step 3: Aggregate cash flow data for each financial element, grouping by required fields
            financial_elements = ['n_total_cash_flow_amount', 'n_total_principal_payment', 'n_total_interest_payment']
            cashflow_data = {}
            for element in financial_elements:
                try:
                    cashflow_data[element] = list(
                        Aggregated_Prod_Cashflow_Base.objects.filter(
                            fic_mis_date=fic_mis_date,
                            process_name=process_name,
                            financial_element=element
                        ).values(
                            'v_prod_code', 'v_party_type_code', 'v_ccy_code', 'v_loan_type'
                        ).annotate(
                            **{f"bucket_{i+1}": Sum(f"bucket_{i+1}") for i in range(50)}
                        )
                    )
                    logger_message = f"Aggregated {len(cashflow_data[element])} records for {element}"
                    logger.info(logger_message)
                    print(logger_message)
                    Log.objects.create(
                        function_name='populate_liquidity_gap_results_base',
                        log_level='INFO',
                        message=logger_message,
                        status='SUCCESS'
                    )
                except Exception as e:
                    error_message = f"Error aggregating {element}: {e}"
                    logger.error(error_message)
                    print(error_message)
                    Log.objects.create(
                        function_name='populate_liquidity_gap_results_base',
                        log_level='ERROR',
                        message=error_message,
                        detailed_error=traceback.format_exc(),
                        status='FAILURE'
                    )
                    return 0

            # Step 4: Combine aggregated data from different financial elements
            combined_data = {}
            for element, records in cashflow_data.items():
                for record in records:
                    key = (
                        record['v_prod_code'],
                        record.get('v_party_type_code'),
                        record['v_ccy_code'],
                        record['v_loan_type']
                    )
                    if key not in combined_data:
                        combined_data[key] = {
                            'v_prod_code': record['v_prod_code'],
                            'v_party_type_code': record.get('v_party_type_code'),
                            'v_ccy_code': record['v_ccy_code'],
                            'v_loan_type': record['v_loan_type'],
                            'buckets': {f'bucket_{i+1}': {'cash_flow': 0, 'principal': 0, 'interest': 0} for i in range(50)}
                        }
                    for i in range(50):
                        bucket_field = f'bucket_{i+1}'
                        if element == 'n_total_cash_flow_amount':
                            combined_data[key]['buckets'][bucket_field]['cash_flow'] = record.get(bucket_field, 0)
                        elif element == 'n_total_principal_payment':
                            combined_data[key]['buckets'][bucket_field]['principal'] = record.get(bucket_field, 0)
                        elif element == 'n_total_interest_payment':
                            combined_data[key]['buckets'][bucket_field]['interest'] = record.get(bucket_field, 0)

            # Step 5: Fetch the first 4 unique time buckets for the process
            try:
                time_buckets = TimeBucketMaster.objects.filter(process_name=process_name).order_by('bucket_number')
                if not time_buckets.exists():
                    logger_message = f"No time buckets for process: {process_name}"
                    logger.warning(logger_message)
                    print(logger_message)
                    Log.objects.create(
                        function_name='populate_liquidity_gap_results_base',
                        log_level='WARNING',
                        message=logger_message,
                        status='FAILURE'
                    )
                    return 0
                logger_message = f"Fetched {len(time_buckets)} time buckets"
                logger.info(logger_message)
                print(logger_message)
                Log.objects.create(
                    function_name='populate_liquidity_gap_results_base',
                    log_level='INFO',
                    message=logger_message,
                    status='SUCCESS'
                )
            except Exception as e:
                error_message = f"Error fetching time buckets: {e}"
                logger.error(error_message)
                print(error_message)
                Log.objects.create(
                    function_name='populate_liquidity_gap_results_base',
                    log_level='ERROR',
                    message=error_message,
                    detailed_error=traceback.format_exc(),
                    status='FAILURE'
                )
                return 0

            # Step 6: Process combined records and insert into LiquidityGapResultsBase
            for key, data in combined_data.items():
                product_code = data['v_prod_code']
                party_type_code = data['v_party_type_code']
                currency_code = data['v_ccy_code']
                loan_type = data['v_loan_type']

                # Retrieve product info based on v_prod_code
                product_info = product_info_lookup.get(product_code)
                if not product_info:
                    logger_message = f"No product info for {product_code}. Using defaults."
                    logger.warning(logger_message)
                    print(logger_message)
                    product_name = ""
                    prod_type_desc = ""
                    flow_type = "Inflow"  # Default assumption; adjust if needed
                else:
                    product_name = product_info.get('v_product_name', '')
                    prod_type_desc = product_info.get('v_prod_type_desc', '')
                    flow_type = product_info.get('v_flow_type', 'Inflow')

                # Retrieve v_product_splits based on both v_prod_code and v_party_type_code
                v_product_splits = product_splits_lookup.get((product_code, party_type_code))

                cumulative_inflow = 0
                cumulative_outflow = 0

                print(f"Processing {product_code} with party {party_type_code}")

                for idx, bucket in enumerate(time_buckets):
                    bucket_field = f'bucket_{idx+1}'
                    bucket_values = data['buckets'][bucket_field]
                    inflows = bucket_values['cash_flow'] if flow_type == 'Inflow' else 0
                    outflows = bucket_values['cash_flow'] if flow_type == 'Outflow' else 0
                    net_liquidity_gap = inflows - outflows

                    if flow_type == 'Inflow':
                        cumulative_inflow += inflows
                    elif flow_type == 'Outflow':
                        cumulative_outflow += outflows
                    cumulative_gap = cumulative_inflow - cumulative_outflow

                    # Duplicate check considers v_product_splits to separate party types
                    if LiquidityGapResultsBase.objects.filter(
                        fic_mis_date=fic_mis_date,
                        process_name=process_name,
                        v_prod_code=product_code,
                        v_ccy_code=currency_code,
                        bucket_start_date=bucket.start_date,
                        bucket_end_date=bucket.end_date,
                        bucket_number=bucket.bucket_number,
                        v_product_splits=v_product_splits
                    ).exists():
                        print(f"Skipping duplicate for {product_code}, party {party_type_code}, bucket {bucket.bucket_number}")
                        continue

                    try:
                        LiquidityGapResultsBase.objects.create(
                            fic_mis_date=fic_mis_date,
                            process_name=process_name,
                            account_type=flow_type,
                            v_product_name=product_name,
                            v_prod_code=product_code,
                            v_ccy_code=currency_code,
                            v_prod_type=product_info.get('v_prod_type', '') if product_info else '',
                            v_prod_type_desc=prod_type_desc,
                            v_loan_type=loan_type,
                            v_product_splits=v_product_splits,
                            n_total_cash_flow_amount=bucket_values['cash_flow'],
                            n_total_principal_payment=bucket_values['principal'],
                            n_total_interest_payment=bucket_values['interest'],
                            bucket_start_date=bucket.start_date,
                            bucket_end_date=bucket.end_date,
                            bucket_number=bucket.bucket_number,
                            inflows=inflows,
                            outflows=outflows,
                            net_liquidity_gap=net_liquidity_gap,
                            cumulative_gap=cumulative_gap
                        )
                        logger_message = f"Inserted record for {product_code}, party {party_type_code}, bucket {bucket.bucket_number}"
                        logger.info(logger_message)
                        print(logger_message)
                        # Log.objects.create(
                        #     function_name='populate_liquidity_gap_results_base',
                        #     log_level='INFO',
                        #     message=logger_message,
                        #     status='SUCCESS'
                        # )
                    except Exception as e:
                        error_message = f"Insert error for {product_code}, party {party_type_code}, bucket {bucket.bucket_number}: {e}"
                        logger.error(error_message)
                        print(error_message)
                        Log.objects.create(
                            function_name='populate_liquidity_gap_results_base',
                            log_level='ERROR',
                            message=error_message,
                            detailed_error=traceback.format_exc(),
                            status='FAILURE'
                        )

    except Exception as e:
        error_message = f"Population error: {e}"
        logger.error(error_message)
        print(error_message)
        Log.objects.create(
            function_name='populate_liquidity_gap_results_base',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        return 0

    logger_message = f"Liquidity Gap Results populated for {fic_mis_date}, {process_name}"
    logger.info(logger_message)
    print(logger_message)
    Log.objects.create(
        function_name='populate_liquidity_gap_results_base',
        log_level='INFO',
        message=logger_message,
        status='SUCCESS'
    )
    return 1






# from django.db.models import Sum
# from django.db import transaction
# from django.core.cache import cache
# from ..models import Aggregated_Prod_Cashflow_Base, TimeBucketMaster, Dim_Product, LiquidityGapResultsBase
# import logging

# logger = logging.getLogger(__name__)

# def populate_liquidity_gap_results_base(fic_mis_date, process_name):
#     """
#     Fetches aggregated data from Aggregated_Prod_Cashflow_Base, groups by product and party type,
#     retrieves product details based on v_prod_code and v_product_splits based on both v_prod_code and v_party_type_code,
#     then stores separated results in LiquidityGapResultsBase.
#     If no matching product info is found, uses default values and continues processing.
#     """
#     try:
#         with transaction.atomic():
#             # Step 1: Delete existing records
#             deleted_count = LiquidityGapResultsBase.objects.filter(
#                 fic_mis_date=fic_mis_date, process_name=process_name
#             ).delete()[0]
#             logger.info(f"Deleted {deleted_count} records for {fic_mis_date}, {process_name}")
#             print(f"Deleted {deleted_count} records for {fic_mis_date}, {process_name}")

#             # Step 2: Fetch and cache product data with party type info
#             cache_key = f"product_lookup_{fic_mis_date}"
#             cache_data = cache.get(cache_key)
#             if not cache_data:
#                 try:
#                     products = Dim_Product.objects.filter(fic_mis_date=fic_mis_date).values(
#                         'v_prod_code', 'v_prod_type', 'v_flow_type', 
#                         'v_product_name', 'v_prod_type_desc', 
#                         'v_party_type_code', 'v_product_splits'
#                     )
#                     product_info_lookup = {}
#                     product_splits_lookup = {}
#                     for prod in products:
#                         code = prod['v_prod_code']
#                         ptc = prod['v_party_type_code']
#                         # Store first occurrence of product info based on v_prod_code
#                         if code not in product_info_lookup:
#                             product_info_lookup[code] = prod
#                         # Map (v_prod_code, v_party_type_code) to v_product_splits
#                         product_splits_lookup[(code, ptc)] = prod['v_product_splits']
#                     cache_data = {
#                         'product_info_lookup': product_info_lookup,
#                         'product_splits_lookup': product_splits_lookup
#                     }
#                     cache.set(cache_key, cache_data, timeout=3600)
#                     logger.info(f"Cached product data with {len(product_info_lookup)} entries")
#                     print(f"Cached product data with {len(product_info_lookup)} entries")
#                 except Exception as e:
#                     logger.error(f"Error fetching product data: {e}")
#                     print(f"Error fetching product data: {e}")
#                     return
#             else:
#                 product_info_lookup = cache_data['product_info_lookup']
#                 product_splits_lookup = cache_data['product_splits_lookup']

#             # Step 3: Aggregate cash flow data for each financial element, grouping by required fields
#             financial_elements = ['n_total_cash_flow_amount', 'n_total_principal_payment', 'n_total_interest_payment']
#             cashflow_data = {}
#             for element in financial_elements:
#                 try:
#                     cashflow_data[element] = list(
#                         Aggregated_Prod_Cashflow_Base.objects.filter(
#                             fic_mis_date=fic_mis_date,
#                             process_name=process_name,
#                             financial_element=element
#                         ).values(
#                             'v_prod_code', 'v_party_type_code', 'v_ccy_code', 'v_loan_type'
#                         ).annotate(
#                             **{f"bucket_{i+1}": Sum(f"bucket_{i+1}") for i in range(50)}
#                         )
#                     )
#                     logger.info(f"Aggregated {len(cashflow_data[element])} records for {element}")
#                     print(f"Aggregated {len(cashflow_data[element])} records for {element}")
#                 except Exception as e:
#                     logger.error(f"Error aggregating {element}: {e}")
#                     print(f"Error aggregating {element}: {e}")
#                     return

#             # Step 4: Combine aggregated data from different financial elements
#             combined_data = {}
#             for element, records in cashflow_data.items():
#                 for record in records:
#                     key = (
#                         record['v_prod_code'],
#                         record.get('v_party_type_code'),
#                         record['v_ccy_code'],
#                         record['v_loan_type']
#                     )
#                     if key not in combined_data:
#                         combined_data[key] = {
#                             'v_prod_code': record['v_prod_code'],
#                             'v_party_type_code': record.get('v_party_type_code'),
#                             'v_ccy_code': record['v_ccy_code'],
#                             'v_loan_type': record['v_loan_type'],
#                             'buckets': {f'bucket_{i+1}': {'cash_flow': 0, 'principal': 0, 'interest': 0} for i in range(50)}
#                         }
#                     for i in range(50):
#                         bucket_field = f'bucket_{i+1}'
#                         if element == 'n_total_cash_flow_amount':
#                             combined_data[key]['buckets'][bucket_field]['cash_flow'] = record.get(bucket_field, 0)
#                         elif element == 'n_total_principal_payment':
#                             combined_data[key]['buckets'][bucket_field]['principal'] = record.get(bucket_field, 0)
#                         elif element == 'n_total_interest_payment':
#                             combined_data[key]['buckets'][bucket_field]['interest'] = record.get(bucket_field, 0)

#             # Step 5: Fetch the first 4 unique time buckets for the process
#             try:
#                 time_buckets = TimeBucketMaster.objects.filter(process_name=process_name).order_by('bucket_number')
#                 if not time_buckets.exists():
#                     logger.warning(f"No time buckets for process: {process_name}")
#                     print(f"No time buckets for process: {process_name}")
#                     return
#                 print(f"Fetched {len(time_buckets)} time buckets")
#             except Exception as e:
#                 logger.error(f"Error fetching time buckets: {e}")
#                 print(f"Error fetching time buckets: {e}")
#                 return

#             # Step 6: Process combined records and insert into LiquidityGapResultsBase
#             for key, data in combined_data.items():
#                 product_code = data['v_prod_code']
#                 party_type_code = data['v_party_type_code']
#                 currency_code = data['v_ccy_code']
#                 loan_type = data['v_loan_type']

#                 # Retrieve product info based on v_prod_code
#                 product_info = product_info_lookup.get(product_code)
#                 if not product_info:
#                     logger.warning(f"No product info for {product_code}. Using defaults.")
#                     print(f"No product info for {product_code}. Using defaults.")
#                     product_name = ""
#                     prod_type_desc = ""
#                     flow_type = "Inflow"  # Default assumption; adjust if needed
#                 else:
#                     product_name = product_info.get('v_product_name', '')
#                     prod_type_desc = product_info.get('v_prod_type_desc', '')
#                     flow_type = product_info.get('v_flow_type', 'Inflow')

#                 # Retrieve v_product_splits based on both v_prod_code and v_party_type_code
#                 v_product_splits = product_splits_lookup.get((product_code, party_type_code))

#                 cumulative_inflow = 0
#                 cumulative_outflow = 0

#                 print(f"Processing {product_code} with party {party_type_code}")

#                 for idx, bucket in enumerate(time_buckets):
#                     bucket_field = f'bucket_{idx+1}'
#                     bucket_values = data['buckets'][bucket_field]
#                     inflows = bucket_values['cash_flow'] if flow_type == 'Inflow' else 0
#                     outflows = bucket_values['cash_flow'] if flow_type == 'Outflow' else 0
#                     net_liquidity_gap = inflows - outflows

#                     if flow_type == 'Inflow':
#                         cumulative_inflow += inflows
#                     elif flow_type == 'Outflow':
#                         cumulative_outflow += outflows
#                     cumulative_gap = cumulative_inflow - cumulative_outflow

#                     # Duplicate check considers v_product_splits to separate party types
#                     if LiquidityGapResultsBase.objects.filter(
#                         fic_mis_date=fic_mis_date,
#                         process_name=process_name,
#                         v_prod_code=product_code,
#                         v_ccy_code=currency_code,
#                         bucket_start_date=bucket.start_date,
#                         bucket_end_date=bucket.end_date,
#                         bucket_number=bucket.bucket_number,
#                         v_product_splits=v_product_splits
#                     ).exists():
#                         print(f"Skipping duplicate for {product_code}, party {party_type_code}, bucket {bucket.bucket_number}")
#                         continue

#                     try:
#                         LiquidityGapResultsBase.objects.create(
#                             fic_mis_date=fic_mis_date,
#                             process_name=process_name,
#                             account_type=flow_type,
#                             v_product_name=product_name,
#                             v_prod_code=product_code,
#                             v_ccy_code=currency_code,
#                             v_prod_type=product_info.get('v_prod_type', '') if product_info else '',
#                             v_prod_type_desc=prod_type_desc,
#                             v_loan_type=loan_type,
#                             v_product_splits=v_product_splits,
#                             n_total_cash_flow_amount=bucket_values['cash_flow'],
#                             n_total_principal_payment=bucket_values['principal'],
#                             n_total_interest_payment=bucket_values['interest'],
#                             bucket_start_date=bucket.start_date,
#                             bucket_end_date=bucket.end_date,
#                             bucket_number=bucket.bucket_number,
#                             inflows=inflows,
#                             outflows=outflows,
#                             net_liquidity_gap=net_liquidity_gap,
#                             cumulative_gap=cumulative_gap
#                         )
#                         logger.info(f"Inserted record for {product_code}, party {party_type_code}, bucket {bucket.bucket_number}")
#                     except Exception as e:
#                         logger.error(f"Insert error for {product_code}, party {party_type_code}, bucket {bucket.bucket_number}: {e}")
#                         print(f"Insert error for {product_code}, party {party_type_code}, bucket {bucket.bucket_number}: {e}")

#     except Exception as e:
#         logger.error(f"Population error: {e}")
#         print(f"Population error: {e}")

#     logger.info(f"Liquidity Gap Results populated for {fic_mis_date}, {process_name}")
#     print(f"Liquidity Gap Results populated for {fic_mis_date}, {process_name}")

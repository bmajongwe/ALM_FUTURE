from django.db.models import Sum
from django.db import transaction
from django.core.cache import cache
from ..models import Aggregated_Prod_Cashflow_Base, TimeBucketMaster, Dim_Product, LiquidityGapResultsBase
import logging

logger = logging.getLogger(__name__)

def populate_liquidity_gap_results_base(fic_mis_date, process_name):
    """
    This function fetches aggregated data from Aggregated_Prod_Cashflow_Base,
    determines inflows and outflows based on v_flow_type from Dim_Product,
    and stores the results in LiquidityGapResultsBase with only unique bucket date ranges.
    """

    try:
        # Step 1: Start an atomic transaction to ensure deletion and insertion are handled together
        with transaction.atomic():
            # Delete existing records for the same fic_mis_date and process_name
            deleted_count = LiquidityGapResultsBase.objects.filter(fic_mis_date=fic_mis_date, process_name=process_name).delete()[0]
            logger.info(f"Deleted {deleted_count} existing records for fic_mis_date: {fic_mis_date} and process_name: {process_name}")
            print(f"Deleted {deleted_count} existing records for fic_mis_date: {fic_mis_date} and process_name: {process_name}")

            # Step 2: Fetch product data from Dim_Product and cache it for faster lookup
            cache_key = f"product_lookup_{fic_mis_date}"
            product_lookup = cache.get(cache_key)
            if not product_lookup:
                try:
                    product_data = Dim_Product.objects.values('v_prod_code', 'v_prod_type', 'v_flow_type', 'v_product_name', 'v_prod_type_desc')
                    product_lookup = {prod['v_prod_code']: prod for prod in product_data}
                    cache.set(cache_key, product_lookup, timeout=3600)  # Cache for 1 hour
                    logger.info(f"Fetched and cached product data from Dim_Product: {len(product_lookup)} products")
                    print(f"Fetched and cached product data from Dim_Product: {len(product_lookup)} products")
                except Exception as e:
                    logger.error(f"Error fetching product data from Dim_Product: {e}")
                    print(f"Error fetching product data from Dim_Product: {e}")
                    return

            # Step 3: Fetch and aggregate cash flow data for each financial element type
            financial_elements = ['n_total_cash_flow_amount', 'n_total_principal_payment', 'n_total_interest_payment']
            cashflow_data = {}

            for element in financial_elements:
                try:
                    cashflow_data[element] = Aggregated_Prod_Cashflow_Base.objects.filter(
                        fic_mis_date=fic_mis_date, process_name=process_name, financial_element=element
                    ).values('v_prod_code', 'v_ccy_code', 'v_loan_type').annotate(
                        **{f"bucket_{i+1}": Sum(f"bucket_{i+1}") for i in range(50)}
                    )
                    logger.info(f"Fetched and aggregated cashflow data for financial element {element}")
                    print(f"Fetched and aggregated cashflow data for financial element {element}, records: {len(cashflow_data[element])}")
                except Exception as e:
                    logger.error(f"Error fetching cashflow data for financial element {element}: {e}")
                    print(f"Error fetching cashflow data for financial element {element}: {e}")
                    return

            # Step 4: Fetch the first 4 unique time buckets from TimeBucketMaster for the given process
            try:
                time_buckets = TimeBucketMaster.objects.filter(process_name=process_name).order_by('bucket_number')[:4]
                if not time_buckets.exists():
                    logger.warning(f"No time buckets found for process: {process_name}")
                    print(f"No time buckets found for process: {process_name}")
                    return
                logger.info(f"Fetched time buckets for process: {process_name}")
                print(f"Fetched {len(time_buckets)} time buckets for process: {process_name}")
            except Exception as e:
                logger.error(f"Error fetching time bucket data: {e}")
                print(f"Error fetching time bucket data: {e}")
                return

            # Step 5: Process and insert data into LiquidityGapResultsBase with unique bucket ranges
            for grouped_cashflow in cashflow_data.values():
                for cashflow in grouped_cashflow:
                    product_code = cashflow['v_prod_code']
                    currency_code = cashflow['v_ccy_code']
                    loan_type = cashflow['v_loan_type']

                    # Fetch product details from the lookup dictionary
                    product_info = product_lookup.get(product_code)
                    if not product_info:
                        logger.warning(f"No product info found for product code: {product_code}. Skipping.")
                        print(f"No product info found for product code: {product_code}. Skipping.")
                        continue

                    # Fetch product-specific fields from Dim_Product
                    product_name = product_info.get('v_product_name')
                    prod_type_desc = product_info.get('v_prod_type_desc')
                    flow_type = product_info['v_flow_type']  # Use this directly for inflow/outflow classification

                    # Initialize cumulative inflows and outflows
                    cumulative_inflow = 0
                    cumulative_outflow = 0

                    print(f"Processing product code: {product_code}, currency code: {currency_code}, loan type: {loan_type}")

                    # Iterate over the unique 4 time buckets to populate records
                    for idx, bucket in enumerate(time_buckets):
                        inflows = cashflow.get(f'bucket_{idx+1}', 0) if flow_type == 'Inflow' else 0
                        outflows = cashflow.get(f'bucket_{idx+1}', 0) if flow_type == 'Outflow' else 0
                        net_liquidity_gap = inflows - outflows

                        # Update cumulative inflow or outflow separately
                        if flow_type == 'Inflow':
                            cumulative_inflow += inflows
                        elif flow_type == 'Outflow':
                            cumulative_outflow += outflows

                        cumulative_gap = cumulative_inflow - cumulative_outflow

                        # Check if a record with the same combination exists to avoid duplication
                        if LiquidityGapResultsBase.objects.filter(
                            fic_mis_date=fic_mis_date,
                            process_name=process_name,
                            v_prod_code=product_code,
                            v_ccy_code=currency_code,
                            bucket_start_date=bucket.start_date,
                            bucket_end_date=bucket.end_date,
                            bucket_number=bucket.bucket_number
                        ).exists():
                            print(f"Skipping duplicate entry for product {product_code}, bucket {bucket.bucket_number}")
                            continue

                        # Insert data into LiquidityGapResultsBase for this unique bucket range
                        try:
                            LiquidityGapResultsBase.objects.create(
                                fic_mis_date=fic_mis_date,
                                process_name=process_name,
                                account_type=flow_type,
                                v_product_name=product_name,
                                v_prod_code=product_code,
                                v_ccy_code=currency_code,
                                v_prod_type=product_info.get('v_prod_type', ''),
                                v_prod_type_desc=prod_type_desc,
                                v_loan_type=loan_type,
                                n_total_cash_flow_amount=cashflow.get(f'bucket_{idx+1}', 0),
                                n_total_principal_payment=next((item[f'bucket_{idx+1}'] for item in cashflow_data['n_total_principal_payment'] if item['v_prod_code'] == product_code), 0),
                                n_total_interest_payment=next((item[f'bucket_{idx+1}'] for item in cashflow_data['n_total_interest_payment'] if item['v_prod_code'] == product_code), 0),
                                bucket_start_date=bucket.start_date,
                                bucket_end_date=bucket.end_date,
                                bucket_number=bucket.bucket_number,
                                inflows=inflows,
                                outflows=outflows,
                                net_liquidity_gap=net_liquidity_gap,
                                cumulative_gap=cumulative_gap
                            )
                            logger.info(f"Inserted result for product {product_code}, bucket {bucket.bucket_number}")
                            print(f"Inserted result for product {product_code}, bucket {bucket.bucket_number}")
                        except Exception as e:
                            logger.error(f"Error inserting liquidity gap result for product {product_code}, bucket {bucket.bucket_number}: {e}")
                            print(f"Error inserting liquidity gap result for product {product_code}, bucket {bucket.bucket_number}: {e}")

    except Exception as e:
        logger.error(f"Error during population of liquidity gap results: {e}")
        print(f"Error during population of liquidity gap results: {e}")

    logger.info(f"Liquidity Gap Results populated for fic_mis_date {fic_mis_date} and process {process_name}")
    print(f"Liquidity Gap Results populated for fic_mis_date {fic_mis_date} and process {process_name}")

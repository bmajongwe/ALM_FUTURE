from django.db import transaction
from django.db.models import Max
from ..models import *
import traceback

def get_party_type_map():
    """
    Retrieve the party type mappings from the PartyTypeMapping table.
    Raises an exception if no records are found, forcing users to populate
    the table first.
    """
    mappings = PartyTypeMapping.objects.all()
    if not mappings.exists():
        raise ValueError("No records found in PartyTypeMapping. Please add them first.")
    # Build a dictionary: { '1000': 'Bank', '300': 'Company', ... }
    return {m.v_party_type_code: m.description for m in mappings}

def clean_string(s):
    """
    Trim leading and trailing spaces and replace '+' with '-' in the string if it's not None.
    """
    return s.strip().replace('+', '-') if s else s

def populate_dim_product(fic_mis_date):
    """
    Populate Dim_Product using records from Ldn_Financial_Instrument based on the provided fic_mis_date,
    and data from Ldn_Product_Master and Ldn_Common_Coa_Master based on their respective maximum fic_mis_date.
    Only distinct combinations of (v_prod_code, v_party_type_code) are inserted to handle multiple splits
    for the same product code, ensuring each (product code, party type) pair creates a record if it doesn't
    already exist. Party type mappings are fetched dynamically from PartyTypeMapping.
    """
    try:
        # Log start of function
        logger_message = f"Starting Dim_Product population for fic_mis_date: {fic_mis_date}."
        print(logger_message)
        Log.objects.create(
            function_name='populate_dim_product',
            log_level='INFO',
            message=logger_message,
            status='SUCCESS'
        )

        # Step 0: Delete existing records for this fic_mis_date in Dim_Product
        deleted_count = Dim_Product.objects.filter(fic_mis_date=fic_mis_date).delete()[0]
        logger_message = f"Deleted {deleted_count} existing records for fic_mis_date: {fic_mis_date}"
        print(logger_message)
        Log.objects.create(
            function_name='populate_dim_product',
            log_level='INFO',
            message=logger_message,
            status='SUCCESS'
        )

        # Step 1: Find the maximum fic_mis_date among Ldn_Product_Master and Ldn_Common_Coa_Master
        max_fic_mis_date_product_master = Ldn_Product_Master.objects.aggregate(Max('fic_mis_date'))['fic_mis_date__max']
        max_fic_mis_date_coa_master = Ldn_Common_Coa_Master.objects.aggregate(Max('fic_mis_date'))['fic_mis_date__max']
        max_fic_mis_date = max(max_fic_mis_date_product_master, max_fic_mis_date_coa_master)

        logger_message = (
            f"Using fic_mis_date: {fic_mis_date} for Ldn_Financial_Instrument.\n"
            f"Using maximum fic_mis_date: {max_fic_mis_date} for Ldn_Product_Master and Ldn_Common_Coa_Master."
        )
        print(logger_message)
        Log.objects.create(
            function_name='populate_dim_product',
            log_level='INFO',
            message=logger_message,
            status='SUCCESS'
        )

        # Step 2: Get all relevant financial instruments for this fic_mis_date
        financial_instruments = Ldn_Financial_Instrument.objects.filter(fic_mis_date=fic_mis_date)
        logger_message = f"Retrieved {financial_instruments.count()} records from Ldn_Financial_Instrument for fic_mis_date: {fic_mis_date}"
        print(logger_message)
        Log.objects.create(
            function_name='populate_dim_product',
            log_level='INFO',
            message=logger_message,
            status='SUCCESS'
        )

        # Step 3: Retrieve Ldn_Product_Master data for the product codes in the financial instruments
        product_master_data = Ldn_Product_Master.objects.filter(
            fic_mis_date=max_fic_mis_date,
            v_prod_code__in=financial_instruments.values_list('v_prod_code', flat=True)
        )
        logger_message = f"Retrieved {product_master_data.count()} records from Ldn_Product_Master for maximum fic_mis_date: {max_fic_mis_date}"
        print(logger_message)
        Log.objects.create(
            function_name='populate_dim_product',
            log_level='INFO',
            message=logger_message,
            status='SUCCESS'
        )

        # Step 4: Retrieve Ldn_Common_Coa_Master data for the same maximum fic_mis_date
        #         grouping by v_common_coa_code to get the latest record for each code
        latest_coa_master = (
            Ldn_Common_Coa_Master.objects.filter(fic_mis_date=max_fic_mis_date)
            .values('v_common_coa_code')
            .annotate(latest_fic_mis_date=Max('fic_mis_date'))
        )
        coa_master_data = Ldn_Common_Coa_Master.objects.filter(
            fic_mis_date__in=[item['latest_fic_mis_date'] for item in latest_coa_master],
            v_common_coa_code__in=[item['v_common_coa_code'] for item in latest_coa_master]
        )
        logger_message = f"Retrieved {coa_master_data.count()} records from Ldn_Common_Coa_Master for maximum fic_mis_date: {max_fic_mis_date}"
        print(logger_message)
        Log.objects.create(
            function_name='populate_dim_product',
            log_level='INFO',
            message=logger_message,
            status='SUCCESS'
        )

        # Step 5: Build lookup dictionaries for product and COA
        product_lookup = {p.v_prod_code: p for p in product_master_data}
        coa_lookup = {c.v_common_coa_code: c for c in coa_master_data}
        logger_message = f"Created lookup dictionaries with {len(product_lookup)} Product entries and {len(coa_lookup)} COA entries."
        print(logger_message)
        Log.objects.create(
            function_name='populate_dim_product',
            log_level='INFO',
            message=logger_message,
            status='SUCCESS'
        )

        # Define sets for categorizing account types
        asset_types = {'EARNINGASSETS', 'OTHERASSET'}
        liability_types = {'INTBEARINGLIABS', 'OTHERLIABS'}
        inflow_types = {'EARNINGASSETS', 'OTHERASSET'}
        outflow_types = {'INTBEARINGLIABS', 'OTHERLIABS'}

        # Fetch the party type mappings from the database
        party_type_map = get_party_type_map()

        new_records_count = 0
        with transaction.atomic():
            # Loop over each financial instrument and create Dim_Product entries
            for fin_inst in financial_instruments:
                product_record = product_lookup.get(fin_inst.v_prod_code)
                if not product_record:
                    continue

                coa_record = coa_lookup.get(product_record.v_common_coa_code)
                if coa_record and coa_record.v_account_type in asset_types:
                    v_balance_sheet_category = "Assets"
                    v_flow_type = "Inflow" if coa_record.v_account_type in inflow_types else "Outflow"
                elif coa_record and coa_record.v_account_type in liability_types:
                    v_balance_sheet_category = "Liabilities"
                    v_flow_type = "Outflow" if coa_record.v_account_type in outflow_types else "Inflow"
                else:
                    v_balance_sheet_category = product_record.v_balance_sheet_category
                    v_flow_type = None

                # Step 6: Find the matching Ldn_Customer_Info record using the latest available record up to current fic_mis_date
                customer_info = Ldn_Customer_Info.objects.filter(
                    v_party_id=fin_inst.v_cust_ref_code,
                    fic_mis_date__lte=fic_mis_date
                ).order_by('-fic_mis_date').first()

                if customer_info:
                    numeric_code = str(customer_info.v_party_type_code or '')
                    # Use the party_type_map dictionary to get the description (e.g., 'Bank')
                    v_product_splits_val = party_type_map.get(numeric_code, 'Other')
                    dim_product_party_type_code = numeric_code
                else:
                    # Fallback if no matching customer info
                    v_product_splits_val = 'Other'
                    dim_product_party_type_code = ''

                # Check if this combination already exists (same fic_mis_date, product code, party type)
                existing_dim = Dim_Product.objects.filter(
                    fic_mis_date=fic_mis_date,
                    v_prod_code=fin_inst.v_prod_code,
                    v_party_type_code=dim_product_party_type_code
                ).exists()
                if existing_dim:
                    logger_message = (
                        f"Skipping product code {fin_inst.v_prod_code}, "
                        f"party type code {dim_product_party_type_code} as it already exists "
                        f"for fic_mis_date {fic_mis_date}."
                    )
                    print(logger_message)
                    # Log.objects.create(
                    #     function_name='populate_dim_product',
                    #     log_level='INFO',
                    #     message=logger_message,
                    #     status='SUCCESS'
                    # )
                    continue

                # Create the new Dim_Product record with cleaned string values
                dim_product = Dim_Product(
                    v_prod_desc=clean_string(product_record.v_prod_desc),
                    v_prod_code=clean_string(product_record.v_prod_code),
                    fic_mis_date=fic_mis_date,
                    f_latest_record_indicator='Y',
                    v_prod_group_desc=clean_string(product_record.v_prod_group_desc),
                    v_prod_type=clean_string(product_record.v_prod_type),
                    n_prod_skey=product_record.id,
                    v_account_type=clean_string(coa_record.v_account_type) if coa_record else None,
                    v_balance_sheet_category=clean_string(v_balance_sheet_category),
                    v_balance_sheet_category_desc=clean_string(product_record.v_balance_sheet_category_desc),
                    v_prod_type_desc=clean_string(product_record.v_prod_type_desc),
                    v_product_name=clean_string(product_record.v_prod_name),
                    v_flow_type=clean_string(v_flow_type) if v_flow_type else None,
                    v_created_by='system',
                    v_last_modified_by='system',
                    v_product_splits=clean_string(v_product_splits_val),
                    v_party_type_code=clean_string(dim_product_party_type_code)
                )
                dim_product.save()
                new_records_count += 1
                logger_message = (
                    f"Inserted record for product code: {clean_string(product_record.v_prod_code)}, "
                    f"party type code: {clean_string(dim_product_party_type_code)}, "
                    f"flow type: {clean_string(v_flow_type) if v_flow_type else 'None'}."
                )
                print(logger_message)
                # Log.objects.create(
                #     function_name='populate_dim_product',
                #     log_level='INFO',
                #     message=logger_message,
                #     status='SUCCESS'
                # )

        logger_message = f"Dim_Product population completed. {new_records_count} new records inserted with f_latest_record_indicator='Y'."
        print(logger_message)
        Log.objects.create(
            function_name='populate_dim_product',
            log_level='INFO',
            message=logger_message,
            status='SUCCESS'
        )
        return 1

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"Error during Dim_Product population: {e}")
        Log.objects.create(
            function_name='populate_dim_product',
            log_level='ERROR',
            message=str(e),
            detailed_error=error_details,
            status='FAILURE'
        )
        return 0

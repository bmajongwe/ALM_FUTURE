from django.db import transaction
from django.db.models import Max
from ..models import Ldn_Product_Master, Ldn_Common_Coa_Master, Dim_Product, Ldn_Financial_Instrument

def populate_dim_product(fic_mis_date):
    """
    Populate Dim_Product using records from Ldn_Financial_Instrument based on the provided fic_mis_date,
    and data from Ldn_Product_Master and Ldn_Common_Coa_Master based on their respective maximum fic_mis_date.
    Only distinct v_prod_code values are inserted, and if a product code is already populated, it is skipped.
    """
    try:
        # Step 0: Delete existing records in Dim_Product for the given fic_mis_date
        deleted_count = Dim_Product.objects.filter(fic_mis_date=fic_mis_date).delete()[0]
        print(f"Deleted {deleted_count} existing records for fic_mis_date: {fic_mis_date}")

        # Step 1: Retrieve maximum fic_mis_date for Ldn_Product_Master and Ldn_Common_Coa_Master
        max_fic_mis_date_product_master = Ldn_Product_Master.objects.aggregate(Max('fic_mis_date'))['fic_mis_date__max']
        max_fic_mis_date_coa_master = Ldn_Common_Coa_Master.objects.aggregate(Max('fic_mis_date'))['fic_mis_date__max']
        max_fic_mis_date = max(max_fic_mis_date_product_master, max_fic_mis_date_coa_master)
        
        print(f"Using fic_mis_date: {fic_mis_date} for Ldn_Financial_Instrument.")
        print(f"Using maximum fic_mis_date: {max_fic_mis_date} for Ldn_Product_Master and Ldn_Common_Coa_Master.")

        # Step 2: Retrieve records from Ldn_Financial_Instrument using the provided fic_mis_date
        financial_instruments = Ldn_Financial_Instrument.objects.filter(fic_mis_date=fic_mis_date)
        print(f"Retrieved {financial_instruments.count()} records from Ldn_Financial_Instrument for fic_mis_date: {fic_mis_date}")

        # Step 3: Retrieve corresponding records from Ldn_Product_Master based on v_prod_code in financial_instruments
        product_master_data = Ldn_Product_Master.objects.filter(
            fic_mis_date=max_fic_mis_date,
            v_prod_code__in=financial_instruments.values_list('v_prod_code', flat=True)
        )
        print(f"Retrieved {product_master_data.count()} records from Ldn_Product_Master for maximum fic_mis_date: {max_fic_mis_date}")

        # Step 4: Retrieve corresponding records from Ldn_Common_Coa_Master based on v_common_coa_code
        latest_coa_master = (
            Ldn_Common_Coa_Master.objects.filter(fic_mis_date=max_fic_mis_date)
            .values('v_common_coa_code')
            .annotate(latest_fic_mis_date=Max('fic_mis_date'))
        )
        coa_master_data = Ldn_Common_Coa_Master.objects.filter(
            fic_mis_date__in=[item['latest_fic_mis_date'] for item in latest_coa_master],
            v_common_coa_code__in=[item['v_common_coa_code'] for item in latest_coa_master]
        )
        print(f"Retrieved {coa_master_data.count()} records from Ldn_Common_Coa_Master for maximum fic_mis_date: {max_fic_mis_date}")

        # Step 5: Create lookup dictionaries based on v_prod_code and v_common_coa_code
        product_lookup = {product.v_prod_code: product for product in product_master_data}
        coa_lookup = {coa.v_common_coa_code: coa for coa in coa_master_data}
        print(f"Created lookup dictionaries with {len(product_lookup)} Product entries and {len(coa_lookup)} COA entries.")

        # Define the asset, liability, inflow, and outflow categories
        asset_types = {'EARNINGASSETS', 'OTHERASSET'}
        liability_types = {'INTBEARINGLIABS', 'OTHERLIABS'}
        inflow_types = {'EARNINGASSETS', 'OTHERASSET'}  # Example inflow types
        outflow_types = {'INTBEARINGLIABS', 'OTHERLIABS'}  # Example outflow types

        # Step 6: Populate Dim_Product with f_latest_record_indicator='Y' for new records
        new_records_count = 0
        with transaction.atomic():
            for fin_inst in financial_instruments:
                # Check if the product code already exists in Dim_Product for the given fic_mis_date
                if Dim_Product.objects.filter(fic_mis_date=fic_mis_date, v_prod_code=fin_inst.v_prod_code).exists():
                    print(f"Skipping product code {fin_inst.v_prod_code} as it already exists for fic_mis_date {fic_mis_date}.")
                    continue  # Skip this product code if it already exists

                # Find the linked product and COA records
                product_record = product_lookup.get(fin_inst.v_prod_code)
                coa_record = coa_lookup.get(product_record.v_common_coa_code if product_record else None)

                if product_record:
                    # Determine v_balance_sheet_category and v_flow_type based on v_account_type
                    if coa_record and coa_record.v_account_type in asset_types:
                        v_balance_sheet_category = "Assets"
                        v_flow_type = "Inflow" if coa_record.v_account_type in inflow_types else "Outflow"
                    elif coa_record and coa_record.v_account_type in liability_types:
                        v_balance_sheet_category = "Liabilities"
                        v_flow_type = "Outflow" if coa_record.v_account_type in outflow_types else "Inflow"
                    else:
                        v_balance_sheet_category = product_record.v_balance_sheet_category  # Default to value in product_record
                        v_flow_type = None  # Set to None or a default value if needed

                    # Prepare the Dim_Product instance
                    dim_product = Dim_Product(
                        v_prod_desc=product_record.v_prod_desc,
                        v_prod_code=product_record.v_prod_code,
                        fic_mis_date=fic_mis_date,  # Use fic_mis_date from Financial Instrument data
                        f_latest_record_indicator='Y',  # Mark new records as latest
                        v_prod_group_desc=product_record.v_prod_group_desc,
                        v_prod_type=product_record.v_prod_type,
                        n_prod_skey=product_record.id,  # Using the primary key as the surrogate key
                        v_account_type=coa_record.v_account_type if coa_record else None,
                        v_balance_sheet_category=v_balance_sheet_category,  # Set based on v_account_type
                        v_balance_sheet_category_desc=product_record.v_balance_sheet_category_desc,
                        v_prod_type_desc=product_record.v_prod_type_desc,
                        v_product_name=product_record.v_prod_name,
                        v_flow_type=v_flow_type,  # Set flow type based on logic
                        v_created_by='system',  # Default user for creation
                        v_last_modified_by='system'  # Default user for modification
                    )
                    
                    # Save the Dim_Product instance
                    dim_product.save()
                    new_records_count += 1
                    print(f"Inserted record for product code: {product_record.v_prod_code} with f_latest_record_indicator='Y' and flow type '{v_flow_type}'.")

        print(f"Dim_Product population completed. {new_records_count} new records inserted with f_latest_record_indicator='Y'.")

    except Exception as e:
        print(f"Error during Dim_Product population: {e}")

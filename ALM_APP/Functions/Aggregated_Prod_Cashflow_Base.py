from django.db.models import Sum
from ..models import *
import traceback

def aggregate_by_prod_code( process_name, fic_mis_date):
    """
    This function groups data from AggregatedCashflowByBuckets by v_prod_code,
    sums the bucket values, and stores the result in Aggregated_Prod_Cashflow_Base.
    """

    inserted_records = 0
    try:
        # Step 1: Delete any existing records in Aggregated_Prod_Cashflow_Base for the same fic_mis_date and process_name
        deleted_count = Aggregated_Prod_Cashflow_Base.objects.filter(fic_mis_date=fic_mis_date, process_name=process_name).delete()[0]
        logger_message = f"Deleted {deleted_count} existing records for fic_mis_date: {fic_mis_date} and process_name: {process_name}"
        print(logger_message)
        Log.objects.create(
            function_name='aggregate_by_prod_code',
            log_level='INFO',
            message=logger_message,
            status='SUCCESS'
        )

        # Step 2: Fetch all records from AggregatedCashflowByBuckets for the given fic_mis_date and process_name
        cashflow_buckets = AggregatedCashflowByBuckets.objects.filter(fic_mis_date=fic_mis_date, process_name=process_name)

        if not cashflow_buckets.exists():
            logger_message = f"No cashflows found for fic_mis_date: {fic_mis_date} and process_name: {process_name}"
            print(logger_message)
            Log.objects.create(
                function_name='aggregate_by_prod_code',
                log_level='INFO',
                message=logger_message,
                status='SUCCESS'
            )
            return 0

        # Step 3: Group the data by v_prod_code and sum the bucket values
        grouped_data = cashflow_buckets.values('v_prod_code', 'v_ccy_code', 'v_loan_type', 'v_party_type_code', 'financial_element').annotate(
            **{f'bucket_{i}': Sum(f'bucket_{i}') for i in range(1, 51)}
        )

        # Step 4: Insert the aggregated data into Aggregated_Prod_Cashflow_Base
        for record in grouped_data:
            try:
                # Get the corresponding AggregatedCashflowByBucket and TimeBucketMaster record
                cashflow_by_bucket = AggregatedCashflowByBuckets.objects.filter(
                    v_prod_code=record['v_prod_code'],
                    fic_mis_date=fic_mis_date,
                    process_name=process_name,
                    v_loan_type=record['v_loan_type'],
                    v_party_type_code=record['v_party_type_code'],
                    financial_element=record['financial_element']
                ).first()

                time_bucket_master = TimeBucketMaster.objects.filter(
                    process_name=process_name
                ).first()

                Aggregated_Prod_Cashflow_Base.objects.create(
                    fic_mis_date=fic_mis_date,
                    process_name=process_name,
                    v_prod_code=record['v_prod_code'],
                    v_ccy_code=record['v_ccy_code'],
                    v_loan_type=record['v_loan_type'],
                    v_party_type_code=record['v_party_type_code'],
                    financial_element=record['financial_element'],
                    cashflow_by_bucket=cashflow_by_bucket,  # Link to AggregatedCashflowByBucket
                    time_bucket_master=time_bucket_master,  # Link to TimeBucketMaster
                    **{f'bucket_{i}': record.get(f'bucket_{i}', 0) for i in range(1, 51)}
                )
                inserted_records += 1
            except Exception as e:
                error_message = f"Error inserting record for v_prod_code: {record['v_prod_code']}, Error: {str(e)}"
                print(error_message)
                Log.objects.create(
                    function_name='aggregate_by_prod_code',
                    log_level='ERROR',
                    message=error_message,
                    detailed_error=traceback.format_exc(),
                    status='FAILURE'
                )

        logger_message = f"Successfully aggregated cashflows by product code for process '{process_name}' and fic_mis_date {fic_mis_date}. Inserted {inserted_records} records."
        print(logger_message)
        Log.objects.create(
            function_name='aggregate_by_prod_code',
            log_level='INFO',
            message=logger_message,
            status='SUCCESS'
        )
        return 1

    except TypeError as e:
        error_message = f"Error executing aggregate_by_prod_code: {str(e)}"
        print(error_message)
        Log.objects.create(
            function_name='aggregate_by_prod_code',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        return 0

    except Exception as e:
        error_message = f"Error during aggregation for fic_mis_date {fic_mis_date} and process_name {process_name}: {str(e)}"
        print(error_message)
        Log.objects.create(
            function_name='aggregate_by_prod_code',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        return 0






# from django.db.models import Sum
# from ..models import *

# def aggregate_by_prod_code(fic_mis_date, process_name):
#     """
#     This function groups data from AggregatedCashflowByBuckets by v_prod_code,
#     sums the bucket values, and stores the result in Aggregated_Prod_Cashflow_Base.
#     """

#     try:
#         # Step 1: Delete any existing records in Aggregated_Prod_Cashflow_Base for the same fic_mis_date and process_name
#         Aggregated_Prod_Cashflow_Base.objects.filter(fic_mis_date=fic_mis_date, process_name=process_name).delete()
#         print(f"Deleted existing records for fic_mis_date: {fic_mis_date} and process_name: {process_name}")

#         # Step 2: Fetch all records from AggregatedCashflowByBuckets for the given fic_mis_date and process_name
#         cashflow_buckets = AggregatedCashflowByBuckets.objects.filter(fic_mis_date=fic_mis_date, process_name=process_name)

#         if not cashflow_buckets.exists():
#             print(f"No cashflows found for fic_mis_date: {fic_mis_date} and process_name: {process_name}")
#             return

#         # Step 3: Group the data by v_prod_code and sum the bucket values
#         grouped_data = cashflow_buckets.values('v_prod_code', 'v_ccy_code', 'v_loan_type', 'v_party_type_code','financial_element').annotate(
#             bucket_1=Sum('bucket_1'),
#             bucket_2=Sum('bucket_2'),
#             bucket_3=Sum('bucket_3'),
#             bucket_4=Sum('bucket_4'),
#             bucket_5=Sum('bucket_5'),
#             bucket_6=Sum('bucket_6'),
#             bucket_7=Sum('bucket_7'),
#             bucket_8=Sum('bucket_8'),
#             bucket_9=Sum('bucket_9'),
#             bucket_10=Sum('bucket_10'),
#             bucket_11=Sum('bucket_11'),
#             bucket_12=Sum('bucket_12'),
#             bucket_13=Sum('bucket_13'),
#             bucket_14=Sum('bucket_14'),
#             bucket_15=Sum('bucket_15'),
#             bucket_16=Sum('bucket_16'),
#             bucket_17=Sum('bucket_17'),
#             bucket_18=Sum('bucket_18'),
#             bucket_19=Sum('bucket_19'),
#             bucket_20=Sum('bucket_20'),
#             bucket_21=Sum('bucket_21'),
#             bucket_22=Sum('bucket_22'),
#             bucket_23=Sum('bucket_23'),
#             bucket_24=Sum('bucket_24'),
#             bucket_25=Sum('bucket_25'),
#             bucket_26=Sum('bucket_26'),
#             bucket_27=Sum('bucket_27'),
#             bucket_28=Sum('bucket_28'),
#             bucket_29=Sum('bucket_29'),
#             bucket_30=Sum('bucket_30'),
#             bucket_31=Sum('bucket_31'),
#             bucket_32=Sum('bucket_32'),
#             bucket_33=Sum('bucket_33'),
#             bucket_34=Sum('bucket_34'),
#             bucket_35=Sum('bucket_35'),
#             bucket_36=Sum('bucket_36'),
#             bucket_37=Sum('bucket_37'),
#             bucket_38=Sum('bucket_38'),
#             bucket_39=Sum('bucket_39'),
#             bucket_40=Sum('bucket_40'),
#             bucket_41=Sum('bucket_41'),
#             bucket_42=Sum('bucket_42'),
#             bucket_43=Sum('bucket_43'),
#             bucket_44=Sum('bucket_44'),
#             bucket_45=Sum('bucket_45'),
#             bucket_46=Sum('bucket_46'),
#             bucket_47=Sum('bucket_47'),
#             bucket_48=Sum('bucket_48'),
#             bucket_49=Sum('bucket_49'),
#             bucket_50=Sum('bucket_50')
#         )

#         # Step 4: Insert the aggregated data into Aggregated_Prod_Cashflow_Base
#         for record in grouped_data:
#             try:
#                 # Get the corresponding AggregatedCashflowByBucket and TimeBucketMaster record
#                 cashflow_by_bucket = AggregatedCashflowByBuckets.objects.filter(
#                     v_prod_code=record['v_prod_code'],
#                     fic_mis_date=fic_mis_date,
#                     process_name=process_name,
#                     v_loan_type=record ['v_loan_type'],
#                     v_party_type_code=record['v_party_type_code'],
#                     financial_element=record['financial_element']
#                 ).first()

#                 time_bucket_master = TimeBucketMaster.objects.filter(
#                     process_name=process_name
#                 ).first()

#                 Aggregated_Prod_Cashflow_Base.objects.create(
#                     fic_mis_date=fic_mis_date,
#                     process_name=process_name,
#                     v_prod_code=record['v_prod_code'],
#                     v_ccy_code=record['v_ccy_code'],
#                     v_loan_type=record['v_loan_type'],
#                     v_party_type_code=record['v_party_type_code'],
#                     financial_element=record['financial_element'],
#                     cashflow_by_bucket=cashflow_by_bucket,  # Link to AggregatedCashflowByBucket
#                     time_bucket_master=time_bucket_master,  # Link to TimeBucketMaster
#                     bucket_1=record['bucket_1'],
#                     bucket_2=record['bucket_2'],
#                     bucket_3=record['bucket_3'],
#                     bucket_4=record['bucket_4'],
#                     bucket_5=record['bucket_5'],
#                     bucket_6=record['bucket_6'],
#                     bucket_7=record['bucket_7'],
#                     bucket_8=record['bucket_8'],
#                     bucket_9=record['bucket_9'],
#                     bucket_10=record['bucket_10'],
#                     bucket_11=record['bucket_11'],
#                     bucket_12=record['bucket_12'],
#                     bucket_13=record['bucket_13'],
#                     bucket_14=record['bucket_14'],
#                     bucket_15=record['bucket_15'],
#                     bucket_16=record['bucket_16'],
#                     bucket_17=record['bucket_17'],
#                     bucket_18=record['bucket_18'],
#                     bucket_19=record['bucket_19'],
#                     bucket_20=record['bucket_20'],
#                     bucket_21=record['bucket_21'],
#                     bucket_22=record['bucket_22'],
#                     bucket_23=record['bucket_23'],
#                     bucket_24=record['bucket_24'],
#                     bucket_25=record['bucket_25'],
#                     bucket_26=record['bucket_26'],
#                     bucket_27=record['bucket_27'],
#                     bucket_28=record['bucket_28'],
#                     bucket_29=record['bucket_29'],
#                     bucket_30=record['bucket_30'],
#                     bucket_31=record['bucket_31'],
#                     bucket_32=record['bucket_32'],
#                     bucket_33=record['bucket_33'],
#                     bucket_34=record['bucket_34'],
#                     bucket_35=record['bucket_35'],
#                     bucket_36=record['bucket_36'],
#                     bucket_37=record['bucket_37'],
#                     bucket_38=record['bucket_38'],
#                     bucket_39=record['bucket_39'],
#                     bucket_40=record['bucket_40'],
#                     bucket_41=record['bucket_41'],
#                     bucket_42=record['bucket_42'],
#                     bucket_43=record['bucket_43'],
#                     bucket_44=record['bucket_44'],
#                     bucket_45=record['bucket_45'],
#                     bucket_46=record['bucket_46'],
#                     bucket_47=record['bucket_47'],
#                     bucket_48=record['bucket_48'],
#                     bucket_49=record['bucket_49'],
#                     bucket_50=record['bucket_50']
#                 )
#             except Exception as e:
#                 print(f"Error inserting record for v_prod_code: {record['v_prod_code']}, Error: {e}")

#         print(f"Successfully aggregated cashflows by product code for process '{process_name}' and fic_mis_date {fic_mis_date}.")

#     except Exception as e:
#         print(f"Error during aggregation: {e}")

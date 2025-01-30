import logging
import traceback
from datetime import datetime
from django.core.exceptions import ObjectDoesNotExist
from ..models import Log, Process_Rn
from ALM_APP.Functions.Aggregated_Acc_level_cashflows import (
    calculate_behavioral_pattern_distribution,
    calculate_time_buckets_and_spread
)
from ALM_APP.Functions.Aggregated_Prod_Cashflow_Base import aggregate_by_prod_code
from ALM_APP.Functions.populate_dim import populate_dim_product
from ALM_APP.Functions.Dim_dates import populate_dim_dates_from_time_buckets
from ALM_APP.Functions.populate_liquidity_gap_results_base import populate_liquidity_gap_results_base
from ALM_APP.Functions.ldn_update import update_date
from ALM_APP.Functions.cashflow import project_cash_flows
from ALM_APP.Functions.aggregate_cashflows import aggregate_cashflows_to_product_level


logger = logging.getLogger(__name__)

def execute_alm_process_logic(process_name, fic_mis_date):
    """
    Executes the ALM process logic directly, replacing the view functionality.
    Accepts a process_name and fic_mis_date.
    After executing the main logic, runs additional functions in sequence.
    Logs to the Log table but does not integrate audit trails.
    """
    logger.info(f"Accessed execute_alm_process_logic with process_name='{process_name}', fic_mis_date='{fic_mis_date}'.")
    Log.objects.create(
        function_name='execute_alm_process_logic',
        log_level='INFO',
        message=f"Accessed execute_alm_process_logic with process_name='{process_name}', fic_mis_date='{fic_mis_date}'.",
        status='SUCCESS'
    )

    # Step 1: Validate date format
    try:
        execution_date = datetime.strptime(fic_mis_date, "%Y-%m-%d")
        logger.debug(f"Validated date format for fic_mis_date='{fic_mis_date}'.")
        Log.objects.create(
            function_name='execute_alm_process_logic',
            log_level='DEBUG',
            message=f"Validated date format for fic_mis_date='{fic_mis_date}'.",
            status='SUCCESS'
        )
    except ValueError as e:
        error_message = "Invalid date format. Please use YYYY-MM-DD."
        logger.error(error_message)
        Log.objects.create(
            function_name='execute_alm_process_logic',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        raise ValueError(error_message) from e

    # --- NEW STEP: Call your three functions first ---
    try:
        logger.debug("Starting update_date...")
        update_date(fic_mis_date)
        logger.debug("Completed update_date successfully.")
        Log.objects.create(
            function_name='execute_alm_process_logic',
            log_level='DEBUG',
            message=f"update_date finished for fic_mis_date='{fic_mis_date}'.",
            status='SUCCESS'
        )

        logger.debug("Starting project_cash_flows...")
        project_cash_flows(fic_mis_date)
        logger.debug("Completed project_cash_flows successfully.")
        Log.objects.create(
            function_name='execute_alm_process_logic',
            log_level='DEBUG',
            message=f"project_cash_flows finished for fic_mis_date='{fic_mis_date}'.",
            status='SUCCESS'
        )

        logger.debug("Starting aggregate_cashflows_to_product_level...")
        aggregate_cashflows_to_product_level(fic_mis_date)
        logger.debug("Completed aggregate_cashflows_to_product_level successfully.")
        Log.objects.create(
            function_name='execute_alm_process_logic',
            log_level='DEBUG',
            message=f"aggregate_cashflows_to_product_level finished for fic_mis_date='{fic_mis_date}'.",
            status='SUCCESS'
        )

        logger.info("All initial functions (update_date, project_cash_flows, aggregate_cashflows_to_product_level) executed successfully.")
        Log.objects.create(
            function_name='execute_alm_process_logic',
            log_level='INFO',
            message=(
                f"All initial functions executed successfully for fic_mis_date='{fic_mis_date}'."
            ),
            status='SUCCESS'
        )
    except Exception as e:
        error_message = f"Error in initial processing steps (update_date, project_cash_flows, aggregate_cashflows_to_product_level): {e}"
        logger.error(error_message)
        Log.objects.create(
            function_name='execute_alm_process_logic',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        raise RuntimeError(error_message) from e
    # --- END NEW STEP ---

    # Step 2: Fetch the process by process_name in Process_Rn
    try:
        process = Process_Rn.objects.get(process_name=process_name)
        logger.info(f"Fetched Process_Rn with name='{process_name}'. uses_behavioral_patterns={process.uses_behavioral_patterns}.")
        Log.objects.create(
            function_name='execute_alm_process_logic',
            log_level='INFO',
            message=(
                f"Fetched Process_Rn with name='{process_name}'. "
                f"uses_behavioral_patterns={process.uses_behavioral_patterns}."
            ),
            status='SUCCESS'
        )
    except ObjectDoesNotExist as e:
        error_message = f"Process with name '{process_name}' does not exist in Process_Rn."
        logger.error(error_message)
        Log.objects.create(
            function_name='execute_alm_process_logic',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        raise ValueError(error_message) from e

    # Step 3: Execute logic based on the process type
    try:
        if process.uses_behavioral_patterns:
            logger.debug(f"Process '{process_name}' uses behavioral patterns. Executing distribution.")
            Log.objects.create(
                function_name='execute_alm_process_logic',
                log_level='DEBUG',
                message=f"Process '{process_name}' uses behavioral patterns. Executing distribution.",
                status='SUCCESS'
            )
            calculate_behavioral_pattern_distribution(process.process_name, fic_mis_date)
        else:
            logger.debug(f"Process '{process_name}' does not use behavioral patterns. Executing time buckets and spread.")
            Log.objects.create(
                function_name='execute_alm_process_logic',
                log_level='DEBUG',
                message=f"Process '{process_name}' does not use behavioral patterns. Executing time buckets and spread.",
                status='SUCCESS'
            )
            calculate_time_buckets_and_spread(process.process_name, fic_mis_date)

        success_message = f"Process '{process.process_name}' main logic executed successfully for MIS date {fic_mis_date}."
        logger.info(success_message)
        Log.objects.create(
            function_name='execute_alm_process_logic',
            log_level='INFO',
            message=success_message,
            status='SUCCESS'
        )

        # Step 4: Additional steps
        try:
            aggregate_by_prod_code(process_name, fic_mis_date)
            logger.debug("Aggregated by product code successfully.")
            Log.objects.create(
                function_name='execute_alm_process_logic',
                log_level='DEBUG',
                message="Aggregated by product code successfully.",
                status='SUCCESS'
            )

            populate_dim_product(fic_mis_date)
            logger.debug("Populated dimension product successfully.")
            Log.objects.create(
                function_name='execute_alm_process_logic',
                log_level='DEBUG',
                message="Populated dimension product successfully.",
                status='SUCCESS'
            )

            populate_dim_dates_from_time_buckets(fic_mis_date)
            logger.debug("Populated dimension dates from time buckets successfully.")
            Log.objects.create(
                function_name='execute_alm_process_logic',
                log_level='DEBUG',
                message="Populated dimension dates from time buckets successfully.",
                status='SUCCESS'
            )

            populate_liquidity_gap_results_base(fic_mis_date, process_name)
            logger.debug("Populated liquidity gap results base successfully.")
            Log.objects.create(
                function_name='execute_alm_process_logic',
                log_level='DEBUG',
                message="Populated liquidity gap results base successfully.",
                status='SUCCESS'
            )

            logger.info(f"All additional steps executed successfully for process_name='{process_name}'.")
            Log.objects.create(
                function_name='execute_alm_process_logic',
                log_level='INFO',
                message=(
                    f"All additional steps executed successfully for process_name='{process_name}' "
                    f"and fic_mis_date='{fic_mis_date}'."
                ),
                status='SUCCESS'
            )
            return 1  # Indicates success

        except Exception as e:
            error_message = f"Error in additional processing steps for '{process_name}': {e}"
            logger.error(error_message)
            Log.objects.create(
                function_name='execute_alm_process_logic',
                log_level='ERROR',
                message=error_message,
                detailed_error=traceback.format_exc(),
                status='FAILURE'
            )
            raise RuntimeError(error_message) from e

    except Exception as e:
        error_message = f"Error executing main logic for process '{process_name}': {e}"
        logger.error(error_message)
        Log.objects.create(
            function_name='execute_alm_process_logic',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        raise RuntimeError(error_message) from e

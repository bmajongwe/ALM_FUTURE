from datetime import datetime
from django.core.exceptions import ObjectDoesNotExist
from ..models import *
from ALM_APP.Functions.Aggregated_Acc_level_cashflows import calculate_behavioral_pattern_distribution, calculate_time_buckets_and_spread

def execute_alm_process_logic(process_name, fic_mis_date):
    """
    Executes the ALM process logic directly, replacing the view functionality.
    Accepts a process_name and fic_mis_date.
    """
    try:
        # Validate the date format
        execution_date = datetime.strptime(fic_mis_date, "%Y-%m-%d")
    except ValueError as e:
        error_message = "Invalid date format. Please use YYYY-MM-DD."
        raise ValueError(error_message) from e

    # Fetch the process by process_name in Process_Rn
    try:
        process = Process_Rn.objects.get(process_name=process_name)
    except ObjectDoesNotExist as e:
        error_message = f"Process with name '{process_name}' does not exist in Process_Rn."
        raise ValueError(error_message) from e

    # Execute logic based on the process type
    try:
        if process.uses_behavioral_patterns:
            # Behavioral patterns logic
            calculate_behavioral_pattern_distribution(process.process_name, fic_mis_date)
        else:
            # Time buckets and spread logic
            calculate_time_buckets_and_spread(process.process_name, fic_mis_date)

        # Log success message
        print(f"Process '{process.process_name}' executed successfully for MIS date {fic_mis_date}.")
        return 1  # Indicates success
    except Exception as e:
        error_message = f"Error executing process '{process.process_name}': {e}"
        raise RuntimeError(error_message) from e

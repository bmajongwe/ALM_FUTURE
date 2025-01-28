from decimal import Decimal, InvalidOperation
import logging
import traceback
from django.db import transaction  # Import transaction for atomic operations
from django.utils import timezone  # Import timezone for datetime fields
from ..models import BehavioralPatternConfig, BehavioralPatternEntry, Log



logger = logging.getLogger(__name__)

def define_behavioral_pattern_from_form_data(request):
    """
    Processes the POST data from create_behavioral_pattern and defines a new
    BehavioralPatternConfig with its associated BehavioralPatternEntry objects.
    Logs all relevant actions to the Log table. Does not integrate audit trails.
    """
    logger.info("Accessed define_behavioral_pattern_from_form_data.")
    
    try:
        # Step 1: Retrieve POST parameters
        v_prod_type = request.POST.get('v_prod_type')
        description = request.POST.get('description')

        logger.debug(
            f"Received v_prod_type='{v_prod_type}', description='{description}' in POST data."
        )
        

        # Step 2: Validate mandatory fields
        if not v_prod_type:
            error_message = "Please provide a product type."
            logger.warning(error_message)
            Log.objects.create(
                function_name='define_behavioral_pattern_from_form_data',
                log_level='WARNING',
                message=error_message,
                status='SUCCESS'
            )
            return {'error': error_message}

        if not description:
            error_message = "Please provide a description."
            logger.warning(error_message)
            Log.objects.create(
                function_name='define_behavioral_pattern_from_form_data',
                log_level='WARNING',
                message=error_message,
                status='SUCCESS'
            )
            return {'error': error_message}

        # Step 3: Check uniqueness of v_prod_type
        if BehavioralPatternConfig.objects.filter(v_prod_type=v_prod_type).exists():
            error_message = f'A behavioral pattern for "{v_prod_type}" already exists.'
            logger.warning(error_message)
            
            return {'error': error_message}

        # Step 4: Retrieve arrays of tenors, multipliers, percentages
        tenors = request.POST.getlist('tenor[]')
        multipliers = request.POST.getlist('multiplier[]')
        percentages = request.POST.getlist('percentage[]')

        logger.debug(
            f"Retrieved {len(tenors)} tenors, {len(multipliers)} multipliers, "
            f"{len(percentages)} percentages."
        )
        

        if not tenors or not percentages or len(tenors) != len(percentages):
            error_message = "Please enter at least one behavioral pattern entry with matching tenors and percentages."
            logger.warning(error_message)
            Log.objects.create(
                function_name='define_behavioral_pattern_from_form_data',
                log_level='WARNING',
                message=error_message,
                status='SUCCESS'
            )
            return {'error': error_message}

        # Step 5: Validate and convert percentages to Decimal
        try:
            percentage_values = [Decimal(p) for p in percentages]
        except InvalidOperation:
            error_message = "Invalid percentage value entered."
            logger.error(error_message)
            Log.objects.create(
                function_name='define_behavioral_pattern_from_form_data',
                log_level='ERROR',
                message=error_message,
                detailed_error=traceback.format_exc(),
                status='FAILURE'
            )
            return {'error': error_message}

        # Step 6: Validate total percentage equals 100%
        total_percentage = sum(percentage_values)
        if total_percentage != Decimal('100.000'):
            error_message = f"The total percentage across all entries must equal 100%. Got {total_percentage}."
            logger.warning(error_message)
            
            return {'error': error_message}

        # Step 7: Save pattern and entries atomically
        try:
            with transaction.atomic():
                pattern_config = BehavioralPatternConfig(
                    v_prod_type=v_prod_type,
                    description=description,
                    created_by="System",
                    last_changed_by="System"
                )
                pattern_config.save()

                current_entries = 0
                for i in range(len(tenors)):
                    tenor = int(tenors[i])
                    multiplier = multipliers[i]
                    percentage = percentage_values[i]

                    current_entries += 1
                    BehavioralPatternEntry.objects.create(
                        pattern=pattern_config,
                        tenor=tenor,
                        multiplier=multiplier,
                        percentage=percentage,
                        order=current_entries
                    )

            logger.info(f"Behavioral pattern config created for v_prod_type='{v_prod_type}' with {current_entries} entries.")
            
        except Exception as e:
            error_message = f"An unexpected error occurred while saving pattern and entries: {str(e)}"
            logger.error(error_message)
            Log.objects.create(
                function_name='define_behavioral_pattern_from_form_data',
                log_level='ERROR',
                message=error_message,
                detailed_error=traceback.format_exc(),
                status='FAILURE'
            )
            return {'error': "An unexpected error occurred. Please try again."}

    except Exception as e:
        error_message = f"General Error: {str(e)}"
        logger.error(error_message)
        Log.objects.create(
            function_name='define_behavioral_pattern_from_form_data',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        return {'error': "An unexpected error occurred. Please try again."}

    # If everything goes well
    logger.info(f"Behavioral pattern created successfully for '{v_prod_type}'.")
    
    return {'success': True}



# Utility function for editing behavioral patterns
import logging
import traceback
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.utils import timezone

from ..models import (
    BehavioralPatternConfig,
    BehavioralPatternEntry,
    Log
)

logger = logging.getLogger(__name__)

def update_behavioral_pattern_from_form_data(request, pattern):
    """
    Updates an existing BehavioralPatternConfig (pattern) using POST data. Recreates
    its BehavioralPatternEntry objects. Logs all actions to the Log table (no audit trail).
    """
    logger.info(f"Accessed update_behavioral_pattern_from_form_data for pattern ID='{pattern.id}'.")
    

    try:
        # Step 1: Retrieve POST parameters
        v_prod_type = request.POST.get('v_prod_type')
        description = request.POST.get('description')

        logger.debug(
            f"Received v_prod_type='{v_prod_type}', description='{description}' "
            f"for pattern ID='{pattern.id}'."
        )
        

        # Step 2: Validate mandatory fields
        if not v_prod_type:
            error_message = "Please provide a product type."
            logger.warning(error_message)
            
            return {'error': error_message}
        
        if not description:
            error_message = "Please provide a description."
            logger.warning(error_message)
            
            return {'error': error_message}

        # Step 3: Ensure uniqueness of v_prod_type, excluding current pattern
        if BehavioralPatternConfig.objects.filter(v_prod_type=v_prod_type).exclude(id=pattern.id).exists():
            error_message = f'A behavioral pattern for "{v_prod_type}" already exists.'
            logger.warning(error_message)
            
            return {'error': error_message}

        # Step 4: Retrieve form data for entries
        tenors = request.POST.getlist('tenor[]')
        multipliers = request.POST.getlist('multiplier[]')
        percentages = request.POST.getlist('percentage[]')

        logger.debug(
            f"Retrieved {len(tenors)} tenors, {len(multipliers)} multipliers, "
            f"{len(percentages)} percentages for pattern ID='{pattern.id}'."
        )
        
        # Step 5: Validate entries
        if not tenors or not percentages or len(tenors) != len(percentages):
            error_message = "Please enter valid behavioral pattern entries."
            logger.warning(error_message)
            
            return {'error': error_message}

        # Step 6: Validate and convert percentages
        try:
            percentage_values = [Decimal(p) for p in percentages]
            total_percentage = sum(percentage_values)
            # Allow a small float rounding margin for equality with 100.0
            if not Decimal('99.999') <= total_percentage <= Decimal('100.001'):
                error_message = "The total percentage must equal 100%."
                logger.warning(error_message)
                
                return {'error': error_message}
        except InvalidOperation as e:
            error_message = "Invalid percentage value entered."
            logger.error(error_message)
            Log.objects.create(
                function_name='update_behavioral_pattern_from_form_data',
                log_level='ERROR',
                message=error_message,
                detailed_error=traceback.format_exc(),
                status='FAILURE'
            )
            return {'error': error_message}

        # Step 7: Atomically update pattern and recreate entries
        try:
            with transaction.atomic():
                # Update pattern details
                pattern.v_prod_type = v_prod_type
                pattern.description = description
                pattern.last_changed_date = timezone.now()
                pattern.last_changed_by = "System"  # Default
                pattern.save()

                # Delete existing entries
                deleted_count = pattern.entries.all().delete()
                logger.debug(
                    f"Deleted existing entries for pattern ID='{pattern.id}'. "
                    f"Count: {deleted_count}"
                )
                

                # Recreate entries
                current_entries = 0
                for i in range(len(tenors)):
                    current_entries += 1
                    BehavioralPatternEntry.objects.create(
                        pattern=pattern,
                        tenor=int(tenors[i]),
                        multiplier=multipliers[i],
                        percentage=percentage_values[i],
                        order=current_entries
                    )

                logger.info(
                    f"Updated BehavioralPatternConfig ID='{pattern.id}' with {current_entries} new entries."
                )
                

        except Exception as e:
            error_message = f"An unexpected error occurred while updating pattern ID='{pattern.id}': {str(e)}"
            logger.error(error_message)
            Log.objects.create(
                function_name='update_behavioral_pattern_from_form_data',
                log_level='ERROR',
                message=error_message,
                detailed_error=traceback.format_exc(),
                status='FAILURE'
            )
            return {'error': "An unexpected error occurred. Please try again."}

    except Exception as e:
        error_message = f"General Error while updating pattern ID='{pattern.id}': {str(e)}"
        logger.error(error_message)
        Log.objects.create(
            function_name='update_behavioral_pattern_from_form_data',
            log_level='ERROR',
            message=error_message,
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        return {'error': "An unexpected error occurred. Please try again."}

    logger.info(f"Behavioral pattern with ID='{pattern.id}' updated successfully.")
    
    return {'success': True}



# Utility function for deleting behavioral patterns
logger = logging.getLogger(__name__)

def delete_behavioral_pattern_by_id(id):
    """
    Utility function for deleting a BehavioralPatternConfig by its ID.
    Logs actions and errors to the Log table (no audit trail).
    """
    logger.info(f"Accessed delete_behavioral_pattern_by_id with ID='{id}'.")

    try:
        pattern = BehavioralPatternConfig.objects.get(id=id)
        logger.debug(f"Fetched BehavioralPatternConfig with ID='{id}' for deletion.")
        
        pattern.delete()
        logger.info(f"BehavioralPatternConfig with ID='{id}' deleted successfully.")
        
        return {'success': True}

    except BehavioralPatternConfig.DoesNotExist:
        error_message = f"Behavioral pattern with ID='{id}' not found."
        logger.warning(error_message)
        Log.objects.create(
            function_name='delete_behavioral_pattern_by_id',
            log_level='WARNING',
            message=error_message,
            status='SUCCESS'
        )
        return {'error': 'Behavioral pattern not found.'}

    except Exception as e:
        error_details = traceback.format_exc()
        error_message = f"An unexpected error occurred while deleting the pattern with ID='{id}': {str(e)}"
        logger.error(error_message)
        Log.objects.create(
            function_name='delete_behavioral_pattern_by_id',
            log_level='ERROR',
            message=error_message,
            detailed_error=error_details,
            status='FAILURE'
        )
        return {'error': 'An unexpected error occurred while deleting the pattern.'}



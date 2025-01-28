from User.models import AuditTrail
from ..models import ProductFilter, Process
from django.shortcuts import get_object_or_404
from django.db import transaction
import logging
import traceback
from django.shortcuts import get_object_or_404
from ..models import *



# Utility function to create or update a product filter
logger = logging.getLogger(__name__)

def create_or_update_filter(filter_id=None, data=None):
    """
    Creates or updates a ProductFilter instance. If filter_id is provided, updates the existing filter;
    otherwise, creates a new one. Integrates logging and audit trails for record-keeping.
    """
    if data is None:
        data = {}

    logger.info(f"Accessed create_or_update_filter with filter_id='{filter_id}' and data='{data}'.")
    Log.objects.create(
        function_name='create_or_update_filter',
        log_level='INFO',
        message=f"Accessed create_or_update_filter with filter_id='{filter_id}' and data='{data}'.",
        status='SUCCESS'
    )

    try:
        # Step 1: Fetch existing filter if filter_id is provided; otherwise create a new instance
        if filter_id:
            filter_instance = get_object_or_404(ProductFilter, id=filter_id)
            action = "update"
            logger.info(f"Fetched existing ProductFilter with ID='{filter_id}'.")
            Log.objects.create(
                function_name='create_or_update_filter',
                log_level='INFO',
                message=f"Fetched existing ProductFilter with ID='{filter_id}'.",
                status='SUCCESS'
            )
        else:
            filter_instance = ProductFilter()
            action = "create"
            logger.info("Creating a new ProductFilter instance.")
            Log.objects.create(
                function_name='create_or_update_filter',
                log_level='INFO',
                message="Creating a new ProductFilter instance.",
                status='SUCCESS'
            )

        # Step 2: Update the fields
        filter_instance.field_name = data.get('field_name')
        filter_instance.condition = data.get('condition')
        filter_instance.value = data.get('value')
        filter_instance.created_by = data.get('created_by', 'System')

        # Step 3: Save the instance
        filter_instance.save()
        logger.info(f"ProductFilter {action}d successfully with ID='{filter_instance.id}'.")
        Log.objects.create(
            function_name='create_or_update_filter',
            log_level='INFO',
            message=f"ProductFilter {action}d successfully with ID='{filter_instance.id}'.",
            status='SUCCESS'
        )

        # Step 4: Create an AuditTrail entry
        AuditTrail.objects.create(
            user=None,  # Adjust if you have a user context. For system updates, you may leave it as None
            user_name="",  # or data.get('user_name', '') if you have it in 'data'
            user_surname="",  # or data.get('user_surname', '')
            model_name="ProductFilter",
            action=action,
            object_id=str(filter_instance.id),
            change_description=f"{action.capitalize()}d ProductFilter with field_name='{filter_instance.field_name}', "
                               f"condition='{filter_instance.condition}', value='{filter_instance.value}'."
        )
        logger.info(f"AuditTrail entry created for ProductFilter ID='{filter_instance.id}'.")
        
        return filter_instance

    except Exception as e:
        error_details = traceback.format_exc()
        error_message = f"Error during create_or_update_filter: {str(e)}"
        logger.error(error_message)
        Log.objects.create(
            function_name='create_or_update_filter',
            log_level='ERROR',
            message=error_message,
            detailed_error=error_details,
            status='FAILURE'
        )
        return None





#####################################################################################
# Utility function to delete a filter


logger = logging.getLogger(__name__)

def delete_filter(filter_id):
    """
    Deletes a ProductFilter instance by its ID.
    Integrates logging and an audit trail to record the deletion.
    """
    logger.info(f"Accessed delete_filter with filter_id='{filter_id}'.")
    Log.objects.create(
        function_name='delete_filter',
        log_level='INFO',
        message=f"Accessed delete_filter for filter_id='{filter_id}'.",
        status='SUCCESS'
    )

    try:
        filter_instance = get_object_or_404(ProductFilter, id=filter_id)
        filter_id_str = str(filter_instance.id)
        logger.debug(f"Fetched ProductFilter with ID='{filter_id_str}' for deletion.")
        Log.objects.create(
            function_name='delete_filter',
            log_level='DEBUG',
            message=f"Fetched ProductFilter with ID='{filter_id_str}' for deletion.",
            status='SUCCESS'
        )

        filter_instance.delete()
        logger.info(f"Deleted ProductFilter with ID='{filter_id_str}'.")
        Log.objects.create(
            function_name='delete_filter',
            log_level='INFO',
            message=f"Deleted ProductFilter with ID='{filter_id_str}'.",
            status='SUCCESS'
        )

        # Create an AuditTrail entry for the deletion
        AuditTrail.objects.create(
            user=None,  # Adjust based on your user context if available
            user_name="",  # or data from user object if available
            user_surname="",
            model_name="ProductFilter",
            action="delete",
            object_id=filter_id_str,
            change_description=f"Deleted ProductFilter with ID {filter_id_str}."
        )
        logger.info(f"AuditTrail entry created for deleted ProductFilter ID='{filter_id_str}'.")

    except Exception as e:
        error_details = traceback.format_exc()
        error_message = f"Error deleting ProductFilter ID='{filter_id}': {e}"
        logger.error(error_message)
        Log.objects.create(
            function_name='delete_filter',
            log_level='ERROR',
            message=error_message,
            detailed_error=error_details,
            status='FAILURE'
        )
#####################################################################################################

# Utility function to create or update a process with transaction handling
@transaction.atomic
def create_or_update_process(process_id=None, data=None):
    if data is None:
        data = {}

    # Fetch existing process if ID is provided, otherwise create a new one
    process_instance = get_object_or_404(Process, id=process_id) if process_id else Process()

    # Set the name field
    process_instance.name = data.get('name')
    process_instance.save()

    # Update the filters associated with the process
    filter_ids = data.get('filters', [])
    process_instance.filters.set(ProductFilter.objects.filter(id__in=filter_ids))
    process_instance.save()

    return process_instance

# Utility function to delete a process
def delete_process(process_id):
    process_instance = get_object_or_404(Process, id=process_id)
    process_instance.delete()

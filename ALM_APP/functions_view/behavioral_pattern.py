from pyexpat.errors import messages
from django.shortcuts import get_object_or_404, redirect, render
from ALM_APP.Functions.behavioral_pattern_utils import *
from ALM_APP.models import *
from django.contrib.auth.decorators import login_required

from User.models import AuditTrail






@login_required
def create_behavioral_pattern(request):
    """
    View to create a behavioral pattern. Fetches the existing Time Bucket Definition
    (assuming only one is allowed) and distinct product types from Ldn_Product_Master.
    Integrates logging and audit trail to track user actions and any errors encountered.
    """
    logger.info(f"Accessed create_behavioral_pattern view by user='{request.user}'.")

    # Step 1: Attempt to retrieve Time Bucket Definition and associated Time Buckets
    try:
        time_bucket = TimeBucketDefinition.objects.first()
        bucket_entries = TimeBuckets.objects.filter(definition=time_bucket).order_by('serial_number')
    except TimeBucketDefinition.DoesNotExist:
        messages.error(request, "No Time Bucket Definition exists. Please create one first.")
        logger.warning("TimeBucketDefinition does not exist. Redirecting user to 'time_bucket_list'.")
        Log.objects.create(
            function_name='create_behavioral_pattern',
            log_level='WARNING',
            message="TimeBucketDefinition does not exist. Redirecting to time_bucket_list.",
            status='SUCCESS'
        )
        return redirect('time_bucket_list')

    # Fetch distinct product types from Ldn_Product_Master
    product_types = Ldn_Product_Master.objects.values_list('v_prod_type', flat=True).distinct()

    if request.method == 'POST':
        logger.debug(f"Received POST data for create_behavioral_pattern: {request.POST}")
        Log.objects.create(
            function_name='create_behavioral_pattern',
            log_level='DEBUG',
            message=f"Received POST data: {request.POST}",
            status='SUCCESS'
        )

        # Step 2: Call the function to process the form data
        try:
            result = define_behavioral_pattern_from_form_data(request)
        except Exception as e:
            error_details = traceback.format_exc()
            error_message = f"Error defining behavioral pattern: {str(e)}"
            logger.error(error_message)
            Log.objects.create(
                function_name='create_behavioral_pattern',
                log_level='ERROR',
                message=error_message,
                detailed_error=error_details,
                status='FAILURE'
            )
            messages.error(request, error_message)
            return render(request, 'ALM_APP/behavioral/create_behavioral_pattern.html', {
                'v_prod_type': request.POST.get('v_prod_type'),
                'description': request.POST.get('description'),
                'percentages': request.POST.getlist('percentage[]'),
                'bucket_entries': bucket_entries,
                'product_types': product_types,
            })

        # Step 3: Handle success or error from define_behavioral_pattern_from_form_data
        if 'error' in result:
            error_message = result['error']
            logger.warning(f"Behavioral pattern creation error: {error_message}")
            Log.objects.create(
                function_name='create_behavioral_pattern',
                log_level='WARNING',
                message=f"Behavioral pattern creation error: {error_message}",
                status='SUCCESS'
            )
            messages.error(request, error_message)
            # Return the form with existing data to repopulate the form fields
            return render(request, 'ALM_APP/behavioral/create_behavioral_pattern.html', {
                'v_prod_type': request.POST.get('v_prod_type'),
                'description': request.POST.get('description'),
                'percentages': request.POST.getlist('percentage[]'),
                'bucket_entries': bucket_entries,
                'product_types': product_types,
            })

        if 'success' in result:
            # If define_behavioral_pattern_from_form_data created a new pattern, retrieve its ID if available
            new_pattern_id = result.get('pattern_id', None)
            logger.info("Behavioral pattern saved successfully.")
            Log.objects.create(
                function_name='create_behavioral_pattern',
                log_level='INFO',
                message="Behavioral pattern saved successfully.",
                status='SUCCESS'
            )

            # Step 4: Create an AuditTrail entry for the new behavioral pattern
            AuditTrail.objects.create(
                user=request.user,
                user_name=request.user.name if request.user else '',
                user_surname=request.user.surname if request.user else '',
                model_name="BehavioralPattern",
                action="create",
                object_id=str(new_pattern_id) if new_pattern_id else '',
                change_description=f"Created new behavioral pattern: {request.POST.get('v_prod_type')}."
            )
            logger.info(f"AuditTrail created for new behavioral pattern with ID='{new_pattern_id}'.")

            messages.success(request, "Behavioral pattern saved successfully!")
            return redirect('behavioral_patterns_list')

    # Step 5: Render the form for GET requests
    logger.info("Accessed create_behavioral_pattern view via GET. Rendering form.")
    Log.objects.create(
        function_name='create_behavioral_pattern',
        log_level='INFO',
        message="Rendering create_behavioral_pattern form via GET request.",
        status='SUCCESS'
    )
    return render(request, 'ALM_APP/behavioral/create_behavioral_pattern.html', {
        'bucket_entries': bucket_entries,
        'product_types': product_types,
    })



# View for Behavioral Pattern List

@login_required
def behavioral_patterns_list(request):
    patterns = BehavioralPatternConfig.objects.all().order_by(
        '-created_at')  # Fetching all patterns sorted by newest first
    return render(request, 'ALM_APP/behavioral/behavioral_patterns_list.html', {'patterns': patterns})

#####################################################################################################
# View for Editing Behavioral Pattern

@login_required

def edit_behavioral_pattern(request, id):
    """
    View to edit an existing behavioral pattern. Fetches product types from Ldn_Product_Master
    and updates the pattern if the form is submitted. Logs all actions and integrates
    an audit trail for changes.
    """
    logger.info(f"Accessed edit_behavioral_pattern view for pattern ID='{id}' by user='{request.user}'.")
    Log.objects.create(
        function_name='edit_behavioral_pattern',
        log_level='INFO',
        message=f"Accessed edit_behavioral_pattern view for pattern ID='{id}' by user='{request.user}'.",
        status='SUCCESS'
    )

    try:
        # Step 1: Retrieve the pattern or handle DoesNotExist
        pattern = BehavioralPatternConfig.objects.get(id=id)
        logger.info(f"Loaded BehavioralPatternConfig with ID='{id}'.")
        Log.objects.create(
            function_name='edit_behavioral_pattern',
            log_level='INFO',
            message=f"Loaded BehavioralPatternConfig with ID='{id}'.",
            status='SUCCESS'
        )

        # Step 2: Fetch product types for the dropdown
        product_types = Ldn_Product_Master.objects.values_list('v_prod_type', flat=True).distinct()

        if request.method == 'POST':
            logger.debug(f"Received POST data for edit_behavioral_pattern: {request.POST}")
            Log.objects.create(
                function_name='edit_behavioral_pattern',
                log_level='DEBUG',
                message=f"Received POST data for pattern ID='{id}': {request.POST}",
                status='SUCCESS'
            )

            # Extract data from POST request
            tenors = request.POST.getlist('tenor[]')
            multipliers = request.POST.getlist('multiplier[]')
            percentages = request.POST.getlist('percentage[]')

            logger.debug(
                f"Validating lengths of tenors, multipliers, percentages for pattern ID='{id}'. "
                f"tenors={len(tenors)}, multipliers={len(multipliers)}, percentages={len(percentages)}"
            )
            Log.objects.create(
                function_name='edit_behavioral_pattern',
                log_level='DEBUG',
                message=(
                    f"Validating lengths for pattern ID='{id}': "
                    f"tenors={len(tenors)}, multipliers={len(multipliers)}, percentages={len(percentages)}"
                ),
                status='SUCCESS'
            )

            # Validate data lengths
            if not (len(tenors) == len(multipliers) == len(percentages)):
                error_message = "Mismatch in the number of entries for Tenors, Multipliers, and Percentages."
                logger.warning(error_message)
                Log.objects.create(
                    function_name='edit_behavioral_pattern',
                    log_level='WARNING',
                    message=error_message,
                    status='SUCCESS'
                )
                return render(request, 'ALM_APP/behavioral/edit_behavioral_pattern.html', {
                    'error': error_message,
                    'v_prod_type': request.POST.get('v_prod_type', pattern.v_prod_type),
                    'description': request.POST.get('description', pattern.description),
                    'tenors': tenors,
                    'multipliers': multipliers,
                    'percentages': percentages,
                    'product_types': product_types,
                })

            # Step 3: Call the utility function to update the pattern
            try:
                result = update_behavioral_pattern_from_form_data(request, pattern)
            except Exception as e:
                error_details = traceback.format_exc()
                error_message = f"Error updating behavioral pattern ID='{id}': {str(e)}"
                logger.error(error_message)
                Log.objects.create(
                    function_name='edit_behavioral_pattern',
                    log_level='ERROR',
                    message=error_message,
                    detailed_error=error_details,
                    status='FAILURE'
                )
                messages.error(request, error_message)
                return render(request, 'ALM_APP/behavioral/edit_behavioral_pattern.html', {
                    'error': error_message,
                    'v_prod_type': request.POST.get('v_prod_type', pattern.v_prod_type),
                    'description': request.POST.get('description', pattern.description),
                    'tenors': tenors,
                    'multipliers': multipliers,
                    'percentages': percentages,
                    'product_types': product_types,
                })

            # Step 4: Check result for success or error
            if 'error' in result:
                error_message = result['error']
                logger.warning(f"Behavioral pattern update error for ID='{id}': {error_message}")
                Log.objects.create(
                    function_name='edit_behavioral_pattern',
                    log_level='WARNING',
                    message=f"Behavioral pattern update error for ID='{id}': {error_message}",
                    status='SUCCESS'
                )
                return render(request, 'ALM_APP/behavioral/edit_behavioral_pattern.html', {
                    'error': error_message,
                    'v_prod_type': request.POST.get('v_prod_type', pattern.v_prod_type),
                    'description': request.POST.get('description', pattern.description),
                    'tenors': tenors,
                    'multipliers': multipliers,
                    'percentages': percentages,
                    'product_types': product_types,
                })

            # If successful, display the success message and redirect
            messages.success(request, "Behavioral pattern updated successfully!")
            logger.info(f"Behavioral pattern ID='{id}' updated successfully.")
            Log.objects.create(
                function_name='edit_behavioral_pattern',
                log_level='INFO',
                message=f"Behavioral pattern ID='{id}' updated successfully by user='{request.user}'.",
                status='SUCCESS'
            )

            # Step 5: Create an AuditTrail entry for the updated behavioral pattern
            AuditTrail.objects.create(
                user=request.user,
                user_name=request.user.name if request.user else '',
                user_surname=request.user.surname if request.user else '',
                model_name="BehavioralPatternConfig",
                action="update",
                object_id=str(pattern.id),
                change_description=f"Updated behavioral pattern with ID {pattern.id} for product type {pattern.v_prod_type}."
            )
            logger.info(f"AuditTrail entry created for updated behavioral pattern ID='{pattern.id}'.")

            return redirect('behavioral_patterns_list')

        # If GET request, prepopulate the form
        logger.info(f"Rendering edit form for BehavioralPatternConfig ID='{id}' via GET request.")
        Log.objects.create(
            function_name='edit_behavioral_pattern',
            log_level='INFO',
            message=f"Rendering edit form for BehavioralPatternConfig ID='{id}' via GET request.",
            status='SUCCESS'
        )
        return render(request, 'ALM_APP/behavioral/edit_behavioral_pattern.html', {
            'v_prod_type': pattern.v_prod_type,
            'description': pattern.description,
            'tenors': [entry.tenor for entry in pattern.entries.all()],
            'multipliers': [entry.multiplier for entry in pattern.entries.all()],
            'percentages': [entry.percentage for entry in pattern.entries.all()],
            'product_types': product_types,
        })

    except BehavioralPatternConfig.DoesNotExist:
        error_message = f"Behavioral pattern with ID='{id}' not found."
        logger.error(error_message)
        Log.objects.create(
            function_name='edit_behavioral_pattern',
            log_level='ERROR',
            message=error_message,
            status='FAILURE'
        )
        messages.error(request, "Behavioral pattern not found.")
        return redirect('behavioral_patterns_list')

    except Exception as e:
        error_details = traceback.format_exc()
        error_message = f"An unexpected error occurred while editing ID='{id}': {str(e)}"
        logger.exception(error_message)
        Log.objects.create(
            function_name='edit_behavioral_pattern',
            log_level='ERROR',
            message=error_message,
            detailed_error=error_details,
            status='FAILURE'
        )
        messages.error(request, f"An unexpected error occurred: {str(e)}")
        return redirect('behavioral_patterns_list')

##################################################################################################################

# View for Deleting Behavioral Pattern


logger = logging.getLogger(__name__)

@login_required
def delete_behavioral_pattern(request, id):
    """
    View to delete an existing behavioral pattern by its ID.
    Logs the deletion process and creates an AuditTrail entry for record-keeping.
    """
    logger.info(f"Accessed delete_behavioral_pattern view for pattern ID='{id}' by user='{request.user}'.")
    pattern = BehavioralPatternConfig.objects.get(id=id)
    Log.objects.create(
        
        function_name='delete_behavioral_pattern',
        log_level='INFO',
        message=f"Accessed delete_behavioral_pattern view for pattern ID='{id}' by user='{request.user}'.",
        status='SUCCESS'
    )

    if request.method == 'POST':
        logger.debug(f"Received POST request to delete pattern ID='{id}'.")
        Log.objects.create(
            function_name='delete_behavioral_pattern',
            log_level='DEBUG',
            message=f"Received POST to delete pattern ID='{id}'.",
            status='SUCCESS'
        )

        try:
            result = delete_behavioral_pattern_by_id(id)
        except Exception as e:
            error_details = traceback.format_exc()
            error_message = f"Error deleting behavioral pattern ID='{id}': {str(e)}"
            logger.error(error_message)
            Log.objects.create(
                function_name='delete_behavioral_pattern',
                log_level='ERROR',
                message=error_message,
                detailed_error=error_details,
                status='FAILURE'
            )
            messages.error(request, error_message)
            return redirect('behavioral_patterns_list')

        if 'error' in result:
            error_message = result['error']
            logger.warning(f"Behavioral pattern deletion error for ID='{id}': {error_message}")
            Log.objects.create(
                function_name='delete_behavioral_pattern',
                log_level='WARNING',
                message=f"Behavioral pattern deletion error for ID='{id}': {error_message}",
                status='SUCCESS'
            )
            messages.error(request, error_message)
        else:
            success_message = f"Behavioral pattern ID='{id}' deleted successfully!"
            logger.info(success_message)
            Log.objects.create(
                function_name='delete_behavioral_pattern',
                log_level='INFO',
                message=success_message,
                status='SUCCESS'
            )
            messages.success(request, "Behavioral pattern deleted successfully!")

            # Create an AuditTrail entry for the deletion
            AuditTrail.objects.create(
                user=request.user,
                user_name=request.user.name if request.user else '',
                user_surname=request.user.surname if request.user else '',
                model_name="BehavioralPatternConfig",
                action="delete",
                object_id=str(id),
                change_description=f"Deleted behavioral pattern with ID {id} for product type {pattern.v_prod_type}.."
            )
            logger.info(f"AuditTrail entry created for deleted behavioral pattern ID='{id}'.")

        return redirect('behavioral_patterns_list')
############################################################################################################

@login_required
def view_behavioral_pattern(request, id):
    behavioral_pattern = get_object_or_404(BehavioralPatternConfig, id=id)
    pattern_entries = BehavioralPatternEntry.objects.filter(
        pattern=behavioral_pattern).order_by('order')

    return render(request, 'ALM_APP/behavioral/view_behavioral_pattern.html', {
        'behavioral_pattern': behavioral_pattern,
        'pattern_entries': pattern_entries
    })
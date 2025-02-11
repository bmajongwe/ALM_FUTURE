import logging
from django.contrib import messages
import traceback
from django.shortcuts import get_object_or_404, redirect, render
from ALM_APP.Functions.time_bucket_utils import define_time_bucket_from_form_data, delete_time_bucket_by_id, update_time_bucket_from_form_data
from ALM_APP.models import *
from django.contrib.auth.decorators import login_required

from User.models import AuditTrail




logger = logging.getLogger(__name__)

@login_required
def create_time_bucket(request):
    """
    View to create a single Time Bucket Definition along with associated TimeBuckets.
    If a Time Bucket Definition already exists, the user is redirected to the list page.
    Integrates logging and audit trail to capture user actions and any encountered errors.
    """
    logger.info(f"Accessed create_time_bucket view by user='{request.user}'.")
    Log.objects.create(
        function_name='create_time_bucket',
        log_level='INFO',
        message=f"Accessed create_time_bucket view by user='{request.user}'.",
        status='SUCCESS'
    )

    # Step 1: Check if a Time Bucket Definition already exists
    try:
        if TimeBucketDefinition.objects.exists():
            error_message = "Only one Time Bucket Definition is allowed."
            logger.warning(error_message)
            Log.objects.create(
                function_name='create_time_bucket',
                log_level='WARNING',
                message=error_message,
                status='SUCCESS'
            )
            messages.error(request, error_message)
            return redirect('time_bucket_list')
    except Exception as e:
        error_details = traceback.format_exc()
        error_message = f"Error checking existing Time Bucket Definitions: {str(e)}"
        logger.error(error_message)
        Log.objects.create(
            function_name='create_time_bucket',
            log_level='ERROR',
            message=error_message,
            detailed_error=error_details,
            status='FAILURE'
        )
        messages.error(request, error_message)
        return redirect('time_bucket_list')

    # Step 2: Handle POST request to create a new Time Bucket Definition
    if request.method == 'POST':
        logger.debug(f"Received POST data for create_time_bucket: {request.POST}")
        Log.objects.create(
            function_name='create_time_bucket',
            log_level='DEBUG',
            message=f"Received POST data: {request.POST}",
            status='SUCCESS'
        )

        try:
            result = define_time_bucket_from_form_data(request)
        except Exception as e:
            error_details = traceback.format_exc()
            error_message = f"Error defining time bucket: {str(e)}"
            logger.error(error_message)
            Log.objects.create(
                function_name='create_time_bucket',
                log_level='ERROR',
                message=error_message,
                detailed_error=error_details,
                status='FAILURE'
            )
            messages.error(request, error_message)
            return render(request, 'ALM_APP/time_buckets/create_time_bucket.html', {
                'name': request.POST.get('name'),
                'frequencies': request.POST.getlist('frequency[]'),
                'multipliers': request.POST.getlist('multiplier[]'),
                'start_dates': request.POST.getlist('start_date[]'),
                'end_dates': request.POST.getlist('end_date[]')
            })

        # Step 3: Check the result for errors or success
        if 'error' in result:
            error_message = result['error']
            logger.warning(f"Time bucket creation error: {error_message}")
            Log.objects.create(
                function_name='create_time_bucket',
                log_level='WARNING',
                message=f"Time bucket creation error: {error_message}",
                status='SUCCESS'
            )
            messages.error(request, error_message)

            # Return the form with existing data to repopulate the form fields
            return render(request, 'ALM_APP/time_buckets/create_time_bucket.html', {
                'name': request.POST.get('name'),
                'frequencies': request.POST.getlist('frequency[]'),
                'multipliers': request.POST.getlist('multiplier[]'),
                'start_dates': request.POST.getlist('start_date[]'),
                'end_dates': request.POST.getlist('end_date[]')
            })

        if 'success' in result:
            logger.info("Time bucket definition saved successfully.")
            Log.objects.create(
                function_name='create_time_bucket',
                log_level='INFO',
                message="Time bucket definition saved successfully.",
                status='SUCCESS'
            )

            # Step 4: Create an AuditTrail entry for new Time Bucket Definition
            new_definition_id = result.get('definition_id')
            AuditTrail.objects.create(
                user=request.user,
                user_name=request.user.name if request.user else '',
                user_surname=request.user.surname if request.user else '',
                model_name="TimeBucketDefinition",
                action="create",
                object_id=str(new_definition_id) if new_definition_id else '',
                change_description=f"Created new TimeBucketDefinition with ID {new_definition_id}."
            )
            logger.info(f"AuditTrail created for new TimeBucketDefinition ID='{new_definition_id}'.")

            messages.success(request, "Time bucket saved successfully!")
            return redirect('time_bucket_list')

    # Step 5: Render the form for GET requests
    logger.info("Accessed create_time_bucket view via GET. Rendering form.")
    Log.objects.create(
        function_name='create_time_bucket',
        log_level='INFO',
        message="Rendering create_time_bucket form via GET request.",
        status='SUCCESS'
    )
    return render(request, 'ALM_APP/time_buckets/create_time_bucket.html')



# View for Listing Time Buckets
@login_required
def time_buckets_list(request):
    time_buckets = TimeBucketDefinition.objects.all().order_by(
        '-created_at')  # Fetching all time buckets sorted by newest first
    return render(request, 'ALM_APP/time_buckets/time_bucket_list.html', {'time_buckets': time_buckets})

#####################################################################################################
# View for Editing a Time Bucket


logger = logging.getLogger(__name__)

@login_required
def edit_time_bucket(request, id):
    """
    View to edit an existing Time Bucket Definition. Prepopulates form data if the definition exists.
    Updates the definition upon POST and logs all actions. Also integrates AuditTrail for changes.
    """
    logger.info(f"Accessed edit_time_bucket view for TimeBucketDefinition ID='{id}' by user='{request.user}'.")
    Log.objects.create(
        function_name='edit_time_bucket',
        log_level='INFO',
        message=f"Accessed edit_time_bucket view for ID='{id}' by user='{request.user}'.",
        status='SUCCESS'
    )

    try:
        # Step 1: Retrieve the time bucket definition to edit
        time_bucket = TimeBucketDefinition.objects.get(id=id)
        logger.info(f"Loaded TimeBucketDefinition with ID='{id}'.")
        Log.objects.create(
            function_name='edit_time_bucket',
            log_level='INFO',
            message=f"Loaded TimeBucketDefinition with ID='{id}'.",
            status='SUCCESS'
        )

        if request.method == 'POST':
            logger.debug(f"Received POST data for edit_time_bucket: {request.POST}")
            Log.objects.create(
                function_name='edit_time_bucket',
                log_level='DEBUG',
                message=f"Received POST data for definition ID='{id}': {request.POST}",
                status='SUCCESS'
            )

            try:
                # Step 2: Call the utility function to update the time bucket
                result = update_time_bucket_from_form_data(request, time_bucket)
            except Exception as e:
                error_details = traceback.format_exc()
                error_message = f"Error updating TimeBucketDefinition ID='{id}': {str(e)}"
                logger.error(error_message)
                Log.objects.create(
                    function_name='edit_time_bucket',
                    log_level='ERROR',
                    message=error_message,
                    detailed_error=error_details,
                    status='FAILURE'
                )
                messages.error(request, error_message)
                return render(request, 'ALM_APP/time_buckets/edit_time_bucket.html', {
                    'error': error_message,
                    'name': time_bucket.name,
                    'frequencies': [entry.frequency for entry in time_bucket.buckets.all()],
                    'multipliers': [entry.multiplier for entry in time_bucket.buckets.all()],
                    'start_dates': [entry.start_date for entry in time_bucket.buckets.all()],
                    'end_dates': [entry.end_date for entry in time_bucket.buckets.all()],
                })

            # Step 3: Check result for error or success
            if 'error' in result:
                error_message = result['error']
                logger.warning(f"Time bucket update error for ID='{id}': {error_message}")
                Log.objects.create(
                    function_name='edit_time_bucket',
                    log_level='WARNING',
                    message=f"Time bucket update error for ID='{id}': {error_message}",
                    status='SUCCESS'
                )
                return render(request, 'ALM_APP/time_buckets/edit_time_bucket.html', {
                    'error': error_message,
                    'name': time_bucket.name,
                    'frequencies': [entry.frequency for entry in time_bucket.buckets.all()],
                    'multipliers': [entry.multiplier for entry in time_bucket.buckets.all()],
                    'start_dates': [entry.start_date for entry in time_bucket.buckets.all()],
                    'end_dates': [entry.end_date for entry in time_bucket.buckets.all()],
                })

            # If successful, display the success message and redirect
            messages.success(request, "Time bucket updated successfully!")
            logger.info(f"TimeBucketDefinition ID='{id}' updated successfully.")
            Log.objects.create(
                function_name='edit_time_bucket',
                log_level='INFO',
                message=f"TimeBucketDefinition ID='{id}' updated successfully by user='{request.user}'.",
                status='SUCCESS'
            )

            # Step 4: Create an AuditTrail entry for the updated Time Bucket Definition
            AuditTrail.objects.create(
                user=request.user,
                user_name=request.user.name if request.user else '',
                user_surname=request.user.surname if request.user else '',
                model_name="TimeBucketDefinition",
                action="update",
                object_id=str(time_bucket.id),
                change_description=f"Updated TimeBucketDefinition with ID {time_bucket.id} (name='{time_bucket.name}')."
            )
            logger.info(f"AuditTrail entry created for updated TimeBucketDefinition ID='{time_bucket.id}'.")

            return redirect('time_bucket_list')

        # If GET request, prepopulate the form with current data
        logger.info(f"Rendering edit form for TimeBucketDefinition ID='{id}' via GET.")
        Log.objects.create(
            function_name='edit_time_bucket',
            log_level='INFO',
            message=f"Rendering edit form for TimeBucketDefinition ID='{id}' via GET request.",
            status='SUCCESS'
        )
        return render(request, 'ALM_APP/time_buckets/edit_time_bucket.html', {
            'name': time_bucket.name,
            'frequencies': [entry.frequency for entry in time_bucket.buckets.all()],
            'multipliers': [entry.multiplier for entry in time_bucket.buckets.all()],
            'start_dates': [entry.start_date for entry in time_bucket.buckets.all()],
            'end_dates': [entry.end_date for entry in time_bucket.buckets.all()],
        })

    except TimeBucketDefinition.DoesNotExist:
        error_message = f"TimeBucketDefinition with ID='{id}' not found."
        logger.error(error_message)
        Log.objects.create(
            function_name='edit_time_bucket',
            log_level='ERROR',
            message=error_message,
            status='FAILURE'
        )
        messages.error(request, "Time bucket not found.")
        return redirect('time_bucket_list')

    except Exception as e:
        error_details = traceback.format_exc()
        error_message = f"An unexpected error occurred while editing TimeBucketDefinition ID='{id}': {str(e)}"
        logger.exception(error_message)
        Log.objects.create(
            function_name='edit_time_bucket',
            log_level='ERROR',
            message=error_message,
            detailed_error=error_details,
            status='FAILURE'
        )
        messages.error(request, f"An unexpected error occurred: {str(e)}")
        return redirect('time_bucket_list')

##########################################################################################################


# View for Deleting a Time Bucket


logger = logging.getLogger(__name__)

@login_required
def delete_time_bucket(request, id):
    """
    View to delete an existing Time Bucket Definition by its ID.
    Logs the deletion process and creates an AuditTrail entry for record-keeping.
    """
    logger.info(f"Accessed delete_time_bucket view for ID='{id}' by user='{request.user}'.")
    Log.objects.create(
        function_name='delete_time_bucket',
        log_level='INFO',
        message=f"Accessed delete_time_bucket view for ID='{id}' by user='{request.user}'.",
        status='SUCCESS'
    )

    if request.method == 'POST':
        logger.debug(f"Received POST request to delete TimeBucketDefinition ID='{id}'.")
        Log.objects.create(
            function_name='delete_time_bucket',
            log_level='DEBUG',
            message=f"Received POST request to delete TimeBucketDefinition ID='{id}'.",
            status='SUCCESS'
        )

        try:
            result = delete_time_bucket_by_id(id)
        except Exception as e:
            error_details = traceback.format_exc()
            error_message = f"Error deleting time bucket ID='{id}': {str(e)}"
            logger.error(error_message)
            Log.objects.create(
                function_name='delete_time_bucket',
                log_level='ERROR',
                message=error_message,
                detailed_error=error_details,
                status='FAILURE'
            )
            messages.error(request, error_message)
            return redirect('time_bucket_list')

        if 'error' in result:
            error_message = result['error']
            logger.warning(f"Time bucket deletion warning for ID='{id}': {error_message}")
            Log.objects.create(
                function_name='delete_time_bucket',
                log_level='WARNING',
                message=f"Time bucket deletion warning for ID='{id}': {error_message}",
                status='SUCCESS'
            )
            messages.error(request, error_message)
        else:
            success_message = f"Time bucket ID='{id}' deleted successfully!"
            logger.info(success_message)
            Log.objects.create(
                function_name='delete_time_bucket',
                log_level='INFO',
                message=success_message,
                status='SUCCESS'
            )
            messages.success(request, "Time bucket deleted successfully!")

            # Create an AuditTrail entry for the deletion
            AuditTrail.objects.create(
                user=request.user,
                user_name=request.user.name if request.user else '',
                user_surname=request.user.surname if request.user else '',
                model_name="TimeBucketDefinition",
                action="delete",
                object_id=str(id),
                change_description=f"Deleted TimeBucketDefinition with ID {id}."
            )
            logger.info(f"AuditTrail entry created for deleted TimeBucketDefinition ID='{id}'.")

        return redirect('time_bucket_list')
####################################################################################################


@login_required
def view_time_bucket(request, id):
    # Retrieve the specific Time Bucket Definition
    time_bucket = get_object_or_404(TimeBucketDefinition, id=id)

    # Pass the time bucket and its entries to the template
    return render(request, 'ALM_APP/time_buckets/view_time_bucket.html', {
        'time_bucket': time_bucket,
        'buckets': time_bucket.buckets.all().order_by('serial_number')
    })

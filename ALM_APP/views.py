from ALM_APP.Functions.alm_execution_functions import execute_alm_process_logic
from .models import LiquidityGapResultsCons
from .Functions.liquidity_gap_utils import filter_queryset_by_form, get_date_buckets, prepare_inflow_outflow_data, calculate_totals
from .models import LiquidityGapResultsBase
from openpyxl.utils import get_column_letter
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl import Workbook
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.db.models import Sum, F
from django.contrib import messages
from .Functions.liquidity_gap_utils import *
from .forms import LiquidityGapReportFilterForm
from .models import LiquidityGapResultsBase, LiquidityGapResultsCons
from django.shortcuts import render
from collections import defaultdict
import os
from django.views.generic.detail import DetailView
from django.urls import reverse_lazy
from django.views import View
import openpyxl
import pandas as pd
from decimal import Decimal
import csv
import traceback
from django.contrib import messages  # Import messages framework
from django.shortcuts import get_object_or_404, render, redirect
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.conf import settings


from .Functions.data import *

from .Functions.Operations import *
from .forms import *
from datetime import datetime
from django.http import HttpResponse
from .Functions.Aggregated_Prod_Cashflow_Base import *
from .Functions.populate_liquidity_gap_results_base import *
from .Functions.ldn_update import *
from .Functions.aggregate_cashflows import *
from .Functions.Aggregated_Acc_level_cashflows import *
from .Functions.behavioral_pattern_utils import define_behavioral_pattern_from_form_data, delete_behavioral_pattern_by_id, update_behavioral_pattern_from_form_data
from .Functions.time_bucket_utils import define_time_bucket_from_form_data, update_time_bucket_from_form_data, delete_time_bucket_by_id
from .Functions.populate_dim import populate_dim_product
from .Functions.Dim_dates import *
from .Functions.product_filter_utils import *
from .Functions.process_utils import *
from .Functions.cashflow import *

from datetime import datetime, timedelta
from django.shortcuts import render, redirect
from .models import TimeBuckets, TimeBucketDefinition, product_level_cashflows


@login_required



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


#####################################################################################################

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


# ProductFilter Views
class ProductFilterListView(ListView):
    model = ProductFilter
    template_name = 'ALM_APP/filters/filter_list.html'
    context_object_name = 'filters'


class ProductFilterCreateView(CreateView):
    model = ProductFilter
    form_class = ProductFilterForm
    template_name = 'ALM_APP/filters/filter_form.html'
    success_url = reverse_lazy('product_filter_list')

    def form_valid(self, form):
        create_or_update_filter(data=form.cleaned_data)
        messages.success(self.request, 'Product filter created successfully.')
        return redirect(self.success_url)


class ProductFilterUpdateView(UpdateView):
    model = ProductFilter
    form_class = ProductFilterForm
    template_name = 'ALM_APP/filters/filter_update.html'
    success_url = reverse_lazy('product_filter_list')

    def form_valid(self, form):
        create_or_update_filter(
            filter_id=self.object.id, data=form.cleaned_data)
        messages.success(self.request, 'Product filter updated successfully.')
        return redirect(self.success_url)


class ProductFilterDeleteView(View):
    success_url = reverse_lazy('product_filter_list')

    def post(self, request, *args, **kwargs):
        # Retrieve the filter to delete
        product_filter = get_object_or_404(ProductFilter, id=kwargs['pk'])
        delete_filter(filter_id=product_filter.id)
        messages.success(request, 'Product filter deleted successfully.')
        return redirect(self.success_url)


class ProductFilterDetailView(DetailView):
    model = ProductFilter
    template_name = 'ALM_APP/filters/filter_detail.html'
    context_object_name = 'filter'

    def get_object(self):
        # Fetch the filter based on ID or raise a 404 error
        filter_id = self.kwargs.get('pk')
        return get_object_or_404(ProductFilter, pk=filter_id)


# Process Views
class ProcessListView(ListView):
    model = Process
    template_name = 'ALM_APP/filters/process_list.html'
    context_object_name = 'processes'


###############################################################################################


logger = logging.getLogger(__name__)

@login_required
def process_create_view(request):
    """
    A multi-step view for creating a process with optional behavioral patterns and associated filters.
    Utilizes session data to manage steps and includes detailed logging and audit trail integration.
    """
    step = request.session.get('step', 1)
    logger.info(f"Accessed process_create_view with step='{step}' by user='{request.user}'.")
    Log.objects.create(
        function_name='process_create_view',
        log_level='INFO',
        message=f"Accessed process_create_view with step='{step}' by user='{request.user}'.",
        status='SUCCESS'
    )

    # Step 1: Basic Process Information
    if step == 1:
        logger.debug("Step 1: Collecting basic process information.")
        Log.objects.create(
            function_name='process_create_view',
            log_level='DEBUG',
            message="Step 1: Collecting basic process information.",
            status='SUCCESS'
        )

        if request.method == 'POST':
            process_name = request.POST.get('name')
            process_description = request.POST.get('description')
            use_behavioral_patterns = request.POST.get('use_behavioral_patterns')

            logger.debug(f"Received POST data at step 1: process_name='{process_name}', "
                         f"use_behavioral_patterns='{use_behavioral_patterns}'")
            Log.objects.create(
                function_name='process_create_view',
                log_level='DEBUG',
                message=(
                    f"Received POST data at step 1: process_name='{process_name}', "
                    f"use_behavioral_patterns='{use_behavioral_patterns}'"
                ),
                status='SUCCESS'
            )

            if not process_name:
                error_message = "Process name is required."
                logger.warning(error_message)
                Log.objects.create(
                    function_name='process_create_view',
                    log_level='WARNING',
                    message=error_message,
                    status='SUCCESS'
                )
                messages.error(request, error_message)
                return render(request, 'ALM_APP/filters/process_create.html', {'step': step})

            # Store the data in session
            request.session['process_name'] = process_name
            request.session['process_description'] = process_description
            request.session['use_behavioral_patterns'] = use_behavioral_patterns

            # Determine next step based on behavioral pattern usage
            if use_behavioral_patterns == 'yes':
                request.session['step'] = 3
            else:
                request.session['step'] = 2

            logger.info(f"Step 1 completed. Transitioning to step='{request.session['step']}'.")
            Log.objects.create(
                function_name='process_create_view',
                log_level='INFO',
                message=f"Step 1 completed. Transitioning to step='{request.session['step']}'.",
                status='SUCCESS'
            )
            return redirect('process_create')

        return render(request, 'ALM_APP/filters/process_create.html', {'step': step})

    # Step 2: Select Filters
    elif step == 2:
        logger.debug("Step 2: Selecting filters for the process.")
        Log.objects.create(
            function_name='process_create_view',
            log_level='DEBUG',
            message="Step 2: Selecting filters for the process.",
            status='SUCCESS'
        )

        filters = ProductFilter.objects.all()

        if request.method == 'POST':
            if 'previous' in request.POST:
                request.session['step'] = 1
                logger.info("User clicked 'previous' at step 2, returning to step 1.")
                Log.objects.create(
                    function_name='process_create_view',
                    log_level='INFO',
                    message="User clicked 'previous' at step 2, returning to step 1.",
                    status='SUCCESS'
                )
                return redirect('process_create')
            else:
                selected_filters = request.POST.getlist('filters')
                request.session['selected_filters'] = selected_filters
                request.session['step'] = 3
                logger.info(f"Selected filters: {selected_filters}. Moving to step 3.")
                Log.objects.create(
                    function_name='process_create_view',
                    log_level='INFO',
                    message=f"Selected filters: {selected_filters}. Moving to step 3.",
                    status='SUCCESS'
                )
                return redirect('process_create')

        return render(request, 'ALM_APP/filters/process_create.html', {
            'step': step,
            'filters': filters
        })

    # Step 3: Confirmation & Finalization
    elif step == 3:
        logger.debug("Step 3: Confirmation and finalization of process creation.")
        Log.objects.create(
            function_name='process_create_view',
            log_level='DEBUG',
            message="Step 3: Confirmation and finalization of process creation.",
            status='SUCCESS'
        )

        process_name = request.session.get('process_name')
        process_description = request.session.get('process_description')
        use_behavioral_patterns = request.session.get('use_behavioral_patterns')
        selected_filters = request.session.get('selected_filters', [])
        filters = ProductFilter.objects.filter(id__in=selected_filters)

        if request.method == 'POST':
            if 'previous' in request.POST:
                previous_step = 2 if use_behavioral_patterns == 'no' else 1
                request.session['step'] = previous_step
                logger.info(f"User clicked 'previous' at step 3, returning to step='{previous_step}'.")
                Log.objects.create(
                    function_name='process_create_view',
                    log_level='INFO',
                    message=f"User clicked 'previous' at step 3, returning to step='{previous_step}'.",
                    status='SUCCESS'
                )
                return redirect('process_create')
            else:
                # Attempt to finalize process creation
                try:
                    process = finalize_process_creation(request)
                    success_message = f"Process '{process.name}' created successfully."
                    messages.success(request, success_message)
                    logger.info(success_message)
                    Log.objects.create(
                        function_name='process_create_view',
                        log_level='INFO',
                        message=success_message,
                        status='SUCCESS'
                    )

                    # Create an AuditTrail entry for process creation
                    AuditTrail.objects.create(
                        user=request.user,
                        user_name=request.user.name if request.user else '',
                        user_surname=request.user.surname if request.user else '',
                        model_name="Process,Process_Rn",
                        action="create",
                        object_id=str(process.id),
                        change_description=(
                            f"Created process '{process.name}' with "
                            f"behavioral_patterns='{use_behavioral_patterns}' and "
                            f"{len(selected_filters)} selected filters."
                        )
                    )
                    logger.info(f"AuditTrail entry created for new Process ID='{process.id}'.")

                except Exception as e:
                    error_details = traceback.format_exc()
                    error_message = f"Error creating process: {str(e)}"
                    logger.error(error_message)
                    Log.objects.create(
                        function_name='process_create_view',
                        log_level='ERROR',
                        message=error_message,
                        detailed_error=error_details,
                        status='FAILURE'
                    )
                    messages.error(request, error_message)
                    return redirect('process_create')

                # Clear session
                request.session.pop('process_name', None)
                request.session.pop('process_description', None)
                request.session.pop('use_behavioral_patterns', None)
                request.session.pop('selected_filters', None)
                request.session.pop('step', None)

                return redirect('processes_list')

        return render(request, 'ALM_APP/filters/process_create.html', {
            'step': step,
            'process_name': process_name,
            'process_description': process_description,
            'selected_filters': filters,
            'use_behavioral_patterns': use_behavioral_patterns
        })

    # If step is invalid or session step is missing, reset to 1
    logger.warning("Invalid step detected or session step missing. Resetting to step=1.")
    Log.objects.create(
        function_name='process_create_view',
        log_level='WARNING',
        message="Invalid step detected or session step missing. Resetting to step=1.",
        status='SUCCESS'
    )
    request.session['step'] = 1
    return redirect('process_create')

###############################################################################################


logger = logging.getLogger(__name__)
@login_required
def execute_alm_process_view(request):
    """
    View to execute an ALM process for a given fic_mis_date.
    This function checks whether the selected process uses behavioral patterns
    and calls the appropriate functions to complete the ALM flow.
    Logs all actions to the 'Log' table but does not integrate audit trails.
    """
    logger.info(f"Accessed execute_alm_process_view by user='{request.user}' if authenticated.")
    Log.objects.create(
        function_name='execute_alm_process_view',
        log_level='INFO',
        message=f"Accessed execute_alm_process_view by user='{request.user}' if authenticated.",
        status='SUCCESS'
    )

    if request.method == 'POST':
        logger.debug(f"Received POST data in execute_alm_process_view: {request.POST}")
        Log.objects.create(
            function_name='execute_alm_process_view',
            log_level='DEBUG',
            message=f"Received POST data: {request.POST}",
            status='SUCCESS'
        )

        process_id = request.POST.get('process_id')
        fic_mis_date = request.POST.get('fic_mis_date')

        # Validate date format
        try:
            datetime.strptime(fic_mis_date, "%Y-%m-%d")
        except ValueError:
            error_message = "Invalid date format. Please use YYYY-MM-DD."
            logger.warning(error_message)
            Log.objects.create(
                function_name='execute_alm_process_view',
                log_level='WARNING',
                message=error_message,
                status='SUCCESS'
            )
            messages.error(request, error_message)
            return redirect('processes_list')

        # Fetch the process
        try:
            process = get_object_or_404(Process_Rn, id=process_id)
            logger.info(f"Fetched Process_Rn with ID='{process_id}' (name='{process.process_name}').")
            Log.objects.create(
                function_name='execute_alm_process_view',
                log_level='INFO',
                message=f"Fetched Process_Rn with ID='{process_id}' (name='{process.process_name}').",
                status='SUCCESS'
            )
        except Exception as e:
            error_details = traceback.format_exc()
            error_message = f"Error fetching process with ID='{process_id}': {str(e)}"
            logger.error(error_message)
            Log.objects.create(
                function_name='execute_alm_process_view',
                log_level='ERROR',
                message=error_message,
                detailed_error=error_details,
                status='FAILURE'
            )
            messages.error(request, error_message)
            return redirect('processes_list')

        # Execute the process flow
        try:
            logger.info(f"Starting ALM process execution for '{process.process_name}' with date='{fic_mis_date}'.")
            Log.objects.create(
                function_name='execute_alm_process_view',
                log_level='INFO',
                message=f"Starting ALM process execution for '{process.process_name}' with date='{fic_mis_date}'.",
                status='SUCCESS'
            )

            # Determine if behavioral patterns should be applied
            if process.uses_behavioral_patterns:
                calculate_behavioral_pattern_distribution(process.process_name, fic_mis_date)
                logger.debug(f"Behavioral pattern distribution calculated for '{process.process_name}'.")
                Log.objects.create(
                    function_name='execute_alm_process_view',
                    log_level='DEBUG',
                    message=f"Behavioral pattern distribution calculated for '{process.process_name}'.",
                    status='SUCCESS'
                )
            else:
                calculate_time_buckets_and_spread(process.process_name, fic_mis_date)
                logger.debug(f"Time buckets and spread calculated for '{process.process_name}'.")
                Log.objects.create(
                    function_name='execute_alm_process_view',
                    log_level='DEBUG',
                    message=f"Time buckets and spread calculated for '{process.process_name}'.",
                    status='SUCCESS'
                )

            # Additional steps in the ALM flow
            aggregate_by_prod_code(process.process_name, fic_mis_date)
            logger.debug(f"Aggregated by product code for '{process.process_name}'.")
            Log.objects.create(
                function_name='execute_alm_process_view',
                log_level='DEBUG',
                message=f"Aggregated by product code for '{process.process_name}'.",
                status='SUCCESS'
            )

            populate_dim_product(fic_mis_date)
            logger.debug(f"Dim product populated for date='{fic_mis_date}'.")
            Log.objects.create(
                function_name='execute_alm_process_view',
                log_level='DEBUG',
                message=f"Dim product populated for date='{fic_mis_date}'.",
                status='SUCCESS'
            )

            populate_dim_dates_from_time_buckets(fic_mis_date)
            logger.debug(f"Dim dates populated from time buckets for date='{fic_mis_date}'.")
            Log.objects.create(
                function_name='execute_alm_process_view',
                log_level='DEBUG',
                message=f"Dim dates populated from time buckets for date='{fic_mis_date}'.",
                status='SUCCESS'
            )

            populate_liquidity_gap_results_base(fic_mis_date, process.process_name)
            logger.debug(f"Liquidity gap results base populated for '{process.process_name}'.")
            Log.objects.create(
                function_name='execute_alm_process_view',
                log_level='DEBUG',
                message=f"Liquidity gap results base populated for '{process.process_name}'.",
                status='SUCCESS'
            )

            success_message = f"Process '{process.process_name}' executed successfully."
            logger.info(success_message)
            Log.objects.create(
                function_name='execute_alm_process_view',
                log_level='INFO',
                message=success_message,
                status='SUCCESS'
            )
            messages.success(request, success_message)

        except Exception as e:
            error_details = traceback.format_exc()
            error_message = f"Error executing process '{process.process_name}': {str(e)}"
            logger.error(error_message)
            Log.objects.create(
                function_name='execute_alm_process_view',
                log_level='ERROR',
                message=error_message,
                detailed_error=error_details,
                status='FAILURE'
            )
            messages.error(request, error_message)

        return redirect('processes_list')

    # Render a simple form if GET request
    logger.info("Rendering execute_alm_process_view form via GET request.")
    Log.objects.create(
        function_name='execute_alm_process_view',
        log_level='INFO',
        message="Rendering execute_alm_process_view form via GET request.",
        status='SUCCESS'
    )
    return render(request, 'ALM_APP/filters/process_execute.html')



##################################################################################################################################



logger = logging.getLogger(__name__)

@login_required
def ProcessUpdateView(request, process_id):
    """
    A multi-step view for editing an existing process. This view modifies both
    Process_Rn and Process objects using the same process_id. Integrates detailed
    logging and an audit trail for change tracking.
    """
    # Step 0: Fetch the existing objects and current editing step
    logger.info(f"Accessed ProcessUpdateView for process_id='{process_id}' by user='{request.user}'.")
    Log.objects.create(
        function_name='ProcessUpdateView',
        log_level='INFO',
        message=f"Accessed ProcessUpdateView for process_id='{process_id}' by user='{request.user}'.",
        status='SUCCESS'
    )

    try:
        process_rn = get_object_or_404(Process_Rn, id=process_id)
        process = get_object_or_404(Process, id=process_id)
        logger.debug(f"Fetched Process_Rn and Process for ID='{process_id}'.")
        Log.objects.create(
            function_name='ProcessUpdateView',
            log_level='DEBUG',
            message=f"Fetched Process_Rn and Process for ID='{process_id}'.",
            status='SUCCESS'
        )
    except Exception as e:
        error_details = traceback.format_exc()
        error_message = f"Error retrieving Process_Rn or Process with ID='{process_id}': {str(e)}"
        logger.error(error_message)
        Log.objects.create(
            function_name='ProcessUpdateView',
            log_level='ERROR',
            message=error_message,
            detailed_error=error_details,
            status='FAILURE'
        )
        messages.error(request, error_message)
        return redirect('processes_list')

    step = request.session.get('edit_step', 1)
    logger.info(f"Current Edit Step for process_id='{process_id}': {step}")
    Log.objects.create(
        function_name='ProcessUpdateView',
        log_level='INFO',
        message=f"Current Edit Step for process_id='{process_id}': {step}",
        status='SUCCESS'
    )

    # Step 1: Basic Process Information
    if step == 1:
        logger.debug("Step 1: Editing basic process information.")
        Log.objects.create(
            function_name='ProcessUpdateView',
            log_level='DEBUG',
            message="Step 1: Editing basic process information.",
            status='SUCCESS'
        )

        if request.method == 'POST':
            process_name = request.POST.get('name')
            process_description = request.POST.get('description')
            use_behavioral_patterns = request.POST.get('use_behavioral_patterns')

            logger.debug(
                f"POST data at step 1: name='{process_name}', description='{process_description}', "
                f"use_behavioral_patterns='{use_behavioral_patterns}'"
            )
            Log.objects.create(
                function_name='ProcessUpdateView',
                log_level='DEBUG',
                message=(
                    f"POST data at step 1: name='{process_name}', "
                    f"description='{process_description}', use_behavioral_patterns='{use_behavioral_patterns}'"
                ),
                status='SUCCESS'
            )

            if not process_name:
                error_message = "Process name is required."
                logger.warning(error_message)
                Log.objects.create(
                    function_name='ProcessUpdateView',
                    log_level='WARNING',
                    message=error_message,
                    status='SUCCESS'
                )
                messages.error(request, error_message)
                return render(request, 'ALM_APP/filters/process_edit.html', {
                    'step': step,
                    'process': process_rn,
                })

            request.session['edit_process_name'] = process_name
            request.session['edit_process_description'] = process_description
            request.session['edit_use_behavioral_patterns'] = use_behavioral_patterns

            # Move to the next step based on behavioral pattern usage
            if use_behavioral_patterns == 'yes':
                request.session['edit_step'] = 3
            else:
                request.session['edit_step'] = 2

            logger.info(f"Step 1 completed, transitioning to step='{request.session['edit_step']}' for process_id='{process_id}'.")
            Log.objects.create(
                function_name='ProcessUpdateView',
                log_level='INFO',
                message=(
                    f"Step 1 completed, transitioning to step='{request.session['edit_step']}' "
                    f"for process_id='{process_id}'."
                ),
                status='SUCCESS'
            )
            return redirect('process_update', process_id=process_id)

        return render(request, 'ALM_APP/filters/process_edit.html', {
            'step': step,
            'process': process_rn,
            'process_name': process_rn.process_name,
            'process_description': process_rn.description,
            'use_behavioral_patterns': 'yes' if process_rn.uses_behavioral_patterns else 'no',
        })

    # Step 2: Select Filters
    elif step == 2:
        logger.debug("Step 2: Editing filters for the process.")
        Log.objects.create(
            function_name='ProcessUpdateView',
            log_level='DEBUG',
            message="Step 2: Editing filters for the process.",
            status='SUCCESS'
        )

        filters = ProductFilter.objects.all()
        selected_filters = request.session.get(
            'edit_selected_filters',
            process_rn.filters.values_list('id', flat=True)
        )

        if request.method == 'POST':
            if 'previous' in request.POST:
                request.session['edit_step'] = 1
                logger.info("User clicked 'previous' at step 2, returning to step 1.")
                Log.objects.create(
                    function_name='ProcessUpdateView',
                    log_level='INFO',
                    message="User clicked 'previous' at step 2, returning to step 1.",
                    status='SUCCESS'
                )
                return redirect('process_update', process_id=process_id)
            else:
                selected_filters = request.POST.getlist('filters')
                request.session['edit_selected_filters'] = selected_filters
                request.session['edit_step'] = 3
                logger.info(f"Selected filters: {selected_filters}. Moving to step 3.")
                Log.objects.create(
                    function_name='ProcessUpdateView',
                    log_level='INFO',
                    message=f"Selected filters: {selected_filters}. Moving to step 3.",
                    status='SUCCESS'
                )
                return redirect('process_update', process_id=process_id)

        return render(request, 'ALM_APP/filters/process_edit.html', {
            'step': step,
            'process': process_rn,
            'filters': filters,
            'selected_filters': selected_filters,
        })

    # Step 3: Confirmation & Finalization
    elif step == 3:
        logger.debug("Step 3: Confirming and finalizing process update.")
        Log.objects.create(
            function_name='ProcessUpdateView',
            log_level='DEBUG',
            message="Step 3: Confirming and finalizing process update.",
            status='SUCCESS'
        )

        process_name = request.session.get('edit_process_name', process_rn.process_name)
        process_description = request.session.get('edit_process_description', process_rn.description)
        use_behavioral_patterns = request.session.get('edit_use_behavioral_patterns', 'no')
        selected_filters = request.session.get(
            'edit_selected_filters',
            process_rn.filters.values_list('id', flat=True)
        )
        filters = ProductFilter.objects.filter(id__in=selected_filters)

        if request.method == 'POST':
            if 'previous' in request.POST:
                previous_step = 2 if use_behavioral_patterns == 'no' else 1
                request.session['edit_step'] = previous_step
                logger.info(f"User clicked 'previous' at step 3, returning to step='{previous_step}'.")
                Log.objects.create(
                    function_name='ProcessUpdateView',
                    log_level='INFO',
                    message=f"User clicked 'previous' at step 3, returning to step='{previous_step}'.",
                    status='SUCCESS'
                )
                return redirect('process_update', process_id=process_id)
            else:
                logger.debug(f"Finalizing process update with name='{process_name}', description='{process_description}', filters={list(selected_filters)}.")
                Log.objects.create(
                    function_name='ProcessUpdateView',
                    log_level='DEBUG',
                    message=(
                        f"Finalizing process update with name='{process_name}', description='{process_description}', "
                        f"filters={list(selected_filters)}."
                    ),
                    status='SUCCESS'
                )

                try:
                    finalize_process_update(process_rn, process, {
                        'name': process_name,
                        'description': process_description,
                        'use_behavioral_patterns': use_behavioral_patterns,
                        'filters': selected_filters,
                    })
                    success_message = f"Process '{process_name}' updated successfully."
                    messages.success(request, success_message)
                    logger.info(success_message)
                    Log.objects.create(
                        function_name='ProcessUpdateView',
                        log_level='INFO',
                        message=success_message,
                        status='SUCCESS'
                    )

                    # Create an AuditTrail entry for updating the process
                    AuditTrail.objects.create(
                        user=request.user,
                        user_name=request.user.name if request.user else '',
                        user_surname=request.user.surname if request.user else '',
                        model_name="Process,Process_Rn",
                        action="update",
                        object_id=str(process_id),
                        change_description=(
                            f"Updated process '{process_name}' with "
                            f"behavioral_patterns='{use_behavioral_patterns}' and "
                            f"{len(selected_filters)} selected filters."
                        )
                    )
                    logger.info(f"AuditTrail entry created for updated process ID='{process_id}'.")

                except Exception as e:
                    error_details = traceback.format_exc()
                    error_message = f"Error updating process: {str(e)}"
                    logger.error(error_message)
                    Log.objects.create(
                        function_name='ProcessUpdateView',
                        log_level='ERROR',
                        message=error_message,
                        detailed_error=error_details,
                        status='FAILURE'
                    )
                    messages.error(request, error_message)
                    return redirect('process_update', process_id=process_id)

                # Clear session
                request.session.pop('edit_process_name', None)
                request.session.pop('edit_process_description', None)
                request.session.pop('edit_use_behavioral_patterns', None)
                request.session.pop('edit_selected_filters', None)
                request.session.pop('edit_step', None)

                return redirect('processes_list')

        return render(request, 'ALM_APP/filters/process_edit.html', {
            'step': step,
            'process': process_rn,
            'process_name': process_name,
            'process_description': process_description,
            'selected_filters': filters,
            'use_behavioral_patterns': use_behavioral_patterns,
        })

    # If step is invalid or not found, reset to step 1
    logger.warning(
        f"Invalid or missing edit_step detected for process_id='{process_id}'. Resetting to step=1."
    )
    Log.objects.create(
        function_name='ProcessUpdateView',
        log_level='WARNING',
        message=f"Invalid or missing edit_step detected for process_id='{process_id}'. Resetting to step=1.",
        status='SUCCESS'
    )
    request.session['edit_step'] = 1
    return redirect('process_update', process_id=process_id)



#########################################################################
def processes_view(request, process_id):
    """
    Displays the details of a specific process.
    """
    process = get_object_or_404(Process, id=process_id)
    filters = process.filters.all()  # Assuming Process has a filters relationship
    return render(request, 'ALM_APP/filters/process_detail.html', {
        'process': process,
        'filters': filters,
    })



####################################################################################



logger = logging.getLogger(__name__)

@login_required
def ProcessDeleteView(request, process_id):
    """
    View to delete an existing process by its ID from both Process and Process_Rn tables.
    Integrates logging and audit trail for record-keeping.
    """
    logger.info(f"Accessed ProcessDeleteView for process_id='{process_id}' by user='{request.user}'.")
    Log.objects.create(
        function_name='ProcessDeleteView',
        log_level='INFO',
        message=f"Accessed ProcessDeleteView for process_id='{process_id}' by user='{request.user}'.",
        status='SUCCESS'
    )

    if request.method == 'POST':
        logger.debug(f"Received POST request to delete process_id='{process_id}'.")
        Log.objects.create(
            function_name='ProcessDeleteView',
            log_level='DEBUG',
            message=f"Received POST request to delete process_id='{process_id}'.",
            status='SUCCESS'
        )

        # Try fetching the process from both tables without raising 404
        process_in_main_table = Process.objects.filter(id=process_id).first()
        process_in_rn_table = Process_Rn.objects.filter(id=process_id).first()

        try:
            deleted_any = False

            # Handle deletion if the process exists in the main table
            if process_in_main_table:
                main_table_name = process_in_main_table.name if hasattr(process_in_main_table, 'name') else f"Process-{process_id}"
                process_in_main_table.delete()
                success_message = f"Process '{main_table_name}' deleted successfully from Process table."
                logger.info(success_message)
                Log.objects.create(
                    function_name='ProcessDeleteView',
                    log_level='INFO',
                    message=success_message,
                    status='SUCCESS'
                )
                messages.success(request, success_message)
                deleted_any = True

                # Audit trail for main table deletion
                AuditTrail.objects.create(
                    user=request.user,
                    user_name=request.user.name if request.user else '',
                    user_surname=request.user.surname if request.user else '',
                    model_name="Process",
                    action="delete",
                    object_id=str(process_id),
                    change_description=f"Deleted process (main table) with ID {process_id}."
                )
                logger.info(f"AuditTrail entry created for deleted process ID='{process_id}' in main table.")

            # Handle deletion if the process exists in the RN table
            if process_in_rn_table:
                rn_table_name = process_in_rn_table.process_name if hasattr(process_in_rn_table, 'process_name') else f"ProcessRn-{process_id}"
                process_in_rn_table.delete()
                success_message = f"Process '{rn_table_name}' deleted successfully from Process_Rn table."
                logger.info(success_message)
                Log.objects.create(
                    function_name='ProcessDeleteView',
                    log_level='INFO',
                    message=success_message,
                    status='SUCCESS'
                )
                messages.success(request, success_message)
                deleted_any = True

                # Audit trail for RN table deletion
                AuditTrail.objects.create(
                    user=request.user,
                    user_name=request.user.name if request.user else '',
                    user_surname=request.user.surname if request.user else '',
                    model_name="Process_Rn",
                    action="delete",
                    object_id=str(process_id),
                    change_description=f"Deleted process (RN table) with ID {process_id}."
                )
                logger.info(f"AuditTrail entry created for deleted process ID='{process_id}' in RN table.")

            # If the process was not found in either table
            if not deleted_any:
                error_message = f"Process with ID='{process_id}' does not exist in either table."
                logger.warning(error_message)
                Log.objects.create(
                    function_name='ProcessDeleteView',
                    log_level='WARNING',
                    message=error_message,
                    status='SUCCESS'
                )
                messages.error(request, error_message)

        except Exception as e:
            error_details = traceback.format_exc()
            error_message = f"Failed to delete process ID='{process_id}': {str(e)}"
            logger.error(error_message)
            Log.objects.create(
                function_name='ProcessDeleteView',
                log_level='ERROR',
                message=error_message,
                detailed_error=error_details,
                status='FAILURE'
            )
            messages.error(request, error_message)

        return redirect('processes_list')

    elif request.method == 'GET':
        logger.debug(f"Received GET request for process_id='{process_id}' deletion confirmation.")
        Log.objects.create(
            function_name='ProcessDeleteView',
            log_level='DEBUG',
            message=f"Received GET request for process_id='{process_id}' deletion confirmation.",
            status='SUCCESS'
        )

        # Check for the existence of the process in either table for confirmation
        process_in_main_table = Process.objects.filter(id=process_id).first()
        process_in_rn_table = Process_Rn.objects.filter(id=process_id).first()

        if process_in_main_table or process_in_rn_table:
            # Show confirmation page
            obj = process_in_main_table or process_in_rn_table
            return render(
                request,
                'ALM_APP/filters/process_confirm_delete.html',
                {'object': obj}
            )
        else:
            error_message = f"Process with ID='{process_id}' does not exist in either table."
            logger.warning(error_message)
            Log.objects.create(
                function_name='ProcessDeleteView',
                log_level='WARNING',
                message=error_message,
                status='SUCCESS'
            )
            messages.error(request, 'Process does not exist.')
            return redirect('processes_list')

    logger.warning("Invalid request method encountered in ProcessDeleteView.")
    Log.objects.create(
        function_name='ProcessDeleteView',
        log_level='WARNING',
        message="Invalid request method encountered in ProcessDeleteView.",
        status='SUCCESS'
    )
    return HttpResponseForbidden("Invalid request method")
#################################################################
















################################################################################################################



logger = logging.getLogger(__name__)

@login_required


def liquidity_gap_report_base(request):
    """
    View to display a base Liquidity Gap Report. Reads from session and GET parameters to filter data.
    Produces a multi-currency view of inflows, outflows, net liquidity gaps, and optional drill-downs.
    Logs actions to the Log table but does not integrate audit trails.
    """
    logger.info("Accessed liquidity_gap_report_base view.")
    Log.objects.create(
        function_name='liquidity_gap_report_base',
        log_level='INFO',
        message="Accessed liquidity_gap_report_base view.",
        status='SUCCESS'
    )

    # Step 1: Manage GET parameters and session-based filters
    if request.GET:
        logger.debug(f"Received GET parameters for liquidity_gap_report_base: {request.GET}")
        Log.objects.create(
            function_name='liquidity_gap_report_base',
            log_level='DEBUG',
            message=f"Received GET parameters: {request.GET}",
            status='SUCCESS'
        )

        session_filters = request.session.get('filters_base', {})
        new_params = request.GET.dict()
        merged_filters = {**session_filters, **new_params}
        request.session['filters_base'] = merged_filters
        filters = merged_filters
    else:
        filters = request.session.get('filters_base', {})

    # Step 2: Initialize the form and base queryset
    form = LiquidityGapReportFilterForm(filters or None)
    base_queryset = LiquidityGapResultsBase.objects.all()

    # Step 3: Determine fic_mis_date from form or fallback to the latest
    if form.is_valid():
        fic_mis_date = form.cleaned_data.get('fic_mis_date')
    else:
        fic_mis_date = None

    if not fic_mis_date:
        fic_mis_date = get_latest_fic_mis_date()
        if not fic_mis_date:
            error_message = "No data available for the selected filters."
            logger.warning(error_message)
            Log.objects.create(
                function_name='liquidity_gap_report_base',
                log_level='WARNING',
                message=error_message,
                status='SUCCESS'
            )
            messages.error(request, error_message)
            return render(
                request,
                'ALM_APP/reports/liquidity_gap_report_base.html',
                {'form': form}
            )

    logger.debug(f"Using fic_mis_date='{fic_mis_date}' for liquidity gap report.")
    Log.objects.create(
        function_name='liquidity_gap_report_base',
        log_level='DEBUG',
        message=f"Using fic_mis_date='{fic_mis_date}' for report.",
        status='SUCCESS'
    )

    # Step 4: Retrieve date buckets for the fic_mis_date
    date_buckets = get_date_buckets(fic_mis_date)
    if not date_buckets.exists():
        error_message = "No date buckets available for the selected filters."
        logger.warning(error_message)
        Log.objects.create(
            function_name='liquidity_gap_report_base',
            log_level='WARNING',
            message=error_message,
            status='SUCCESS'
        )
        messages.error(request, error_message)
        return render(
            request,
            'ALM_APP/reports/liquidity_gap_report_base.html',
            {'form': form}
        )

    # Step 5: Read additional drill-down and currency params
    drill_down_product = request.GET.get('drill_down_product')
    drill_down_splits = request.GET.get('drill_down_splits')
    selected_currency = request.GET.get('selected_currency', None)

    logger.debug(
        f"Drill-down params: product='{drill_down_product}', splits='{drill_down_splits}', currency='{selected_currency}'."
    )
    Log.objects.create(
        function_name='liquidity_gap_report_base',
        log_level='DEBUG',
        message=(
            f"Drill-down params: product='{drill_down_product}', "
            f"splits='{drill_down_splits}', currency='{selected_currency}'."
        ),
        status='SUCCESS'
    )

    # Step 6: Filter the base queryset by form + fic_mis_date
    base_queryset = filter_queryset_by_form(form, base_queryset).filter(fic_mis_date=fic_mis_date)
    logger.debug(f"Base queryset filtered with {base_queryset.count()} records remaining.")
    Log.objects.create(
        function_name='liquidity_gap_report_base',
        log_level='DEBUG',
        message=f"Base queryset filtered to {base_queryset.count()} records.",
        status='SUCCESS'
    )

    # Step 7: Prepare currency-specific data structure
    from collections import defaultdict
    currency_data = defaultdict(lambda: {
        'inflow_data': {},
        'outflow_data': {},
        'net_liquidity_gap': {},
        'net_gap_percentage': {},
        'cumulative_gap': {},
        'first_inflow_product': None,
        'remaining_inflow_data': {},
        'first_outflow_product': None,
        'remaining_outflow_data': {},
        'aggregated_product_details': None,
        'aggregated_split_details': None,
    })

    # Determine which currencies to iterate over
    if selected_currency:
        currencies = [selected_currency]
    else:
        currencies = base_queryset.values_list('v_ccy_code', flat=True).distinct()
    logger.info(f"Processing currencies: {list(currencies)}")
    Log.objects.create(
        function_name='liquidity_gap_report_base',
        log_level='INFO',
        message=f"Processing currencies: {list(currencies)}",
        status='SUCCESS'
    )

    # Step 8: Build currency-specific data
    for currency in currencies:
        currency_queryset = base_queryset.filter(v_ccy_code=currency)
        local_drill_down_qs = currency_queryset

        if drill_down_product:
            local_drill_down_qs = local_drill_down_qs.filter(v_prod_type=drill_down_product)
        if drill_down_splits:
            local_drill_down_qs = local_drill_down_qs.filter(v_product_name=drill_down_splits)

        # Aggregated drill-down logic
        local_aggregated_product_details = None
        local_aggregated_split_details = None

        # If drilling down by splits
        if drill_down_splits:
            drill_down_splits_details = list(
                local_drill_down_qs
                .values('v_product_splits', 'bucket_number')
                .annotate(
                    inflows_total=Sum('inflows'),
                    outflows_total=Sum('outflows'),
                    total=Sum(F('inflows') - F('outflows'))
                )
            )
            grouped_split_data = defaultdict(lambda: {b['bucket_number']: 0 for b in date_buckets})
            for detail in drill_down_splits_details:
                split_name = detail.get('v_product_splits')
                bucket_number = detail['bucket_number']
                grouped_split_data[split_name][bucket_number] += detail.get('total', 0)

            local_aggregated_split_details = [
                {
                    'v_product_splits': split_name,
                    'buckets': buckets,
                    'total': sum(buckets.values())
                }
                for split_name, buckets in grouped_split_data.items()
            ]

        # If drilling down by product
        elif drill_down_product:
            drill_down_details = list(
                local_drill_down_qs
                .values('v_product_name', 'bucket_number')
                .annotate(
                    inflows_total=Sum('inflows'),
                    outflows_total=Sum('outflows'),
                    total=Sum(F('inflows') - F('outflows'))
                )
            )
            grouped_data = defaultdict(lambda: {b['bucket_number']: 0 for b in date_buckets})
            for detail in drill_down_details:
                product_name = detail.get('v_product_name')
                bucket_number = detail['bucket_number']
                grouped_data[product_name][bucket_number] += detail.get('total', 0)

            local_aggregated_product_details = [
                {
                    'v_product_name': product_name,
                    'buckets': buckets,
                    'total': sum(buckets.values())
                }
                for product_name, buckets in grouped_data.items()
            ]

        # Prepare inflow/outflow data
        inflow_data, outflow_data = prepare_inflow_outflow_data(local_drill_down_qs)
        net_liquidity_gap, net_gap_percentage, cumulative_gap = calculate_totals(
            date_buckets, inflow_data, outflow_data
        )

        # Compute total for each product in inflow_data
        for product, buckets in inflow_data.items():
            inflow_data[product]['total'] = sum(
                buckets.get(b['bucket_number'], 0) for b in date_buckets
            )
        # Compute total for each product in outflow_data
        for product, buckets in outflow_data.items():
            outflow_data[product]['total'] = sum(
                buckets.get(b['bucket_number'], 0) for b in date_buckets
            )

        # Compute total for net_liquidity_gap
        net_liquidity_gap['total'] = sum(
            net_liquidity_gap.get(b['bucket_number'], 0) for b in date_buckets
        )
        # Compute total for net_gap_percentage
        net_gap_percentage['total'] = (
            sum(net_gap_percentage.get(b['bucket_number'], 0) for b in date_buckets) / len(date_buckets)
        ) if len(date_buckets) > 0 else 0

        # Compute total for cumulative_gap
        last_bucket = date_buckets.last()
        cumulative_gap['total'] = cumulative_gap.get(last_bucket['bucket_number'], 0) if last_bucket else 0

        # Identify first/remaining inflow product
        if inflow_data:
            first_inflow_product_key = list(inflow_data.keys())[0]
            first_inflow_product = (first_inflow_product_key, inflow_data[first_inflow_product_key])
            remaining_inflow_data = inflow_data.copy()
            remaining_inflow_data.pop(first_inflow_product_key, None)
        else:
            first_inflow_product = None
            remaining_inflow_data = {}

        # Identify first/remaining outflow product
        if outflow_data:
            first_outflow_product_key = list(outflow_data.keys())[0]
            first_outflow_product = (first_outflow_product_key, outflow_data[first_outflow_product_key])
            remaining_outflow_data = outflow_data.copy()
            remaining_outflow_data.pop(first_outflow_product_key, None)
        else:
            first_outflow_product = None
            remaining_outflow_data = {}

        # Update currency_data structure
        currency_data[currency].update({
            'inflow_data': inflow_data,
            'outflow_data': outflow_data,
            'first_inflow_product': first_inflow_product,
            'remaining_inflow_data': remaining_inflow_data,
            'first_outflow_product': first_outflow_product,
            'remaining_outflow_data': remaining_outflow_data,
            'net_liquidity_gap': net_liquidity_gap,
            'net_gap_percentage': net_gap_percentage,
            'cumulative_gap': cumulative_gap,
            'aggregated_product_details': local_aggregated_product_details,
            'aggregated_split_details': local_aggregated_split_details,
        })

        logger.debug(f"Processed currency='{currency}' in liquidity gap report with {len(inflow_data)} inflow items and {len(outflow_data)} outflow items.")
        Log.objects.create(
            function_name='liquidity_gap_report_base',
            log_level='DEBUG',
            message=(
                f"Processed currency='{currency}' with {len(inflow_data)} inflow items "
                f"and {len(outflow_data)} outflow items."
            ),
            status='SUCCESS'
        )

    # Prepare context for rendering
    context = {
        'form': form,
        'fic_mis_date': fic_mis_date,
        'date_buckets': date_buckets,
        'currency_data': dict(currency_data),
        'total_columns': len(date_buckets) + 3,
        'drill_down_product': drill_down_product,
        'drill_down_splits': drill_down_splits,
        'selected_currency': selected_currency,
    }

    logger.info("Finished building data for liquidity_gap_report_base. Rendering template.")
    Log.objects.create(
        function_name='liquidity_gap_report_base',
        log_level='INFO',
        message="Finished building data for liquidity_gap_report_base. Rendering template.",
        status='SUCCESS'
    )

    return render(request, 'ALM_APP/reports/liquidity_gap_report_base.html', context)


#######################



########################################################################################################################


logger = logging.getLogger(__name__)
@login_required
def liquidity_gap_report_cons(request):
    """
    View to display a consolidated Liquidity Gap Report. Reads from session and GET parameters
    to filter data. Produces a multi-currency view of inflows, outflows, net liquidity gaps,
    and optional drill-downs. Logs actions to the Log table but does not integrate audit trails.
    """
    logger.info("Accessed liquidity_gap_report_cons view.")
    Log.objects.create(
        function_name='liquidity_gap_report_cons',
        log_level='INFO',
        message="Accessed liquidity_gap_report_cons view.",
        status='SUCCESS'
    )

    # Step 1: Manage GET parameters and session-based filters
    if request.GET:
        logger.debug(f"Received GET parameters for liquidity_gap_report_cons: {request.GET}")
        Log.objects.create(
            function_name='liquidity_gap_report_cons',
            log_level='DEBUG',
            message=f"Received GET parameters: {request.GET}",
            status='SUCCESS'
        )

        session_filters = request.session.get('filters_cons', {})
        new_params = request.GET.dict()
        merged_filters = {**session_filters, **new_params}
        request.session['filters_cons'] = merged_filters
        filters = merged_filters
    else:
        filters = request.session.get('filters_cons', {})

    # Step 2: Initialize the form and cons_queryset
    form = LiquidityGapReportFilterForm_cons(filters or None)
    cons_queryset = LiquidityGapResultsCons.objects.all()
    logger.debug("Initialized LiquidityGapReportFilterForm_cons and base cons_queryset.")
    Log.objects.create(
        function_name='liquidity_gap_report_cons',
        log_level='DEBUG',
        message="Initialized LiquidityGapReportFilterForm_cons and base cons_queryset.",
        status='SUCCESS'
    )

    # Step 3: Determine fic_mis_date from the form or fallback to the latest
    if form.is_valid():
        fic_mis_date = form.cleaned_data.get('fic_mis_date')
    else:
        fic_mis_date = None

    if not fic_mis_date:
        fic_mis_date = get_latest_fic_mis_date()
        if not fic_mis_date:
            error_message = "No data available for the selected filters."
            logger.warning(error_message)
            Log.objects.create(
                function_name='liquidity_gap_report_cons',
                log_level='WARNING',
                message=error_message,
                status='SUCCESS'
            )
            messages.error(request, error_message)
            return render(request, 'ALM_APP/reports/liquidity_gap_report_cons.html', {'form': form})

    logger.debug(f"Using fic_mis_date='{fic_mis_date}' for liquidity gap report (consolidated).")
    Log.objects.create(
        function_name='liquidity_gap_report_cons',
        log_level='DEBUG',
        message=f"Using fic_mis_date='{fic_mis_date}' for report (consolidated).",
        status='SUCCESS'
    )

    # Step 4: Retrieve date buckets for fic_mis_date
    date_buckets = get_date_buckets(fic_mis_date)
    if not date_buckets.exists():
        error_message = "No date buckets available for the selected filters."
        logger.warning(error_message)
        Log.objects.create(
            function_name='liquidity_gap_report_cons',
            log_level='WARNING',
            message=error_message,
            status='SUCCESS'
        )
        messages.error(request, error_message)
        return render(request, 'ALM_APP/reports/liquidity_gap_report_cons.html', {'form': form})

    # Step 5: Drill-down parameters
    drill_down_product_cons = request.GET.get('drill_down_product_cons')
    drill_down_splits_cons = request.GET.get('drill_down_splits_cons')
    logger.debug(
        f"Drill-down params: product='{drill_down_product_cons}', splits='{drill_down_splits_cons}'."
    )
    Log.objects.create(
        function_name='liquidity_gap_report_cons',
        log_level='DEBUG',
        message=(
            f"Drill-down params: product='{drill_down_product_cons}', "
            f"splits='{drill_down_splits_cons}'."
        ),
        status='SUCCESS'
    )

    # Step 6: Filter the queryset
    cons_queryset = filter_queryset_by_form(form, cons_queryset).filter(fic_mis_date=fic_mis_date)
    logger.debug(f"Filtered cons_queryset to {cons_queryset.count()} records.")
    Log.objects.create(
        function_name='liquidity_gap_report_cons',
        log_level='DEBUG',
        message=f"Filtered cons_queryset to {cons_queryset.count()} records.",
        status='SUCCESS'
    )

    drill_down_details_cons = None
    drill_down_splits_details_cons = None
    aggregated_product_details_cons = None
    aggregated_split_details_cons = None

    # Step 7: Handle splits drill-down if specified
    if drill_down_splits_cons:
        drill_down_splits_details_cons = list(
            cons_queryset.filter(v_product_name=drill_down_splits_cons)
            .values('v_product_splits', 'bucket_number')
            .annotate(
                inflows_total=Sum('inflows'),
                outflows_total=Sum('outflows'),
                total=Sum(F('inflows') - F('outflows'))
            )
        )
        grouped_split_data_cons = defaultdict(lambda: {bucket['bucket_number']: 0 for bucket in date_buckets})
        for detail in drill_down_splits_details_cons:
            split_name = detail.get('v_product_splits')
            bucket_number = detail['bucket_number']
            grouped_split_data_cons[split_name][bucket_number] += detail.get('total', 0)

        aggregated_split_details_cons = [
            {
                'v_product_splits': split_name,
                'buckets': buckets,
                'total': sum(buckets.values())
            }
            for split_name, buckets in grouped_split_data_cons.items()
        ]

    # Step 8: Handle product drill-down if specified
    elif drill_down_product_cons:
        drill_down_details_cons = list(
            cons_queryset.filter(v_prod_type=drill_down_product_cons)
            .values('v_product_name', 'bucket_number')
            .annotate(
                inflows_total=Sum('inflows'),
                outflows_total=Sum('outflows'),
                total=Sum(F('inflows') - F('outflows'))
            )
        )
        grouped_data_cons = defaultdict(lambda: {bucket['bucket_number']: 0 for bucket in date_buckets})
        for detail in drill_down_details_cons:
            product_name = detail.get('v_product_name')
            bucket_number = detail['bucket_number']
            grouped_data_cons[product_name][bucket_number] += detail.get('total', 0)

        aggregated_product_details_cons = [
            {
                'v_product_name': product_name,
                'buckets': buckets,
                'total': sum(buckets.values())
            }
            for product_name, buckets in grouped_data_cons.items()
        ]

    # Step 9: Prepare inflow and outflow data
    cons_inflow_data, cons_outflow_data = prepare_inflow_outflow_data(cons_queryset)
    cons_net_liquidity_gap, cons_net_gap_percentage, cons_cumulative_gap = calculate_totals(
        date_buckets, cons_inflow_data, cons_outflow_data
    )

    # Extract first and remaining inflow data
    if cons_inflow_data:
        cons_first_inflow_product = list(cons_inflow_data.items())[0]
        cons_remaining_inflow_data = cons_inflow_data.copy()
        cons_remaining_inflow_data.pop(cons_first_inflow_product[0], None)
    else:
        cons_first_inflow_product = None
        cons_remaining_inflow_data = {}

    # Extract first and remaining outflow data
    if cons_outflow_data:
        cons_first_outflow_product = list(cons_outflow_data.items())[0]
        cons_remaining_outflow_data = cons_outflow_data.copy()
        cons_remaining_outflow_data.pop(cons_first_outflow_product[0], None)
    else:
        cons_first_outflow_product = None
        cons_remaining_outflow_data = {}

    cons_data = {
        'inflow_data': cons_inflow_data,
        'outflow_data': cons_outflow_data,
        'first_inflow_product': cons_first_inflow_product,
        'remaining_inflow_data': cons_remaining_inflow_data,
        'first_outflow_product': cons_first_outflow_product,
        'remaining_outflow_data': cons_remaining_outflow_data,
        'net_liquidity_gap': cons_net_liquidity_gap,
        'net_gap_percentage': cons_net_gap_percentage,
        'cumulative_gap': cons_cumulative_gap,
    }

    logger.debug(f"Prepared consolidated data for liquidity gap: {cons_data}")
    # Do not log the entire structure if it's too large, for brevity we do minimal logs
    Log.objects.create(
        function_name='liquidity_gap_report_cons',
        log_level='DEBUG',
        message=f"Prepared consolidated data for liquidity gap (keys: {list(cons_data.keys())}).",
        status='SUCCESS'
    )

    # Optional sub-drill data
    drill_cons_data = None
    if drill_down_product_cons or drill_down_splits_cons:
        if drill_down_product_cons:
            drill_queryset = cons_queryset.filter(v_prod_type=drill_down_product_cons)
        elif drill_down_splits_cons:
            drill_queryset = cons_queryset.filter(v_product_name=drill_down_splits_cons)

        drill_inflow_data, drill_outflow_data = prepare_inflow_outflow_data(drill_queryset)
        drill_net_liquidity_gap, drill_net_gap_percentage, drill_cumulative_gap = calculate_totals(
            date_buckets, drill_inflow_data, drill_outflow_data
        )

        drill_cons_data = {
            'inflow_data': drill_inflow_data,
            'outflow_data': drill_outflow_data,
            'net_liquidity_gap': drill_net_liquidity_gap,
            'net_gap_percentage': drill_net_gap_percentage,
            'cumulative_gap': drill_cumulative_gap,
        }
        logger.debug("Prepared drill-down data for consolidated liquidity gap report.")
        Log.objects.create(
            function_name='liquidity_gap_report_cons',
            log_level='DEBUG',
            message="Prepared drill-down data for consolidated liquidity gap report.",
            status='SUCCESS'
        )

    # Extract distinct currencies
    currency_data = cons_queryset.values_list('v_ccy_code', flat=True).distinct()
    logger.debug(f"Extracted currency data for consolidated report: {list(currency_data)}")
    Log.objects.create(
        function_name='liquidity_gap_report_cons',
        log_level='DEBUG',
        message=f"Extracted currency data: {list(currency_data)}",
        status='SUCCESS'
    )

    context = {
        'form': form,
        'fic_mis_date': fic_mis_date,
        'date_buckets': date_buckets,
        'currency_data': currency_data,
        'cons_data': cons_data,
        'drill_cons_data': drill_cons_data,
        'total_columns': len(date_buckets) + 3,
        'drill_down_product_cons': drill_down_product_cons,
        'drill_down_splits_cons': drill_down_splits_cons,
        'aggregated_product_details_cons': aggregated_product_details_cons,
        'aggregated_split_details_cons': aggregated_split_details_cons,
    }

    logger.info("Rendering liquidity_gap_report_cons template with consolidated data.")
    Log.objects.create(
        function_name='liquidity_gap_report_cons',
        log_level='INFO',
        message="Rendering liquidity_gap_report_cons template with consolidated data.",
        status='SUCCESS'
    )

    return render(request, 'ALM_APP/reports/liquidity_gap_report_cons.html', context)




















# def liquidity_gap_report(request):
#     # Initialize the form with GET parameters
#     form = LiquidityGapReportFilterForm(request.GET or None)

#     # Start with the full queryset for base and consolidated results
#     base_queryset = LiquidityGapResultsBase.objects.all()
#     cons_queryset = LiquidityGapResultsCons.objects.all()

#     # Get fic_mis_date from the form or fallback to the latest date in Dim_Dates
#     fic_mis_date = form.cleaned_data.get(
#         'fic_mis_date') if form.is_valid() else None
#     if not fic_mis_date:
#         fic_mis_date = get_latest_fic_mis_date()
#         if not fic_mis_date:
#             messages.error(
#                 request, "No data available for the selected filters.")
#             return render(request, 'ALM_APP/reports/liquidity_gap_report.html', {'form': form})

#     # Get date buckets for fic_mis_date
#     date_buckets = get_date_buckets(fic_mis_date)
#     if not date_buckets.exists():
#         messages.error(
#             request, "No date buckets available for the selected filters.")
#         return render(request, 'ALM_APP/reports/liquidity_gap_report.html', {'form': form})

#     # Check if this is a drill-down request for product or splits
#     drill_down_product = request.GET.get('drill_down_product', None)
#     drill_down_splits = request.GET.get('drill_down_splits', None)
#     drill_down_product_cons = request.GET.get('drill_down_product_cons', None)
#     drill_down_splits_cons = request.GET.get('drill_down_splits_cons', None)

#     # Filter base and consolidated querysets by form fields
#     base_queryset = filter_queryset_by_form(
#         form, base_queryset).filter(fic_mis_date=fic_mis_date)
#     cons_queryset = filter_queryset_by_form(
#         form, cons_queryset).filter(fic_mis_date=fic_mis_date)

#     # Prepare drill-down details for products or splits on cons and base
#     drill_down_details = None
#     drill_down_splits_details = None
#     aggregated_product_details = None
#     aggregated_split_details = None

#     drill_down_details_cons = None
#     drill_down_splits_details_cons = None
#     aggregated_product_details_cons = None
#     aggregated_split_details_cons = None

#     if drill_down_splits:  # Drill-down for splits
#         drill_down_splits_details = list(
#             base_queryset.filter(v_product_name=drill_down_splits)
#             .values('v_product_splits', 'bucket_number')
#             .annotate(
#                 inflows_total=Sum('inflows'),
#                 outflows_total=Sum('outflows'),
#                 total=Sum(F('inflows') - F('outflows'))
#             )
#         )

#         # Group data by product splits and bucket
#         grouped_split_data = defaultdict(
#             lambda: {bucket['bucket_number']: 0 for bucket in date_buckets})
#         for detail in drill_down_splits_details:
#             # Get product split name
#             split_name = detail.get('v_product_splits')
#             bucket_number = detail['bucket_number']  # Get bucket number
#             # Aggregate figures by bucket
#             grouped_split_data[split_name][bucket_number] += detail.get(
#                 'total', 0)

#         # Convert grouped data into a list for the template
#         aggregated_split_details = [
#             {
#                 'v_product_splits': split_name,  # Include split name
#                 'buckets': buckets,              # Figures grouped by buckets
#                 'total': sum(buckets.values())   # Total for the product split
#             }
#             for split_name, buckets in grouped_split_data.items()
#         ]

#     elif drill_down_product:  # Drill-down for product names
#         drill_down_details = list(
#             base_queryset.filter(v_prod_type=drill_down_product)
#             .values('v_product_name', 'bucket_number')
#             .annotate(
#                 inflows_total=Sum('inflows'),
#                 outflows_total=Sum('outflows'),
#                 total=Sum(F('inflows') - F('outflows'))
#             )
#         )

#         # Group data by product name and bucket
#         grouped_data = defaultdict(
#             lambda: {bucket['bucket_number']: 0 for bucket in date_buckets})
#         for detail in drill_down_details:
#             product_name = detail.get('v_product_name')  # Get product name
#             bucket_number = detail['bucket_number']  # Get bucket number
#             # Aggregate figures by bucket
#             grouped_data[product_name][bucket_number] += detail.get('total', 0)

#         # Convert grouped data into a list for the template
#         aggregated_product_details = [
#             {
#                 'v_product_name': product_name,  # Include product name
#                 'buckets': buckets,              # Figures grouped by buckets
#                 'total': sum(buckets.values())   # Total for the product name
#             }
#             for product_name, buckets in grouped_data.items()
#         ]

#     if drill_down_splits_cons:  # Drill-down for splits in cons
#         drill_down_splits_details_cons = list(
#             cons_queryset.filter(v_product_name=drill_down_splits_cons)
#             .values('v_product_splits', 'bucket_number')
#             .annotate(
#                 inflows_total=Sum('inflows'),
#                 outflows_total=Sum('outflows'),
#                 total=Sum(F('inflows') - F('outflows'))
#             )
#         )

#         grouped_split_data_cons = defaultdict(
#             lambda: {bucket['bucket_number']: 0 for bucket in date_buckets})
#         for detail in drill_down_splits_details_cons:
#             split_name = detail.get('v_product_splits')
#             bucket_number = detail['bucket_number']
#             grouped_split_data_cons[split_name][bucket_number] += detail.get(
#                 'total', 0)

#         aggregated_split_details_cons = [
#             {
#                 'v_product_splits': split_name,
#                 'buckets': buckets,
#                 'total': sum(buckets.values())
#             }
#             for split_name, buckets in grouped_split_data_cons.items()
#         ]

#     elif drill_down_product_cons:  # Drill-down for product names in cons
#         drill_down_details_cons = list(
#             cons_queryset.filter(v_prod_type=drill_down_product_cons)
#             .values('v_product_name', 'bucket_number')
#             .annotate(
#                 inflows_total=Sum('inflows'),
#                 outflows_total=Sum('outflows'),
#                 total=Sum(F('inflows') - F('outflows'))
#             )
#         )

#         grouped_data_cons = defaultdict(
#             lambda: {bucket['bucket_number']: 0 for bucket in date_buckets})
#         for detail in drill_down_details_cons:
#             product_name = detail.get('v_product_name')
#             bucket_number = detail['bucket_number']
#             grouped_data_cons[product_name][bucket_number] += detail.get(
#                 'total', 0)

#         aggregated_product_details_cons = [
#             {
#                 'v_product_name': product_name,
#                 'buckets': buckets,
#                 'total': sum(buckets.values())
#             }
#             for product_name, buckets in grouped_data_cons.items()
#         ]

#     # Prepare base results
#     currency_data = defaultdict(lambda: {
#         'inflow_data': {}, 'outflow_data': {},
#         'net_liquidity_gap': {}, 'net_gap_percentage': {}, 'cumulative_gap': {},
#         'first_inflow_product': None, 'remaining_inflow_data': {},
#         'first_outflow_product': None, 'remaining_outflow_data': {}
#     })

#     currencies = base_queryset.values_list('v_ccy_code', flat=True).distinct()
#     for currency in currencies:
#         # Filter by currency
#         currency_queryset = base_queryset.filter(v_ccy_code=currency)

#         if drill_down_product:
#             currency_queryset = currency_queryset.filter(
#                 v_prod_type=drill_down_product)
#         if drill_down_splits:
#             currency_queryset = currency_queryset.filter(
#                 v_product_name=drill_down_splits)

#         inflow_data, outflow_data = prepare_inflow_outflow_data(
#             currency_queryset)

#         net_liquidity_gap, net_gap_percentage, cumulative_gap = calculate_totals(
#             date_buckets, inflow_data, outflow_data)

#         for product, buckets in inflow_data.items():
#             inflow_data[product]['total'] = sum(buckets.get(
#                 bucket['bucket_number'], 0) for bucket in date_buckets)

#         for product, buckets in outflow_data.items():
#             outflow_data[product]['total'] = sum(buckets.get(
#                 bucket['bucket_number'], 0) for bucket in date_buckets)

#         net_liquidity_gap['total'] = sum(net_liquidity_gap.get(
#             bucket['bucket_number'], 0) for bucket in date_buckets)
#         net_gap_percentage['total'] = (
#             sum(net_gap_percentage.get(bucket['bucket_number'], 0)
#                 for bucket in date_buckets) / len(date_buckets)
#         ) if len(date_buckets) > 0 else 0

#         last_bucket = date_buckets.last()
#         cumulative_gap['total'] = cumulative_gap.get(
#             last_bucket['bucket_number'], 0) if last_bucket else 0

#         if inflow_data:
#             first_inflow_product = list(inflow_data.items())[0]
#             remaining_inflow_data = inflow_data.copy()
#             remaining_inflow_data.pop(first_inflow_product[0], None)
#         else:
#             first_inflow_product = None
#             remaining_inflow_data = {}

#         if outflow_data:
#             first_outflow_product = list(outflow_data.items())[0]
#             remaining_outflow_data = outflow_data.copy()
#             remaining_outflow_data.pop(first_outflow_product[0], None)
#         else:
#             first_outflow_product = None
#             remaining_outflow_data = {}

#         currency_data[currency].update({
#             'inflow_data': inflow_data,
#             'outflow_data': outflow_data,
#             'first_inflow_product': first_inflow_product,
#             'remaining_inflow_data': remaining_inflow_data,
#             'first_outflow_product': first_outflow_product,
#             'remaining_outflow_data': remaining_outflow_data,
#             'net_liquidity_gap': net_liquidity_gap,
#             'net_gap_percentage': net_gap_percentage,
#             'cumulative_gap': cumulative_gap,
#         })

#     cons_inflow_data, cons_outflow_data = prepare_inflow_outflow_data(
#         cons_queryset)
#     cons_net_liquidity_gap, cons_net_gap_percentage, cons_cumulative_gap = calculate_totals(
#         date_buckets, cons_inflow_data, cons_outflow_data
#     )

#     if cons_inflow_data:
#         cons_first_inflow_product = list(cons_inflow_data.items())[0]
#         cons_remaining_inflow_data = cons_inflow_data.copy()
#         cons_remaining_inflow_data.pop(cons_first_inflow_product[0], None)
#     else:
#         cons_first_inflow_product = None
#         cons_remaining_inflow_data = {}

#     if cons_outflow_data:
#         cons_first_outflow_product = list(cons_outflow_data.items())[0]
#         cons_remaining_outflow_data = cons_outflow_data.copy()
#         cons_remaining_outflow_data.pop(cons_first_outflow_product[0], None)
#     else:
#         cons_first_outflow_product = None
#         cons_remaining_outflow_data = {}

#     cons_data = {
#         'inflow_data': cons_inflow_data,
#         'outflow_data': cons_outflow_data,
#         'first_inflow_product': cons_first_inflow_product,
#         'remaining_inflow_data': cons_remaining_inflow_data,
#         'first_outflow_product': cons_first_outflow_product,
#         'remaining_outflow_data': cons_remaining_outflow_data,
#         'net_liquidity_gap': cons_net_liquidity_gap,
#         'net_gap_percentage': cons_net_gap_percentage,
#         'cumulative_gap': cons_cumulative_gap,
#     }

#     print("Consolidated Data:", cons_data)

#     context = {
#         'form': form,
#         'fic_mis_date': fic_mis_date,
#         'date_buckets': date_buckets,
#         'currency_data': dict(currency_data),
#         'cons_data': cons_data,
#         'total_columns': len(date_buckets) + 3,
#         'drill_down_product': drill_down_product,
#         'drill_down_splits': drill_down_splits,
#         'drill_down_product_cons': drill_down_product_cons,
#         'drill_down_splits_cons': drill_down_splits_cons,
#         'aggregated_product_details': aggregated_product_details,
#         'aggregated_split_details': aggregated_split_details,
#         'aggregated_product_details_cons': aggregated_product_details_cons,
#         'aggregated_split_details_cons': aggregated_split_details_cons
#     }

#     return render(request, 'ALM_APP/reports/liquidity_gap_report.html', context)



##########################################################################################################################
@login_required

def export_liquidity_gap_to_excel(request):
    form = LiquidityGapReportFilterForm(request.GET or None)

    # Parse fic_mis_date from request
    raw_fic_mis_date = request.GET.get('fic_mis_date')
    fic_mis_date = parse_date(raw_fic_mis_date)

    if not fic_mis_date:
        return HttpResponseBadRequest(
            "Invalid date format. Supported formats: 'Aug. 31, 2024', 'August 31, 2024', "
            "'2024-08-31', '31-08-2024', '31/08/2024', '08/31/2024'."
        )

    # Base queryset filtered by fic_mis_date
    queryset = LiquidityGapResultsBase.objects.filter(fic_mis_date=fic_mis_date)
    queryset = filter_queryset_by_form(form, queryset)

    # Handle drill-down parameters
    drill_down_product = request.GET.get('drill_down_product')
    drill_down_splits = request.GET.get('drill_down_splits')

    if drill_down_product:
        queryset = queryset.filter(v_prod_type=drill_down_product)
    if drill_down_splits:
        queryset = queryset.filter(v_product_name=drill_down_splits)

    # Get date buckets
    date_buckets = get_date_buckets(fic_mis_date)
    if not date_buckets.exists():
        return HttpResponseBadRequest("No date buckets available for the selected date.")

    # Prepare headers based on drill-down level
    headers = ["Account Type", "Product"]
    if drill_down_splits:
        headers += ["v_product_name", "v_product_splits"]
    elif drill_down_product:
        headers += ["v_product_name"]

    headers += [
        f"{bucket['bucket_start_date'].strftime('%d-%b-%Y')} to {bucket['bucket_end_date'].strftime('%d-%b-%Y')}"
        for bucket in date_buckets
    ] + ["Total"]

    # Style definitions
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="3B5998", end_color="3B5998", fill_type="solid")
    border = Border(
        left=Side(border_style="thin"), right=Side(border_style="thin"),
        top=Side(border_style="thin"), bottom=Side(border_style="thin")
    )
    alignment_center = Alignment(horizontal="center", vertical="center")
    heading_font = Font(bold=True, size=14)

    # Overview scenario: separate sheets per currency
    if not drill_down_product and not drill_down_splits:
        # Group data by currency (v_ccy_code) and product type
        details = queryset.values('v_ccy_code', 'v_prod_type', 'bucket_number').annotate(
            total=Sum(F('inflows') - F('outflows'))
        )
        currency_grouped = defaultdict(lambda: defaultdict(lambda: {bucket['bucket_number']: 0 for bucket in date_buckets}))
        for detail in details:
            currency = detail['v_ccy_code']  # Use v_ccy_code instead of currency
            prod_type = detail['v_prod_type']
            bucket_number = detail['bucket_number']
            currency_grouped[currency][prod_type][bucket_number] += detail.get('total', 0)

        # Initialize workbook and remove the default sheet
        workbook = Workbook()
        default_sheet = workbook.active
        workbook.remove(default_sheet)

        # Create a sheet for each currency
        for currency, products in currency_grouped.items():
            sheet = workbook.create_sheet(title=str(currency))
            total_columns = len(headers)

            # Dynamic heading for this currency sheet
            sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_columns)
            heading_cell = sheet.cell(row=1, column=1)
            heading_cell.value = f"Overview Report for {currency} on {fic_mis_date}"
            heading_cell.font = heading_font
            heading_cell.alignment = alignment_center

            # Write headers in row 2
            for col_num, header in enumerate(headers, 1):
                cell = sheet.cell(row=2, column=col_num)
                cell.value = header
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = alignment_center
                cell.border = border

            # Write aggregated data rows starting from row 3
            row_num = 3
            for prod_type, buckets in products.items():
                account_type = "Total Inflow" if sum(buckets.values()) >= 0 else "Total Outflow"
                row_prefix = [account_type, prod_type]
                row_data = row_prefix + [
                    buckets.get(bucket['bucket_number'], 0) for bucket in date_buckets
                ] + [sum(buckets.values())]

                for col_num, value in enumerate(row_data, 1):
                    cell = sheet.cell(row=row_num, column=col_num)
                    cell.value = value
                    cell.alignment = alignment_center
                    cell.border = border
                row_num += 1

            # Compute summary rows for the current currency
            currency_qs = queryset.filter(v_ccy_code=currency)  # Filter by current currency
            inflow_data_cur, outflow_data_cur = prepare_inflow_outflow_data(currency_qs)
            net_liquidity_gap_cur, net_gap_percentage_cur, cumulative_gap_cur = calculate_totals(
                date_buckets, inflow_data_cur, outflow_data_cur
            )

            total_outflows_cur = sum(outflow_data_cur.get(bucket['bucket_number'], 0) for bucket in date_buckets)
            net_liquidity_gap_total_cur = sum(net_liquidity_gap_cur.get(bucket['bucket_number'], 0) for bucket in date_buckets)
            cumulative_gap_total_cur = sum(net_liquidity_gap_cur.get(bucket['bucket_number'], 0) for bucket in date_buckets)
            net_gap_percentage_total_cur = (net_liquidity_gap_total_cur / total_outflows_cur * 100) if total_outflows_cur else 0

            prefix_count = 2
            summary_rows = [
                ("Net Liquidity Gap", net_liquidity_gap_cur, net_liquidity_gap_total_cur),
                ("Net Gap as % of Total Outflows", net_gap_percentage_cur, net_gap_percentage_total_cur),
                ("Cumulative Gap", cumulative_gap_cur, cumulative_gap_total_cur),
            ]
            for label, summary_data, summary_total in summary_rows:
                row = [label] + [""] * (prefix_count - 1)
                row += [summary_data.get(bucket['bucket_number'], 0) for bucket in date_buckets]
                row.append(summary_total)

                for col_num, value in enumerate(row, 1):
                    cell = sheet.cell(row=row_num, column=col_num)
                    cell.value = value
                    cell.font = Font(bold=True)
                    cell.alignment = alignment_center
                    cell.border = border
                row_num += 1

            # Auto-adjust column widths for this sheet
            for col in sheet.iter_cols(min_row=2, max_row=sheet.max_row, min_col=1, max_col=sheet.max_column):
                max_length = 0
                for cell in col:
                    if cell.value and not isinstance(cell, openpyxl.cell.cell.MergedCell):
                        max_length = max(max_length, len(str(cell.value)))
                col_letter = get_column_letter(col[0].column)
                sheet.column_dimensions[col_letter].width = max_length + 2

        # Save and return the workbook for overview scenario
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response['Content-Disposition'] = f'attachment; filename="LiquidityGapReport_Overview_{fic_mis_date}.xlsx"'
        workbook.save(response)
        return response

    # Non-overview (drill-down) scenarios
    grouped_data = defaultdict(lambda: {bucket['bucket_number']: 0 for bucket in date_buckets})

    if drill_down_splits:
        details = queryset.values('v_product_splits', 'bucket_number').annotate(
            total=Sum(F('inflows') - F('outflows'))
        )
        for detail in details:
            split_name = detail['v_product_splits']
            bucket_number = detail['bucket_number']
            grouped_data[split_name][bucket_number] += detail.get('total', 0)
        aggregated_data = [
            {'identifier': split_name, 'buckets': buckets, 'total': sum(buckets.values())}
            for split_name, buckets in grouped_data.items()
        ]
    elif drill_down_product:
        details = queryset.values('v_product_name', 'bucket_number').annotate(
            total=Sum(F('inflows') - F('outflows'))
        )
        for detail in details:
            product_name = detail['v_product_name']
            bucket_number = detail['bucket_number']
            grouped_data[product_name][bucket_number] += detail.get('total', 0)
        aggregated_data = [
            {'identifier': product_name, 'buckets': buckets, 'total': sum(buckets.values())}
            for product_name, buckets in grouped_data.items()
        ]
    else:
        details = queryset.values('v_prod_type', 'bucket_number').annotate(
            total=Sum(F('inflows') - F('outflows'))
        )
        for detail in details:
            prod_type = detail['v_prod_type']
            bucket_number = detail['bucket_number']
            grouped_data[prod_type][bucket_number] += detail.get('total', 0)
        aggregated_data = [
            {'identifier': prod_type, 'buckets': buckets, 'total': sum(buckets.values())}
            for prod_type, buckets in grouped_data.items()
        ]

    # Calculate totals for summary rows for non-overview
    inflow_data, outflow_data = prepare_inflow_outflow_data(queryset)
    net_liquidity_gap, net_gap_percentage, cumulative_gap = calculate_totals(
        date_buckets, inflow_data, outflow_data
    )

    total_outflows = sum(outflow_data.get(bucket['bucket_number'], 0) for bucket in date_buckets)
    net_liquidity_gap_total = sum(net_liquidity_gap.get(bucket['bucket_number'], 0) for bucket in date_buckets)
    cumulative_gap_total = sum(cumulative_gap.get(bucket['bucket_number'], 0) for bucket in date_buckets)
    net_gap_percentage_total = (net_liquidity_gap_total / total_outflows * 100) if total_outflows else 0

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Liquidity Gap Report"

    # Determine dynamic heading based on drill-down level
    if drill_down_splits:
        heading_text = f"Drill-Down Report for Split: {drill_down_splits} on {fic_mis_date}"
    elif drill_down_product:
        heading_text = f"Drill-Down Report for Product: {drill_down_product} on {fic_mis_date}"
    else:
        heading_text = f"Overview Report for {fic_mis_date}"

    total_columns = len(headers)
    sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_columns)
    heading_cell = sheet.cell(row=1, column=1)
    heading_cell.value = heading_text
    heading_cell.font = heading_font
    heading_cell.alignment = alignment_center

    # Write headers for non-overview
    sheet.append(headers)
    for col_num, header in enumerate(headers, 1):
        cell = sheet.cell(row=2, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = alignment_center
        cell.border = border

    # Write aggregated data rows for non-overview
    row_num = 3
    for item in aggregated_data:
        if drill_down_splits:
            row_prefix = ["Total Flows", drill_down_product, drill_down_splits, item['identifier']]
        elif drill_down_product:
            row_prefix = ["Total Flows", drill_down_product, item['identifier']]
        else:
            account_type = "Total Inflow" if item['total'] >= 0 else "Total Outflow"
            row_prefix = [account_type, item['identifier']]

        row = row_prefix + [
            item['buckets'].get(bucket['bucket_number'], 0) for bucket in date_buckets
        ] + [item['total']]

        for col_num, value in enumerate(row, 1):
            cell = sheet.cell(row=row_num, column=col_num)
            cell.value = value
            cell.alignment = alignment_center
            cell.border = border
        row_num += 1

    if drill_down_splits:
        prefix_count = 4
    elif drill_down_product:
        prefix_count = 3
    else:
        prefix_count = 2

    summary_rows = [
        ("Net Liquidity Gap", net_liquidity_gap, net_liquidity_gap_total),
        ("Net Gap as % of Total Outflows", net_gap_percentage, net_gap_percentage_total),
        ("Cumulative Gap", cumulative_gap, cumulative_gap_total),
    ]

    for label, summary_data, summary_total in summary_rows:
        row = [label] + [""] * (prefix_count - 1)
        row += [summary_data.get(bucket['bucket_number'], 0) for bucket in date_buckets]
        row.append(summary_total)

        for col_num, value in enumerate(row, 1):
            cell = sheet.cell(row=row_num, column=col_num)
            cell.value = value
            cell.font = Font(bold=True)
            cell.alignment = alignment_center
            cell.border = border
        row_num += 1

    for col in sheet.iter_cols(min_row=2, max_row=sheet.max_row, min_col=1, max_col=sheet.max_column):
        max_length = 0
        for cell in col:
            if cell.value and not isinstance(cell, openpyxl.cell.cell.MergedCell):
                max_length = max(max_length, len(str(cell.value)))
        col_letter = get_column_letter(col[0].column)
        sheet.column_dimensions[col_letter].width = max_length + 2

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response['Content-Disposition'] = f'attachment; filename="LiquidityGapReport_{fic_mis_date}.xlsx"'
    workbook.save(response)
    return response







########################################################################################################################################################################
def parse_date(date_str):
    """
    Parse the date string to handle multiple formats.
    """
    date_formats = [
        "%b. %d, %Y",    # 'Aug. 31, 2024'
        "%B %d, %Y",     # 'August 31, 2024'
        "%Y-%m-%d",      # '2024-08-31'
        "%d-%m-%Y",      # '31-08-2024'
        "%d/%m/%Y",      # '31/08/2024'
        "%m/%d/%Y"       # '08/31/2024'
    ]
    for date_format in date_formats:
        try:
            return datetime.strptime(date_str, date_format).date()
        except ValueError:
            continue
    return None




#################################################################################################################################


@login_required
def export_liquidity_gap_cons_to_excel(request):

    form = LiquidityGapReportFilterForm_cons(request.GET or None)

    # Parse fic_mis_date from request
    raw_fic_mis_date = request.GET.get('fic_mis_date')
    fic_mis_date = parse_date(raw_fic_mis_date)

    if not fic_mis_date:
        return HttpResponseBadRequest(
            "Invalid date format. Supported formats: 'Aug. 31, 2024', 'August 31, 2024', "
            "'2024-08-31', '31-08-2024', '31/08/2024', '08/31/2024'."
        )

    # Base queryset filtered by fic_mis_date
    queryset = LiquidityGapResultsCons.objects.filter(fic_mis_date=fic_mis_date)
    queryset = filter_queryset_by_form(form, queryset)

    # Handle drill-down parameters
    drill_down_product_cons = request.GET.get('drill_down_product_cons')
    drill_down_splits_cons = request.GET.get('drill_down_splits_cons')

    if drill_down_product_cons:
        queryset = queryset.filter(v_prod_type=drill_down_product_cons)
    if drill_down_splits_cons:
        queryset = queryset.filter(v_product_name=drill_down_splits_cons)

    # Get date buckets
    date_buckets = get_date_buckets(fic_mis_date)
    if not date_buckets.exists():
        return HttpResponseBadRequest("No date buckets available for the selected date.")

    # Prepare headers based on drill-down level
    headers = ["Account Type", "Product"]
    if drill_down_splits_cons:
        headers += ["v_product_name", "v_product_splits"]
    elif drill_down_product_cons:
        headers += ["v_product_name"]

    # Extend headers with bucket date ranges and Total column
    headers += [
        f"{bucket['bucket_start_date'].strftime('%d-%b-%Y')} to {bucket['bucket_end_date'].strftime('%d-%b-%Y')}"
        for bucket in date_buckets
    ] + ["Total"]

    # Prepare data for the current drill-down level
    grouped_data = defaultdict(lambda: {bucket['bucket_number']: 0 for bucket in date_buckets})

    if drill_down_splits_cons:
        details = queryset.values('v_product_splits', 'bucket_number').annotate(
            total=Sum(F('inflows') - F('outflows'))
        )
        for detail in details:
            split_name = detail['v_product_splits']
            bucket_number = detail['bucket_number']
            grouped_data[split_name][bucket_number] += detail.get('total', 0)

        aggregated_data = [
            {
                'identifier': split_name,
                'buckets': buckets,
                'total': sum(buckets.values())
            }
            for split_name, buckets in grouped_data.items()
        ]
    elif drill_down_product_cons:
        details = queryset.values('v_product_name', 'bucket_number').annotate(
            total=Sum(F('inflows') - F('outflows'))
        )
        for detail in details:
            product_name = detail['v_product_name']
            bucket_number = detail['bucket_number']
            grouped_data[product_name][bucket_number] += detail.get('total', 0)

        aggregated_data = [
            {
                'identifier': product_name,
                'buckets': buckets,
                'total': sum(buckets.values())
            }
            for product_name, buckets in grouped_data.items()
        ]
    else:
        # Overview level: Group by v_prod_type when no drill-down filters are applied
        details = queryset.values('v_prod_type', 'bucket_number').annotate(
            total=Sum(F('inflows') - F('outflows'))
        )
        for detail in details:
            prod_type = detail['v_prod_type']
            bucket_number = detail['bucket_number']
            grouped_data[prod_type][bucket_number] += detail.get('total', 0)

        aggregated_data = [
            {
                'identifier': prod_type,
                'buckets': buckets,
                'total': sum(buckets.values())
            }
            for prod_type, buckets in grouped_data.items()
        ]

    # Calculate totals for summary rows
    inflow_data, outflow_data = prepare_inflow_outflow_data(queryset)
    net_liquidity_gap, net_gap_percentage, cumulative_gap = calculate_totals(
        date_buckets, inflow_data, outflow_data
    )

    total_outflows = sum(outflow_data.get(bucket['bucket_number'], 0) for bucket in date_buckets)
    net_liquidity_gap_total = sum(net_liquidity_gap.get(bucket['bucket_number'], 0) for bucket in date_buckets)
    cumulative_gap_total = sum(net_liquidity_gap.get(bucket['bucket_number'], 0) for bucket in date_buckets)
    if total_outflows:
        net_gap_percentage_total = (net_liquidity_gap_total / total_outflows) * 100
    else:
        net_gap_percentage_total = 0

    # Initialize workbook and sheet
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Liquidity Gap Report"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="3B5998", end_color="3B5998", fill_type="solid")
    border = Border(
        left=Side(border_style="thin"),
        right=Side(border_style="thin"),
        top=Side(border_style="thin"),
        bottom=Side(border_style="thin")
    )
    alignment_center = Alignment(horizontal="center", vertical="center")
    heading_font = Font(bold=True, size=14)

    # Determine dynamic heading based on drill-down level
    if drill_down_splits_cons:
        heading_text = f"Drill-Down Report for Split: {drill_down_splits_cons} on {fic_mis_date}"
    elif drill_down_product_cons:
        heading_text = f"Drill-Down Report for Product: {drill_down_product_cons} on {fic_mis_date}"
    else:
        heading_text = f"Overview Report for {fic_mis_date}"

    total_columns = len(headers)
    sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_columns)
    heading_cell = sheet.cell(row=1, column=1)
    heading_cell.value = heading_text
    heading_cell.font = heading_font
    heading_cell.alignment = alignment_center

    # Write headers
    sheet.append(headers)
    for col_num, header in enumerate(headers, 1):
        cell = sheet.cell(row=2, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = alignment_center
        cell.border = border

    # Write aggregated data rows
    row_num = 3
    for item in aggregated_data:
        if drill_down_splits_cons:
            row_prefix = ["Total Flows", drill_down_product_cons, drill_down_splits_cons, item['identifier']]
        elif drill_down_product_cons:
            row_prefix = ["Total Flows", drill_down_product_cons, item['identifier']]
        else:
            # For overview, determine account type based on total and use v_prod_type as product
            account_type = "Total Inflow" if item['total'] >= 0 else "Total Outflow"
            row_prefix = [account_type, item['identifier']]

        row = row_prefix + [
            item['buckets'].get(bucket['bucket_number'], 0) for bucket in date_buckets
        ] + [item['total']]

        for col_num, value in enumerate(row, 1):
            cell = sheet.cell(row=row_num, column=col_num)
            cell.value = value
            cell.alignment = alignment_center
            cell.border = border
        row_num += 1

    # Determine fixed prefix column count based on drill-down level
    if drill_down_splits_cons:
        prefix_count = 4
    elif drill_down_product_cons:
        prefix_count = 3
    else:
        prefix_count = 2

    summary_rows = [
        ("Net Liquidity Gap", net_liquidity_gap, net_liquidity_gap_total),
        ("Net Gap as % of Total Outflows", net_gap_percentage, net_gap_percentage_total),
        ("Cumulative Gap", cumulative_gap, cumulative_gap_total),
    ]

    # Write summary rows aligned with the rest of the data
    for label, summary_data, summary_total in summary_rows:
        row = [label] + [""] * (prefix_count - 1)
        row += [summary_data.get(bucket['bucket_number'], 0) for bucket in date_buckets]
        row.append(summary_total)

        for col_num, value in enumerate(row, 1):
            cell = sheet.cell(row=row_num, column=col_num)
            cell.value = value
            cell.font = Font(bold=True)
            cell.alignment = alignment_center
            cell.border = border
        row_num += 1

    # Auto-adjust column widths
    for col in sheet.iter_cols(min_row=2, max_row=sheet.max_row, min_col=1, max_col=sheet.max_column):
        max_length = 0
        for cell in col:
            if cell.value and not isinstance(cell, openpyxl.cell.cell.MergedCell):
                max_length = max(max_length, len(str(cell.value)))
        col_letter = get_column_letter(col[0].column)
        sheet.column_dimensions[col_letter].width = max_length + 2

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response['Content-Disposition'] = f'attachment; filename="LiquidityGapReport_Cons_{fic_mis_date}.xlsx"'
    workbook.save(response)
    return response

















# from django.shortcuts import render
# from .models import LiquidityGapResultsBase, Dim_Dates
# from .forms import LiquidityGapReportFilterForm
# from django.db.models import Sum
# from django.contrib import messages  # Import for user messages
# from datetime import date

# def liquidity_gap_report(request):
#     # Initialize the form with GET parameters
#     form = LiquidityGapReportFilterForm(request.GET or None)

#     # Start with the full queryset
#     queryset = LiquidityGapResultsBase.objects.all()

#     # Apply filters if they are provided
#     fic_mis_date = None
#     if form.is_valid():
#         process_name = form.cleaned_data.get('process_name')
#         fic_mis_date = form.cleaned_data.get('fic_mis_date')
#         v_ccy_code = form.cleaned_data.get('v_ccy_code')
#         account_type = form.cleaned_data.get('account_type')
#         bucket_number = form.cleaned_data.get('bucket_number')

#         if process_name:
#             queryset = queryset.filter(process_name=process_name)
#         if fic_mis_date:
#             queryset = queryset.filter(fic_mis_date=fic_mis_date)
#         if v_ccy_code:
#             queryset = queryset.filter(v_ccy_code=v_ccy_code)
#         if account_type:
#             queryset = queryset.filter(account_type=account_type)
#         if bucket_number:
#             queryset = queryset.filter(bucket_number=bucket_number)

#     # Fallback to the latest fic_mis_date in Dim_Dates if fic_mis_date is not set
#     if not fic_mis_date:
#         try:
#             fic_mis_date = Dim_Dates.objects.latest('fic_mis_date').fic_mis_date
#         except Dim_Dates.DoesNotExist:
#             messages.error(request, "No data available for the selected filters.")
#             return render(request, 'ALM_APP/reports/liquidity_gap_report.html', {'form': form})

#     # Filter Dim_Dates by fic_mis_date for date buckets
#     date_buckets = Dim_Dates.objects.filter(fic_mis_date=fic_mis_date).values(
#         'bucket_number', 'bucket_start_date', 'bucket_end_date'
#     ).distinct().order_by('bucket_number')

#     # Check if no date buckets found
#     if not date_buckets.exists():
#         messages.error(request, "No date buckets available for the selected filters.")
#         return render(request, 'ALM_APP/reports/liquidity_gap_report.html', {'form': form})

#     # Further filter LiquidityGapResultsBase by fic_mis_date if it's not None
#     queryset = queryset.filter(fic_mis_date=fic_mis_date)

#     # Separate inflows and outflows, grouped by product type and bucket number
#     inflow_products = queryset.filter(account_type="Inflow").values('v_prod_type', 'bucket_number').annotate(total=Sum('inflows'))
#     outflow_products = queryset.filter(account_type="Outflow").values('v_prod_type', 'bucket_number').annotate(total=Sum('outflows'))

#     # Prepare data structure for inflows and outflows
#     inflow_data = {}
#     outflow_data = {}

#     for item in inflow_products:
#         prod_type = item['v_prod_type']
#         bucket = item['bucket_number']
#         total = item['total']
#         if prod_type not in inflow_data:
#             inflow_data[prod_type] = {}
#         inflow_data[prod_type][bucket] = total

#     for item in outflow_products:
#         prod_type = item['v_prod_type']
#         bucket = item['bucket_number']
#         total = item['total']
#         if prod_type not in outflow_data:
#             outflow_data[prod_type] = {}
#         outflow_data[prod_type][bucket] = total

#     # Get the first item of inflow and outflow data for easy access in the template
#     first_inflow_product, remaining_inflow_data = None, inflow_data.copy()
#     first_outflow_product, remaining_outflow_data = None, outflow_data.copy()

#     if inflow_data:
#         first_inflow_product = list(inflow_data.items())[0]
#         remaining_inflow_data.pop(first_inflow_product[0], None)

#     if outflow_data:
#         first_outflow_product = list(outflow_data.items())[0]
#         remaining_outflow_data.pop(first_outflow_product[0], None)

#     # Calculate total inflows and total outflows by bucket
#     total_inflows_by_bucket = {}
#     total_outflows_by_bucket = {}

#     for bucket in date_buckets:
#         bucket_number = bucket['bucket_number']
#         total_inflows_by_bucket[bucket_number] = sum(inflow_data.get(prod, {}).get(bucket_number, 0) for prod in inflow_data)
#         total_outflows_by_bucket[bucket_number] = sum(outflow_data.get(prod, {}).get(bucket_number, 0) for prod in outflow_data)

#     # Calculate Net Liquidity Gap, Net Gap as % of Total Outflows, and Cumulative Gap
#     net_liquidity_gap = {bucket: total_inflows_by_bucket[bucket] - total_outflows_by_bucket[bucket] for bucket in total_inflows_by_bucket}
#     net_gap_percentage = {bucket: (net_liquidity_gap[bucket] / total_outflows_by_bucket[bucket] * 100) if total_outflows_by_bucket[bucket] else 0 for bucket in total_outflows_by_bucket}

#     cumulative_gap = {}
#     cumulative_total = 0
#     for bucket in date_buckets:
#         bucket_number = bucket['bucket_number']
#         cumulative_total += net_liquidity_gap[bucket_number]
#         cumulative_gap[bucket_number] = cumulative_total

#     # Calculate total columns (date buckets + 2 for "Account Type" and "Product")
#     total_columns = len(date_buckets) + 2

#     # Prepare context for rendering in the template
#     context = {
#         'form': form,
#         'fic_mis_date': fic_mis_date,
#         'date_buckets': date_buckets,
#         'first_inflow_product': first_inflow_product,
#         'remaining_inflow_data': remaining_inflow_data,
#         'first_outflow_product': first_outflow_product,
#         'remaining_outflow_data': remaining_outflow_data,
#         'currency_code': "BWP",  # Example currency code
#         'total_columns': total_columns,  # Pass the total column count to the template
#         'net_liquidity_gap': net_liquidity_gap,
#         'net_gap_percentage': net_gap_percentage,
#         'cumulative_gap': cumulative_gap,
#     }

#     return render(request, 'ALM_APP/reports/liquidity_gap_report.html', context)


# View to project cash flows based on the fic_mis_date parameter
@login_required
def project_cash_flows_view(request):
    process_name = 'time bucket'
    fic_mis_date = '2024-08-31'
    # status = populate_dim_dates_from_time_buckets(fic_mis_date)
    # status=populate_dim_product(fic_mis_date)
    status= aggregate_by_prod_code(fic_mis_date, process_name)
    # status=update_date(fic_mis_date)
    # status = populate_liquidity_gap_results_base(fic_mis_date, process_name)
    # status= calculate_time_buckets_and_spread(process_name, fic_mis_date)
    # status= aggregate_cashflows_to_product_level(fic_mis_date)

    # status=execute_alm_process_logic(process_name, fic_mis_date)


    

    # status= project_cash_flows(fic_mis_date)



    print(status)
    # project_cash_flows(fic_mis_date)
    return render(request, 'ALM_APP/project_cash_flows.html')

@login_required
def dashboard_view(request):
    # Example data for financial graphs
    mis_date = '2024-07-31'  # Input date in 'YYYY-MM-DD' format
    # perform_interpolation(mis_date)
    # project_cash_flows(mis_date)
    # update_cash_flows_with_ead(mis_date)
    # # #Insert records into FCT_Stage_Determination with the numeric date
    # insert_fct_stage(mis_date)
    # # #determine stage
    # update_stage(mis_date)
    # process_cooling_period_for_accounts(mis_date)
    # update_stage_determination(mis_date)
    # update_stage_determination_accrued_interest_and_ead(mis_date)
    # update_stage_determination_eir(mis_date)
    # update_lgd_for_stage_determination_term_structure(mis_date)
    # calculate_pd_for_accounts(mis_date)
    # insert_cash_flow_data(mis_date)
    # update_financial_cash_flow(mis_date)
    # update_cash_flow_with_pd_buckets(mis_date)
    # update_marginal_pd(mis_date)
    # calculate_expected_cash_flow(mis_date)
    # calculate_discount_factors(mis_date)
    # calculate_cashflow_fields(mis_date)
    # calculate_forward_loss_fields(mis_date)
    # populate_fct_reporting_lines(mis_date)
    # calculate_ecl_based_on_method(mis_date)
    # update_reporting_lines_with_exchange_rate(mis_date)

    return render(request, 'ALM_home.html')


@login_required
def ALM_home_view(request):
    context = {
        'title': ' Home',
        # You can pass any additional context if needed
    }
    return render(request, 'ALM_home.html', context)

from datetime import datetime
import logging
from pyexpat.errors import messages
import traceback
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from ALM_APP.Functions import populate_liquidity_gap_results_base
from ALM_APP.Functions.Aggregated_Acc_level_cashflows import calculate_behavioral_pattern_distribution, calculate_time_buckets_and_spread
from ALM_APP.Functions.Aggregated_Prod_Cashflow_Base import aggregate_by_prod_code
from ALM_APP.Functions.Dim_dates import populate_dim_dates_from_time_buckets
from ALM_APP.Functions.populate_dim import populate_dim_product
from ALM_APP.Functions.process_utils import finalize_process_creation, finalize_process_update
from ALM_APP.Functions.product_filter_utils import create_or_update_filter, delete_filter
from ALM_APP.forms import *
from ALM_APP.models import *
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, CreateView, UpdateView

from User.models import AuditTrail





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


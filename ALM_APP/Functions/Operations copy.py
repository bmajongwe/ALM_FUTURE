import traceback
from django.shortcuts import render, get_object_or_404, redirect
from django.forms import inlineformset_factory
from django.db import transaction
import threading
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import Process_Rn, RunProcess,Function,FunctionExecutionStatus
from ..forms import ProcessFormOp, RunProcessForm
from django.db import transaction
from django.db.models import Q
from django.db.models import Count
from django.http import Http404, JsonResponse
from django.template.loader import render_to_string
from django.db.models import Max
from django.db.models import Min
from datetime import datetime, timedelta
from django.utils import timezone
from django.utils.module_loading import import_string  # Used for dynamic function calling
import sys
from ..Functions.cashflow import *
from ..Functions.Aggregated_Prod_Cashflow_Base import *
from ..Functions.populate_liquidity_gap_results_base import *
from ..Functions.ldn_update import *
from ..Functions.aggregate_cashflows import *
from ..Functions.Aggregated_Acc_level_cashflows import *
from ..Functions.behavioral_pattern_utils import define_behavioral_pattern_from_form_data, delete_behavioral_pattern_by_id, update_behavioral_pattern_from_form_data
from ..Functions.time_bucket_utils import define_time_bucket_from_form_data, update_time_bucket_from_form_data, delete_time_bucket_by_id
from ..Functions.populate_dim import populate_dim_product
from ..Functions.Dim_dates import *
from ..Functions.product_filter_utils import *
from ..Functions.process_utils import *
from ..Functions.cashflow import *
from ..Functions.data import *
from ..Functions.Operations import *
from User.models import  AuditTrail  # Import custom models for logging and auditing
from ..models import  Log  # Import custom models for logging and auditing
from django.db.models import Min, Max







logger = logging.getLogger(__name__)

@login_required
def operations_view(request):
    try:
        logger.info(f"User {request.user} accessed the operations view.")
        return render(request, 'operations/operations.html')
    except Exception as e:
        logger.exception(f"Error rendering operations view: {e}")
        messages.error(request, "An error occurred while loading the operations page.")
        return redirect('home')  # Adjust the redirection target as needed




# List all processes

logger = logging.getLogger(__name__)

@login_required
def process_list(request):
    try:
        processes = Process_Rn.objects.all()
        logger.info(f"User {request.user} retrieved process list.")
        return render(request, 'operations/process_list.html', {'processes': processes})
    except Exception as e:
        logger.exception(f"Error retrieving process list: {e}")
        messages.error(request, "There was an error retrieving the list of processes.")
        return redirect('home')  # Adjust the redirection target as needed


######################################################################################################

# View the details of a specific process, including its associated functions and execution order
logger = logging.getLogger(__name__)

@login_required
def process_detail(request, process_id):
    try:
        process = get_object_or_404(Process_Rn, id=process_id)
        run_processes = RunProcess.objects.filter(process=process).order_by('order')
        
        # Log that the process detail was successfully accessed
        logger.info(f"User {request.user} accessed details for process {process_id}.")
        
        return render(request, 'operations/process_detail.html', {
            'process': process,
            'run_processes': run_processes
        })
    except Exception as e:
        # Log the error and show an error message to the user
        logger.exception(f"Error retrieving details for process {process_id}: {e}")
        messages.error(request, "There was an error retrieving the process details.")
        return redirect('process_list')


####################################################################################################################
logger = logging.getLogger(__name__)

@login_required
def create_process(request, process_id=None):
    """
    View to add or edit a process and its corresponding run processes.
    If process_id is provided, it's an edit; otherwise, it's an add.
    """
    RunProcessFormSet = inlineformset_factory(
        Process_Rn, RunProcess, form=RunProcessForm, extra=1, can_delete=True
    )
    
    process = Process_Rn()
    form_title = 'Create Process'

    if request.method == 'POST':
        form = ProcessFormOp(request.POST, instance=process)
        formset = RunProcessFormSet(request.POST)

        logger.debug("Formset POST Data: %s", request.POST)

        # Validate both form and formset before processing
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    process = form.save()
                    logger.info("Process saved: %s", process)

                    # Create an audit trail entry for the process creation
                    AuditTrail.objects.create(
                        user=request.user,
                        user_name=request.user.name if request.user else '',
                        user_surname=request.user.surname if request.user else '',
                        model_name="Process_Rn",
                        action="create",
                        object_id=str(process.id),
                        change_description=f"Created process with ID {process.id} and name {process}"
                    )

                    # Initialize counter for auto-incrementing order
                    current_order = 1

                    # Iterate over each subform in the formset
                    for subform in formset.forms:
                        if subform.cleaned_data and not subform.cleaned_data.get('DELETE', False):
                            functions = request.POST.getlist(subform.add_prefix('function'))
                            orders = request.POST.getlist(subform.add_prefix('order'))

                            logger.debug("Processing subform: functions=%s, orders=%s", functions, orders)

                            if len(functions) == len(orders):
                                for function_id, order in zip(functions, orders):
                                    if function_id:
                                        function_instance = Function.objects.get(pk=function_id)
                                        # Auto-increment order if not provided
                                        if not order:
                                            order = current_order
                                            current_order += 1
                                        RunProcess.objects.create(
                                            process=process,
                                            function=function_instance,
                                            order=order
                                        )
                                        logger.info("Saved: function=%s, order=%s", function_instance, order)
                            else:
                                function_instance = subform.cleaned_data.get('function')
                                order = subform.cleaned_data.get('order')
                                if function_instance:
                                    # Auto-increment order if not provided
                                    if not order:
                                        order = current_order
                                        current_order += 1
                                    RunProcess.objects.create(
                                        process=process,
                                        function=function_instance,
                                        order=order
                                    )
                                    logger.info("Saved single: function=%s, order=%s", function_instance, order)

                    messages.success(request, 'Process created successfully.')

                    # Log a successful creation event
                    Log.objects.create(
                        function_name='create_process',
                        log_level='INFO',
                        message=f"Process {process.id} created successfully by {request.user}.",
                        status='SUCCESS'
                    )

                    return redirect('process_list')
            except Exception as e:
                error_details = traceback.format_exc()  # Capture full stack trace as a string
                messages.error(request, f"Error saving process: {str(e)}")
                logger.exception("Error saving process")

                # Log the error occurrence
                Log.objects.create(
                    function_name='create_process',
                    log_level='ERROR',
                    detailed_error=error_details,  # Store detailed error info including stack trace
                    message=str(e),
                    status='FAILURE'
                )
        else:
            logger.error("Form Errors: %s", form.errors)
            logger.error("Formset Errors: %s", formset.errors)
            messages.error(request, "Please correct the errors below.")
    else:
        form = ProcessFormOp(instance=process)
        formset = RunProcessFormSet(instance=process)

    return render(request, 'operations/create_process.html', {
        'form': form,
        'formset': formset,
        'title': form_title,
        'filters': []
    })



######################################################################################################

logger = logging.getLogger(__name__)

@login_required
def edit_process(request, process_id):
    """
    View to edit an existing process and its corresponding run processes.
    """
    RunProcessFormSet = inlineformset_factory(
        Process_Rn,
        RunProcess,
        form=RunProcessForm,
        extra=1,
        can_delete=True,
    )

    process = get_object_or_404(Process_Rn, id=process_id)
    form_title = "Edit Process"

    if request.method == "POST":
        form = ProcessFormOp(request.POST, instance=process)
        formset = RunProcessFormSet(request.POST, instance=process)

        logger.debug("Edit Form POST Data: %s", request.POST)
        logger.debug("Edit Form Errors: %s", form.errors)
        logger.debug("Edit Formset Errors: %s", formset.errors)

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    process = form.save(commit=False)
                    process.save()

                    formset.save()

                    # Create an audit trail entry for the process update
                    AuditTrail.objects.create(
                        user=request.user,
                        user_name=request.user.name if request.user else '',
                        user_surname=request.user.surname if request.user else '',
                        model_name="Process_Rn",
                        action="update",
                        object_id=str(process.id),
                        change_description=f"Updated process with ID {process.id}"
                    )

                    messages.success(request, "Process updated successfully.")

                    Log.objects.create(
                        function_name='edit_process',
                        log_level='INFO',
                        message=f"Process {process.id} updated successfully by {request.user}.",
                        status='SUCCESS'
                    )

                    return redirect("process_list")
            except Exception as e:
                error_details = traceback.format_exc()
                messages.error(request, f"Error updating process: {str(e)}")
                logger.exception("Error updating process")
                Log.objects.create(
                    function_name='edit_process',
                    log_level='ERROR',
                    message=str(e),
                    detailed_error=error_details,
                    status='FAILURE'
                )
        else:
            messages.error(
                request,
                "There were errors in the form. Please correct them and try again.",
            )
    else:
        form = ProcessFormOp(instance=process)
        formset = RunProcessFormSet(instance=process)

    return render(
        request,
        "operations/edit_process.html",
        {
            "form": form,
            "formset": formset,
            "title": form_title,
            "process": process,
        },
    )


##################################################################################################################
logger = logging.getLogger(__name__)

@login_required
def delete_process(request, process_id):
    try:
        process_id = int(process_id)  # Ensure process_id is an integer
    except ValueError:
        raise Http404("Invalid process ID")

    process = get_object_or_404(Process_Rn, id=process_id)

    if request.method == 'POST':
        try:
            process.delete()
            messages.success(request, 'Process deleted successfully.')

            # Create an audit trail entry for the deletion
            AuditTrail.objects.create(
                user=request.user,
                user_name=request.user.name if request.user else '',
                user_surname=request.user.surname if request.user else '',
                model_name="Process_Rn",
                action="delete",
                object_id=str(process_id),
                change_description=f"Deleted process with ID {process_id}"
            )

            # Log a successful deletion event
            Log.objects.create(
                function_name='delete_process',
                log_level='INFO',
                message=f"Process {process_id} deleted successfully by {request.user}.",
                status='SUCCESS'
            )

        except Exception as e:
            error_details = traceback.format_exc()
            messages.error(request, f'Error deleting process: {e}')

            # Log the error occurrence
            Log.objects.create(
                function_name='delete_process',
                log_level='ERROR',
                message=str(e),
                detailed_error=error_details,
                status='FAILURE'
            )
        return redirect('process_list')

    return render(request, 'operations/delete_process.html', {'process': process})

##############################################################################################3
# Display and search for processes
@login_required
def execute_process_view(request):
    query = request.GET.get('search', '')
    processes = Process_Rn.objects.filter(Q(process_name__icontains=query))

    return render(request, 'operations/execute_process.html', {
        'processes': processes,
        'query': query,
    })

# Handle execution
# Function to generate the process run ID and count

running_threads = {}
cancel_flags = {}


def generate_process_run_id(process, execution_date):
    """
    Generate a process_run_id in the format 'process_id_execution_date_run_number'.
    """
    # Format the execution date as YYYYMMDD
    execution_date_str = execution_date.strftime('%Y%m%d')
    
    # Base run ID: process_id + execution_date
    base_run_id = f"{process.process_name}_{execution_date_str}"
    
    # Check the database for existing entries with the same base_run_id
    existing_runs = FunctionExecutionStatus.objects.filter(process_run_id__startswith=base_run_id).order_by('-run_count')
    
    # Determine the next run count
    if existing_runs.exists():
        last_run_count = existing_runs[0].run_count
        next_run_count = last_run_count + 1
    else:
        next_run_count = 1
    
    # Generate the full process_run_id with the next run count
    process_run_id = f"{base_run_id}_{next_run_count}"
    
    return process_run_id, next_run_count



###############################################################################################################



# Background function for running the process
# Background function for running the process
logger = logging.getLogger(__name__)



def execute_functions_in_background(function_status_entries, process_run_id, mis_date, execution_log):
    try:
        for status_entry in function_status_entries:
            if cancel_flags.get(process_run_id):  # Check if cancellation was requested
                status_entry.status = 'Cancelled'
                status_entry.execution_end_date = timezone.now()
                status_entry.duration = status_entry.execution_end_date - status_entry.execution_start_date
                status_entry.save()
                logger.info(f"Process {process_run_id} was cancelled.")

                execution_log.end_time = timezone.now()
                execution_log.status = 'CANCELLED'
                execution_log.details = "Process was cancelled."
                execution_log.save()
                break  # Stop execution if cancelled

            function_name = status_entry.function.function_name
            logger.info(f"Preparing to execute function: {function_name}")

            # Set the function status to "Ongoing" and record the start date
            status_entry.status = 'Ongoing'
            status_entry.execution_start_date = timezone.now()  # Start time for the function
            status_entry.save()
            logger.info(f"Function {function_name} marked as Ongoing.")

            # Execute the function
            try:
                if function_name in globals():
                    logger.info(f"Executing function: {function_name} with date {mis_date}")
                    result = globals()[function_name](mis_date)  # Execute the function and capture the return value

                    # Update status and end date based on the return value
                    status_entry.execution_end_date = timezone.now()  # End time for the function
                    if result == 1 or result == '1':
                        status_entry.status = 'Success'
                        logger.info(f"Function {function_name} executed successfully.")
                    elif result == 0 or result == '0':
                        status_entry.status = 'Failed'
                        logger.error(f"Function {function_name} execution failed.")
                        status_entry.save()

                        # Log the failure
                        Log.objects.create(
                            function_name=function_name,
                            log_level='ERROR',
                            message=f"Function {function_name} failed to execute.",
                            detailed_error="Execution returned 0 or failure status.",
                            status='FAILURE'
                        )
                        break  # Stop execution if the function fails
                    else:
                        status_entry.status = 'Failed'
                        logger.error(f"Unexpected return value {result} from function {function_name}.")
                        status_entry.save()

                        # Log the unexpected return
                        Log.objects.create(
                            function_name=function_name,
                            log_level='ERROR',
                            message=f"Unexpected return value {result} from function {function_name}.",
                            detailed_error=f"Return value: {result}",
                            status='FAILURE'
                        )
                        break  # Stop execution for any unexpected result
                else:
                    status_entry.status = 'Failed'
                    logger.error(f"Function {function_name} not found in the global scope.")
                    status_entry.execution_end_date = timezone.now()
                    status_entry.save()

                    # Log the missing function
                    Log.objects.create(
                        function_name=function_name,
                        log_level='ERROR',
                        message=f"Function {function_name} not found in the global scope.",
                        detailed_error="Function is not defined in the global namespace.",
                        status='FAILURE'
                    )
                    break  # Stop execution if the function is not found

            except Exception as e:
                status_entry.status = 'Failed'
                status_entry.execution_end_date = timezone.now()
                logger.exception(f"Error executing {function_name}: {e}")
                status_entry.save()

                # Log the error during execution
                Log.objects.create(
                    function_name=function_name,
                    log_level='ERROR',
                    message=f"Error executing {function_name}: {e}",
                    detailed_error=traceback.format_exc(),
                    status='FAILURE'
                )

                execution_log.end_time = timezone.now()
                execution_log.status = 'FAILED'
                execution_log.details = str(e)
                execution_log.save()
                break  # Stop execution if any function throws an exception

            # Calculate duration
            if status_entry.execution_start_date and status_entry.execution_end_date:
                status_entry.duration = status_entry.execution_end_date - status_entry.execution_start_date

            # Save the final status and duration
            status_entry.save()
            logger.info(f"Updated FunctionExecutionStatus for {function_name} to {status_entry.status}")

    except Exception as outer_e:
        logger.exception(f"Unexpected error in execute_functions_in_background: {outer_e}")
        Log.objects.create(
            function_name='execute_functions_in_background',
            log_level='ERROR',
            message=f"Unexpected error in execution: {outer_e}",
            detailed_error=traceback.format_exc(),
            status='FAILURE'
        )
        execution_log.end_time = timezone.now()
        execution_log.status = 'FAILED'
        execution_log.details = str(outer_e)
        execution_log.save()
    else:
        # If loop completes without break, mark execution as successful
        execution_log.end_time = timezone.now()
        execution_log.status = 'SUCCESS'
        execution_log.details = "All functions executed successfully."
        execution_log.save()



@login_required
def run_process_execution(request):
    if request.method == 'POST':
        try:
            process_id = request.POST.get('process_id')
            selected_function_ids = request.POST.getlist('selected_functions')
            
            # Parse the execution date
            mis_date = request.POST.get('execution_date')
            execution_date = datetime.strptime(mis_date, '%Y-%m-%d')
            logger.info(f"Execution date received: {mis_date}")
            
            # Retrieve the selected process
            process = get_object_or_404(Process_Rn, id=process_id)
            logger.info(f"Process selected: {process.process_name} (ID: {process.id})")
            
            # Fetch the RunProcess records in order of their execution (by 'order' field)
            run_processes = RunProcess.objects.filter(process=process).order_by('order')
            logger.info(f"Number of selected functions to execute: {run_processes.count()}")

            # Generate the process_run_id and run_count
            process_run_id, run_count = generate_process_run_id(process, execution_date)
            logger.info(f"Generated process_run_id: {process_run_id}, run_count: {run_count}")

            # Save all functions as "Pending"
            function_status_entries = []
            for run_process in run_processes:
                status_entry = FunctionExecutionStatus.objects.create(
                    process=process,
                    function=run_process.function,
                    reporting_date=mis_date,  # Use the original string date for the execution status
                    status='Pending',  # Initially marked as "Pending"
                    process_run_id=process_run_id,
                    run_count=run_count,
                    execution_order=run_process.order
                )
                function_status_entries.append(status_entry)
                logger.info(f"Function {run_process.function.function_name} marked as Pending.")

            # Redirect to the monitoring page so the user can see the function statuses
            response = redirect('monitor_specific_process', process_run_id=process_run_id)

            # Create a new execution log entry
            execution_log = ProcessExecutionLog.objects.create(
                process=process,
                user=request.user,
                user_name=request.user.name if request.user else '',
                user_surname=request.user.surname if request.user else '',
                start_time=timezone.now(),
                status='RUNNING'
            )

            # Execute functions in the background (thread)
            execution_thread = threading.Thread(
                target=execute_functions_in_background, 
                args=(function_status_entries, process_run_id, mis_date, execution_log)
            )
            execution_thread.start()

            return response  # Redirects immediately while the background task executes

        except Exception as e:
            logger.exception(f"Error in run_process_execution: {e}")
            messages.error(request, "An error occurred while starting the process execution.")
            return redirect('process_list')
        

        
# def execute_functions_in_background(function_status_entries, process_run_id, mis_date, execution_log):
#     try:
#         for status_entry in function_status_entries:
#             if cancel_flags.get(process_run_id):  # Check if cancellation was requested
#                 status_entry.status = 'Cancelled'
#                 status_entry.execution_end_date = timezone.now()
#                 status_entry.duration = status_entry.execution_end_date - status_entry.execution_start_date
#                 status_entry.save()
#                 logger.info(f"Process {process_run_id} was cancelled.")

#                 execution_log.end_time = timezone.now()
#                 execution_log.status = 'CANCELLED'
#                 execution_log.details = "Process was cancelled."
#                 execution_log.save()
#                 break  # Stop execution if cancelled

#             function_name = status_entry.function.function_name
#             logger.info(f"Preparing to execute function: {function_name}")

#             # Set the function status to "Ongoing" and record the start date
#             status_entry.status = 'Ongoing'
#             status_entry.execution_start_date = timezone.now()  # Start time for the function
#             status_entry.save()
#             logger.info(f"Function {function_name} marked as Ongoing.")

#             # Execute the function
#             try:
#                 if function_name in globals():
#                     logger.info(f"Executing function: {function_name} with date {mis_date}")
#                     result = globals()[function_name](mis_date)  # Execute the function and capture the return value

#                     # Update status and end date based on the return value
#                     status_entry.execution_end_date = timezone.now()  # End time for the function
#                     if result == 1 or result == '1':
#                         status_entry.status = 'Success'
#                         logger.info(f"Function {function_name} executed successfully.")
#                     elif result == 0 or result == '0':
#                         status_entry.status = 'Failed'
#                         logger.error(f"Function {function_name} execution failed.")
#                         status_entry.save()

#                         # Log the failure
#                         Log.objects.create(
#                             function_name=function_name,
#                             log_level='ERROR',
#                             message=f"Function {function_name} failed to execute.",
#                             detailed_error="Execution returned 0 or failure status.",
#                             status='FAILURE'
#                         )
#                         break  # Stop execution if the function fails
#                     else:
#                         status_entry.status = 'Failed'
#                         logger.error(f"Unexpected return value {result} from function {function_name}.")
#                         status_entry.save()

#                         # Log the unexpected return
#                         Log.objects.create(
#                             function_name=function_name,
#                             log_level='ERROR',
#                             message=f"Unexpected return value {result} from function {function_name}.",
#                             detailed_error=f"Return value: {result}",
#                             status='FAILURE'
#                         )
#                         break  # Stop execution for any unexpected result
#                 else:
#                     status_entry.status = 'Failed'
#                     logger.error(f"Function {function_name} not found in the global scope.")
#                     status_entry.execution_end_date = timezone.now()
#                     status_entry.save()

#                     # Log the missing function
#                     Log.objects.create(
#                         function_name=function_name,
#                         log_level='ERROR',
#                         message=f"Function {function_name} not found in the global scope.",
#                         detailed_error="Function is not defined in the global namespace.",
#                         status='FAILURE'
#                     )
#                     break  # Stop execution if the function is not found

#             except Exception as e:
#                 status_entry.status = 'Failed'
#                 status_entry.execution_end_date = timezone.now()
#                 logger.exception(f"Error executing {function_name}: {e}")
#                 status_entry.save()

#                 # Log the error during execution
#                 Log.objects.create(
#                     function_name=function_name,
#                     log_level='ERROR',
#                     message=f"Error executing {function_name}: {e}",
#                     detailed_error=traceback.format_exc(),
#                     status='FAILURE'
#                 )

#                 execution_log.end_time = timezone.now()
#                 execution_log.status = 'FAILED'
#                 execution_log.details = str(e)
#                 execution_log.save()
#                 break  # Stop execution if any function throws an exception

#             # Calculate duration
#             if status_entry.execution_start_date and status_entry.execution_end_date:
#                 status_entry.duration = status_entry.execution_end_date - status_entry.execution_start_date

#             # Save the final status and duration
#             status_entry.save()
#             logger.info(f"Updated FunctionExecutionStatus for {function_name} to {status_entry.status}")

#     except Exception as outer_e:
#         logger.exception(f"Unexpected error in execute_functions_in_background: {outer_e}")
#         Log.objects.create(
#             function_name='execute_functions_in_background',
#             log_level='ERROR',
#             message=f"Unexpected error in execution: {outer_e}",
#             detailed_error=traceback.format_exc(),
#             status='FAILURE'
#         )
#         execution_log.end_time = timezone.now()
#         execution_log.status = 'FAILED'
#         execution_log.details = str(outer_e)
#         execution_log.save()
#     else:
#         # If loop completes without break, mark execution as successful
#         execution_log.end_time = timezone.now()
#         execution_log.status = 'SUCCESS'
#         execution_log.details = "All functions executed successfully."
#         execution_log.save()



# @login_required
# def run_process_execution(request):
#     if request.method == 'POST':
#         try:
#             process_id = request.POST.get('process_id')
#             selected_function_ids = request.POST.getlist('selected_functions')
            
#             # Parse the execution date
#             mis_date = request.POST.get('execution_date')
#             execution_date = datetime.strptime(mis_date, '%Y-%m-%d')
#             logger.info(f"Execution date received: {mis_date}")
            
#             # Retrieve the selected process
#             process = get_object_or_404(Process_Rn, id=process_id)
#             logger.info(f"Process selected: {process.process_name} (ID: {process.id})")
            
#             # Fetch the RunProcess records in order of their execution (by 'order' field)
#             run_processes = RunProcess.objects.filter(process=process).order_by('order')
#             logger.info(f"Number of selected functions to execute: {run_processes.count()}")

#             # Generate the process_run_id and run_count
#             process_run_id, run_count = generate_process_run_id(process, execution_date)
#             logger.info(f"Generated process_run_id: {process_run_id}, run_count: {run_count}")

#             # Save all functions as "Pending"
#             function_status_entries = []
#             for run_process in run_processes:
#                 status_entry = FunctionExecutionStatus.objects.create(
#                     process=process,
#                     function=run_process.function,
#                     reporting_date=mis_date,  # Use the original string date for the execution status
#                     status='Pending',  # Initially marked as "Pending"
#                     process_run_id=process_run_id,
#                     run_count=run_count,
#                     execution_order=run_process.order
#                 )
#                 function_status_entries.append(status_entry)
#                 logger.info(f"Function {run_process.function.function_name} marked as Pending.")

#             # Redirect to the monitoring page so the user can see the function statuses
#             response = redirect('monitor_specific_process', process_run_id=process_run_id)

#             # Create a new execution log entry
#             execution_log = ProcessExecutionLog.objects.create(
#                 process=process,
#                 user=request.user,
#                 user_name=request.user.name if request.user else '',
#                 user_surname=request.user.surname if request.user else '',
#                 start_time=timezone.now(),
#                 status='RUNNING'
#             )

#             # Execute functions in the background (thread)
#             execution_thread = threading.Thread(
#                 target=execute_functions_in_background, 
#                 args=(function_status_entries, process_run_id, mis_date, execution_log)
#             )
#             execution_thread.start()

#             return response  # Redirects immediately while the background task executes

#         except Exception as e:
#             logger.exception(f"Error in run_process_execution: {e}")
#             messages.error(request, "An error occurred while starting the process execution.")
#             return redirect('process_list')

        ###########################################################################################################

@login_required
def get_process_functions(request, process_id):
    process = get_object_or_404(Process_Rn, id=process_id)
    functions_html = render_to_string('operations/_functions_list.html', {'run_processes': process.run_processes.all()})
    return JsonResponse({'html': functions_html})

####################################################################################################################

# Monitor running process page
@login_required
def monitor_running_process_view(request):
    # Fetch distinct reporting dates and order by date descending
    available_dates = FunctionExecutionStatus.objects.order_by('-reporting_date').values_list('reporting_date', flat=True).distinct()

    # Get the selected date from the request
    selected_date = request.GET.get('selected_date', '')

    # Filter processes based on the selected date and ensure uniqueness by using annotation
    processes = []
    if selected_date:
        processes = (
            FunctionExecutionStatus.objects.filter(reporting_date=selected_date)
            .values('process__process_name', 'process_run_id')
            .annotate(
                latest_run=Max('process_run_id'),  # Latest run ID
                start_time=Min('execution_start_date'),  # Earliest start time
                end_time=Max('execution_end_date')  # Latest end time
            )
        )

        # Calculate overall status and duration for each process
        for process in processes:
            process_run_id = process['process_run_id']
            function_statuses = FunctionExecutionStatus.objects.filter(process_run_id=process_run_id)

            # Determine the overall status based on the function statuses
            if function_statuses.filter(status='Failed').exists():
                process['overall_status'] = 'Failed'
            elif function_statuses.filter(status='Cancelled').exists():
                process['overall_status'] = 'Cancelled'
            elif function_statuses.filter(status='Ongoing').exists():
                process['overall_status'] = 'Ongoing'
            else:
                process['overall_status'] = 'Success'

            # Calculate duration if start and end times are available
            start_time = process['start_time']
            end_time = process['end_time']
            if start_time and end_time:
                duration = end_time - start_time
                process['duration'] = duration.total_seconds() / 60  # Convert to minutes
            else:
                process['duration'] = None

    context = {
        'selected_date': selected_date,
        'processes': processes,
        'available_dates': available_dates,

    }
    return render(request, 'operations/monitor_running_process.html', context)


@login_required
def monitor_specific_process(request, process_run_id):
    # Fetch the specific process run by its ID
    process_statuses = FunctionExecutionStatus.objects.filter(process_run_id=process_run_id)

    context = {
        'process_statuses': process_statuses,
        'process_run_id': process_run_id,
    }
    return render(request, 'operations/monitor_specific_process.html', context)

@login_required
def get_updated_status_table(request):
    process_run_id = request.GET.get('process_run_id')
    
    # Get all statuses related to the process_run_id
    function_statuses = FunctionExecutionStatus.objects.filter(process_run_id=process_run_id).order_by('execution_order')
    
    # Add total_seconds to each status entry
    for status in function_statuses:
        if isinstance(status.duration, timedelta):
            # Calculate total seconds and assign it as an additional attribute for template access
            status.total_seconds = status.duration.total_seconds()
        else:
            status.total_seconds = None

    # Return the partial template with the updated table
    return render(request, 'operations/status_table.html', {'function_statuses': function_statuses})

@login_required
def get_process_function_status(request, process_run_id):
    # Get all statuses related to the process_run_id
    run_processes = FunctionExecutionStatus.objects.filter(process_run_id=process_run_id).order_by('execution_order')

    # Compute duration details for each process
    for process in run_processes:
        if isinstance(process.duration, timedelta):
            total_seconds = process.duration.total_seconds()
            process.total_seconds = total_seconds
            process.minutes = int(total_seconds // 60)
            process.remaining_seconds = int(total_seconds % 60)
        else:
            process.total_seconds = None
            process.minutes = None
            process.remaining_seconds = None

    # Render the updated table to HTML
    functions_html = render_to_string('operations/_function_status_list.html', {'run_processes': run_processes})
    return JsonResponse({'html': functions_html})



@login_required
def running_processes_view(request):
    # Fetch all ongoing (running) processes from the FunctionExecutionStatus model
    running_processes = FunctionExecutionStatus.objects.filter(status='Ongoing')

    context = {
        'running_processes': running_processes
    }

    return render(request, 'operations/running_processes.html', context)

# Updated function to handle cancellation request
@login_required
def cancel_running_process(request, process_run_id):
    # Check if the process is running
    try:
        # Get all functions related to the given process_run_id
        functions = FunctionExecutionStatus.objects.filter(
            process_run_id=process_run_id,
            status__in=['Pending', 'Ongoing']
        )
        
        if functions.exists():
            # Update the status of all "Pending" and "Ongoing" functions to "Cancelled"
            functions.update(status='Cancelled')
            messages.success(request, f"Process '{process_run_id}' and all pending functions have been cancelled.")
        else:
            messages.info(request, f"No running process found with the given ID '{process_run_id}'.")
    
    except FunctionExecutionStatus.DoesNotExist:
        messages.error(request, f"An error occurred while cancelling the process '{process_run_id}'.")

    return redirect('running_processes')  # Redirect to the running processes list


# INSERT INTO `dim_function` (`function_name`, `description`) VALUES 
# ('populate_liquidity_gap_results_base', 'Populates liquidity gap results with aggregated cashflows.'),
# ('update_date', 'Performs LDN updates based on specified logic.'),
# ('populate_dim_product', 'Populates the Dim Product table with product-related data.'),
# ('populate_dim_dates_from_time_buckets', 'Populates the Dim Dates table with required date ranges and structures.'),
# ('project_cash_flows', 'Projects future cash flows based on product and financial data.'),
# ('aggregate_by_prod_code', 'Aggregates cashflows at the product level for base tables.'),
# ('aggregate_cashflows_to_product_level', 'Aggregates cashflows at the account level for reporting.'),
# ('calculate_time_buckets_and_spread', 'Manages general operations like file processing and batch updates.');

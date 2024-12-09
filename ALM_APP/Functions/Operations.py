from django.shortcuts import render, get_object_or_404, redirect
from django.forms import inlineformset_factory
from django.db import transaction
import threading
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import Process_Rn, RunProcess,Function,FunctionExecutionStatus
from ..forms import ProcessForm, RunProcessForm
from django.db import transaction
from django.db.models import Q
from django.db.models import Count
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.db.models import Max
from django.db.models import Min
from datetime import datetime, timedelta
from django.utils import timezone
from django.utils.module_loading import import_string  # Used for dynamic function calling
import sys
#from ..Functions.cashflow import *

from django.db.models import Min, Max


@login_required
def operations_view(request):
    return render(request, 'operations/operations.html')



# List all processes
@login_required
def process_list(request):
    processes = Process_Rn.objects.all()
    return render(request, 'operations/process_list.html', {'processes': processes})

# View the details of a specific process, including its associated functions and execution order
@login_required
def process_detail(request, process_id):
    process = get_object_or_404(Process_Rn, id=process_id)
    run_processes = RunProcess.objects.filter(process=process).order_by('order')  # Fetch functions in order
    return render(request, 'operations/process_detail.html', {'process': process, 'run_processes': run_processes})

# Create or edit a process
@login_required
def create_process(request, process_id=None):
    """
    View to add or edit a process and its corresponding run processes.
    If process_id is provided, it's an edit; otherwise, it's an add.
    """
    RunProcessFormSet = inlineformset_factory(Process_Rn, RunProcess, form=RunProcessForm, extra=1, can_delete=True)

    
    process = Process_Rn()
    form_title = 'Create Process'

    if request.method == 'POST':
        form = ProcessForm(request.POST, instance=process)
        formset = RunProcessFormSet(request.POST)

        # Print the formset POST data for debugging
        print("Formset POST Data:", request.POST)

        if form.is_valid():
            try:
                with transaction.atomic():
                    process = form.save(commit=False)
                    process.save()  # Save the parent process object
                    print(f"Process saved: {process}")

                    # Handle multiple function and order values
                    for form in formset.forms:
                        functions = request.POST.getlist(form.add_prefix('function'))  # Fetch as list
                        orders = request.POST.getlist(form.add_prefix('order'))  # Fetch as list

                        print(f"Processing form: functions={functions}, orders={orders}")

                        # Loop over the multiple values and save each pair separately
                        if len(functions) == len(orders):
                            for function_id, order in zip(functions, orders):
                                if function_id and order:
                                    # Convert the function_id to a Function instance
                                    function_instance = Function.objects.get(pk=function_id)
                                    
                                    RunProcess.objects.create(
                                        process=process,
                                        function=function_instance,  # Save the Function instance
                                        order=order
                                    )
                                    print(f"Saved: function={function_instance}, order={order}")
                        else:
                            # Handle single function and order values
                            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                                function_instance = form.cleaned_data.get('function')
                                RunProcess.objects.create(
                                    process=process,
                                    function=function_instance,  # Save the Function instance
                                    order=form.cleaned_data.get('order')
                                )
                                print(f"Saved single: function={form.cleaned_data.get('function')}, order={form.cleaned_data.get('order')}")

                    messages.success(request, f'Process {"created" if not process_id else "updated"} successfully.')
                    return redirect('process_list')
            except Exception as e:
                messages.error(request, f"Error saving process: {str(e)}")
                print(f"Error: {e}")
        else:
            print("Form Errors:", form.errors)
            print("Formset Errors:", formset.errors)
            messages.error(request, "Please correct the errors below.")
    else:
        form = ProcessForm(instance=process)
        formset = RunProcessFormSet(instance=process)

    return render(request, 'operations/create_process.html', {
        'form': form,
        'formset': formset,
        'title': form_title,
    })

def edit_process(request, process_id):
    """
    View to edit an existing process and its corresponding run processes.
    """
    # Define the formset for RunProcess with can_delete=True
    RunProcessFormSet = inlineformset_factory(
        Process_Rn,
        RunProcess,
        form=RunProcessForm,
        extra=1,
        can_delete=True,  # Enables deletion functionality
    )

    # Fetch the process object to edit or return 404 if not found
    process = get_object_or_404(Process_Rn, id=process_id)
    form_title = "Edit Process"

    if request.method == "POST":
        form = ProcessForm(request.POST, instance=process)
        formset = RunProcessFormSet(request.POST, instance=process)

        # Debugging: Log errors for clarity
        print("Edit Form POST Data:", request.POST)
        print("Edit Form Errors:", form.errors)
        print("Edit Formset Errors:", formset.errors)

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    # Save the process
                    process = form.save(commit=False)
                    process.save()

                    # Save the formset (RunProcess instances), including deletions
                    formset.save()

                    messages.success(request, "Process updated successfully.")
                    return redirect("process_list")
            except Exception as e:
                messages.error(request, f"Error updating process: {str(e)}")
                print(f"Error: {e}")
        else:
            messages.error(
                request,
                "There were errors in the form. Please correct them and try again.",
            )
    else:
        form = ProcessForm(instance=process)
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


@login_required
def delete_process(request, process_id):
    process = get_object_or_404(Process_Rn, id=process_id)
    if request.method == 'POST':
        try:
            process.delete()
            messages.success(request, 'Process deleted successfully.')
        except Exception as e:
            messages.error(request, f'Error deleting process: {e}')
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


# Background function for running the process
# Background function for running the process
def execute_functions_in_background(function_status_entries, process_run_id, mis_date):
    for status_entry in function_status_entries:

        if cancel_flags.get(process_run_id):  # Check if cancellation was requested
            status_entry.status = 'Cancelled'
            status_entry.execution_end_date = timezone.now()
            status_entry.duration = status_entry.execution_end_date - status_entry.execution_start_date
            status_entry.save()
            print(f"Process {process_run_id} was cancelled.")
            break  # Stop execution if cancelled

        function_name = status_entry.function.function_name
        print(f"Preparing to execute function: {function_name}")

        # Set the function status to "Ongoing" and record the start date
        status_entry.status = 'Ongoing'
        status_entry.execution_start_date = timezone.now()  # Start time for the function
        status_entry.save()
        print(f"Function {function_name} marked as Ongoing.")

        # Execute the function
        try:
            if function_name in globals():
                print(f"Executing function: {function_name} with date {mis_date}")
                result = globals()[function_name](mis_date)  # Execute the function and capture the return value
                
                # Update status and end date based on the return value
                status_entry.execution_end_date = timezone.now()  # End time for the function
                if result == 1 or result == '1':
                    status_entry.status = 'Success'
                    print(f"Function {function_name} executed successfully.")
                elif result == 0 or result == '0':
                    status_entry.status = 'Failed'
                    print(f"Function {function_name} execution failed.")
                    status_entry.save()
                    break  # Stop execution if the function fails
                else:
                    status_entry.status = 'Failed'
                    print(f"Unexpected return value {result} from function {function_name}.")
                    status_entry.save()
                    break  # Stop execution for any unexpected result
            else:
                status_entry.status = 'Failed'
                print(f"Function {function_name} not found in the global scope.")
                status_entry.execution_end_date = timezone.now()
                status_entry.save()
                break  # Stop execution if the function is not found

        except Exception as e:
            status_entry.status = 'Failed'
            status_entry.execution_end_date = timezone.now()
            print(f"Error executing {function_name}: {e}")
            status_entry.save()
            break  # Stop execution if any function throws an exception

        # Calculate duration
        if status_entry.execution_start_date and status_entry.execution_end_date:
            status_entry.duration = status_entry.execution_end_date - status_entry.execution_start_date

        # Save the final status and duration
        status_entry.save()
        print(f"Updated FunctionExecutionStatus for {function_name} to {status_entry.status}")


@login_required
def run_process_execution(request):
    if request.method == 'POST':
        process_id = request.POST.get('process_id')
        selected_function_ids = request.POST.getlist('selected_functions')
        
        # Parse the execution date
        mis_date = request.POST.get('execution_date')
        execution_date = datetime.strptime(mis_date, '%Y-%m-%d')
        print(f"Execution date received: {mis_date}")
        
        # Retrieve the selected process
        process = get_object_or_404(Process_Rn, id=process_id)
        print(f"Process selected: {process.process_name} (ID: {process.id})")
        
        # Fetch the RunProcess records in order of their execution (by 'order' field)
        # run_processes = RunProcess.objects.filter(id__in=selected_function_ids).order_by('order')
        run_processes = RunProcess.objects.filter(process=process).order_by('order')
        print(f"Number of selected functions to execute: {run_processes.count()}")

        # Generate the process_run_id and run_count
        process_run_id, run_count = generate_process_run_id(process, execution_date)
        print(f"Generated process_run_id: {process_run_id}, run_count: {run_count}")

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
            print(f"Function {run_process.function.function_name} marked as Pending.")

        # Redirect to the monitoring page so the user can see the function statuses
        response = redirect('monitor_specific_process', process_run_id=process_run_id)

        # Execute functions in the background (thread)
        execution_thread = threading.Thread(target=execute_functions_in_background, args=(function_status_entries, process_run_id, mis_date))
        execution_thread.start()

        return response  # Redirects immediately while the background task executes
        

@login_required
def get_process_functions(request, process_id):
    process = get_object_or_404(Process_Rn, id=process_id)
    functions_html = render_to_string('operations/_functions_list.html', {'run_processes': process.run_processes.all()})
    return JsonResponse({'html': functions_html})



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
# ('perform_interpolation', 'Performs interpolation on the given data.'),
# ('project_cash_flows', 'Projects future cash flows based on data.'),
# ('update_cash_flows_with_ead', 'Updates cash flows using the exposure at default.'),
# ('insert_fct_stage', 'Inserts records into the FCT Stage Determination.'),
# ('update_stage', 'Determines and updates the current stage of accounts.'),
# ('process_cooling_period_for_accounts', 'Processes the cooling period for accounts.'),
# ('update_stage_determination', 'Updates the stage determination logic.'),
# ('update_stage_determination_accrued_interest_and_ead', 'Updates stage determination with accrued interest and EAD.'),
# ('update_stage_determination_eir', 'Updates stage determination based on the effective interest rate.'),
# ('update_lgd_for_stage_determination_term_structure', 'Updates loss given default for stage determination.'),
# ('update_lgd_for_stage_determination_collateral', 'Updates loss given default for stage determination.'),
# ('calculate_pd_for_accounts', 'Calculates probability of default for accounts.'),
# ('insert_cash_flow_data', 'Inserts cash flow data into the system.'),
# ('update_financial_cash_flow', 'Updates financial cash flow records.'),
# ('update_cash_flow_with_pd_buckets', 'Updates cash flows with probability of default buckets.'),
# ('update_marginal_pd', 'Updates marginal probability of default calculations.'),
# ('calculate_expected_cash_flow', 'Calculates expected cash flow projections.'),
# ('calculate_discount_factors', 'Calculates discount factors for cash flows.'),
# ('calculate_cashflow_fields', 'Calculates various cash flow fields.'),
# ('calculate_forward_loss_fields', 'Calculates forward-looking loss fields.'),
# ('populate_fct_reporting_lines', 'Populates reporting lines for FCT.'),
# ('calculate_ecl_based_on_method', 'Calculates expected credit loss based on selected method.'),
# ('update_reporting_lines_with_exchange_rate', 'Updates reporting lines with the  exchange rates.');

from venv import logger
from ..models import *

def save_process_step1(request, data):
    request.session['process_name'] = data.get('name')
    request.session['process_description'] = data.get('description')

def save_process_step2(request, filter_ids):
    request.session['selected_filters'] = filter_ids


def finalize_process_creation(request):
    """
    Finalize the creation of the process by saving it to both Process and Process_Rn tables with the same ID.
    """
    # Retrieve the process information from session
    process_name = request.session.get('process_name')
    process_description = request.session.get('process_description')
    use_behavioral_patterns = request.session.get('use_behavioral_patterns')

    # Convert 'yes'/'no' to boolean True/False
    use_behavioral_patterns_bool = use_behavioral_patterns == 'yes'

    # Create and save the new process record in the Process table
    process = Process.objects.create(
        name=process_name,
        description=process_description,
        uses_behavioral_patterns=use_behavioral_patterns_bool,
        status='Pending',  # Default status is 'Pending'
        created_by=request.user.name if request.user.is_authenticated else 'System',
        modified_by=request.user.name if request.user.is_authenticated else 'System',
    )

    # Use the same ID to create the record in the Process_Rn table
    process_rn = Process_Rn.objects.create(
        id=process.id,  # Explicitly set the same ID
        process_name=process_name,
        description=process_description,
        uses_behavioral_patterns=use_behavioral_patterns_bool,
        status='Pending',
        created_by=request.user.name if request.user.is_authenticated else 'System',
        modified_by=request.user.name if request.user.is_authenticated else 'System',
    )

    # Link the default function (e.g., 'execute_alm_process_logic') to this new process in Process_Rn
    try:
        default_function = Function.objects.get(function_name='execute_alm_process_logic')
        RunProcess.objects.create(
            process=process_rn,
            function=default_function,
            order=1  # Assign the first execution order
        )
    except Function.DoesNotExist:
        # Log or handle the absence of the default function
        logger.warning("Default function 'execute_alm_process_logic' not found. Process linked without a default function.")

    return process  # Return the created process instance


# def finalize_process_creation(request):
#     """
#     Finalize the creation of the process by saving it to the database.
#     """
#     # Retrieve the process information from session
#     process_name = request.session.get('process_name')
#     process_description = request.session.get('process_description')
#     use_behavioral_patterns = request.session.get('use_behavioral_patterns')

#     # Convert 'yes'/'no' to boolean True/False
#     use_behavioral_patterns_bool = True if use_behavioral_patterns == 'yes' else False

#     # Create and save the new process record in the database
#     process = Process.objects.create(
#         name=process_name,
#         description=process_description,
#         uses_behavioral_patterns=use_behavioral_patterns_bool,  # Save boolean value
#         status='Pending',  # Assuming default status is 'Pending'
#         created_by=request.user.name if request.user.is_authenticated else 'System',
#         modified_by=request.user.name if request.user.is_authenticated else 'System',
#     )

#     # Add logic to save filters or other related data if needed
#     return process




def finalize_process_update(process_rn, process, data):
    """
    Finalize the update of the process by saving changes to both Process and Process_Rn tables.

    Args:
        process_rn (Process_Rn): The existing process in Process_Rn to update.
        process (Process): The existing process in Process to update.
        data (dict): A dictionary containing updated fields.
    """
    # Update Process_Rn fields
    process_rn.process_name = data.get('name', process_rn.process_name)
    process_rn.description = data.get('description', process_rn.description)
    process_rn.uses_behavioral_patterns = data.get('use_behavioral_patterns', 'no') == 'yes'
    process_rn.modified_by = data.get('modified_by', 'System')

    # Update filters if provided (optional, if Process_Rn has filters)
    filters = data.get('filters', [])
    if filters and hasattr(process_rn, 'filters'):
        process_rn.filters.set(filters)

    process_rn.save()

    # Update Process fields
    process.name = data.get('name', process.name)
    process.description = data.get('description', process.description)
    process.uses_behavioral_patterns = data.get('use_behavioral_patterns', 'no') == 'yes'
    process.modified_by = data.get('modified_by', 'System')

    # Update filters if provided (optional, if Process has filters)
    if filters and hasattr(process, 'filters'):
        process.filters.set(filters)

    process.save()

    return process_rn, process


# def finalize_process_update(process, data):
#     """
#     Finalize the update of the process by saving changes to the database.

#     Args:
#         process (Process): The existing process to update.
#         data (dict): A dictionary containing updated fields.
#     """
#     # Update process fields with the provided data
#     process.name = data.get('name', process.name)
#     process.description = data.get('description', process.description)
#     process.uses_behavioral_patterns = data.get('use_behavioral_patterns', 'no') == 'yes'

#     # Update modified_by field
#     process.modified_by = data.get('modified_by', 'System')

#     # Update filters if provided
#     filters = data.get('filters', [])
#     if filters:
#         process.filters.set(filters)

#     # Save the updated process
#     process.save()

#     return process
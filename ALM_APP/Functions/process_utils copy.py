from ..models import Process_Rn

def save_process_step1(request, data):
    request.session['process_name'] = data.get('name')
    request.session['process_description'] = data.get('description')

def save_process_step2(request, filter_ids):
    request.session['selected_filters'] = filter_ids

def finalize_process_creation(request):
    """
    Finalize the creation of the process by saving it to the database.
    """
    # Retrieve the process information from session
    process_name = request.session.get('process_name')
    process_description = request.session.get('process_description')
    use_behavioral_patterns = request.session.get('use_behavioral_patterns')

    # Convert 'yes'/'no' to boolean True/False
    use_behavioral_patterns_bool = True if use_behavioral_patterns == 'yes' else False

    # Create and save the new process record in the database
    process = Process_Rn.objects.create(
        process_name=process_name,
        description=process_description,
        uses_behavioral_patterns=use_behavioral_patterns_bool,  # Save boolean value
        status='Pending',  # Assuming default status is 'Pending'
        created_by=request.user.name if request.user.is_authenticated else 'System',
        modified_by=request.user.name if request.user.is_authenticated else 'System',
    )

    # Add logic to save filters or other related data if needed
    return Process_Rn




def finalize_process_update(process, data):
    """
    Finalize the update of the process by saving changes to the database.

    Args:
        process (Process): The existing process to update.
        data (dict): A dictionary containing updated fields.
    """
    # Update process fields with the provided data
    process.name = data.get('name', process.name)
    process.description = data.get('description', process.description)
    process.uses_behavioral_patterns = data.get('use_behavioral_patterns', 'no') == 'yes'

    # Update modified_by field
    process.modified_by = data.get('modified_by', 'System')

    # Update filters if provided
    filters = data.get('filters', [])
    if filters:
        process.filters.set(filters)

    # Save the updated process
    process.save()

    return process
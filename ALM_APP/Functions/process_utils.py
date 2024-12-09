from ..models import Process

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
    process = Process.objects.create(
        name=process_name,
        description=process_description,
        uses_behavioral_patterns=use_behavioral_patterns_bool,  # Save boolean value
        status='Pending',  # Assuming default status is 'Pending'
        created_by=request.user.username if request.user.is_authenticated else 'System',
        modified_by=request.user.username if request.user.is_authenticated else 'System',
    )

    # Add logic to save filters or other related data if needed
    return process

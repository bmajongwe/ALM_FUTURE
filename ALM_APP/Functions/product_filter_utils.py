from ..models import ProductFilter, Process
from django.shortcuts import get_object_or_404
from django.db import transaction

# Utility function to create or update a product filter
def create_or_update_filter(filter_id=None, data=None):
    if data is None:
        data = {}

    # Fetch existing filter if ID is provided, otherwise create a new one
    filter_instance = get_object_or_404(ProductFilter, id=filter_id) if filter_id else ProductFilter()

    # Set the fields
    filter_instance.field_name = data.get('field_name')
    filter_instance.condition = data.get('condition')
    filter_instance.value = data.get('value')
    filter_instance.created_by = data.get('created_by', 'System')  # Set default to 'System'

    # Save the instance
    filter_instance.save()
    return filter_instance

# Utility function to delete a filter
def delete_filter(filter_id):
    filter_instance = get_object_or_404(ProductFilter, id=filter_id)
    filter_instance.delete()

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

from decimal import Decimal, InvalidOperation
import traceback
from django.db import transaction
from django.utils import timezone
from ..models import TimeBucketDefinition, TimeBuckets

def define_time_bucket_from_form_data(request):
    try:
        # Retrieve the name for the time bucket definition
        name = request.POST.get('name')

        if not name:
            print("Error: No name provided for the time bucket.")
            return {'error': 'Please provide a name for the time bucket definition.'}

        # Ensure uniqueness of the name
        if TimeBucketDefinition.objects.filter(name=name).exists():
            print(f"Error: Duplicate time bucket definition for '{name}' found.")
            return {'error': f'A time bucket definition for "{name}" already exists.'}

        # Retrieve the data for the entries
        frequencies = request.POST.getlist('frequency[]')
        multipliers = request.POST.getlist('multiplier[]')
        start_dates = request.POST.getlist('start_date[]')
        end_dates = request.POST.getlist('end_date[]')

        # Validate entries
        if not frequencies or not multipliers or not start_dates or not end_dates:
            print("Error: Missing entries for time buckets.")
            return {'error': 'Please enter at least one time bucket entry with frequency, multiplier, start date, and end date.'}

        # Use transaction.atomic() to ensure both config and entries are saved together
        with transaction.atomic():
            # Create the TimeBucketDefinition (initial save)
            bucket_definition = TimeBucketDefinition(
                name=name,
                created_by="System",  # Placeholder value for created_by
                last_changed_by="System"  # Placeholder value for last_changed_by
            )
            bucket_definition.save()

            # Initialize the order for time buckets
            current_entries = 0

            # Create and save each TimeBuckets object
            for i in range(len(frequencies)):
                frequency = int(frequencies[i])
                multiplier = multipliers[i]
                start_date = start_dates[i]
                end_date = end_dates[i]

                # Increment the order for each entry
                current_entries += 1
                TimeBuckets.objects.create(
                    definition=bucket_definition,
                    serial_number=current_entries,
                    frequency=frequency,
                    multiplier=multiplier,
                    start_date=start_date,
                    end_date=end_date
                )

    except Exception as e:
        print("General Error: An unexpected error occurred.")
        traceback.print_exc()
        return {'error': 'An unexpected error occurred. Please try again.'}

    # If everything goes well, return success
    return {'success': True}


# Utility function for updating time buckets
def update_time_bucket_from_form_data(request, bucket_definition):
    try:
        name = request.POST.get('name')

        if not name:
            return {'error': 'Please provide a name for the time bucket definition.'}

        # Ensure uniqueness excluding current definition
        if TimeBucketDefinition.objects.filter(name=name).exclude(id=bucket_definition.id).exists():
            return {'error': f'A time bucket definition for "{name}" already exists.'}

        # Retrieve the data for the entries
        frequencies = request.POST.getlist('frequency[]')
        multipliers = request.POST.getlist('multiplier[]')
        start_dates = request.POST.getlist('start_date[]')
        end_dates = request.POST.getlist('end_date[]')

        # Validate entries
        if not frequencies or not multipliers or not start_dates or not end_dates:
            return {'error': 'Please enter valid time bucket entries with frequency, multiplier, start date, and end date.'}

        # Use transaction.atomic() to ensure consistency
        with transaction.atomic():
            # Update the time bucket definition details
            bucket_definition.name = name
            bucket_definition.last_changed_date = timezone.now()
            bucket_definition.last_changed_by = "System"  # Placeholder value
            bucket_definition.save()

            # Delete existing entries
            bucket_definition.buckets.all().delete()

            # Initialize the order for time buckets
            current_entries = 0

            # Create and save new entries with auto-incremented order
            for i in range(len(frequencies)):
                current_entries += 1
                TimeBuckets.objects.create(
                    definition=bucket_definition,
                    serial_number=current_entries,
                    frequency=int(frequencies[i]),
                    multiplier=multipliers[i],
                    start_date=start_dates[i],
                    end_date=end_dates[i]


                    
                )

    except Exception as e:
        traceback.print_exc()
        return {'error': 'An unexpected error occurred. Please try again.'}

    return {'success': True}


# Utility function for deleting time bucket definitions
def delete_time_bucket_by_id(id):
    try:
        bucket_definition = TimeBucketDefinition.objects.get(id=id)
        bucket_definition.delete()
        return {'success': True}
    except TimeBucketDefinition.DoesNotExist:
        return {'error': 'Time bucket definition not found.'}
    except Exception as e:
        traceback.print_exc()
        return {'error': 'An unexpected error occurred while deleting the time bucket.'}

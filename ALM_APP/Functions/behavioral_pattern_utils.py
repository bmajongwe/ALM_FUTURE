from decimal import Decimal, InvalidOperation
import traceback
from django.db import transaction  # Import transaction for atomic operations
from django.utils import timezone  # Import timezone for datetime fields
from ..models import BehavioralPatternConfig, BehavioralPatternEntry

def define_behavioral_pattern_from_form_data(request):
    try:
        # Retrieve the product type and description from POST data
        v_prod_type = request.POST.get('v_prod_type')
        description = request.POST.get('description')

        # Check if product type and description are provided
        if not v_prod_type:
            print("Error: No product type provided.")
            return {'error': 'Please provide a product type.'}
        
        if not description:
            print("Error: No description provided.")
            return {'error': 'Please provide a description.'}

        # Ensure uniqueness of v_prod_type (check if the product type already has a pattern)
        if BehavioralPatternConfig.objects.filter(v_prod_type=v_prod_type).exists():
            print(f"Error: Duplicate behavioral pattern for '{v_prod_type}' found.")
            return {'error': f'A behavioral pattern for "{v_prod_type}" already exists.'}

        # Retrieve the data for the entries (tenors, multipliers, percentages)
        tenors = request.POST.getlist('tenor[]')
        multipliers = request.POST.getlist('multiplier[]')
        percentages = request.POST.getlist('percentage[]')

        # Validate if entries (tenors, multipliers, percentages) are provided
        if not tenors or not percentages or len(tenors) != len(percentages):
            print("Error: No entries provided or mismatch in tenors and percentages.")
            return {'error': 'Please enter at least one behavioral pattern entry.'}

        try:
            # Convert percentages to Decimal values for accurate calculation
            percentage_values = [Decimal(p) for p in percentages]

            # Validate that the total percentage across all entries equals 100%
            total_percentage = sum(percentage_values)
            if total_percentage != Decimal('100.000'):
                print(f"Error: Total percentage does not equal 100%. Got {total_percentage}.")
                return {'error': 'The total percentage across all entries must equal 100%.'}

        except InvalidOperation as e:
            # If percentage conversion fails, log the error and return an appropriate message
            print("Error: Invalid percentage value entered.")
            traceback.print_exc()  # Print detailed error trace for debugging
            return {'error': 'Invalid percentage value entered.'}

        # Use transaction.atomic() to ensure both config and entries are saved together
        with transaction.atomic():
            # Create the BehavioralPatternConfig (initial save with default values for created_by and last_changed_by)
            pattern_config = BehavioralPatternConfig(
                v_prod_type=v_prod_type, 
                description=description,
                created_by="System",  # Default value as we don't have user authentication
                last_changed_by="System"  # Default value for last changed
            )
            pattern_config.save()

            # Get current number of entries for order
            current_entries = 0

            # Create and save each BehavioralPatternEntry object
            for i in range(len(tenors)):
                tenor = int(tenors[i])
                multiplier = multipliers[i]
                percentage = percentage_values[i]

                # Save the entry linked to the pattern config with an auto-incrementing order
                current_entries += 1
                BehavioralPatternEntry.objects.create(
                    pattern=pattern_config,
                    tenor=tenor,
                    multiplier=multiplier,
                    percentage=percentage,
                    order=current_entries  # Auto-increment the order
                )

    except Exception as e:
        # Log any general unexpected errors
        print("General Error: An unexpected error occurred.")
        traceback.print_exc()  # Print detailed error trace for debugging
        return {'error': 'An unexpected error occurred. Please try again.'}

    # If everything goes well, return success
    return {'success': True}



# Utility function for editing behavioral patterns
def update_behavioral_pattern_from_form_data(request, pattern):
    try:
        v_prod_type = request.POST.get('v_prod_type')
        description = request.POST.get('description')

        if not v_prod_type:
            return {'error': 'Please provide a product type.'}
        
        if not description:
            return {'error': 'Please provide a description.'}

        # Ensure uniqueness excluding current pattern
        if BehavioralPatternConfig.objects.filter(v_prod_type=v_prod_type).exclude(id=pattern.id).exists():
            return {'error': f'A behavioral pattern for "{v_prod_type}" already exists.'}

        # Retrieve form data
        tenors = request.POST.getlist('tenor[]')
        multipliers = request.POST.getlist('multiplier[]')
        percentages = request.POST.getlist('percentage[]')

        # Validate the entries
        if not tenors or not percentages or len(tenors) != len(percentages):
            return {'error': 'Please enter valid behavioral pattern entries.'}

        try:
            percentage_values = [Decimal(p) for p in percentages]
            total_percentage = sum(percentage_values)
            if not Decimal('99.999') <= total_percentage <= Decimal('100.001'):
                return {'error': 'The total percentage must equal 100%.'}

        except InvalidOperation:
            traceback.print_exc()
            return {'error': 'Invalid percentage value entered.'}

        # Use transaction.atomic() to ensure consistency
        with transaction.atomic():
            # Update pattern details
            pattern.v_prod_type = v_prod_type
            pattern.description = description
            pattern.last_changed_date = timezone.now()  # Update last changed date
            pattern.last_changed_by = "System"  # Default value as we don't have user authentication
            pattern.save()

            # Delete existing entries using the correct related_name 'entries'
            pattern.entries.all().delete()

            # Get current number of entries for order
            current_entries = 0

            # Create and save new entries with an auto-incrementing order
            for i in range(len(tenors)):
                current_entries += 1
                BehavioralPatternEntry.objects.create(
                    pattern=pattern,
                    tenor=int(tenors[i]),
                    multiplier=multipliers[i],
                    percentage=percentage_values[i],
                    order=current_entries  # Auto-increment the order
                )

    except Exception as e:
        traceback.print_exc()
        return {'error': 'An unexpected error occurred. Please try again.'}

    return {'success': True}


# Utility function for deleting behavioral patterns
def delete_behavioral_pattern_by_id(id):
    try:
        pattern = BehavioralPatternConfig.objects.get(id=id)
        pattern.delete()
        return {'success': True}
    except BehavioralPatternConfig.DoesNotExist:
        return {'error': 'Behavioral pattern not found.'}
    except Exception as e:
        traceback.print_exc()
        return {'error': 'An unexpected error occurred while deleting the pattern.'}

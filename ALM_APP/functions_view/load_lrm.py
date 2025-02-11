# views.py

from django.shortcuts import get_object_or_404, render, redirect
from django.db.models import Q
from datetime import timedelta
from ..forms import ProcessNameForm, ProductTypeForm, TimeHorizonForm
from ..models import LiquidityGapResultsBase, ExtractedLiquidityData, LrmSelectionConfig, LrmTimeHorizonConfig
from django.shortcuts import render, redirect
from django.db import transaction


def select_process_name(request):
    if request.method == 'POST':
        selected = request.POST.getlist('process_name_choices')
        request.session['selected_process_names'] = selected
        return redirect('select_product_type')
    qs = LiquidityGapResultsBase.objects.values_list('process_name', flat=True).distinct()
    form = ProcessNameForm()
    form.fields['process_name_choices'].choices = [(p, p) for p in qs]
    return render(request, 'LRM_APP/pre_load_lrm/select_process_name.html', {'form': form})
##############################################################################################
def select_product_type(request):
    if request.method == 'POST':
        selected = request.POST.getlist('product_type_choices')
        request.session['selected_product_types'] = selected
        return redirect('select_time_horizon')
    qs = LiquidityGapResultsBase.objects.values_list('v_prod_type', flat=True).distinct()
    form = ProductTypeForm()
    form.fields['product_type_choices'].choices = [(p, p) for p in qs]
    return render(request, 'LRM_APP/pre_load_lrm/select_product_type.html', {'form': form})

##################################################################################################

def select_time_horizon(request):
    """Step for selecting time horizon dynamically from the database."""

    if request.method == "POST":
        selected_time_ranges = request.POST.getlist("time_range_choices")
        request.session["selected_time_ranges"] = selected_time_ranges
        return redirect("retrieve_data")

    # Fetch time horizons from the database
    time_horizons = LrmTimeHorizonConfig.objects.all()

    return render(request, "LRM_APP/pre_load_lrm/define_time_horizon.html", {
        "time_horizons": time_horizons
    })






########################################################################################################################  



def select_purpose(request):
    """Step for selecting the purpose of the extraction (LCR or NSFR)."""

    # Fetch existing selection purposes
    existing_configs = LrmSelectionConfig.objects.values_list('selection_purpose', flat=True)

    if request.method == "POST":
        selection_purpose = request.POST.get("selection_purpose")

        # Prevent duplicate selection
        if selection_purpose in existing_configs:
            return render(request, "LRM_APP/pre_load_lrm/select_purpose.html", {
                "existing_purposes": existing_configs,
                "error": "This selection already exists. You can edit it instead."
            })

        request.session["selection_purpose"] = selection_purpose  # Store in session
        return redirect("select_process_name")

    return render(request, "LRM_APP/pre_load_lrm/select_purpose.html", {
        "existing_purposes": existing_configs
    })


###################################################################################################
def retrieve_data(request):
    """Display selected choices before finalizing and saving them."""

    # Retrieve stored selections
    selected_process_names = request.session.get('selected_process_names', [])
    selected_product_types = request.session.get('selected_product_types', [])
    selected_time_horizons = request.session.get('selected_time_ranges', [])
    selection_purpose = request.session.get('selection_purpose', 'LCR')  # Default to LCR

    if request.method == "POST":
        # Check if an existing record for the selection purpose exists
        existing_config = LrmSelectionConfig.objects.filter(selection_purpose=selection_purpose).first()

        if existing_config:
            # Update the existing selection instead of creating a duplicate
            existing_config.selected_process_names = selected_process_names
            existing_config.selected_product_types = selected_product_types
            existing_config.selected_time_horizons = selected_time_horizons
            existing_config.save()
        else:
            # Create a new selection if no previous record exists
            LrmSelectionConfig.objects.create(
                selection_purpose=selection_purpose,
                selected_process_names=selected_process_names,
                selected_product_types=selected_product_types,
                selected_time_horizons=selected_time_horizons
            )

        return redirect("list_selections")  # Redirect to confirmation page

    return render(request, "LRM_APP/pre_load_lrm/retrieve_data.html", {
        "selected_process_names": selected_process_names,
        "selected_product_types": selected_product_types,
        "selected_time_horizons": selected_time_horizons,
        "selection_purpose": selection_purpose
    })


#############################################################################################33

def list_selections(request):
    """Display a list of LCR & NSFR selections."""
    selections = LrmSelectionConfig.objects.all()
    return render(request, "LRM_APP/pre_load_lrm/list_selections.html", {"selections": selections})

#########################################################################################

def view_selection(request, id):
    """Display details of a single LCR or NSFR selection."""
    selection = get_object_or_404(LrmSelectionConfig, id=id)
    return render(request, "LRM_APP/pre_load_lrm/view_selection.html", {"selection": selection})


###############################################################################################



def edit_selection(request, id):
    """Edit an existing LCR or NSFR selection on a single page."""
    selection = get_object_or_404(LrmSelectionConfig, id=id)
    time_horizons = LrmTimeHorizonConfig.objects.all()

    # Available process names & product types (should be fetched dynamically)
    available_processes = ["Process A", "Process B", "Process C"]  # Fetch from DB
    available_products = ["Loan", "Deposit", "Investment"]  # Fetch from DB

    if request.method == "POST":
        selection.selection_purpose = request.POST.get("selection_purpose")
        selection.selected_process_names = request.POST.getlist("selected_process_names")
        selection.selected_product_types = request.POST.getlist("selected_product_types")
        selection.selected_time_horizons = request.POST.getlist("selected_time_horizons")
        selection.save()
        return redirect("view_selection", id=id)

    return render(request, "LRM_APP/pre_load_lrm/edit_selection.html", {
        "selection": selection,
        "available_processes": available_processes,
        "available_products": available_products,
        "time_horizons": time_horizons,
    })


# def edit_selection(request, id):
#     """Edit an existing LCR or NSFR selection."""
#     selection = get_object_or_404(LrmSelectionConfig, id=id)

#     if request.method == "POST":
#         selection.selected_process_names = request.POST.getlist("selected_process_names")
#         selection.selected_product_types = request.POST.getlist("selected_product_types")
#         selection.selected_time_horizons = request.POST.getlist("selected_time_horizons")
#         selection.save()
#         return redirect("view_selection", id=id)

#     return render(request, "LRM_APP/pre_load_lrm/edit_selection.html", {
#         "selection": selection
#     })

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib import messages
import requests
from django.urls import reverse
from ALM_APP.models import DimCurrency, DimCurrencyMaster
from ..forms import DimCurrencyCreateForm, DimCurrencyForm, DimCurrencyFormSet, deactivate_other_active_currencies




def currency_status_view(request):
    """
    Displays all currencies with an edit button.
    Clicking 'Edit' will take the user to a dedicated edit page.
    """
    currencies = DimCurrency.objects.all().order_by('code')
    return render(request, 'system/rates/currency_status.html', {'currencies': currencies})



##########################################################################################

def add_currency_view(request):
    """
    Allows users to add new currencies by selecting a code.
    The currency name is auto-filled via API.
    Status = 'Inactive', Reporting Currency = 'No' by default.
    """
    if request.method == 'POST':
        form = DimCurrencyCreateForm(request.POST)
        if form.is_valid():
            currency = form.save(commit=False)  # Don't save immediately
            currency.status = 'Inactive'  # Default value
            currency.reporting_currency = 'No'  # Default value
            currency.save()  # Save to database
            messages.success(request, f"Currency '{currency.code}' added successfully!")
            return redirect('currency_status')  # Redirect to currency list
        else:
            messages.error(request, "There was an issue adding the currency. Please check the errors.")
    else:
        form = DimCurrencyCreateForm()

    return render(request, 'system/rates/add_currency.html', {'form': form})




#############################################################################
import requests



# API to fetch currency codes & names dynamically
def fetch_currency_list(request):
    """
    Fetch currency codes & names from the database and return them as JSON.
    """
    currencies = DimCurrencyMaster.objects.all().values("code", "name")
    return JsonResponse({"currencies": list(currencies)})


#############################################################################


# Show a list of all currencies with edit links
def currency_status_view(request):
    """
    Displays all currencies with an edit button.
    Clicking 'Edit' will take the user to a dedicated edit page.
    """
    currencies = DimCurrency.objects.all().order_by('code')
    return render(request, 'system/rates/currency_status.html', {'currencies': currencies})




def currency_status_edit_view(request, pk):
    """
    Allows editing only one selected currency instead of showing all.
    Ensures validation for only one (Active, Yes) currency.
    """
    currency = get_object_or_404(DimCurrency, pk=pk)

    if request.method == 'POST':
        form = DimCurrencyForm(request.POST, instance=currency)
        if form.is_valid():
            # Deactivate others if this currency is being set to (Active, Yes)
            if form.cleaned_data['status'] == 'Active' and form.cleaned_data['reporting_currency'] == 'Yes':
                deactivate_other_active_currencies(currency)
            
            form.save()
            messages.success(request, f"Currency '{currency.code}' updated successfully!")
            return redirect('currency_status')  # Redirect to list page
        else:
            messages.error(request, "There was an issue updating the currency. Please check the errors below.")
    else:
        form = DimCurrencyForm(instance=currency)

    return render(request, 'system/rates/currency_status_edit.html', {'form': form, 'currency': currency})

##################################################################################################

def delete_currency_view(request, pk):
    """
    Handles AJAX request to delete a currency without reloading the page.
    """
    if request.method == "POST":
        currency = get_object_or_404(DimCurrency, pk=pk)
        currency.delete()
        return JsonResponse({"success": True, "message": f"Currency '{currency.code}' deleted successfully!"})

    return JsonResponse({"success": False, "message": "Invalid request."})
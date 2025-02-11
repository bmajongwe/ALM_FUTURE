from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from ALM_APP.forms import *



@login_required
def configurations_management(request):
    """
    View for the Data Quality Check page.
    """
    return render(request, 'system/system_options.html')
#################################################################################################################



def party_type_add_view(request):
    if request.method == 'POST':
        form = PartyTypeMappingForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Party Type Mapping added successfully.")
                return redirect('party_type_list')  # Adjust URL name if needed
            except IntegrityError:
                # This handles the rare race condition where a duplicate slips through
                form.add_error('v_party_type_code', "A party type mapping with this code already exists.")
    else:
        form = PartyTypeMappingForm()
    return render(request, 'system/splits/party_type_add.html', {'form': form})

#######################################################################################################################
def party_type_list_view(request):
    party_types = PartyTypeMapping.objects.all()
    return render(request, 'system/splits/party_type_list.html', {'party_types': party_types})

################################################################################################
def party_type_detail_view(request, pk):
    party_type = get_object_or_404(PartyTypeMapping, pk=pk)
    return render(request, 'system/splits/party_type_detail.html', {'party_type': party_type})

###################################################################################################################
def party_type_update_view(request, pk):
    party_type = get_object_or_404(PartyTypeMapping, pk=pk)
    if request.method == 'POST':
        form = PartyTypeMappingForm(request.POST, instance=party_type)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Party Type Mapping updated successfully.")
                return redirect('party_type_list')
            except IntegrityError:
                form.add_error('v_party_type_code', "A party type mapping with this code already exists.")
    else:
        form = PartyTypeMappingForm(instance=party_type)
    return render(request, 'system/splits/party_type_update.html', {'form': form, 'party_type': party_type})
########################################################################################################




def party_type_delete_view(request, pk):
    party_type = get_object_or_404(PartyTypeMapping, pk=pk)
    if request.method == 'POST':
        party_type.delete()
        messages.success(request, "Party Type Mapping deleted successfully.")
        return redirect('party_type_list')
    return render(request, 'system/splits/party_type_confirm_delete.html', {'party_type': party_type}) 
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from ..models import Fsi_Interest_Method
from ..forms import InterestMethodForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.timezone import now  # For timestamping


@login_required
def cashflow_projections(request):
    # This view will render the page that shows two options: Documentation and Interest Method
    context = {
        'title': 'Cashflow Projections',
        # No need to pass the URLs from the view, as they're now hardcoded in the HTML
    }
    return render(request, 'system/cashflow_projections/index.html', context)

@login_required
def cashflow_projections_documentation(request):
    # You can pass any context data if needed
    context = {
        'title': 'Cash Flow Generation Issues and Solutions',
    }
    return render(request, 'system/cashflow_projections/cash_flow_generation_issues.html', context)



# List View

class InterestMethodListView(LoginRequiredMixin,ListView):
    model = Fsi_Interest_Method
    template_name = 'system/cashflow_projections/interest_method_list.html'
    context_object_name = 'methods'

# Create View
class InterestMethodCreateView(LoginRequiredMixin,CreateView):
    model = Fsi_Interest_Method
    form_class = InterestMethodForm
    template_name = 'system/cashflow_projections/interest_method_form.html'
    success_url = reverse_lazy('interest_method_list')

    def form_valid(self, form):
        # Set the created_by field to the currently logged-in user
        instance = form.save(commit=False)
        instance.created_by = self.request.user
        instance.save()   
        # Log the creation in the AuditTrail
        # AuditTrail.objects.create(
        #         user=self.request.user,
        #         model_name='Fsi_Interest_Method',
        #         action='create',
        #         object_id=instance.pk,
        #         change_description=f"Created Interest Method: {instance.v_interest_method}",
        #         timestamp=now(),
        #     )  
        messages.success(self.request, "Interest method added successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "There was an error adding the interest method. Please try again.")
        return super().form_invalid(form)

# Update View
class InterestMethodUpdateView(LoginRequiredMixin,UpdateView):
    model = Fsi_Interest_Method
    form_class = InterestMethodForm
    template_name = 'system/cashflow_projections/interest_method_form.html'
    success_url = reverse_lazy('interest_method_list')

    def form_valid(self, form):
        # Set the created_by field to the currently logged-in user
        instance = form.save(commit=False)
        previous_method = self.get_object().v_interest_method 
        instance.created_by = self.request.user
        instance.save() 
        # Log the update in the AuditTrail
        # AuditTrail.objects.create(
        #         user=self.request.user,
        #         model_name='Fsi_Interest_Method',
        #         action='update',
        #         object_id=instance.pk,
        #         change_description=(
        #             f"Updated Interest Method: From {previous_method} to {instance.v_interest_method}"
        #         ),
        #         timestamp=now(),
        #     )    
        messages.success(self.request, "Interest method updated successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "There was an error updating the interest method. Please try again.")
        return super().form_invalid(form)

# Delete View
class InterestMethodDeleteView(LoginRequiredMixin, DeleteView):
    model = Fsi_Interest_Method
    template_name = 'system/cashflow_projections/interest_method_confirm_delete.html'
    success_url = reverse_lazy('interest_method_list')

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            # Log the deletion in the AuditTrail
            # AuditTrail.objects.create(
            #     user=self.request.user,
            #     model_name='Fsi_Interest_Method',
            #     action='delete',
            #     object_id=instance.pk,
            #     change_description=f"Deleted Interest Method: {instance.v_interest_method}",
            #     timestamp=now(),
            # )
            messages.success(self.request, "Interest method deleted successfully!")
        except Exception as e:
            messages.error(self.request, f"An unexpected error occurred while logging the deletion: {e}")
        return super().delete(request, *args, **kwargs)
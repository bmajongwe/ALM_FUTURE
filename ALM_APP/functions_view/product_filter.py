from pyexpat.errors import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from ALM_APP.Functions.product_filter_utils import create_or_update_filter, delete_filter
from ALM_APP.forms import *
from ALM_APP.models import *
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, CreateView, UpdateView
from django.views.generic.detail import DetailView







# ProductFilter Views
class ProductFilterListView(ListView):
    model = ProductFilter
    template_name = 'ALM_APP/filters/filter_list.html'
    context_object_name = 'filters'


class ProductFilterCreateView(CreateView):
    model = ProductFilter
    form_class = ProductFilterForm
    template_name = 'ALM_APP/filters/filter_form.html'
    success_url = reverse_lazy('product_filter_list')

    def form_valid(self, form):
        create_or_update_filter(data=form.cleaned_data)
        messages.success(self.request, 'Product filter created successfully.')
        return redirect(self.success_url)


class ProductFilterUpdateView(UpdateView):
    model = ProductFilter
    form_class = ProductFilterForm
    template_name = 'ALM_APP/filters/filter_update.html'
    success_url = reverse_lazy('product_filter_list')

    def form_valid(self, form):
        create_or_update_filter(
            filter_id=self.object.id, data=form.cleaned_data)
        messages.success(self.request, 'Product filter updated successfully.')
        return redirect(self.success_url)


class ProductFilterDeleteView(View):
    success_url = reverse_lazy('product_filter_list')

    def post(self, request, *args, **kwargs):
        # Retrieve the filter to delete
        product_filter = get_object_or_404(ProductFilter, id=kwargs['pk'])
        delete_filter(filter_id=product_filter.id)
        messages.success(request, 'Product filter deleted successfully.')
        return redirect(self.success_url)


class ProductFilterDetailView(DetailView):
    model = ProductFilter
    template_name = 'ALM_APP/filters/filter_detail.html'
    context_object_name = 'filter'

    def get_object(self):
        # Fetch the filter based on ID or raise a 404 error
        filter_id = self.kwargs.get('pk')
        return get_object_or_404(ProductFilter, pk=filter_id)
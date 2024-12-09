# forms.py
from django import forms
from .models import *

class TimeBucketsForm(forms.ModelForm):
    class Meta:
        model = TimeBuckets
        fields = ['serial_number', 'frequency', 'multiplier']




class FileUploadForm(forms.Form):
    file = forms.FileField(label='Select a file')
    table = forms.ChoiceField(choices=[
        ('Ldn_Product_Master', 'Ldn Product Master'),
        # ('Ldn_Financial_Assets_Instrument', 'Ldn Financial Assets Instrument'),
        ('Ldn_Common_Coa_Master', 'Ldn Common Coa Master'),
        ('NewFinancialTable', 'NewFinancialTable'),  # Add the new table here

    ])





class ProductFilterForm(forms.ModelForm):
    field_name = forms.ChoiceField(choices=[])

    class Meta:
        model = ProductFilter
        fields = ['field_name', 'condition', 'value']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Get field names dynamically from the Product Master model
        product_master_fields = [(field.name, field.verbose_name) for field in Ldn_Product_Master._meta.fields]
        self.fields['field_name'].choices = product_master_fields

class ProcessForm(forms.ModelForm):
    filters = forms.ModelMultipleChoiceField(
        queryset=ProductFilter.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )



    class Meta:
        model = Process
        fields = ['name', 'filters']



# forms.py
from django import forms
from .models import LiquidityGapResultsBase

class LiquidityGapReportFilterForm(forms.Form):
    process_name = forms.ChoiceField(
        required=False,
        choices=[('', '--- Select Process ---')] + [(p, p) for p in LiquidityGapResultsBase.objects.values_list('process_name', flat=True).distinct()],
        label="Process"
    )
    fic_mis_date = forms.ChoiceField(
        choices=[('', '-- Select Date --')] + [
            (choice, choice) for choice in LiquidityGapResultsBase.objects.values_list('fic_mis_date', flat=True).distinct().order_by('fic_mis_date')
        ],
        required=False,
        label="As of Date"
    )
    v_ccy_code = forms.ChoiceField(
        required=False,
        choices=[('', '--- Select Currency ---')] + [(c, c) for c in LiquidityGapResultsBase.objects.values_list('v_ccy_code', flat=True).distinct()],
        label="Currency"
    )
    account_type = forms.ChoiceField(
        required=False,
        choices=[('', '--- Select Result Type ---'), ('Inflow', 'Inflow'), ('Outflow', 'Outflow')],
        label="Result Type"
    )
    bucket_number = forms.ChoiceField(
        choices=[('', '-- Select Bucket Number --')] + [
            (choice, choice) for choice in LiquidityGapResultsBase.objects.values_list('bucket_number', flat=True).distinct().order_by('bucket_end_date')
        ],
        required=False,
        label="Bucket End Date"
    )




























from django import forms
from .models import *
from django.forms import inlineformset_factory
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

class UploadFileForm(forms.Form):
    file = forms.FileField(label='Select a file', widget=forms.ClearableFileInput(attrs={'class': 'form-control'}))

class ColumnSelectionForm(forms.Form):
    def __init__(self, *args, **kwargs):
        columns = kwargs.pop('columns', [])
        super(ColumnSelectionForm, self).__init__(*args, **kwargs)
        
        # Dynamically generate a MultipleChoiceField for selecting columns
        self.fields['selected_columns'] = forms.MultipleChoiceField(
            choices=[(col, col) for col in columns],
            widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
            label='Select Columns to Include',
            initial=columns  # By default, select all columns
        )

class ColumnMappingForm(forms.Form):
    def __init__(self, *args, selected_columns=None, model_fields=None, **kwargs):
        super(ColumnMappingForm, self).__init__(*args, **kwargs)

        if selected_columns and model_fields:
            for column in selected_columns:
                self.fields[column] = forms.ChoiceField(
                    choices=[(field, field) for field in model_fields] + [('unmapped', 'Unmapped')],
                    required=False
                )
                # Set the initial value for each field if provided in kwargs['initial']
                if 'initial' in kwargs and 'column_mappings' in kwargs['initial']:
                    if column in kwargs['initial']['column_mappings']:
                        self.fields[column].initial = kwargs['initial']['column_mappings'][column]

                        
    def clean(self):
        cleaned_data = super().clean()
        column_mappings = {key.replace('column_mapping_', ''): value for key, value in cleaned_data.items()}
        return {'column_mappings': column_mappings}






##########################################################


def generate_filter_form(model_class):
    """
    Dynamically generate a filter form based on the model's fields.
    """
    class FilterForm(forms.Form):
        pass

    for field in model_class._meta.fields:
        if isinstance(field, forms.CharField):
            FilterForm.base_fields[field.name] = forms.CharField(
                required=False,
                label=field.verbose_name,
                widget=forms.TextInput(attrs={'class': 'form-control'})
            )
        elif isinstance(field, forms.DateField):
            FilterForm.base_fields[field.name] = forms.DateField(
                required=False,
                label=field.verbose_name,
                widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
            )
        elif isinstance(field, forms.IntegerField):
            FilterForm.base_fields[field.name] = forms.IntegerField(
                required=False,
                label=field.verbose_name,
                widget=forms.NumberInput(attrs={'class': 'form-control'})
            )
        elif isinstance(field, forms.FloatField):
            FilterForm.base_fields[field.name] = forms.FloatField(
                required=False,
                label=field.verbose_name,
                widget=forms.NumberInput(attrs={'class': 'form-control'})
            )
        # Add other field types as needed

    return FilterForm

class FilterForm(forms.Form):
    filter_column = forms.CharField(widget=forms.HiddenInput())
    filter_value = forms.CharField(widget=forms.HiddenInput())

    ######################


   
#cashflow interest method
class InterestMethodForm(forms.ModelForm):
    class Meta:
        model = Fsi_Interest_Method
        fields = ['v_interest_method', 'description']
        widgets = {
            'v_interest_method': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control'}),
        }


class RunProcessForm(forms.ModelForm):
    class Meta:
        model = RunProcess
        fields = ['function', 'order']
        widgets = {
            'function': forms.Select(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Execution Order'}),
        }

    def __init__(self, *args, **kwargs):
        super(RunProcessForm, self).__init__(*args, **kwargs)
        self.fields['function'].empty_label = "Select Function"
        self.helper = FormHelper(self)
        self.helper.form_method = 'post'

    # Custom validation (example)
    def clean(self):
        cleaned_data = super().clean()

        # Skip validation if the form is marked for deletion
        if self.cleaned_data.get('DELETE', False):
            return cleaned_data

        order = cleaned_data.get('order')

        # Validation: Order should be a positive number
        if order is None or order <= 0:
            raise forms.ValidationError("Order must be a positive number.")

        return cleaned_data

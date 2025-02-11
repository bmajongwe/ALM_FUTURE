# forms.py
from django import forms
from .models import *
from django import forms
from django.forms import modelformset_factory, BaseModelFormSet
from django import forms
from .models import DimCurrency



class ProcessNameForm(forms.Form):
    process_name_choices = forms.MultipleChoiceField(
        required=False,
        widget=forms.SelectMultiple(attrs={'size': '10'}),
        choices=[]
    )

class ProductTypeForm(forms.Form):
    product_type_choices = forms.MultipleChoiceField(
        required=False,
        widget=forms.SelectMultiple(attrs={'size': '10'}),
        choices=[]
    )

class TimeHorizonForm(forms.Form):
    TIME_RANGES = [
        ('0-30', '0–30 Days'),
        ('31-60', '31–60 Days'),
    ]
    time_range = forms.ChoiceField(choices=TIME_RANGES)
    

class DimCurrencyCreateForm(forms.ModelForm):
    class Meta:
        model = DimCurrency
        fields = ['code', 'currency_name']  # Only input fields




def deactivate_other_active_currencies(current_currency):
    """
    Deactivates other currencies when a new currency is set as Active and Reporting = Yes.
    """
    DimCurrency.objects.filter(status="Active", reporting_currency="Yes").exclude(pk=current_currency.pk).update(
        status="Inactive", reporting_currency="No"
    )

class DimCurrencyForm(forms.ModelForm):
    class Meta:
        model = DimCurrency
        fields = ['status', 'reporting_currency']  # Only allow editing these fields

    def clean(self):
        """
        Ensures only one currency can be set as (Active, Yes).
        """
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        reporting_currency = cleaned_data.get("reporting_currency")

        if status == "Active" and reporting_currency == "Yes":
            # Check if another currency is already set as (Active, Yes)
            existing_active = DimCurrency.objects.filter(status="Active", reporting_currency="Yes").exclude(pk=self.instance.pk)
            if existing_active.exists():
                raise forms.ValidationError("Only one currency can be Active and Reporting = Yes.")
        
        return cleaned_data


class BaseDimCurrencyFormSet(BaseModelFormSet):
    def clean(self):
        """
        Enforces that only one currency can be Active & Reporting=Yes.
        Prevents setting Reporting=Yes if Status=Inactive.
        """
        super().clean()
        active_reporting_count = 0

        for form in self.forms:
            if not form.cleaned_data:
                continue  # Skip invalid forms
            
            status = form.cleaned_data.get('status')
            reporting = form.cleaned_data.get('reporting_currency')

            # Prevent Inactive currencies from being set as Reporting=Yes
            if status == 'Inactive' and reporting == 'Yes':
                form.add_error(
                    'reporting_currency',
                    "Cannot set Reporting=Yes when Status is Inactive."
                )

            # Enforce only one (Active, Yes)
            if status == 'Active' and reporting == 'Yes':
                active_reporting_count += 1
                if active_reporting_count > 1:
                    raise forms.ValidationError(
                        "Only one currency can be Active and Reporting=Yes."
                    )

DimCurrencyFormSet = modelformset_factory(
    DimCurrency,
    form=DimCurrencyForm,
    formset=BaseDimCurrencyFormSet,
    extra=0,  # No extra empty forms
    can_delete=False  # Prevent deletion
)


class PartyTypeMappingForm(forms.ModelForm):
    class Meta:
        model = PartyTypeMapping
        fields = ['v_party_type_code', 'description']

    def clean_v_party_type_code(self):
        code = self.cleaned_data.get("v_party_type_code")
        # When updating an instance, exclude the current record:
        qs = PartyTypeMapping.objects.filter(v_party_type_code=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A party type mapping with this code already exists.")
        return code

        
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

from django import forms
from .models import Process_Rn, ProductFilter

class ProcessForm(forms.ModelForm):
    filters = forms.ModelMultipleChoiceField(
        queryset=ProductFilter.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Process_Rn
        fields = ['process_name', 'description', 'uses_behavioral_patterns', 'filters']



# class ProcessForm(forms.ModelForm):
#     filters = forms.ModelMultipleChoiceField(
#         queryset=ProductFilter.objects.all(),
#         widget=forms.CheckboxSelectMultiple,
#         required=False
#     )




#     class Meta:
#         model = Process
#         fields = ['name', 'filters']



# forms.py
from django import forms
from .models import LiquidityGapResultsBase

class LiquidityGapReportFilterForm(forms.Form):
    process_name = forms.ChoiceField(
        required=False,
        choices=[(p, p) for p in LiquidityGapResultsBase.objects.values_list('process_name', flat=True).distinct()],
        label="Process"
    )
    fic_mis_date = forms.ChoiceField(
        choices= [
            (choice, choice) for choice in LiquidityGapResultsBase.objects.values_list('fic_mis_date', flat=True).distinct().order_by('fic_mis_date')
        ],
        required=False,
        label="As of Date"
    )
    v_ccy_code = forms.ChoiceField(
        required=False,
        choices= [(c, c) for c in LiquidityGapResultsBase.objects.values_list('v_ccy_code', flat=True).distinct()],
        label="Currency"
    )
    account_type = forms.ChoiceField(
        required=False,
        choices=[('Inflow', 'Inflow'), ('Outflow', 'Outflow')],
        label="Result Type"
    )
    bucket_number = forms.ChoiceField(
        choices=[
            (choice, choice) for choice in LiquidityGapResultsBase.objects.values_list('bucket_number', flat=True).distinct().order_by('bucket_end_date')
        ],
        required=False,
        label="Bucket End Date"
    )

class LiquidityGapReportFilterForm_cons(forms.Form):
    process_name = forms.ChoiceField(
        required=False,
        choices=[(p, p) for p in LiquidityGapResultsCons.objects.values_list('process_name', flat=True).distinct()],
        label="Process"
    )
    fic_mis_date = forms.ChoiceField(
        choices= [
            (choice, choice) for choice in LiquidityGapResultsCons.objects.values_list('fic_mis_date', flat=True).distinct().order_by('fic_mis_date')
        ],
        required=False,
        label="As of Date"
    )
    v_ccy_code = forms.ChoiceField(
        required=False,
        choices= [(c, c) for c in LiquidityGapResultsCons.objects.values_list('v_ccy_code', flat=True).distinct()],
        label="Currency"
    )
    account_type = forms.ChoiceField(
        required=False,
        choices=[('Inflow', 'Inflow'), ('Outflow', 'Outflow')],
        label="Result Type"
    )
    bucket_number = forms.ChoiceField(
        choices=[
            (choice, choice) for choice in LiquidityGapResultsCons.objects.values_list('bucket_number', flat=True).distinct().order_by('bucket_end_date')
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


class ProcessFormOp(forms.ModelForm):
    class Meta:
        model = Process_Rn
        fields = ['process_name']
        widgets = {
            'process_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Process Name'}),
        }

    def __init__(self, *args, **kwargs):
        super(ProcessFormOp, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Save Process'))


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

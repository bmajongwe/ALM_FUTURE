from django.shortcuts import render,redirect, get_object_or_404
from ..models import *
from ..forms import *
import pandas as pd
from django.views import View
from django.contrib import messages
from threading import Thread
from queue import Queue
from django.db import transaction, IntegrityError, DatabaseError
from django.core.exceptions import ValidationError
from django.db import connection
from django.apps import apps
from django.forms import modelform_factory
from django.db.models import Q
import csv
from django.http import HttpResponse,JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError, DatabaseError as DBError
from django.views import View
import pandas as pd





@login_required
def data_management(request):
    return render(request, 'load_data/data_management.html')

class FileUploadView(LoginRequiredMixin,View):
    template_name = 'load_data/file_upload_step1.html'

    def get(self, request):
        form = UploadFileForm()

        # Fetch staging tables from the database
        stg_tables = TableMetadata.objects.filter(table_type='STG').values_list('table_name', flat=True)

        return render(request, self.template_name, {
            'form': form,
            'stg_tables': stg_tables  # Pass the staging tables to the template
        })

    def post(self, request):
        form = UploadFileForm(request.POST, request.FILES)
        selected_table = request.POST.get('table_name')  # Get selected table from the form

        if form.is_valid() and selected_table:
            file = form.cleaned_data['file']

            try:
                # Automatically detect file type and process accordingly
                if file.name.endswith('.csv'):
                    df = pd.read_csv(file)
                elif file.name.endswith(('.xls', '.xlsx')):
                    df = pd.read_excel(file)
                else:
                    messages.error(request, "Unsupported file format. Please upload a CSV or Excel file.")
                    return render(request, self.template_name, {'form': form, 'stg_tables': TableMetadata.objects.filter(table_type='STG')})

                # Convert Timestamps to strings for JSON serialization
                df = df.applymap(lambda x: x.isoformat() if isinstance(x, pd.Timestamp) else x)


                # Store the data, column names, and selected table in session for later steps
                request.session['file_data'] = df.to_dict()  # Save the full data in session
                request.session['columns'] = list(df.columns)
                request.session['selected_table'] = selected_table  # Save the selected table

                # Prepare preview for rendering (first 10 rows)
                preview_data = {
                    'headers': list(df.columns),
                    'rows': df.head(10).values.tolist()  # Show the first 10 rows for preview
                }

                return render(request, self.template_name, {
                    'form': form,
                    'preview_data': preview_data,
                    'show_next_button': True,
                    'table_name': selected_table,
                    'file_name': file.name,
                    'stg_tables': TableMetadata.objects.filter(table_type='STG')
                })
            except Exception as e:
                messages.error(request, f"Error processing file: {e}")
        return render(request, self.template_name, {
            'form': form,
            'stg_tables': TableMetadata.objects.filter(table_type='STG')
        })
    
class ColumnSelectionView(LoginRequiredMixin,View):
    template_name = 'load_data/file_upload_step2.html'

    def get(self, request):
        columns = request.session.get('columns', [])
        if not columns:
            messages.error(request, "No columns found. Please upload a file first.")
            return redirect('file_upload')
        form = ColumnSelectionForm(columns=columns, initial={'selected_columns': columns})
        return render(request, self.template_name, {'form': form, 'columns': columns})

    def post(self, request):
        selected_columns = request.POST.get('selected_columns_hidden').split(',')
        if selected_columns:
            request.session['selected_columns'] = selected_columns
            return redirect('map_columns')
        else:
            messages.error(request, "You must select at least one column.")
        return render(request, self.template_name, {'form': form})

########################
class ColumnMappingView(LoginRequiredMixin,View):
    template_name = 'load_data/file_upload_step3.html'

    def get(self, request):
        selected_columns = request.session.get('selected_columns', [])
        selected_table = request.session.get('selected_table')  # Get the selected table from the session

        # Get the model class dynamically based on the selected table
        try:
            model_class = apps.get_model('IFRS9', selected_table)  # Replace 'IFRS9' with your actual app name
        except LookupError:
            messages.error(request, "Error: The selected table does not exist.")
            return render(request, self.template_name)

        model_fields = [f.name for f in model_class._meta.fields]

        # Create initial mappings based on matching names (case-insensitive)
        initial_mappings = {}
        unmapped_columns = []

        for column in selected_columns:
            match = next((field for field in model_fields if field.lower() == column.lower()), None)
            if match:
                initial_mappings[column] = match
            else:
                initial_mappings[column] = 'unmapped'  # Set to 'unmapped' if no match is found
                unmapped_columns.append(column)  # Track unmapped columns

        # Initialize the form with the mappings
        form = ColumnMappingForm(
            initial={'column_mappings': initial_mappings}, 
            selected_columns=selected_columns, 
            model_fields=model_fields
        )

  

        # Check if there are unmapped columns
        if unmapped_columns:
            messages.warning(request, "The following columns were not automatically mapped: " + ", ".join(unmapped_columns))
        
        return render(request, self.template_name, {'form': form, 'unmapped_columns': unmapped_columns})

    def post(self, request):
        selected_columns = request.session.get('selected_columns', [])
        selected_table = request.session.get('selected_table')  # Get the selected table from the session

        # Get the model class dynamically based on the selected table
        try:
            model_class = apps.get_model('IFRS9', selected_table)  # Replace 'IFRS9' with your actual app name
        except LookupError:
            messages.error(request, "Error: The selected table does not exist.")
            return render(request, self.template_name)

        model_fields = [f.name for f in model_class._meta.fields]

        # Initialize the form with POST data
        form = ColumnMappingForm(request.POST, selected_columns=selected_columns, model_fields=model_fields)

        if form.is_valid():
            # Safely get the 'column_mappings' from cleaned_data
            mappings = form.cleaned_data.get('column_mappings', {})

           

            # Validate that all columns have been mapped (i.e., not mapped to 'unmapped')
            unmapped_columns = [col for col, mapped_to in mappings.items() if mapped_to == 'unmapped']
            if unmapped_columns:
                messages.error(request, "The following columns are not mapped: " + ", ".join(unmapped_columns))
                return render(request, self.template_name, {'form': form, 'unmapped_columns': unmapped_columns})

            # Ensure that there are mappings before proceeding
            if not mappings or all(value == 'unmapped' for value in mappings.values()):
                messages.error(request, "Error: No valid column mappings provided. Please map all columns before proceeding.")
                return render(request, self.template_name, {'form': form, 'unmapped_columns': unmapped_columns})

            # Save the mappings to the session
            request.session['column_mappings'] = mappings

            return redirect('submit_to_database')

        # If the form is not valid, render the form again with errors
        messages.error(request, "Error: Invalid form submission. Please check your mappings and try again.")
        return render(request, self.template_name, {'form': form})


#####################




class SubmitToDatabaseView(LoginRequiredMixin, View):
    template_name = 'load_data/file_upload_step4.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        try:
            # Retrieve data from the session
            df_data = request.session.get('file_data')
            selected_columns = request.session.get('selected_columns')
            mappings = request.session.get('column_mappings')
            selected_table = request.session.get('selected_table')

            if not df_data or not selected_columns or not mappings:
                return JsonResponse({'status': 'error', 'message': 'Missing data in the session.'}, status=400)

            # Convert session data to DataFrame and apply mappings
            df = pd.DataFrame(df_data)
            df = df[selected_columns].rename(columns=mappings)

            # Clean the data
            df = self.clean_data(df)

            # Convert date columns to YYYY-MM-DD format
            for column in df.columns:
                if 'date' in column.lower():
                    df[column] = pd.to_datetime(df[column], errors='coerce').dt.strftime('%Y-%m-%d').astype(str)
            
            # Retrieve the model class dynamically
            model_class = apps.get_model('IFRS9', selected_table)

            # Define chunk size for bulk insert
            chunk_size = 5000
            total_chunks = len(df) // chunk_size + (1 if len(df) % chunk_size > 0 else 0)
            request.session['progress'] = 0

            # Counter to track the total number of records successfully inserted
            success_count = 0

            for i, chunk_start in enumerate(range(0, len(df), chunk_size), start=1):
                # Prepare the chunk for insertion
                chunk_df = df.iloc[chunk_start:chunk_start + chunk_size]
                records_to_insert = [model_class(**row.to_dict()) for _, row in chunk_df.iterrows()]

                try:
                    # Bulk create the records with conflict handling
                    model_class.objects.bulk_create(records_to_insert)
                    success_count += len(records_to_insert)  # Increment success count by inserted records
                except IntegrityError as e:
                    return JsonResponse({'status': 'error', 'message': f'Integrity error: {str(e)}'}, status=400)
                except ValidationError as e:
                    error_messages = "; ".join(f"{field}: {', '.join(errors)}" for field, errors in e.message_dict.items())
                    return JsonResponse({'status': 'error', 'message': f'Validation error: {error_messages}'}, status=400)
                except DBError as e:
                    return JsonResponse({'status': 'error', 'message': f'Database error: {str(e)}'}, status=400)

                # Update progress in session after each chunk
                request.session['progress'] = int((i / total_chunks) * 100)
                request.session.modified = True

            # Mark completion and return success message with count of records uploaded
            request.session['progress'] = 100
            return JsonResponse({'status': 'success', 'message': f'{success_count} records successfully uploaded.'})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f"Unexpected error: {str(e)}"}, status=500)
        
    def clean_data(self, df):
        """
        Cleans the DataFrame by applying various data cleaning steps.
        """
        # Remove leading and trailing spaces from all string columns
        for column in df.select_dtypes(include=['object']).columns:
            df[column] = df[column].str.strip()

        # Trim whitespace and normalize spaces between words
        for column in df.select_dtypes(include=['object']).columns:
            df[column] = df[column].str.strip().str.replace(r'\s+', ' ', regex=True)

        # Convert all text to uppercase
        for column in df.select_dtypes(include=['object']).columns:
            df[column] = df[column].str.upper()
        # Additional cleaning steps can be added here, such as:
        df.dropna(how='all', inplace=True)  # Drop rows where all values are NaN
        # Drop duplicates
        df.drop_duplicates(inplace=True)

        return df
class CheckProgressView(LoginRequiredMixin, View):
    def get(self, request):
        progress = request.session.get('progress', 0)
        return JsonResponse({'progress': progress})
    

     
    ####################################################################
@login_required
def data_entry_view(request):
    table_form = TableSelectForm(request.POST or None)
    data_form = None

    if request.method == 'POST':
        if table_form.is_valid():
            selected_table = table_form.cleaned_data['table_name'].table_name  # Get the selected table's name

            try:
                # Get the model class dynamically
                model_class = apps.get_model('IFRS9', selected_table)  # Replace 'IFRS9' with your actual app name
            except LookupError:
                messages.error(request, "Error: The selected table does not exist.")
                return render(request, 'load_data/data_entry.html', {'table_form': table_form, 'data_form': data_form})

            # Dynamically create a form for the selected model
            DynamicForm = modelform_factory(model_class, fields='__all__')
            data_form = DynamicForm(request.POST or None)

            if data_form.is_valid():
                try:
                    data_form.save()
                    messages.success(request, "Data successfully saved!")
                    return redirect('data_entry')
                except IntegrityError as e:
                    messages.error(request, f"Database Error: {e}")
                except ValidationError as e:
                    messages.error(request, f"Validation Error: {e.message_dict}")
                except Exception as e:
                    messages.error(request, f"Unexpected Error: {e}")
    
    return render(request, 'load_data/data_entry.html', {
        'table_form': table_form,
        'data_form': data_form
    })


@login_required
def get_fic_mis_dates(request):
    table_name = request.GET.get('table_name')
    try:
        model_class = apps.get_model('IFRS9', table_name)
        dates = model_class.objects.values_list('fic_mis_date', flat=True).distinct().order_by('-fic_mis_date')
        date_choices = [(date, date.strftime('%Y-%m-%d')) for date in dates]
        return JsonResponse({'dates': date_choices})
    except LookupError:
        return JsonResponse({'error': 'Table not found'}, status=404)
    
########################################################

class TableSelectForm(LoginRequiredMixin, forms.Form):
    table_name = forms.ChoiceField(choices=[], label="--select table--")
    fic_mis_date = forms.ChoiceField(choices=[('', '--select date--')], required=False, label="Select Date")

    def __init__(self, *args, **kwargs):
        # Get the initial table_name and fic_mis_date if they exist
        initial_table_name = kwargs['data'].get('table_name') if 'data' in kwargs else None
        initial_fic_mis_date = kwargs['data'].get('fic_mis_date') if 'data' in kwargs else None
        
        super().__init__(*args, **kwargs)
        
        # Populate table_name choices with a prompt
        app_models = apps.get_app_config('IFRS9').get_models()
        self.fields['table_name'].choices = [('', '--select table--')] + [
            (model._meta.model_name, model._meta.verbose_name) for model in app_models
        ]

        # If a table is selected, populate fic_mis_date choices
        if initial_table_name:
            model_class = apps.get_model('IFRS9', initial_table_name)
            distinct_dates = model_class.objects.values_list('fic_mis_date', flat=True).distinct().order_by('-fic_mis_date')
            self.fields['fic_mis_date'].choices = [('', '--select date--')] + [
                (date, date.strftime('%Y-%m-%d')) for date in distinct_dates
            ]
            # Set the initial value for fic_mis_date
            if initial_fic_mis_date:
                self.fields['fic_mis_date'].initial = initial_fic_mis_date

@login_required
def view_data(request):
    table_form = TableSelectForm(request.GET or None)
    data = None
    columns = []
    column_unique_values = {}
    table_name = request.GET.get('table_name')
    fic_mis_date = request.GET.get('fic_mis_date')

    if table_form.is_valid():
        if table_name and fic_mis_date:
            try:
                # Get the model class dynamically based on the selected table
                model_class = apps.get_model('IFRS9', table_name)
                print(f"Selected Table: {table_name}, Selected Date: {fic_mis_date}")

                # Apply filtering by `fic_mis_date` using `__date` for compatibility
                data = model_class.objects.filter(fic_mis_date__date=fic_mis_date)
                
                # Debug output
                print(f"Query: {data.query}")
                print(f"Data Count: {data.count()}")  # Check if data is returned

                # Get column names and unique values for each column
                columns = [field.name for field in model_class._meta.fields]
                for column in columns:
                    column_unique_values[column] = model_class.objects.values_list(column, flat=True).distinct()
                
                if not data:
                    messages.warning(request, "No data found for the selected date.")
                
            except LookupError:
                messages.error(request, "Error: The selected table does not exist.")
        else:
            messages.warning(request, "Please select both a table and a date to view data.")
            
            # Repopulate `fic_mis_date` choices based on selected table
            if table_name:
                model_class = apps.get_model('IFRS9', table_name)
                distinct_dates = model_class.objects.values_list('fic_mis_date', flat=True).distinct().order_by('-fic_mis_date')
                table_form.fields['fic_mis_date'].choices = [('', 'Select Date')] + [(date, date) for date in distinct_dates]

    return render(request, 'load_data/view_data.html', {
        'table_form': table_form,
        'data': data,
        'columns': columns,
        'column_unique_values': column_unique_values,
        'table_name': table_name,
        'fic_mis_date': fic_mis_date,
    })


@login_required
def filter_table(request):
    # Get table_name from the GET parameters
    table_name = request.GET.get('table_name')
    table_form = TableSelectForm(initial={'table_name': table_name})
    data = None
    columns = []
    column_unique_values = {}
    
    # Retrieve other parameters
    fic_mis_date = request.GET.get('fic_mis_date')
    filter_column = request.GET.get('filter_column')
    filter_values = request.GET.get('filter_values')
    sort_order = request.GET.get('sort_order')

    if table_name and fic_mis_date:  # Ensure both table_name and fic_mis_date are required for data retrieval
        try:
            model_class = apps.get_model('IFRS9', table_name)
            
            # Start by filtering directly on fic_mis_date, without __date lookup
            data = model_class.objects.filter(fic_mis_date=fic_mis_date)

            # Additional column-specific filtering if provided
            if filter_column and filter_values:
                filter_values_list = filter_values.split(',')
                filter_values_list = [value for value in filter_values_list if value not in ["on", "(Select All)"]]
                
                filters = Q()
                if "None" in filter_values_list:
                    filter_values_list.remove("None")
                    filters |= Q(**{f"{filter_column}__isnull": True})
                if filter_values_list:
                    filters |= Q(**{f"{filter_column}__in": filter_values_list})
                
                data = data.filter(filters)

            # Apply sorting if specified
            if filter_column and sort_order:
                data = data.order_by(filter_column if sort_order == 'asc' else f'-{filter_column}')

            # Retrieve columns and unique values for dropdown filters
            columns = [field.name for field in model_class._meta.fields]
            for column in columns:
                column_unique_values[column] = data.values_list(column, flat=True).distinct()

            # Debug output
            print(f"SQL Query: {data.query}")
            print(f"Data Count: {data.count()}")

        except LookupError:
            messages.error(request, "Error: The selected table does not exist.")
            print("Error: The selected table does not exist.")
    else:
        messages.warning(request, "Please select both a table and a date to view data.")

    return render(request, 'load_data/view_data.html', {
        'table_form': table_form,
        'data': data,
        'columns': columns,
        'column_unique_values': column_unique_values,
        'table_name': table_name,
        'fic_mis_date': fic_mis_date,
    })


@login_required
def download_data(request, table_name):
    try:
        # Get the model class dynamically using the table name
        model_class = apps.get_model('IFRS9', table_name)
        data = model_class.objects.all()

        # Handle filtering via GET parameters
        filter_column = request.GET.get('filter_column')
        filter_values = request.GET.get('filter_values')

        if filter_column and filter_values:
            filter_values_list = filter_values.split(',')

            # Filter out any unwanted values like "on" or "Select All"
            filter_values_list = [value for value in filter_values_list if value not in ["on", "(Select All)"]]

            # Prepare a Q object to combine multiple conditions
            filters = Q()

            # If "None" is selected, add an isnull filter
            if "None" in filter_values_list:
                filter_values_list.remove("None")
                filters |= Q(**{f"{filter_column}__isnull": True})

            # If there are other values selected, add the in filter
            if filter_values_list:
                filters |= Q(**{f"{filter_column}__in": filter_values_list})

            # Apply the combined filter to the data
            data = data.filter(filters)

        # Handle sorting via GET parameters
        sort_order = request.GET.get('sort_order')
        if filter_column and sort_order:
            if sort_order == 'asc':
                data = data.order_by(filter_column)
            elif sort_order == 'desc':
                data = data.order_by(f'-{filter_column}')

        # Create the HTTP response object with the appropriate CSV header.
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{table_name}.csv"'

        writer = csv.writer(response)
        # Write the headers
        writer.writerow([field.name for field in model_class._meta.fields])

        # Write the data rows
        for item in data:
            writer.writerow([getattr(item, field.name) for field in model_class._meta.fields])

        return response

    except LookupError:
        messages.error(request, "Error: The selected table does not exist.")
        return redirect('view_data')


@login_required
def edit_row(request, table_name, row_id):
    try:
        # Get the model class dynamically
        model_class = apps.get_model('IFRS9', table_name)
        row = get_object_or_404(model_class, id=row_id)

        if request.method == 'POST':
            # Update the row with new data from the AJAX request
            for field, value in request.POST.items():
                if field != 'csrfmiddlewaretoken':
                    setattr(row, field, value)
            row.save()

            return JsonResponse({'success': True})  # Respond with success

        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)

    except LookupError:
        return JsonResponse({'success': False, 'error': 'Table not found'}, status=404)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def delete_row(request, table_name, row_id):
    try:
        # Get the model class dynamically
        model_class = apps.get_model('IFRS9', table_name)
        row = get_object_or_404(model_class, id=row_id)

        if request.method == 'POST':
            row.delete()
            return JsonResponse({'success': True})  # Respond with success

        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)

    except LookupError:
        return JsonResponse({'success': False, 'error': 'Table not found'}, status=404)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)




# INSERT INTO `tablemetadata` (`table_name`, `description`, `table_type`) VALUES 
# ('Ldn_Bank_Product_Info', 'Information about bank products offered.', 'STG'),
# ('Ldn_Customer_Info', 'Details about customers including personal and contact information.', 'STG'),
# ('Ldn_Customer_Rating_Detail', 'Customer credit ratings and assessment details.', 'STG'),
# ('Ldn_Exchange_Rate', 'Exchange rates for various currencies.', 'STG'),
# ('Ldn_Expected_Cashflow', 'Expected cash flows based on financial models.', 'STG'),
# ('Ldn_Financial_Instrument', 'Details of financial instruments used in transactions.', 'STG'),
# ('Ldn_LGD_Term_Structure', 'Loss Given Default (LGD) term structure details.', 'STG'),
# ('Ldn_PD_Term_Structure', 'Probability of Default (PD) term structure details.', 'STG'),
# ('Ldn_PD_Term_Structure_Dtl', 'Detailed probability of default term structures.', 'STG'),
# ('Ldn_Payment_Schedule', 'Schedule of payments related to financial products.', 'STG');

# ALM_APP/urls.py
from django.urls import path
from . import views 
from .views import *
from .views import *
from .Functions.data import *

from .Functions.Operations import *






urlpatterns = [
    # path('success/', views.success, name='success'),
    path('project_cash_flows/', project_cash_flows_view, name='project_cash_flows'),
    #path('project-cash-flows/', project_cash_flows_view, name='project_cash_flows'),
    # path('define-time-buckets/', views.define_time_buckets, name='define_time_buckets'),
    #path('time-buckets-list/', views.time_buckets_list, name='time_buckets_list'),
    # path('liquidity_gap_results/', liquidity_gap_results_view, name='liquidity_gap_results'),
    # path('create_behavioral_pattern/', liquidity_gap_results_view, name='create_behavioral_pattern'),

        # behavioural patterns URLs
    path('create_behavioral_pattern/', views.create_behavioral_pattern, name='create_behavioral_pattern'),
    path('behavioral_patterns_list/', views.behavioral_patterns_list, name='behavioral_patterns_list'),
    path('edit_behavioral_pattern/<int:id>/', views.edit_behavioral_pattern, name='edit_behavioral_pattern'),
    path('delete_behavioral_pattern/<int:id>/', views.delete_behavioral_pattern, name='delete_behavioral_pattern'),
    path('view_behavioral_patterns/<int:id>/', views.view_behavioral_pattern, name='view_behavioral_pattern'),
   
       # Time buckets URLs
    path('time_bucket_list/', views.time_buckets_list, name='time_bucket_list'),
    path('create_time_bucket/', views.create_time_bucket, name='create_time_bucket'),
    path('edit_time_bucket/<int:id>/', views.edit_time_bucket, name='edit_time_bucket'),
    path('delete_time_buckets/<int:id>/', views.delete_time_bucket, name='delete_time_bucket'),
    path('view_time_bucket/<int:id>/', views.view_time_bucket, name='view_time_bucket'),

    # ProductFilter URLs
    path('filters/', ProductFilterListView.as_view(), name='product_filter_list'),
    path('filters/create/', ProductFilterCreateView.as_view(), name='product_filter_create'),
    path('filters/create/', ProductFilterCreateView.as_view(), name='create_filter'),
    path('filters/<int:pk>/edit/', ProductFilterUpdateView.as_view(), name='product_filter_update'),
    path('filters/<int:pk>/delete/', ProductFilterDeleteView.as_view(), name='product_filter_delete'),
    path('filters/<int:pk>/', views.ProductFilterDetailView.as_view(), name='product_filter_detail'),

    # Process URLs
    path('processes/', ProcessListView.as_view(), name='processes_list'),
    path('processes/create/', views.process_create_view, name='process_create'),
    path('processes/execute/', views.execute_alm_process_view, name='execute_process'),
    path('processes/<int:pk>/edit/', ProcessUpdateView.as_view(), name='process_update'),
    path('processes/<int:pk>/delete/', ProcessDeleteView.as_view(), name='process_delete'),

    # Reports URLs
    path('reports/liquidity-gap/', views.liquidity_gap_report, name='liquidity_gap_report'),
    path('export/liquidity-gap/', export_liquidity_gap_to_excel, name='export_liquidity_gap_to_excel'),
    path('export/liquidity-gap-cons/', views.export_liquidity_gap_cons_to_excel, name='export_liquidity_gap_cons_to_excel'),









path('', dashboard_view, name='dashboard'),
    path('ifrs9-home-list/', views.ifrs9_home_view, name='ifrs9_home'),
    path('data_management/', views.data_management, name='data_management'),
    path('upload/', FileUploadView.as_view(), name='file_upload'),
    path('select_columns/', ColumnSelectionView.as_view(), name='select_columns'),
    path('map_columns/', ColumnMappingView.as_view(), name='map_columns'),
    path('submit_to_database/', SubmitToDatabaseView.as_view(), name='submit_to_database'),
    path('upload/progress/', CheckProgressView.as_view(), name='check_progress'),
    path('data-entry/', data_entry_view, name='data_entry'),
    path('get_fic_mis_dates/', views.get_fic_mis_dates, name='get_fic_mis_dates'),
    path('view-data/', view_data, name='view_data'),
    path('filter-table/', filter_table, name='filter_table'),
    path('download-data/<str:table_name>/', download_data, name='download_data'),
    path('edit-row/<str:table_name>/<int:row_id>/', edit_row, name='edit_row'),
    path('delete-row/<str:table_name>/<int:row_id>/', delete_row, name='delete_row'),




    path('operations/', views.operations_view, name='operations'),
    path('process/', views.process_list, name='process_list'),
    path('process/<int:process_id>/', views.process_detail, name='process_detail'),
    path('process/create/', views.create_process, name='create_process'),
    path('edit_process/<int:process_id>/', views.edit_process, name='edit_process'),
    path('process/delete/<int:process_id>/', views.delete_process, name='delete_process'),
    path('process/execute/', views.execute_process_view, name='execute_process_view'),
    path('process/run/', views.run_process_execution, name='run_process_execution'),
    path('ajax/get_process_functions/<int:process_id>/', views.get_process_functions, name='get_process_functions'),
    path('process/monitor/', views.monitor_running_process_view, name='monitor_running_process_view'),
    path('ajax/get_process_function_status/<str:process_run_id>/', views.get_process_function_status, name='get_process_function_status'),
    path('process/monitor/<str:process_run_id>/', views.monitor_specific_process, name='monitor_specific_process'),
    path('get-updated-status-table/', views.get_updated_status_table, name='get_updated_status_table'),
    path('running-processes/', running_processes_view, name='running_processes'),
    path('cancel-process/<str:process_run_id>/', cancel_running_process, name='cancel_running_process'),




   
]

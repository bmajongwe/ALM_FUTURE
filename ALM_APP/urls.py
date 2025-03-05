# ALM_APP/urls.py
from django.urls import path

from ALM_APP.Functions.Cashflow_projections import *
from ALM_APP.functions_view.alm_lrm import LRM_ALM
from ALM_APP.functions_view.alm_reports import export_liquidity_gap_cons_to_excel, export_liquidity_gap_to_excel, liquidity_gap_report_base, liquidity_gap_report_cons
from ALM_APP.functions_view.behavioral_pattern import *
from ALM_APP.functions_view.hqla_report_view import hqla_report_view, lcr_inflows_view, lcr_outflows_view, lcr_report_view
from ALM_APP.functions_view.load_lrm import  edit_selection, list_selections, retrieve_data, select_process_name, select_product_type, select_purpose, select_time_horizon, view_selection
from ALM_APP.functions_view.nsfr import nsfr_stock_list_view, nsfr_stock_summary_view
from ALM_APP.functions_view.party_splits import configurations_management, party_type_add_view, party_type_delete_view, party_type_detail_view, party_type_list_view, party_type_update_view
from ALM_APP.functions_view.proccess import *
from ALM_APP.functions_view.product_filter import ProductFilterCreateView, ProductFilterDeleteView, ProductFilterDetailView, ProductFilterListView, ProductFilterUpdateView
from ALM_APP.functions_view.rates import add_currency_view, currency_status_edit_view, currency_status_view, delete_currency_view, fetch_currency_list
from ALM_APP.functions_view.time_bucket import *
from . import views
from .views import *
from .views import *
from .Functions.data import *

from .Functions.Operations import *




urlpatterns = [
    # path('success/', views.success, name='success'),
    path('project_cash_flows/', project_cash_flows_view, name='project_cash_flows'),
    # path('project-cash-flows/', project_cash_flows_view, name='project_cash_flows'),
    # path('define-time-buckets/', views.define_time_buckets, name='define_time_buckets'),
    # path('time-buckets-list/', views.time_buckets_list, name='time_buckets_list'),
    # path('liquidity_gap_results/', liquidity_gap_results_view, name='liquidity_gap_results'),
    # path('create_behavioral_pattern/', liquidity_gap_results_view, name='create_behavioral_pattern'),

    # behavioural patterns URLs
    path('create_behavioral_pattern/', create_behavioral_pattern,
         name='create_behavioral_pattern'),
    path('behavioral_patterns_list/', behavioral_patterns_list,
         name='behavioral_patterns_list'),
    path('edit_behavioral_pattern/<int:id>/',
         edit_behavioral_pattern, name='edit_behavioral_pattern'),
    path('delete_behavioral_pattern/<int:id>/',
         delete_behavioral_pattern, name='delete_behavioral_pattern'),
    path('view_behavioral_patterns/<int:id>/',
         view_behavioral_pattern, name='view_behavioral_pattern'),

    # Time buckets URLs
    path('time_bucket_list/', time_buckets_list, name='time_bucket_list'),
    path('create_time_bucket/', create_time_bucket,
         name='create_time_bucket'),
    path('edit_time_bucket/<int:id>/',
         edit_time_bucket, name='edit_time_bucket'),
    path('delete_time_buckets/<int:id>/',
         delete_time_bucket, name='delete_time_bucket'),
    path('view_time_bucket/<int:id>/',
         view_time_bucket, name='view_time_bucket'),

    # ProductFilter URLs
    path('filters/', ProductFilterListView.as_view(), name='product_filter_list'),
    path('filters/create/', ProductFilterCreateView.as_view(),
         name='product_filter_create'),
    path('filters/create/', ProductFilterCreateView.as_view(), name='create_filter'),
    path('filters/<int:pk>/edit/', ProductFilterUpdateView.as_view(),
         name='product_filter_update'),
    path('filters/<int:pk>/delete/', ProductFilterDeleteView.as_view(),
         name='product_filter_delete'),
    path('filters/<int:pk>/', ProductFilterDetailView.as_view(),
         name='product_filter_detail'),

    # Process URLs
     path('processes/', ProcessListView.as_view(), name='processes_list'),
     path('processes/create/', process_create_view, name='process_create'),
     path('processes/execute/', execute_alm_process_view,
         name='execute_process'),
#     path('processes/<int:pk>/edit/',
#          ProcessUpdateView.as_view(), name='process_update'),
     path('processes/<int:process_id>/edit/', ProcessUpdateView, name='process_update'),
     path('processes/<int:process_id>/detail/', processes_view, name='processes_view'),
     path('processes/<int:process_id>/delete/', ProcessDeleteView, name='process_delete'),


    # Reports URLs
#     path('reports/liquidity-gap/', views.liquidity_gap_report,
#          name='liquidity_gap_report'),
    path('export/liquidity-gap/', export_liquidity_gap_to_excel,
         name='export_liquidity_gap_to_excel'),
    path('export/liquidity-gap-cons/', export_liquidity_gap_cons_to_excel,
         name='export_liquidity_gap_cons_to_excel'),
     path('liquidity-gap/base/', liquidity_gap_report_base, name='liquidity_gap_report_base'),
    path('liquidity-gap/cons/', liquidity_gap_report_cons, name='liquidity_gap_report_cons'),










    path('', dashboard_view, name='dashboard'),
    path('ALM-home-list/', views.ALM_home_view, name='ALM_home'),
    path('data_management/', views.data_management, name='data_management'),
    path('upload/', FileUploadView.as_view(), name='file_upload'),
    path('select_columns/', ColumnSelectionView.as_view(), name='select_columns'),
    path('map_columns/', ColumnMappingView.as_view(), name='map_columns'),
    path('submit_to_database/', SubmitToDatabaseView.as_view(),
         name='submit_to_database'),
    path('upload/progress/', CheckProgressView.as_view(), name='check_progress'),
    path('data-entry/', data_entry_view, name='data_entry'),
    path('get_fic_mis_dates/', views.get_fic_mis_dates, name='get_fic_mis_dates'),
    path('view-data/', view_data, name='view_data'),
    path('filter-table/', filter_table, name='filter_table'),
    path('download-data/<str:table_name>/',
         download_data, name='download_data'),
    path('edit-row/<str:table_name>/<int:row_id>/', edit_row, name='edit_row'),
    path('delete-row/<str:table_name>/<int:row_id>/',
         delete_row, name='delete_row'),




    path('operations/', views.operations_view, name='operations'),
    path('process/', views.process_list, name='process_list'),
    path('process/<int:process_id>/', views.process_detail, name='process_detail'),
    path('process/create/', views.create_process, name='create_process'),
    path('edit_process/<int:process_id>/',
         views.edit_process, name='edit_process'),
    path('process/delete/<int:process_id>/',views.delete_process, name='delete_process'),
    path('process/execute/', views.execute_process_view,
         name='execute_process_view'),
    path('process/run/', views.run_process_execution,
         name='run_process_execution'),
    path('ajax/get_process_functions/<int:process_id>/',
         views.get_process_functions, name='get_process_functions'),
    path('process/monitor/', views.monitor_running_process_view,
         name='monitor_running_process_view'),
    path('ajax/get_process_function_status/<str:process_run_id>/',
         views.get_process_function_status, name='get_process_function_status'),
    path('process/monitor/<str:process_run_id>/',
         views.monitor_specific_process, name='monitor_specific_process'),
    path('get-updated-status-table/', views.get_updated_status_table,
         name='get_updated_status_table'),
    path('running-processes/', running_processes_view, name='running_processes'),
    path('cancel-process/<str:process_run_id>/', cancel_running_process, name='cancel_running_process'),
    path('data-quality-check/', views.data_quality_check, name='data_quality_check'),
    path('check-missing-customers/', views.check_missing_customers, name='check_missing_customers'),
    path('check-missing-products/', views.check_missing_products, name='check_missing_products'),
    path('check-cashflow-data/', views.check_cashflow_data, name='check_cashflow_data'),
    # path('check-missing-fields/', views.check_missing_fields, name='check_missing_fields'),


    #system management
    path('configurations/', configurations_management, name='configurations_management'),
    path('party-type/add/', party_type_add_view, name='party_type_add'),
    path('party-type/list/', party_type_list_view, name='party_type_list'),
    path('party-type/detail/<int:pk>/', party_type_detail_view, name='party_type_detail'),
    path('party-type/update/<int:pk>/', party_type_update_view, name='party_type_update'),
    path('party-type/delete/<int:pk>/', party_type_delete_view, name='party_type_delete'),


#     intrests

    path('cashflow-projections/', cashflow_projections, name='cashflow_projections'),
    path('cashflow-projections/documentation/', cashflow_projections_documentation, name='cashflow_projections_documentation'),
    path('interest-methods/', InterestMethodListView.as_view(), name='interest_method_list'),
    path('interest-methods/add/', InterestMethodCreateView.as_view(), name='interest_method_add'),
    path('interest-methods/<int:pk>/edit/', InterestMethodUpdateView.as_view(), name='interest_method_edit'),
    path('interest-methods/<int:pk>/delete/', InterestMethodDeleteView.as_view(), name='interest_method_delete'),
    
    path('currency/status/edit/<int:pk>/', currency_status_edit_view, name='currency_status_edit'),
    path('currency/status/', currency_status_view, name='currency_status'),
    path('currency/add/', add_currency_view, name='add_currency'),
    path('currency/list/', fetch_currency_list, name='fetch_currency_list'),
    path("currency/delete/<int:pk>/", delete_currency_view, name="delete_currency"),





#     LRM
    path('ALM_LRM/', LRM_ALM, name='LRM_ALM'),


     path('select_purpose/', select_purpose, name='select_purpose'),
    path('select_process_name/', select_process_name, name='select_process_name'),
    path('select_product_type/', select_product_type, name='select_product_type'),
    path('select_time_horizon/', select_time_horizon, name='select_time_horizon'),
    path('retrieve_data/', retrieve_data, name='retrieve_data'),
    path('selections/', list_selections, name='list_selections'),
    path('selections/<int:id>/', view_selection, name='view_selection'),
    path('selections/<int:id>/edit/', edit_selection, name='edit_selection'),

    # Map /hqla-report/ to the hqla_report_view
    path('hqla-report/', hqla_report_view, name='hqla_report'),
    path('lcr_outflows/', lcr_outflows_view, name='lcr_outflows'),
    path('lcr_inflows/', lcr_inflows_view, name='lcr_inflows'),
    path('lcr-report/', lcr_report_view, name='lcr_report'),


    path('nsfr-stocks/', nsfr_stock_list_view, name='nsfr_stock_list'),
    path('nsfr-stocks-summary/', nsfr_stock_summary_view, name='nsfr_stock_summary'),








 

  


]

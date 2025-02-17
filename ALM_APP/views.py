from ALM_APP.Functions.classify_and_store_hqla import classify_and_store_hqla_multi_ccy
from ALM_APP.Functions.alm_execution_functions import execute_alm_process_logic
from ALM_APP.Functions.pre_load_lrm import transfer_lrm_data
from .models import LiquidityGapResultsCons
from .Functions.liquidity_gap_utils import filter_queryset_by_form, get_date_buckets, prepare_inflow_outflow_data, calculate_totals
from .models import LiquidityGapResultsBase
from openpyxl.utils import get_column_letter
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl import Workbook
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.db.models import Sum, F
from django.contrib import messages
from .Functions.liquidity_gap_utils import *
from .forms import LiquidityGapReportFilterForm
from .models import LiquidityGapResultsBase, LiquidityGapResultsCons
from django.shortcuts import render
from collections import defaultdict
import os
from django.views.generic.detail import DetailView
from django.urls import reverse_lazy
from django.views import View
import openpyxl
import pandas as pd
from decimal import Decimal
import csv
import traceback
from django.contrib import messages  # Import messages framework
from django.shortcuts import get_object_or_404, render, redirect
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.conf import settings


from .Functions.data import *

from .Functions.Operations import *
from .forms import *
from datetime import datetime
from django.http import HttpResponse
from .Functions.Aggregated_Prod_Cashflow_Base import *
from .Functions.populate_liquidity_gap_results_base import *
from .Functions.ldn_update import *
from .Functions.aggregate_cashflows import *
from .Functions.Aggregated_Acc_level_cashflows import *
from .Functions.behavioral_pattern_utils import define_behavioral_pattern_from_form_data, delete_behavioral_pattern_by_id, update_behavioral_pattern_from_form_data
from .Functions.time_bucket_utils import define_time_bucket_from_form_data, update_time_bucket_from_form_data, delete_time_bucket_by_id
from .Functions.populate_dim import populate_dim_product
from .Functions.Dim_dates import *
from .Functions.product_filter_utils import *
from .Functions.process_utils import *
from .Functions.cashflow import *

from datetime import datetime, timedelta
from django.shortcuts import render, redirect
from .models import TimeBuckets, TimeBucketDefinition, product_level_cashflows




# View to project cash flows based on the fic_mis_date parameter
@login_required
def project_cash_flows_view(request):
    process_name = 'time bucket'
    fic_mis_date = '2024-08-31'
    # status = populate_dim_dates_from_time_buckets(fic_mis_date)
    # status=populate_dim_product(fic_mis_date)
    # status= aggregate_by_prod_code(fic_mis_date, process_name)
    # status=update_date(fic_mis_date)
    # status = populate_liquidity_gap_results_base(fic_mis_date, process_name)
    # status= calculate_time_buckets_and_spread(process_name, fic_mis_date)
    # status= aggregate_cashflows_to_product_level(fic_mis_date)

    # status=execute_alm_process_logic(process_name, fic_mis_date)


    # status=transfer_lrm_data(fic_mis_date)

    status=classify_and_store_hqla_multi_ccy(fic_mis_date)


    # status= project_cash_flows(fic_mis_date)



    print(status)
    # project_cash_flows(fic_mis_date)
    return render(request, 'ALM_APP/project_cash_flows.html')

@login_required
def dashboard_view(request):
    # Example data for financial graphs
    mis_date = '2024-07-31'  # Input date in 'YYYY-MM-DD' format
    # perform_interpolation(mis_date)
    # project_cash_flows(mis_date)
    # update_cash_flows_with_ead(mis_date)
    # # #Insert records into FCT_Stage_Determination with the numeric date
    # insert_fct_stage(mis_date)
    # # #determine stage
    # update_stage(mis_date)
    # process_cooling_period_for_accounts(mis_date)
    # update_stage_determination(mis_date)
    # update_stage_determination_accrued_interest_and_ead(mis_date)
    # update_stage_determination_eir(mis_date)
    # update_lgd_for_stage_determination_term_structure(mis_date)
    # calculate_pd_for_accounts(mis_date)
    # insert_cash_flow_data(mis_date)
    # update_financial_cash_flow(mis_date)
    # update_cash_flow_with_pd_buckets(mis_date)
    # update_marginal_pd(mis_date)
    # calculate_expected_cash_flow(mis_date)
    # calculate_discount_factors(mis_date)
    # calculate_cashflow_fields(mis_date)
    # calculate_forward_loss_fields(mis_date)
    # populate_fct_reporting_lines(mis_date)
    # calculate_ecl_based_on_method(mis_date)
    # update_reporting_lines_with_exchange_rate(mis_date)

    return render(request, 'ALM_home.html')


@login_required
def ALM_home_view(request):
    context = {
        'title': ' Home',
        # You can pass any additional context if needed
    }
    return render(request, 'ALM_home.html', context)

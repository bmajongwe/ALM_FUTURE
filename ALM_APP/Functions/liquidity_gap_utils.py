# ALM_APP/liquidity_gap_utils.py

from django.db.models import Sum
from ..models import *
from django.contrib import messages

def get_latest_fic_mis_date():
    try:
        return Dim_Dates.objects.latest('fic_mis_date').fic_mis_date
    except Dim_Dates.DoesNotExist:
        return None

def get_date_buckets(fic_mis_date):
    return Dim_Dates.objects.filter(fic_mis_date=fic_mis_date).values(
        'bucket_number', 'bucket_start_date', 'bucket_end_date'
    ).distinct().order_by('bucket_number')

def filter_queryset_by_form(form, queryset):
    if form.is_valid():
        process_name = form.cleaned_data.get('process_name')
        fic_mis_date = form.cleaned_data.get('fic_mis_date')
        v_ccy_code = form.cleaned_data.get('v_ccy_code')
        account_type = form.cleaned_data.get('account_type')
        bucket_number = form.cleaned_data.get('bucket_number')

        if process_name:
            queryset = queryset.filter(process_name=process_name)
        if fic_mis_date:
            queryset = queryset.filter(fic_mis_date=fic_mis_date)
        if v_ccy_code:
            queryset = queryset.filter(v_ccy_code=v_ccy_code)
        if account_type:
            queryset = queryset.filter(account_type=account_type)
        if bucket_number:
            queryset = queryset.filter(bucket_number=bucket_number)

    return queryset

def prepare_inflow_outflow_data(queryset, group_by='v_prod_type'):
    """
    Prepare inflow and outflow data, grouped either by product type (default) or product name.
    """
    inflow_products = (
        queryset.filter(account_type="Inflow")
        .values(group_by, 'bucket_number')
        .annotate(total=Sum('inflows'))
    )
    outflow_products = (
        queryset.filter(account_type="Outflow")
        .values(group_by, 'bucket_number')
        .annotate(total=Sum('outflows'))
    )

    inflow_data = {}
    outflow_data = {}

    # Process inflow data
    for item in inflow_products:
        group = item[group_by]
        bucket = item['bucket_number']
        total = item['total']
        if group not in inflow_data:
            inflow_data[group] = {}
        inflow_data[group][bucket] = total
        inflow_data[group]['total'] = inflow_data[group].get('total', 0) + total

    # Process outflow data
    for item in outflow_products:
        group = item[group_by]
        bucket = item['bucket_number']
        total = item['total']
        if group not in outflow_data:
            outflow_data[group] = {}
        outflow_data[group][bucket] = total
        outflow_data[group]['total'] = outflow_data[group].get('total', 0) + total

    return inflow_data, outflow_data


def calculate_totals(date_buckets, inflow_data, outflow_data):
    """
    Calculate net liquidity gap, net gap percentage, and cumulative gap based on inflow and outflow data.
    """
    total_inflows_by_bucket = {}
    total_outflows_by_bucket = {}

    # Calculate total inflows and outflows for each bucket
    for bucket in date_buckets:
        bucket_number = bucket['bucket_number']
        total_inflows_by_bucket[bucket_number] = sum(
            inflow_data.get(group, {}).get(bucket_number, 0) for group in inflow_data
        )
        total_outflows_by_bucket[bucket_number] = sum(
            outflow_data.get(group, {}).get(bucket_number, 0) for group in outflow_data
        )

    # Calculate net liquidity gap and percentage
    net_liquidity_gap = {
        bucket: total_inflows_by_bucket.get(bucket, 0) - total_outflows_by_bucket.get(bucket, 0)
        for bucket in total_inflows_by_bucket
    }
    net_gap_percentage = {
        bucket: (net_liquidity_gap[bucket] / total_outflows_by_bucket[bucket] * 100)
        if total_outflows_by_bucket[bucket]
        else 0
        for bucket in total_outflows_by_bucket
    }

    # Calculate cumulative gap
    cumulative_gap = {}
    cumulative_total = 0
    for bucket in date_buckets:
        bucket_number = bucket['bucket_number']
        cumulative_total += net_liquidity_gap[bucket_number]
        cumulative_gap[bucket_number] = cumulative_total

    return net_liquidity_gap, net_gap_percentage, cumulative_gap




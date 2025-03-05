
# views.py
from django.shortcuts import render
from itertools import groupby
from ..models import NSFRStock

def nsfr_stock_list_view(request):
    # 1) Retrieve filter parameters from GET request
    fic_mis_date_selected = request.GET.get("fic_mis_date", "")
    currency_selected = request.GET.get("currency", "")

    # 2) Build the base queryset ordered by v_nsfr_type, v_prod_type_level, row_category, and v_prod_type
    qs = NSFRStock.objects.all().order_by(
        'v_nsfr_type',
        'v_prod_type_level',
        'row_category',  # ensures total rows appear after normal rows
        'v_prod_type'
    )

    # 3) Apply filters if provided
    if fic_mis_date_selected:
        qs = qs.filter(fic_mis_date=fic_mis_date_selected)
    if currency_selected:
        qs = qs.filter(v_ccy_code=currency_selected)

    # 4) Get distinct MIS dates and currencies for the dropdown filters
    all_mis_dates = NSFRStock.objects.values_list("fic_mis_date", flat=True).distinct()
    all_currencies = NSFRStock.objects.values_list("v_ccy_code", flat=True).distinct()

    # 5) Group the records by v_nsfr_type into a dictionary.
    # For each v_nsfr_type, group by v_prod_type_level (ignoring overall_total rows) and pull out overall_total row.
    grouped_data = {}
    for nsfr_type, type_group in groupby(qs, key=lambda r: r.v_nsfr_type):
        records_for_this_type = list(type_group)
        
        overall_total = next(
            (r for r in records_for_this_type if r.row_category == "overall_total"),
            None
        )
        
        subcategories = []
        for level, level_group in groupby(
            (r for r in records_for_this_type if r.row_category != "overall_total"),
            key=lambda r: r.v_prod_type_level
        ):
            rows = list(level_group)
            normal_rows = [r for r in rows if r.row_category == "normal"]
            level_total = next((r for r in rows if r.row_category == "level_total"), None)
            subcategories.append({
                "v_prod_type_level": level,
                "normal_rows": normal_rows,
                "level_total_row": level_total,
            })
        
        grouped_data[nsfr_type] = {
            "v_nsfr_type": nsfr_type,
            "subcategories": subcategories,
            "overall_total_row": overall_total,
        }

    # 6) Define the desired order for v_nsfr_type.
    # For example, if your NSFRStock.v_nsfr_type values are "RSF" (Required Stable Funding) and "ASF" (Available Stable Funding),
    # you can enforce that order.
    ordered_types = ["RSF", "ASF"]
    ordered_grouped_data = []
    for t in ordered_types:
        if t in grouped_data:
            ordered_grouped_data.append(grouped_data[t])
    # Append any remaining types not in the ordered_types list.
    for t, group in grouped_data.items():
        if t not in ordered_types:
            ordered_grouped_data.append(group)

    # 7) Build context and render the template
    context = {
        "grouped_data": ordered_grouped_data,
        "all_mis_dates": all_mis_dates,
        "all_currencies": all_currencies,
        "fic_mis_date_selected": fic_mis_date_selected,
        "currency_selected": currency_selected,
    }
    return render(request, "LRM_APP/nsfr/nsfr_stock_list.html", context)




# # views.py
# from django.shortcuts import render
# from itertools import groupby
# from ..models import NSFRStock, NSFRStockSummary

# def nsfr_stock_list_view(request):
#     # Retrieve filter parameters from GET request
#     fic_mis_date_selected = request.GET.get("fic_mis_date", "")
#     currency_selected = request.GET.get("currency", "")

#     qs = NSFRStock.objects.all().order_by(
#         'v_nsfr_type',
#         'v_prod_type_level',
#         'row_category',   # ensures total rows appear after normal rows
#         'v_prod_type'
#     )

#     # Filter by FIC MIS Date if provided
#     if fic_mis_date_selected:
#         qs = qs.filter(fic_mis_date=fic_mis_date_selected)
#     # Filter by Currency if provided
#     if currency_selected:
#         qs = qs.filter(v_ccy_code=currency_selected)

#     # Get distinct dates and currencies for the dropdown filters
#     all_mis_dates = NSFRStock.objects.values_list("fic_mis_date", flat=True).distinct()
#     all_currencies = NSFRStock.objects.values_list("v_ccy_code", flat=True).distinct()

#     grouped_data = []
#     # Group first by v_nsfr_type
#     for nsfr_type, type_group in groupby(qs, key=lambda r: r.v_nsfr_type):
#         subcategories = []
#         records_for_this_type = list(type_group)

#         # Pull out an overall total (if any)
#         overall_total = next(
#             (r for r in records_for_this_type if r.row_category == "overall_total"), 
#             None
#         )

#         # Group by v_prod_type_level for normal + level_total (ignoring overall_total)
#         for level, level_group in groupby(
#             (r for r in records_for_this_type if r.row_category != "overall_total"),
#             key=lambda r: r.v_prod_type_level
#         ):
#             rows = list(level_group)
#             normal_rows = [r for r in rows if r.row_category == "normal"]
#             level_total = next((r for r in rows if r.row_category == "level_total"), None)

#             subcategories.append({
#                 "v_prod_type_level": level,
#                 "normal_rows": normal_rows,
#                 "level_total_row": level_total
#             })

#         grouped_data.append({
#             "v_nsfr_type": nsfr_type,
#             "subcategories": subcategories,
#             "overall_total_row": overall_total
#         })

#     context = {
#         "grouped_data": grouped_data,
#         "all_mis_dates": all_mis_dates,
#         "all_currencies": all_currencies,
#         "fic_mis_date_selected": fic_mis_date_selected,
#         "currency_selected": currency_selected,
#     }
#     return render(request, "LRM_APP/nsfr/nsfr_stock_list.html", context)





   

# views.py
from django.shortcuts import render
from django.db.models import Case, When, IntegerField
from itertools import groupby
from ..models import NSFRStockSummary

def nsfr_stock_summary_view(request):
    # 1) Read filter parameters from GET
    fic_mis_date_selected = request.GET.get("fic_mis_date", "")
    currency_selected = request.GET.get("currency", "")

    # 2) Build base queryset
    qs = NSFRStockSummary.objects.all()

    # 3) Apply filters if provided
    if fic_mis_date_selected:
        qs = qs.filter(fic_mis_date=fic_mis_date_selected)
    if currency_selected:
        qs = qs.filter(v_ccy_code=currency_selected)

    # 4) Annotate each row with a custom "type_order" so we can order them as desired:
    #    0 => REQUIRED STABLE FUNDING
    #    1 => AVAILABLE STABLE FUNDING
    #    2 => NSFR RATIO
    #    3 => Everything else (if any)
    qs = qs.annotate(
        type_order=Case(
            When(v_nsfr_type="REQUIRED STABLE FUNDING", then=0),
            When(v_nsfr_type="AVAILABLE STABLE FUNDING", then=1),
            When(v_nsfr_type="NSFR RATIO", then=2),
            default=3,
            output_field=IntegerField()
        )
    )

    # 5) Order by "type_order", then by "row_category" so level_total rows come before overall_total,
    # and then by v_prod_type_level for consistency.
    qs = qs.order_by('type_order', 'row_category', 'v_prod_type_level')

    # 6) Group the records by v_nsfr_type into a dictionary
    grouped_data = {}
    for vtype, group in groupby(qs, key=lambda r: r.v_nsfr_type):
        grouped_data[vtype] = list(group)

    # 7) Define the desired order for v_nsfr_type (as used by the template)
    ordered_types = ["REQUIRED STABLE FUNDING", "AVAILABLE STABLE FUNDING", "NSFR RATIO"]

    # 8) Gather distinct MIS dates and currencies for filter dropdowns
    all_mis_dates = NSFRStockSummary.objects.values_list("fic_mis_date", flat=True).distinct()
    all_currencies = NSFRStockSummary.objects.values_list("v_ccy_code", flat=True).distinct()

    # 9) Build context and render the template
    context = {
        "grouped_data": grouped_data,
        "ordered_types": ordered_types,
        "all_mis_dates": all_mis_dates,
        "all_currencies": all_currencies,
        "fic_mis_date_selected": fic_mis_date_selected,
        "currency_selected": currency_selected,
    }
    return render(request, "LRM_APP/nsfr/nsfr_stock_summary.html", context)

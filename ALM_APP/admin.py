from django.contrib import admin
from .models import *

#Registering the models in the admin interface
admin.site.register(Ldn_Product_Master)
admin.site.register(Ldn_Common_Coa_Master)
admin.site.register(Dim_Product)
admin.site.register(Dim_Common_Coa)
admin.site.register(Dim_Dates)
admin.site.register(Dim_Fcst_Rates_Scenario)
admin.site.register(Dim_Result_Bucket)



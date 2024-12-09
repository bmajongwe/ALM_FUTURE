# ALM_APP/models.py
from django.db import models
from datetime import timedelta, date
from django.utils import timezone
from django.forms import ValidationError


from django.db import models
from django.core.exceptions import ValidationError

class BehavioralPatternConfig(models.Model):
    v_prod_type = models.CharField(max_length=255, unique=True)  ## Ensure v_prod_type is unique, Product type linked to the product master
    description = models.TextField()  # Optional description of the pattern
    created_at = models.DateTimeField(auto_now_add=True)  # This will automatically store the creation time
    created_by = models.CharField(max_length=100, default='System')  # New field for the creator
    last_changed_at = models.DateTimeField(auto_now=True)  # Automatically updated on every save
    last_changed_by = models.CharField(max_length=100, default='System')  # New field for the person who made the last change



    def __str__(self):
        return f"Behavioral Pattern for {self.v_prod_type}"

# New model for pattern entries (tenor, multiplier, percentage)
class BehavioralPatternEntry(models.Model):
    order = models.IntegerField()  # New field to store the order of the entry
    pattern = models.ForeignKey(BehavioralPatternConfig, on_delete=models.CASCADE, related_name='entries')
    tenor = models.IntegerField()  # Tenor for bucket (e.g., 1 month)
    multiplier = models.CharField(max_length=10, choices=[('Days', 'Days'), ('Months', 'Months'), ('Years', 'Years')])
    percentage = models.DecimalField(max_digits=6, decimal_places=3)

    def __str__(self):
        return f"Tenor: {self.tenor}, Multiplier: {self.multiplier}, Percentage: {self.percentage}"

    def clean(self):
        # Ensure percentage is valid (e.g., between 0 and 100)
        if self.percentage < 0 or self.percentage > 100:
            raise ValidationError("Percentage must be between 0 and 100.")

    


class TimeBucketMaster(models.Model):
    process_name = models.CharField(max_length=100)  # Name of the process (e.g., "Process X")
    bucket_number = models.IntegerField()  # Bucket number (1 to N)
    start_date = models.DateField()  # Start date of the time bucket
    end_date = models.DateField()  # End date of the time bucket
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp of bucket creation

    class Meta:
        unique_together = ('process_name', 'bucket_number')  # Ensure unique bucket per process

    def __str__(self):
        return f"{self.process_name} - Bucket {self.bucket_number} ({self.start_date} to {self.end_date})"




class TimeBucketDefinition(models.Model):
    name = models.CharField(max_length=100)  # Name of the time bucket set
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=100, default="System")
    last_changed_at = models.DateTimeField(auto_now=True)
    last_changed_by = models.CharField(max_length=100, default="System")

    def __str__(self):
        return self.name


class TimeBuckets(models.Model):
    # Auto-incremented serial number within the scope of each definition
    serial_number = models.IntegerField()
    # Foreign key to associate with TimeBucketDefinition
    definition = models.ForeignKey(TimeBucketDefinition, on_delete=models.CASCADE, related_name='buckets')  
    # Date range
    start_date = models.DateField()  # Start date for this time bucket
    end_date = models.DateField()  # End date for this time bucket
    # Frequency details
    frequency = models.IntegerField()  # Frequency as an integer (e.g., 7 days, 3 months)
    multiplier = models.CharField(max_length=20)  # Days, Months, Years

    class Meta:
        db_table = 'time_buckets'

    def __str__(self):
        return f"Bucket {self.serial_number}: {self.start_date} - {self.end_date} ({self.multiplier})"
    
    def save(self, *args, **kwargs):
        # Auto-increment serial_number based on the defi
        if not self.pk:
            last_bucket = TimeBuckets.objects.filter(definition=self.definition).order_by('-serial_number').first()
            self.serial_number = (last_bucket.serial_number + 1) if last_bucket else 1
        super(TimeBuckets, self).save(*args, **kwargs)










class Function(models.Model):
    function_name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = 'dim_function'

    def __str__(self):
        return self.function_name

class Process_Rn(models.Model):
    process_name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'dim_process'

    def __str__(self):
        return self.process_name

class TableMetadata(models.Model):
    TABLE_TYPE_CHOICES = [('FACT', 'Fact Table'),('DIM', 'Dimension Table'),('REF', 'Reference Table'),('STG', 'Staging Table'),('OTHER', 'Other'),]
    table_name = models.CharField(max_length=50, unique=True)
    description = models.TextField(null=True, blank=True)
    table_type = models.CharField(max_length=10, choices=TABLE_TYPE_CHOICES, default='OTHER')

    class Meta:
        db_table = "TableMetadata"
class FunctionExecutionStatus(models.Model):
    process = models.ForeignKey(Process_Rn, on_delete=models.CASCADE)
    function = models.ForeignKey(Function, on_delete=models.CASCADE)
    execution_start_date = models.DateTimeField(auto_now_add=True)  # Renamed from execution_date to execution_start_date
    execution_end_date = models.DateTimeField(null=True, blank=True)  # New field for when the function finishes execution
    duration = models.DurationField(null=True, blank=True)
    execution_order = models.PositiveIntegerField(null=True)
    reporting_date = models.DateField(null=True)
    status = models.CharField(max_length=20, choices=[('Pending', 'Pending'), ('Ongoing', 'Ongoing'), ('Success', 'Success'), ('Failed', 'Failed')], default='Pending')
    
    # Track process execution instances
    process_run_id = models.CharField(max_length=50)  # Combined process_id, execution_date, and run_count
    run_count = models.PositiveIntegerField()  # Tracks how many times this process has been executed on a particular date

    class Meta:
        db_table = 'dim_function_execution_status'
        ordering = ['run_count', 'execution_start_date']
        constraints = [
            models.UniqueConstraint(fields=['execution_start_date', 'process_run_id','function'], name='unique_execution_process')
        ]
      

    def __str__(self):
        return f"{self.process.process_name} - {self.function.function_name} - {self.status}"
    
    


class RunProcess(models.Model):
    process = models.ForeignKey(Process_Rn, on_delete=models.CASCADE, related_name='run_processes')
    function = models.ForeignKey(Function, on_delete=models.CASCADE)
    order = models.PositiveIntegerField()  # Order in which the function will be executed

    class Meta:
        ordering = ['order']  # Ensures the functions are executed in the specified order
        db_table = 'dim_process_dtl'

    def __str__(self):
        return f"{self.process.process_name} - {self.function.function_name} - Order: {self.order}"










class Ldn_Financial_Instrument(models.Model):
    fic_mis_date = models.DateField(null=True)
    v_account_number = models.CharField(max_length=255, unique=True, null=False)
    v_cust_ref_code = models.CharField(max_length=50, null=True)
    v_prod_code = models.CharField(max_length=50, null=True)
    n_curr_interest_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, help_text="Fixed interest rate for the loan")    
    # The changing interest rate (e.g., LIBOR or SOFR)
    n_interest_changing_rate = models.DecimalField(max_digits=5, decimal_places=4, null=True, help_text="Changing interest rate value, e.g., LIBOR rate at a specific time")   
    v_interest_freq_unit = models.CharField(max_length=50, null=True)
    v_interest_payment_type = models.CharField(max_length=50, null=True)
    v_day_count_ind= models.CharField(max_length=7,default='30/365', help_text="This column stores the accrual basis code for interest accrual calculation.")
    # New fields for variable rate and fees   
    v_management_fee_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, help_text="Annual management fee rate, e.g., 1%")
    n_wht_percent= models.DecimalField(max_digits=10, decimal_places=2, null=True)
    n_effective_interest_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    n_accrued_interest = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    d_start_date = models.DateField(null=True)
    d_last_payment_date = models.DateField(null=True)
    d_next_payment_date = models.DateField(null=True)
    d_maturity_date = models.DateField(null=True)
    v_amrt_repayment_type = models.CharField(max_length=50, null=True)
    v_amrt_term_unit = models.CharField(max_length=50, null=True)
    n_eop_curr_prin_bal = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    n_eop_int_bal = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    n_eop_bal = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    n_collateral_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    n_acct_risk_score = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    v_ccy_code = models.CharField(max_length=10, null=True)
    v_loan_type = models.CharField(max_length=50, null=True)
    m_fees = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    v_m_fees_term_unit=models.CharField(max_length=1, null=True)
    v_lob_code = models.CharField(max_length=50, null=True)
    v_lv_code = models.CharField(max_length=50, null=True)
    v_country_id = models.CharField(max_length=50, null=True)
    v_credit_score = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    v_collateral_type = models.CharField(max_length=50, null=True)
    v_loan_desc = models.CharField(max_length=255, null=True)
    v_account_classification_cd = models.CharField(max_length=50, null=True)
    v_gaap_code = models.CharField(max_length=50, null=True)
    v_branch_code = models.CharField(max_length=50, null=True)
    class Meta:
        db_table = 'Ldn_Financial_Instrument'



class product_level_cashflows(models.Model):
    fic_mis_date = models.DateField(null=False)
    v_account_number = models.CharField(max_length=255, null=False)
    v_prod_code = models.CharField(max_length=50, null=False)
    v_loan_type = models.CharField(max_length=50, null=True)
    V_CASH_FLOW_TYPE = models.CharField(max_length=50, null=True, blank=True)  # Example field for cash flow type
    n_cash_flow_bucket = models.IntegerField() 
    d_cashflow_date = models.DateField()  # New field to store the cashflow date
    n_total_cash_flow_amount = models.DecimalField(max_digits=20, decimal_places=2)
    n_total_principal_payment = models.DecimalField(max_digits=20, decimal_places=2)
    n_total_interest_payment = models.DecimalField(max_digits=20, decimal_places=2)
    n_total_balance = models.DecimalField(max_digits=20, decimal_places=2)
    v_ccy_code = models.CharField(max_length=10)
    record_count = models.IntegerField(default=0)


    class Meta:
        db_table = 'product_level_cashflows'

class Ldn_Payment_Schedule(models.Model):
    fic_mis_date = models.DateField(null=False)
    v_account_number = models.CharField(max_length=50, null=False)
    d_payment_date = models.DateField(null=False)
    n_principal_payment_amt = models.DecimalField(max_digits=22, decimal_places=3, null=True)
    n_interest_payment_amt = models.DecimalField(max_digits=22, decimal_places=3, null=True)
    n_amount = models.DecimalField(max_digits=22, decimal_places=3, null=True)
    v_payment_type_cd = models.CharField(max_length=20, null=True)  # Payment type code
    class Meta:
        db_table = 'Ldn_Payment_Schedule'


class NewFinancialTable(models.Model):
    v_account_number = models.CharField(max_length=255, null=True)
    v_gaap_code = models.CharField(max_length=50, null=True)
    fic_mis_date = models.DateField(null=True)
    n_load_run_id = models.IntegerField(null=True)
    v_ccy_code = models.CharField(max_length=10, null=True)
    v_data_origin = models.CharField(max_length=255, null=True)
    v_org_unit_code = models.CharField(max_length=255, null=True)
    v_prod_code = models.CharField(max_length=255, null=True)
    v_cust_type = models.CharField(max_length=50, null=True)
    v_cust_ref_code = models.CharField(max_length=50, null=True)
    d_value_date = models.DateField(null=True)
    d_closed_date = models.DateField(null=True)
    d_open_date = models.DateField(null=True)
    d_maturity_date = models.DateField(null=True)
    d_last_payment_date = models.DateField(null=True)
    d_next_payment_date = models.DateField(null=True)
    n_eop_bal = models.DecimalField(max_digits=15, decimal_places=2, null=True)
    n_eop_prin_amt = models.DecimalField(max_digits=15, decimal_places=2, null=True)
    n_cur_payment = models.DecimalField(max_digits=15, decimal_places=2, null=True)
    n_curr_interest_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    v_day_count_ind = models.CharField(max_length=50, null=True)
    n_int_freq = models.IntegerField(null=True)
    v_interest_freq_unit = models.CharField(max_length=50, null=True)
    v_repayment_type = models.CharField(max_length=255, null=True)
    v_amrt_type_cd = models.CharField(max_length=50, null=True)
    n_amrt_term = models.IntegerField(null=True)
    v_amrt_term_unit = models.CharField(max_length=10, null=True)

    class Meta:
        db_table = 'new_financial_table'

class FSI_Expected_Cashflow(models.Model):
    fic_mis_date = models.DateField()
    v_account_number = models.CharField(max_length=50)
    v_loan_type = models.CharField(max_length=50, null=True)
    n_cash_flow_bucket = models.IntegerField() 
    d_cash_flow_date = models.DateField()
    n_principal_payment = models.DecimalField(max_digits=20, decimal_places=2)
    n_interest_payment = models.DecimalField(max_digits=20, decimal_places=2)
    n_cash_flow_amount = models.DecimalField(max_digits=20, decimal_places=2)
    n_balance = models.DecimalField(max_digits=20, decimal_places=2)
    n_accrued_interest = models.DecimalField(max_digits=22, decimal_places=3, null=True, blank=True)  # Accrued interest
    n_exposure_at_default = models.DecimalField(max_digits=22, decimal_places=3, null=True, blank=True) 
    V_CASH_FLOW_TYPE = models.CharField(max_length=10)
    management_fee_added = models.DecimalField(max_digits=20, decimal_places=2)
    V_CCY_CODE = models.CharField(max_length=3)

    class Meta:
        db_table = 'FSI_Expected_Cashflow'
        unique_together = ('fic_mis_date', 'v_account_number', 'd_cash_flow_date')


class Fsi_Interest_Method(models.Model):
    # Define choices for the interest method
    INTEREST_METHOD_CHOICES = [('Simple', 'Simple Interest'), ('Compound', 'Compound Interest'),('Amortized', 'Amortized Interest'),('Floating', 'Floating/Variable Interest'),]
    
    v_interest_method = models.CharField( max_length=50, choices=INTEREST_METHOD_CHOICES,unique=True)
    description = models.TextField(blank=True)  # Optional description for documentation
  

    def _str_(self):
        return self.v_interest_method
    






class ProductFilter(models.Model):
    field_name = models.CharField(max_length=50)  # Name of the field to filter by
    condition = models.CharField(max_length=50)  # Type of condition (equals, contains, etc.)
    value = models.CharField(max_length=255)  # Value to filter with
    created_by = models.CharField(max_length=50, default='System')
    created_at = models.DateTimeField(default=timezone.now)
    modified_by = models.CharField(max_length=50, default='System')
    modified_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.field_name} {self.condition} {self.value}"


class Process(models.Model):
    name = models.CharField(max_length=100)  # Name of the process (e.g., 'contractual', 'forecast', etc.
    description = models.TextField(null=True, blank=True)  # Optional description for the process
    uses_behavioral_patterns = models.BooleanField(default=False)
    filters = models.ManyToManyField(ProductFilter, related_name='processes')
    execution_date = models.DateTimeField(null=True, blank=True)  # Optional field to track last execution date
    status = models.CharField(max_length=20, default='Pending')  # Track status (e.g., 'Pending', 'Completed')
    created_by = models.CharField(max_length=50, default='System')
    created_at = models.DateTimeField(default=timezone.now)
    modified_by = models.CharField(max_length=50, default='System')
    modified_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
# class Process(models.Model):
#     name = models.CharField(max_length=100)
#     filters = models.ManyToManyField(ProductFilter, related_name='processes')
#     created_by = models.CharField(max_length=50, default='System')
#     created_at = models.DateTimeField(default=timezone.now)
#     modified_by = models.CharField(max_length=50, default='System')
#     modified_at = models.DateTimeField(auto_now=True)

#     def __str__(self):
#         return self.name

class Ldn_Product_Master(models.Model):  # Class name with underscores
    v_prod_code = models.CharField(max_length=20, null=False)  # VARCHAR2(20)
    fic_mis_date = models.DateField(null=False)  # DATE
    v_prod_name = models.CharField(max_length=255, null=True)  # VARCHAR2(255)
    v_prod_type = models.CharField(max_length=255, null=True)  # VARCHAR2(20)
    v_prod_group_desc = models.CharField(max_length=255, null=True)  # VARCHAR2(255)
    f_prod_rate_sensitivity = models.CharField(max_length=1, null=True)  # VARCHAR2(1)
    v_common_coa_code = models.CharField(max_length=20, null=True)  # VARCHAR2(20)
    v_balance_sheet_category = models.CharField(max_length=20, null=True)  # VARCHAR2(20)
    v_balance_sheet_category_desc = models.CharField(max_length=255, null=True)  # VARCHAR2(255)
    v_prod_type_desc = models.CharField(max_length=255, null=True)  # VARCHAR2(255)
    v_load_type = models.CharField(max_length=20, null=True)  # VARCHAR2(20)
    v_lob_code = models.CharField(max_length=20, null=True)  # VARCHAR2(20)
    v_prod_desc = models.CharField(max_length=255, null=True)  # VARCHAR2(255)

    class Meta:
        db_table = 'LDN_PRODUCT_MASTER'  # Explicitly set the table name

    def __str__(self):
        return self.v_prod_code
    


class Ldn_Common_Coa_Master(models.Model):  # Class with underscores in the name
    v_common_coa_code = models.CharField(max_length=20, null=True)  # VARCHAR2(20 CHAR)
    v_common_coa_name = models.CharField(max_length=150, null=True)  # VARCHAR2(150 CHAR)
    v_common_coa_description = models.CharField(max_length=60, null=True)  # VARCHAR2(60 CHAR)
    v_accrual_basis_code = models.CharField(max_length=10, null=True)  # VARCHAR2(10 CHAR)
    v_account_type = models.CharField(max_length=20, null=True)  # VARCHAR2(20 CHAR)
    fic_mis_date = models.DateField(null=True)  # DATE
    v_rollup_signage_code = models.CharField(max_length=5, null=True)  # VARCHAR2(5 CHAR)
    d_start_date = models.DateField(null=True)  # DATE
    d_end_date = models.DateField(null=True)  # DATE

    class Meta:
        db_table = 'LDN_COMMON_COA_MASTER'  # Explicitly set the table name


class Dim_Product(models.Model):  # Class with underscores in the name
    v_prod_desc = models.CharField(max_length=255, null=True)  # VARCHAR2(255 CHAR)
    v_prod_code = models.CharField(max_length=255, null=False)  # VARCHAR2(20 CHAR) NOT NULL
    fic_mis_date = models.DateField(null=True)  # DATE
    v_prod_family_desc = models.CharField(max_length=255, null=True)  # VARCHAR2(255 CHAR)
    v_prod_code_level3 = models.CharField(max_length=20, null=True)  # VARCHAR2(20 CHAR)
    v_prod_group = models.CharField(max_length=5, null=True)  # VARCHAR2(5 CHAR)
    f_latest_record_indicator = models.CharField(max_length=1, null=True)  # CHAR(1 CHAR)
    d_record_end_date = models.DateField(null=True)  # DATE
    d_record_start_date = models.DateField(null=True)  # DATE
    v_prod_group_desc = models.CharField(max_length=255, null=True)  # VARCHAR2(255 CHAR)
    v_prod_type = models.CharField(max_length=255, null=True)  # VARCHAR2(20 CHAR)
    f_prod_rate_sensitivity = models.CharField(max_length=1, null=True)  # VARCHAR2(1 CHAR)
    v_account_type = models.CharField(max_length=20, null=True)  # VARCHAR2(20 CHAR)
    v_prod_branch_code = models.CharField(max_length=10, null=True)  # VARCHAR2(10 CHAR)
    v_prod_code_level1 = models.CharField(max_length=20, null=True)  # VARCHAR2(20 CHAR)
    n_prod_skey = models.BigIntegerField(null=False)  # NUMBER(14,0) NOT NULL
    v_prod_code_level1_desc = models.CharField(max_length=255, null=True)  # VARCHAR2(255 CHAR)
    v_prod_code_level2_desc = models.CharField(max_length=255, null=True)  # VARCHAR2(255 CHAR)
    v_prod_code_level3_desc = models.CharField(max_length=255, null=True)  # VARCHAR2(255 CHAR)
    d_created_date = models.DateField(null=True)  # DATE
    d_last_modified_date = models.DateField(null=True)  # DATE
    n_account_type = models.IntegerField(null=True)  # NUMBER(5,0)
    n_product_id = models.BigIntegerField(null=True)  # NUMBER(14,0)
    n_product_id_level01 = models.BigIntegerField(null=True)  # NUMBER(14,0)
    n_product_id_level02 = models.BigIntegerField(null=True)  # NUMBER(14,0)
    n_product_id_level03 = models.BigIntegerField(null=True)  # NUMBER(14,0)
    n_product_id_level04 = models.BigIntegerField(null=True)  # NUMBER(14,0)
    n_product_id_level05 = models.BigIntegerField(null=True)  # NUMBER(14,0)
    n_product_id_level06 = models.BigIntegerField(null=True)  # NUMBER(14,0)
    n_product_id_level07 = models.BigIntegerField(null=True)  # NUMBER(14,0)
    v_balance_sheet_category = models.CharField(max_length=255, null=True)  # VARCHAR2(20 CHAR)
    v_balance_sheet_category_desc = models.CharField(max_length=255, null=True)  # VARCHAR2(255 CHAR)
    v_created_by = models.CharField(max_length=40, null=True)  # VARCHAR2(40 CHAR)
    v_last_modified_by = models.CharField(max_length=30, null=True)  # VARCHAR2(30 CHAR)
    v_prod_type_desc = models.CharField(max_length=255, null=True)  # VARCHAR2(255 CHAR)
    v_product_name = models.CharField(max_length=150, null=True)  # VARCHAR2(150 CHAR)
    v_product_name_level01 = models.CharField(max_length=150, null=True)  # VARCHAR2(150 CHAR)
    v_product_name_level02 = models.CharField(max_length=150, null=True)  # VARCHAR2(150 CHAR)
    v_product_name_level03 = models.CharField(max_length=150, null=True)  # VARCHAR2(150 CHAR)
    v_product_name_level04 = models.CharField(max_length=150, null=True)  # VARCHAR2(150 CHAR)
    v_product_name_level05 = models.CharField(max_length=150, null=True)  # VARCHAR2(150 CHAR)
    v_product_name_level06 = models.CharField(max_length=150, null=True)  # VARCHAR2(150 CHAR)
    v_product_name_level07 = models.CharField(max_length=150, null=True)  # VARCHAR2(150 CHAR)
    v_prod_name = models.CharField(max_length=255, null=True)  # VARCHAR2(255 CHAR)
    v_lob_code = models.CharField(max_length=20, null=True)  # VARCHAR2(20 CHAR)
    n_lob_skey = models.BigIntegerField(null=True)  # NUMBER(10,0)
    n_product_limit = models.DecimalField(max_digits=22, decimal_places=3, null=True)  # NUMBER(22,3)
    n_interest_only_term = models.IntegerField(null=True)  # NUMBER(5,0)
    v_prod_code_level4 = models.CharField(max_length=20, null=True)  # VARCHAR2(20 CHAR)
    v_prod_code_level5 = models.CharField(max_length=20, null=True)  # VARCHAR2(20 CHAR)
    v_prod_code_level6 = models.CharField(max_length=20, null=True)  # VARCHAR2(20 CHAR)
    v_prod_code_level7 = models.CharField(max_length=20, null=True)  # VARCHAR2(20 CHAR)
    v_prod_code_level4_desc = models.CharField(max_length=255, null=True)  # VARCHAR2(255 CHAR)
    v_prod_code_level5_desc = models.CharField(max_length=255, null=True)  # VARCHAR2(255 CHAR)
    v_prod_code_level6_desc = models.CharField(max_length=255, null=True)  # VARCHAR2(255 CHAR)
    v_prod_code_level7_desc = models.CharField(max_length=255, null=True)  # VARCHAR2(255 CHAR)
    v_flow_type = models.CharField(max_length=20, choices=[('Inflow', 'Inflow'), ('Outflow', 'Outflow')], null=True, blank=True)


    class Meta:
        db_table = 'DIM_PRODUCT'  # Explicitly set the table name


class Dim_Common_Coa(models.Model):  # Class with underscores in the name
    n_common_coa_skey = models.BigIntegerField(null=False)  # NUMBER(14,0) NOT NULL
    n_common_coa_id = models.BigIntegerField(null=False)  # NUMBER(14,0) NOT NULL
    v_common_coa_name = models.CharField(max_length=150, null=False)  # VARCHAR2(150 CHAR) NOT NULL
    v_created_by = models.CharField(max_length=40, null=True)  # VARCHAR2(40 CHAR)
    v_last_modified_by = models.CharField(max_length=30, null=True)  # VARCHAR2(30 CHAR)
    d_last_modified_date = models.DateField(null=True)  # DATE
    f_latest_record_indicator = models.CharField(max_length=1, null=True)  # CHAR(1 CHAR)
    n_common_coa_id_level01 = models.BigIntegerField(null=True)  # NUMBER(14,0)
    n_common_coa_id_level02 = models.BigIntegerField(null=True)  # NUMBER(14,0)
    n_common_coa_id_level03 = models.BigIntegerField(null=True)  # NUMBER(14,0)
    n_common_coa_id_level04 = models.BigIntegerField(null=True)  # NUMBER(14,0)
    n_common_coa_id_level05 = models.BigIntegerField(null=True)  # NUMBER(14,0)
    n_common_coa_id_level06 = models.BigIntegerField(null=True)  # NUMBER(14,0)
    n_common_coa_id_level07 = models.BigIntegerField(null=True)  # NUMBER(14,0)
    v_common_coa_name_level01 = models.CharField(max_length=150, null=True)  # VARCHAR2(150 CHAR)
    v_common_coa_name_level02 = models.CharField(max_length=150, null=True)  # VARCHAR2(150 CHAR)
    v_common_coa_name_level03 = models.CharField(max_length=150, null=True)  # VARCHAR2(150 CHAR)
    v_common_coa_name_level04 = models.CharField(max_length=150, null=True)  # VARCHAR2(150 CHAR)
    v_common_coa_name_level05 = models.CharField(max_length=150, null=True)  # VARCHAR2(150 CHAR)
    v_common_coa_name_level06 = models.CharField(max_length=150, null=True)  # VARCHAR2(150 CHAR)
    v_common_coa_name_level07 = models.CharField(max_length=150, null=True)  # VARCHAR2(150 CHAR)
    n_account_type = models.IntegerField(null=True)  # NUMBER(5,0)
    v_common_coa_code = models.CharField(max_length=20, null=True)  # VARCHAR2(20 CHAR)
    v_common_coa_type = models.CharField(max_length=20, null=True)  # VARCHAR2(20 CHAR)
    v_common_coa_type_desc = models.CharField(max_length=60, null=True)  # VARCHAR2(60 CHAR)
    fic_mis_date = models.DateField(null=True)  # DATE
    d_record_start_date = models.DateField(null=True)  # DATE
    d_record_end_date = models.DateField(null=True)  # DATE

    class Meta:
        db_table = 'DIM_COMMON_COA'  # Explicitly set the table name



class Dim_Result_Bucket(models.Model):  # Class with underscores in the name
    n_result_bucket_skey = models.BigIntegerField(null=False)  # NUMBER(10,0) NOT NULL
    n_start_date_index = models.IntegerField(null=True)  # NUMBER(5,0)
    d_parent_start_date = models.DateField(null=True)  # DATE
    d_bucket_start_date = models.DateField(null=True)  # DATE
    d_bucket_end_date = models.DateField(null=True)  # DATE
    n_bucket_no = models.IntegerField(null=False)  # NUMBER(5,0) NOT NULL
    v_bucket_name = models.CharField(max_length=30, null=True)  # VARCHAR2(30 CHAR)
    n_bucket_term_freq = models.BigIntegerField(null=True)  # NUMBER(10,0)
    f_bucket_term_freq_mult = models.CharField(max_length=1, null=True)  # CHAR(1 CHAR)
    v_created_by = models.CharField(max_length=40, null=True)  # VARCHAR2(40 CHAR)
    d_created_date = models.DateField(null=True)  # DATE
    v_last_modified_by = models.CharField(max_length=30, null=True)  # VARCHAR2(30 CHAR)
    d_last_modified_date = models.DateField(null=True)  # DATE
    f_latest_record_indicator = models.CharField(max_length=1, null=True)  # CHAR(1 CHAR)
    v_bucket_type = models.CharField(max_length=20, null=True)  # VARCHAR2(20 CHAR)
    n_bucket_end_days = models.IntegerField(null=True)  # NUMBER(5,0)
    n_bucket_start_days = models.IntegerField(null=True)  # NUMBER(5,0)
    n_time_bucket_sys_id = models.BigIntegerField(null=True)  # NUMBER(10,0)
    n_bucket_number_category = models.IntegerField(null=True)  # NUMBER(5,0)
    v_bucket_name_category = models.CharField(max_length=30, null=True)  # VARCHAR2(30 CHAR)
    n_bucket_number_sub_category = models.IntegerField(null=True)  # NUMBER(5,0)
    v_bucket_name_sub_category = models.CharField(max_length=30, null=True)  # VARCHAR2(30 CHAR)
    d_as_of_date = models.DateField(null=True)  # DATE
    fic_mis_date = models.DateField(null=True)  # DATE
    d_record_start_date = models.DateField(null=True)  # DATE
    d_record_end_date = models.DateField(null=True)  # DATE
    v_result_bucket_desc = models.CharField(max_length=255, null=True)  # VARCHAR2(255 CHAR)

    class Meta:
        db_table = 'DIM_RESULT_BUCKET'  # Explicitly set the table name


class Dim_Fcst_Rates_Scenario(models.Model):  # Class with underscores in the name
    n_proc_scen_skey = models.BigIntegerField(null=False)  # NUMBER(10,0) NOT NULL
    n_scenario_num = models.BigIntegerField(null=False)  # NUMBER(20,0) NOT NULL
    n_process_id = models.BigIntegerField(null=False)  # NUMBER(20,0) NOT NULL
    n_process_type = models.IntegerField(null=False)  # NUMBER(5,0) NOT NULL
    v_created_by = models.CharField(max_length=40, null=True)  # VARCHAR2(40 CHAR)
    d_created_date = models.DateField(null=True)  # DATE
    v_last_modified_by = models.CharField(max_length=30, null=True)  # VARCHAR2(30 CHAR)
    d_last_modified_date = models.DateField(null=True)  # DATE
    d_start_date = models.DateField(null=True)  # DATE
    d_end_date = models.DateField(null=True)  # DATE
    f_latest_record_indicator = models.CharField(max_length=1, null=True)  # CHAR(1 CHAR)
    v_process_name = models.CharField(max_length=100, null=False)  # VARCHAR2(100 CHAR) NOT NULL
    v_scenario_name = models.CharField(max_length=60, null=False)  # VARCHAR2(60 CHAR) NOT NULL
    n_fcast_rate_sys_id = models.BigIntegerField(null=True)  # NUMBER(10,0)
    v_fcast_rate_name = models.CharField(max_length=50, null=True)  # VARCHAR2(50 CHAR)
    fic_mis_date = models.DateField(null=True)  # DATE
    d_record_start_date = models.DateField(null=True)  # DATE
    d_record_end_date = models.DateField(null=True)  # DATE
    v_fcast_rate_scenario_desc = models.CharField(max_length=255, null=True)  # VARCHAR2(255 CHAR)

    class Meta:
        db_table = 'DIM_FCST_RATES_SCENARIO'  # Explicitly set the table name


class Dim_Dates(models.Model):  # Class with underscores in the name
    n_date_skey = models.BigIntegerField(null=False)  # NUMBER(10,0) NOT NULL
    fic_mis_date = models.DateField()  # Ensure this exists
    d_calendar_date = models.DateField(null=True)  # DATE NOT NULL
    n_half_calendar = models.IntegerField(null=True)  # NUMBER(2,0)
    n_month_calendar = models.IntegerField(null=True)  # NUMBER(2,0)
    n_qtr_calendar = models.IntegerField(null=True)  # NUMBER(1,0)
    n_trimester_calendar = models.BigIntegerField(null=True)  # NUMBER(10,0)
    n_week_calendar = models.IntegerField(null=True)  # NUMBER(2,0)
    n_year_calendar = models.IntegerField(null=True)  # NUMBER(5,0)
    v_day_name = models.CharField(max_length=30, null=True)  # VARCHAR2(30 CHAR)
    n_day_of_month = models.IntegerField(null=True)  # NUMBER(2,0)
    n_day_of_week = models.IntegerField(null=True)  # NUMBER(1,0)
    n_day_of_year = models.IntegerField(null=True)  # NUMBER(3,0)
    v_half_period_name = models.CharField(max_length=50, null=True)  # VARCHAR2(50 CHAR)
    v_month_period_name = models.CharField(max_length=50, null=True)  # VARCHAR2(50 CHAR)
    v_qtr_period_name = models.CharField(max_length=50, null=True)  # VARCHAR2(50 CHAR)
    v_ter_period_name = models.CharField(max_length=50, null=True)  # VARCHAR2(50 CHAR)
    v_week_period_name = models.CharField(max_length=50, null=True)  # VARCHAR2(50 CHAR)
    v_year_period_name = models.CharField(max_length=50, null=True)  # VARCHAR2(50 CHAR)
    v_created_by = models.CharField(max_length=40, null=True)  # VARCHAR2(40 CHAR)
    d_created_date = models.DateField(null=True)  # DATE
    v_last_modified_by = models.CharField(max_length=30, null=True)  # VARCHAR2(30 CHAR)
    d_last_modified_date = models.DateField(null=True)  # DATE
    bucket_start_date = models.DateField(null=True)  # DATE
    bucket_end_date = models.DateField(null=True)  # DATE
    bucket_number = models.IntegerField(null=True)  # New field for bucket number
    f_latest_record_indicator = models.CharField(max_length=1, null=True)  # CHAR(1 CHAR)
    d_fiscal_quarter_start_date = models.DateField(null=True)  # DATE
    d_fiscal_quarter_end_date = models.DateField(null=True)  # DATE
    d_fiscal_month_start_date = models.DateField(null=True)  # DATE
    d_fiscal_month_end_date = models.DateField(null=True)  # DATE
    d_fiscal_year_start_date = models.DateField(null=True)  # DATE
    d_fiscal_year_end_date = models.DateField(null=True)  # DATE
    v_fiscal_qtr_period_name = models.CharField(max_length=50, null=True)  # VARCHAR2(50 CHAR)
    v_fiscal_year_name = models.CharField(max_length=50, null=True)  # VARCHAR2(50 CHAR)

    class Meta:
        db_table = 'DIM_DATES'  # Explicitly set the table name


class Fsi_Financial_Assets_Processing(models.Model):  # Class with underscores in the name
    cur_net_par_bal_c = models.DecimalField(max_digits=14, decimal_places=2, null=True)  # NUMBER(14,2)
    product_id = models.BigIntegerField(null=False)  # NUMBER(14,0) NOT NULL
    iso_currency_cd = models.CharField(max_length=15, null=False)  # VARCHAR2(15 CHAR) NOT NULL
    org_unit_id = models.BigIntegerField(null=False)  # NUMBER(14,0) NOT NULL
    accrual_basis_cd = models.IntegerField(null=True)  # NUMBER(5,0)
    common_coa_id = models.BigIntegerField(null=False)  # NUMBER(14,0) NOT NULL
    as_of_date = models.DateField(null=False)  # DATE NOT NULL
    legal_entity_id = models.BigIntegerField(default=-1, null=False)  # NUMBER(14,0) DEFAULT -1 NOT NULL
    branch_cd = models.IntegerField(null=True)  # NUMBER(5,0)
    cur_book_bal = models.DecimalField(max_digits=14, decimal_places=2, null=True)  # NUMBER(14,2)
    cur_net_rate = models.DecimalField(max_digits=10, decimal_places=6, null=True)  # NUMBER(10,6)
    cur_par_bal = models.DecimalField(max_digits=14, decimal_places=2, null=True)  # NUMBER(14,2)
    identity_code = models.BigIntegerField(null=False)  # NUMBER(10,0) NOT NULL
    identity_code_chg = models.BigIntegerField(null=True)  # NUMBER(10,0)
    id_number = models.BigIntegerField(null=False)  # NUMBER(25,0) NOT NULL
    instrument_type_cd = models.IntegerField(null=True)  # NUMBER(5,0)
    record_count = models.IntegerField(null=True)  # NUMBER(6,0)
    amrt_term = models.IntegerField(null=True)  # NUMBER(5,0)
    amrt_term_mult = models.CharField(max_length=1, null=True)  # CHAR(1 CHAR)
    amrt_type_cd = models.IntegerField(null=True)  # NUMBER(5,0)
    account_number = models.CharField(max_length=50, null=True)  # VARCHAR2(50 CHAR)
    customer_name = models.CharField(max_length=25, null=True)  # VARCHAR2(25 CHAR)
    cur_payment = models.DecimalField(max_digits=14, decimal_places=2, null=True)  # NUMBER(14,2)
    customer_type = models.IntegerField(null=True)  # NUMBER(5,0)
    account_classification_cd = models.IntegerField(null=True)  # NUMBER(5,0)
    issue_date = models.DateField(null=True)  # DATE
    last_payment_date = models.DateField(null=True)  # DATE
    next_payment_date = models.DateField(null=True)  # DATE
    maturity_date = models.DateField(null=True)  # DATE
    customer_id = models.BigIntegerField(null=False)  # NUMBER(14,0) NOT NULL
    behaviour_type_cd = models.IntegerField(null=True)  # NUMBER(5,0)
    behaviour_sub_type_cd = models.IntegerField(null=True)  # NUMBER(5,0)
    maturity_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True)  # NUMBER(14,2)

    class Meta:
        db_table = 'FSI_FINANCIAL_ASSETS_PROCESSING'  # Explicitly set the table name



class AggregatedCashflowByBuckets(models.Model):
    fic_mis_date = models.DateField()  # The base date from product_level_cashflows
    process_name = models.CharField(max_length=100)  # Process name to identify different cashflow processes
    v_account_number = models.CharField(max_length=50)  # Account number being aggregated
    v_prod_code = models.CharField(max_length=50)  # Product code to identify the product
    v_loan_type = models.CharField(max_length=50, null=True)
    v_ccy_code = models.CharField(max_length=10, null=True, blank=True)  # Optional currency code
    financial_element = models.CharField(max_length=50)  # Either 'n_total_cash_flow_amount', 'n_total_principal_payment', or 'n_total_interest_payment'
     # Foreign Key to TimeBucketMaster
    time_bucket_master = models.ForeignKey(TimeBucketMaster, on_delete=models.CASCADE, null=True)
    bucket_1 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 1
    bucket_2 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 2
    bucket_3 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_4 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_5 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_6 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_7 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_8 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_9 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_10 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_11 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_12 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_13= models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_14 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_15= models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_16 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_17 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_18 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_19= models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_20= models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_21 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_22 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_23= models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_24 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_25 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_26 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_27 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_28 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_29 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_30 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_31 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_32 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_33 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_34 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_35 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_36 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_37 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_38 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_39 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_40 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_41 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_42 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_43 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_44 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_45 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_46 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_47 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_48 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_49 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_50 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 50

    class Meta:
        db_table = 'ALM_APP_Aggregated_Acc_Cashflow'

    def __str__(self):
        return f"{self.process_name} - Account: {self.v_account_number} ({self.financial_element})"

class Aggregated_Prod_Cashflow_Base(models.Model):
    fic_mis_date = models.DateField()  # The base date from product_level_cashflows
    process_name = models.CharField(max_length=100)  # Process name to identify different cashflow processes
    v_loan_type = models.CharField(max_length=50, null=True)
    v_prod_code = models.CharField(max_length=50)  # Product code  being aggregated
    v_ccy_code = models.CharField(max_length=10, null=False, blank=False)  #  currency code
    financial_element = models.CharField(max_length=50)  # Either 'n_total_cash_flow_amount', 'n_total_principal_payment', or 'n_total_interest_payment'
    # Foreign Key to AggregatedCashflowByBucket
    cashflow_by_bucket = models.ForeignKey(AggregatedCashflowByBuckets, on_delete=models.CASCADE, null=True)

    # Foreign Key to TimeBucketMaster
    time_bucket_master = models.ForeignKey(TimeBucketMaster, on_delete=models.CASCADE, null=True)

    bucket_1 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 1
    bucket_2 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 2
    bucket_3 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 3
    bucket_4 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 4
    bucket_5 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 5
    bucket_6 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 6
    bucket_7 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 7
    bucket_8 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 8
    bucket_9 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 9
    bucket_10 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 10
    bucket_11 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 11
    bucket_12 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 12
    bucket_13= models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 13
    bucket_14 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 14
    bucket_15= models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 15
    bucket_16 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 16
    bucket_17 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 17
    bucket_18 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 18
    bucket_19= models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 19
    bucket_20= models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 20
    bucket_21 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 21
    bucket_22 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 22
    bucket_23= models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 23
    bucket_24 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 24
    bucket_25 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 25
    bucket_26 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 26
    bucket_27 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 27
    bucket_28 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 28
    bucket_29 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 29
    bucket_30 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 30
    bucket_31 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 31
    bucket_32 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 32
    bucket_33 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 33
    bucket_34 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 34
    bucket_35 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 35
    bucket_36 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 36
    bucket_37 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 37
    bucket_38 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 38
    bucket_39 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 39
    bucket_40 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 40
    bucket_41 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 41
    bucket_42 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 42
    bucket_43 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 43
    bucket_44 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 44
    bucket_45 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 45
    bucket_46 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 46
    bucket_47 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 47
    bucket_48 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 48
    bucket_49 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 49
    bucket_50 = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Sum for bucket 50

    class Meta:
        # unique_together = ('fic_mis_date', 'process_name', 'financial_element')  # Ensure uniqueness
      def __str__(self):
        return f"{self.process_name} - Account: {self.v_prod_code} ({self.financial_element})"
    

class LiquidityGapResultsBase(models.Model):
    fic_mis_date = models.DateField()  # Ensure this exists
    process_name = models.CharField(max_length=100)  # Ensure this exists
    account_type = models.CharField(max_length=20)
    v_prod_type = models.CharField(max_length=255)
    v_prod_code = models.CharField(max_length=50)
    v_ccy_code = models.CharField(max_length=10)
    bucket_number = models.IntegerField()  # New field for bucket number
    bucket_start_date = models.DateField()
    bucket_end_date = models.DateField()
    inflows = models.DecimalField(max_digits=20, decimal_places=2)
    outflows = models.DecimalField(max_digits=20, decimal_places=2)
    net_liquidity_gap = models.DecimalField(max_digits=20, decimal_places=2)
    cumulative_gap = models.DecimalField(max_digits=20, decimal_places=2)
    # New fields
    v_product_name = models.CharField(max_length=255, null=True, blank=True)  # Product name from Dim_Product
    v_product_splits = models.CharField(max_length=255, null=True, blank=True)  # Product splits from Dim_customer
    v_prod_type_desc = models.CharField(max_length=255, null=True, blank=True)  # Product type description
    v_loan_type = models.CharField(max_length=50, null=True, blank=True)  # Loan type from Aggregated_Prod_Cashflow_Base
    n_total_cash_flow_amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Total cash flow amount
    n_total_principal_payment = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Total principal payment
    n_total_interest_payment = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Total interest payment


    class Meta:
        db_table = 'liquidity_gap_results_base'



class LiquidityGapResultsCons(models.Model):
    fic_mis_date = models.DateField()  # Ensure this exists
    process_name = models.CharField(max_length=100)  # Ensure this exists
    account_type = models.CharField(max_length=20)
    v_prod_type = models.CharField(max_length=255)
    v_prod_code = models.CharField(max_length=50)
    v_ccy_code = models.CharField(max_length=10)
    bucket_number = models.IntegerField()  # New field for bucket number
    bucket_start_date = models.DateField()
    bucket_end_date = models.DateField()
    inflows = models.DecimalField(max_digits=20, decimal_places=2)
    outflows = models.DecimalField(max_digits=20, decimal_places=2)
    net_liquidity_gap = models.DecimalField(max_digits=20, decimal_places=2)
    cumulative_gap = models.DecimalField(max_digits=20, decimal_places=2)
    # New fields
    v_product_name = models.CharField(max_length=255, null=True, blank=True)  # Product name from Dim_Product
    v_product_splits = models.CharField(max_length=255, null=True, blank=True)  # Product splits from Dim_customer
    v_prod_type_desc = models.CharField(max_length=255, null=True, blank=True)  # Product type description
    v_loan_type = models.CharField(max_length=50, null=True, blank=True)  # Loan type from Aggregated_Prod_Cashflow_Base
    n_total_cash_flow_amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Total cash flow amount
    n_total_principal_payment = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Total principal payment
    n_total_interest_payment = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Total interest payment


    class Meta:
        db_table = 'liquidity_gap_results_cons'




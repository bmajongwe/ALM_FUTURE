from concurrent.futures import ThreadPoolExecutor
from django.db import transaction
from datetime import timedelta, date
from ..models import *


def get_payment_interval(v_amrt_term_unit, day_count_ind):
    """Determine the payment interval in days based on repayment type and day count convention."""
    if day_count_ind == '30/360':
        if v_amrt_term_unit == 'D':
            return timedelta(days=1)  # Daily payments
        elif v_amrt_term_unit == 'W':
            return timedelta(weeks=1)  # Weekly payments
        elif v_amrt_term_unit == 'M':
            return timedelta(days=30)  # Monthly payments
        elif v_amrt_term_unit == 'Q':
            return timedelta(days=90)  # Quarterly payments
        elif v_amrt_term_unit == 'H':
            return timedelta(days=180)  # Semi-annual payments
        elif v_amrt_term_unit == 'Y':
            return timedelta(days=360)  # Annual payments
        else:
            return timedelta(days=30)  # Default to monthly

    elif day_count_ind == '30/365':
        if v_amrt_term_unit == 'D':
            return timedelta(days=1)  # Daily payments
        elif v_amrt_term_unit == 'W':
            return timedelta(weeks=1)  # Weekly payments
        elif v_amrt_term_unit == 'M':
            return timedelta(days=30)  # Monthly payments
        elif v_amrt_term_unit == 'Q':
            return timedelta(days=91)  # Quarterly payments (approx. 3 months)
        elif v_amrt_term_unit == 'H':
            return timedelta(days=182)  # Semi-annual payments (approx. 6 months)
        elif v_amrt_term_unit == 'Y':
            return timedelta(days=365)  # Annual payments
        else:
            return timedelta(days=30)  # Default to monthly

    else:
        # If the day count convention is unrecognized, use a default
        return timedelta(days=30)


def calculate_cash_flows_for_loan(loan):
    with transaction.atomic():
        customer_info = Ldn_Customer_Info.objects.filter(
            v_party_id=loan.v_cust_ref_code,
            fic_mis_date=loan.fic_mis_date
        ).first()
        party_type_code = customer_info.v_party_type_code if customer_info else None

        # Check if a payment schedule exists for this account and fic_mis_date
        payment_schedule = Ldn_Payment_Schedule.objects.filter(
            v_account_number=loan.v_account_number,
            fic_mis_date=loan.fic_mis_date
        ).order_by('d_payment_date')

        balance = float(loan.n_eop_bal) if loan.n_eop_bal is not None else 0.0  # Start with the current end-of-period balance
        starting_balance = balance  # Keep track of the initial balance
        current_date = loan.d_next_payment_date
        fixed_interest_rate = float(loan.n_curr_interest_rate) if loan.n_curr_interest_rate is not None else 0.0  # Fixed interest rate
        withholding_tax = float(loan.n_wht_percent) if loan.n_wht_percent is not None else 0.0  # WHT percentage as decimal
        management_fee_rate = float(loan.v_management_fee_rate) if loan.v_management_fee_rate is not None else 0.0  # Management fee rate (if applicable)
        v_amrt_term_unit = loan.v_amrt_term_unit
        repayment_type = loan.v_amrt_repayment_type  # Get amortization type (bullet/amortized)
        v_day_count_ind = loan.v_day_count_ind
        cashflow_bucket = 1

        # Fetch the interest method from Fsi_Interest_Method. Default to 'Simple' if none exists.
        interest_method = Fsi_Interest_Method.objects.first()  # Always fetch the first available method
        if not interest_method:
            interest_method = Fsi_Interest_Method.objects.create(v_interest_method='Simple', description="Default Simple Interest Method")

        # Determine payment interval based on repayment type (e.g., 'M', 'Q', 'H', 'Y')
        payment_interval = get_payment_interval(v_amrt_term_unit, v_day_count_ind)

        # Management fee calculation
        management_fee_day = loan.d_start_date.day
        management_fee_month = loan.d_start_date.month
        management_fee_date = date(current_date.year, management_fee_month, management_fee_day)

        if payment_schedule.exists():
            # Use the payment schedule
            bucket = 1
            for schedule in payment_schedule:
                principal_payment = schedule.n_principal_payment_amt or 0
                interest_payment = schedule.n_interest_payment_amt or 0
                total_payment = principal_payment + interest_payment

                # Calculate the new balance
                balance -= principal_payment

                # Store the cash flow
                FSI_Expected_Cashflow.objects.create(
                    fic_mis_date=loan.fic_mis_date,
                    v_account_number=loan.v_account_number,
                    n_cash_flow_bucket=bucket,  # Bucket number based on payment date order
                    d_cash_flow_date=schedule.d_payment_date,
                    n_principal_payment=principal_payment,
                    n_interest_payment=interest_payment,
                    n_cash_flow_amount=total_payment,
                    n_balance=balance,
                    V_CCY_CODE=loan.v_ccy_code,
                    v_party_type_code=party_type_code
                )

                bucket += 1  # Increment the bucket number for the next payment date
        else:
            # No payment schedule exists, proceed with projected cash flows
            periods = ((loan.d_maturity_date - current_date).days // payment_interval.days) + 1
            fixed_principal_payment = round(starting_balance / periods, 2)
            total_principal_paid = 0

            while current_date <= loan.d_maturity_date:
                interest_payment = 0.0

                # Adjust day count factor based on v_day_count_ind
                if v_day_count_ind == '30/360':
                    day_count_factor = 360
                elif v_day_count_ind == '30/365':
                    day_count_factor = 365
                else:
                    day_count_factor = 365  # Default to 365 if the day count convention is unrecognized

                # Interest Calculation based on the method selected
                if interest_method.v_interest_method == 'Simple':
                    interest_payment = balance * fixed_interest_rate * (payment_interval.days / day_count_factor)

                elif interest_method.v_interest_method == 'Compound':
                    interest_payment = balance * ((1 + fixed_interest_rate / (day_count_factor / payment_interval.days)) ** periods - 1)

                elif interest_method.v_interest_method == 'Amortized':
                    interest_rate_per_period = fixed_interest_rate / (day_count_factor / payment_interval.days)
                    total_payment = loan.n_eop_bal * (interest_rate_per_period / (1 - (1 + interest_rate_per_period) ** -periods))
                    interest_payment = balance * interest_rate_per_period
                    principal_payment = total_payment - interest_payment

                elif interest_method.v_interest_method == 'Floating':
                    variable_rate = loan.n_curr_interest_rate + loan.n_variable_rate_margin
                    interest_payment = balance * variable_rate * (payment_interval.days / day_count_factor)

                else:
                    interest_payment = balance * fixed_interest_rate * (payment_interval.days / day_count_factor)  # Default Simple Interest

                wht_payment = interest_payment * withholding_tax  # WHT is calculated on the interest
                interest_payment_net = interest_payment - wht_payment  # Subtract WHT from total interest

                if repayment_type == 'bullet':
                    if periods == 1:  # Check if it's the last bucket (last period)
                        principal_payment = balance  # Pay the entire balance in the last bucket
                    else:
                        principal_payment = 0  # No principal payment before the last bucket
                elif repayment_type == 'amortized':
                    principal_payment = fixed_principal_payment  # Regular amortized principal payment

                total_principal_paid += principal_payment

                management_fee_net = 0
                if current_date.month == management_fee_date.month and current_date.year == management_fee_date.year and management_fee_rate:
                    management_fee_net = balance * management_fee_rate
                    wht_management_fee = management_fee_net * withholding_tax  # WHT on management fee
                    management_fee_net -= wht_management_fee  # Net management fee after WHT
                    management_fee_date = management_fee_date.replace(year=management_fee_date.year + 1)  # Update management fee date for next year

                total_payment = principal_payment + interest_payment_net + management_fee_net

                # Store the cash flow
                FSI_Expected_Cashflow.objects.create(
                    fic_mis_date=loan.fic_mis_date,
                    v_account_number=loan.v_account_number,
                    n_cash_flow_bucket=cashflow_bucket,
                    d_cash_flow_date=current_date,
                    n_principal_payment=principal_payment,
                    n_interest_payment=interest_payment + management_fee_net,  # Include net management fee in interest
                    n_cash_flow_amount=total_payment,
                    n_balance=balance - principal_payment,
                    V_CASH_FLOW_TYPE=repayment_type,
                    management_fee_added=management_fee_net,
                    V_CCY_CODE=loan.v_ccy_code,
                    v_loan_type=loan.v_loan_type,
                    v_cust_ref_code=loan.v_cust_ref_code,
                    v_party_type_code=party_type_code
                )

                balance -= principal_payment
                current_date += payment_interval
                cashflow_bucket += 1
                periods -= 1  # Decrease the number of remaining periods


################################################

def project_cash_flows(fic_mis_date):
    try:
        # Delete existing cash flows for the same fic_mis_date
        FSI_Expected_Cashflow.objects.filter(fic_mis_date=fic_mis_date).delete()

        # Filter loans by the given fic_mis_date
        loans = Ldn_Financial_Instrument.objects.filter(fic_mis_date=fic_mis_date)
        if not loans.exists():
            print(f"ERROR: No loans found for the given fic_mis_date: {fic_mis_date}")
            return 0  # Return 0 if no loans are found

        # Define the number of threads based on the number of loans and system capability
        num_threads = min(10, len(loans))  # Adjust number of threads as needed
        total_cash_flows = 0  # Initialize total cash flows counter

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(calculate_cash_flows_for_loan, loan) for loan in loans]
            for future in futures:
                future.result()  # This will raise exceptions if any occurred in the thread

        # Calculate the total number of projected cash flows
        total_cash_flows = FSI_Expected_Cashflow.objects.filter(fic_mis_date=fic_mis_date).count()

        print(f"INFO: Total of {total_cash_flows} cash flows projected for {loans.count()} loans for MIS date {fic_mis_date}.")
        return 1  # Return 1 on successful completion

    except Exception as e:
        print(f"ERROR: Error occurred: {str(e)}")
        return 0  # Return 0 if an error occurs

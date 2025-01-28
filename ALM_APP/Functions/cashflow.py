
from concurrent.futures import ThreadPoolExecutor
from django.db import transaction
from datetime import timedelta, date
from ..models import *


def get_payment_interval(v_amrt_term_unit, day_count_ind):
    """Determine the payment interval in days based on repayment type and day count convention."""
    # If either v_amrt_term_unit or day_count_ind is missing, default to monthly
    if not v_amrt_term_unit or not day_count_ind:
        return timedelta(days=30)

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


def calculate_cash_flows_for_instrument(instrument):
    with transaction.atomic():
        customer_info = Ldn_Customer_Info.objects.filter(
            v_party_id=instrument.v_cust_ref_code,
            fic_mis_date__lte=instrument.fic_mis_date
        ).order_by('-fic_mis_date').first()
        party_type_code = customer_info.v_party_type_code if customer_info else None


        latest_date = Ldn_Payment_Schedule.objects.filter(
            v_account_number=instrument.v_account_number
        ).aggregate(latest_date=models.Max('fic_mis_date'))['latest_date']

        payment_schedule = Ldn_Payment_Schedule.objects.filter(
            v_account_number=instrument.v_account_number,
            fic_mis_date=latest_date
        ).order_by('d_payment_date')



        # payment_schedule = Ldn_Payment_Schedule.objects.filter(
        #     v_account_number=instrument.v_account_number,
        #     fic_mis_date=instrument.fic_mis_date
        # ).order_by('d_payment_date')

        balance = float(instrument.n_eop_bal) if instrument.n_eop_bal is not None else 0.0
        starting_balance = balance

        # Handle d_next_payment_date, d_last_payment_date, and d_start_date
        if instrument.d_next_payment_date:
            current_date = instrument.d_next_payment_date
        else:
            if instrument.d_last_payment_date:
                current_date = instrument.d_last_payment_date
                if current_date < instrument.d_start_date:
                    current_date = instrument.d_start_date
            else:
                current_date = instrument.d_start_date

        fixed_interest_rate = float(instrument.n_curr_interest_rate) if instrument.n_curr_interest_rate is not None else 0.0
        withholding_tax = float(instrument.n_wht_percent) if instrument.n_wht_percent is not None else 0.0
        management_fee_rate = float(instrument.v_management_fee_rate) if instrument.v_management_fee_rate is not None else 0.0
        v_amrt_term_unit = instrument.v_amrt_term_unit
        repayment_type = instrument.v_amrt_repayment_type
        v_day_count_ind = instrument.v_day_count_ind

        d_maturity_date = instrument.d_maturity_date
        if not d_maturity_date:
            d_maturity_date = current_date + timedelta(days=360)

        cashflow_bucket = 1
        interest_method = Fsi_Interest_Method.objects.first()
        if not interest_method:
            interest_method = Fsi_Interest_Method.objects.create(v_interest_method='Simple', description="Default Simple Interest Method")

        payment_interval = get_payment_interval(v_amrt_term_unit, v_day_count_ind)

        management_fee_day = instrument.d_start_date.day
        management_fee_month = instrument.d_start_date.month
        if current_date < instrument.d_start_date:
            current_date = instrument.d_start_date
        management_fee_date = date(current_date.year, management_fee_month, management_fee_day)

        if payment_schedule.exists():
            bucket = 1
            for schedule in payment_schedule:
                principal_payment = schedule.n_principal_payment_amt or 0
                interest_payment = schedule.n_interest_payment_amt or 0
                total_payment = principal_payment + interest_payment

                balance -= principal_payment

                FSI_Expected_Cashflow.objects.create(
                    fic_mis_date=instrument.fic_mis_date,
                    v_account_number=instrument.v_account_number,
                    n_cash_flow_bucket=bucket,
                    d_cash_flow_date=schedule.d_payment_date,
                    n_principal_payment=principal_payment,
                    n_interest_payment=interest_payment,
                    n_cash_flow_amount=total_payment,
                    n_balance=balance,
                    V_CCY_CODE=instrument.v_ccy_code,
                    v_party_type_code=party_type_code
                )
                bucket += 1
        else:
            periods = ((d_maturity_date - current_date).days // payment_interval.days) + 1
            if periods < 1:
                periods = 1

            fixed_principal_payment = round(starting_balance / periods, 2)
            total_principal_paid = 0

            while current_date <= d_maturity_date:
                interest_payment = 0.0

                if v_day_count_ind == '30/360':
                    day_count_factor = 360
                elif v_day_count_ind == '30/365':
                    day_count_factor = 365
                else:
                    day_count_factor = 365

                if interest_method.v_interest_method == 'Simple':
                    interest_payment = balance * fixed_interest_rate * (payment_interval.days / day_count_factor)
                elif interest_method.v_interest_method == 'Compound':
                    interest_payment = balance * ((1 + fixed_interest_rate / (day_count_factor / payment_interval.days)) ** periods - 1)
                elif interest_method.v_interest_method == 'Amortized':
                    interest_rate_per_period = fixed_interest_rate / (day_count_factor / payment_interval.days)
                    total_payment = instrument.n_eop_bal * (
                        interest_rate_per_period / (1 - (1 + interest_rate_per_period) ** -periods)
                    )
                    interest_payment = balance * interest_rate_per_period
                    principal_payment = total_payment - interest_payment
                elif interest_method.v_interest_method == 'Floating':
                    variable_rate = instrument.n_curr_interest_rate + instrument.n_variable_rate_margin
                    interest_payment = balance * variable_rate * (payment_interval.days / day_count_factor)
                else:
                    interest_payment = balance * fixed_interest_rate * (payment_interval.days / day_count_factor)

                wht_payment = interest_payment * withholding_tax
                interest_payment_net = interest_payment - wht_payment

                if repayment_type == 'bullet':
                    if periods == 1:
                        principal_payment = balance
                    else:
                        principal_payment = 0
                elif repayment_type == 'amortized':
                    principal_payment = fixed_principal_payment
                else:
                    principal_payment = 0

                total_principal_paid += principal_payment

                management_fee_net = 0
                if (
                    current_date.month == management_fee_date.month
                    and current_date.year == management_fee_date.year
                    and management_fee_rate
                ):
                    management_fee_net = balance * management_fee_rate
                    wht_management_fee = management_fee_net * withholding_tax
                    management_fee_net -= wht_management_fee
                    management_fee_date = management_fee_date.replace(year=management_fee_date.year + 1)

                total_payment = principal_payment + interest_payment_net + management_fee_net

                FSI_Expected_Cashflow.objects.create(
                    fic_mis_date=instrument.fic_mis_date,
                    v_account_number=instrument.v_account_number,
                    n_cash_flow_bucket=cashflow_bucket,
                    d_cash_flow_date=current_date,
                    n_principal_payment=principal_payment,
                    n_interest_payment=interest_payment + management_fee_net,
                    n_cash_flow_amount=total_payment,
                    n_balance=balance - principal_payment,
                    V_CASH_FLOW_TYPE=repayment_type,
                    management_fee_added=management_fee_net,
                    V_CCY_CODE=instrument.v_ccy_code,
                    v_loan_type=instrument.v_loan_type,
                    v_cust_ref_code=instrument.v_cust_ref_code,
                    v_party_type_code=party_type_code
                )

                balance -= principal_payment
                current_date += payment_interval
                cashflow_bucket += 1
                periods -= 1


def project_cash_flows(fic_mis_date):
    try:
        FSI_Expected_Cashflow.objects.filter(fic_mis_date=fic_mis_date).delete()
        instruments = Ldn_Financial_Instrument.objects.filter(fic_mis_date=fic_mis_date)
        if not instruments.exists():
            print(f"ERROR: No loans found for the given fic_mis_date: {fic_mis_date}")
            return 0

        num_threads = min(10, len(instruments))
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(calculate_cash_flows_for_instrument, instr) for instr in instruments]
            for future in futures:
                future.result()

        total_cash_flows = FSI_Expected_Cashflow.objects.filter(fic_mis_date=fic_mis_date).count()
        print(f"INFO: Total of {total_cash_flows} cash flows projected for {instruments.count()} loans for MIS date {fic_mis_date}.")
        return 1

    except Exception as e:
        print(f"ERROR: Error occurred: {str(e)}")
        return 0

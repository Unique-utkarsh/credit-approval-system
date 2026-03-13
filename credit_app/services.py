"""
Credit scoring and loan eligibility logic.
"""
import datetime
import math
from decimal import Decimal
from typing import Tuple, Optional

from credit_app.models import Customer, Loan


def calculate_compound_emi(principal: float, annual_rate: float, tenure_months: int) -> float:
    """
    Calculate EMI using compound interest formula.
    EMI = P * r * (1+r)^n / ((1+r)^n - 1)
    where r = monthly interest rate
    """
    if annual_rate == 0:
        return principal / tenure_months

    monthly_rate = annual_rate / (12 * 100)
    emi = principal * monthly_rate * math.pow(1 + monthly_rate, tenure_months) / (
        math.pow(1 + monthly_rate, tenure_months) - 1
    )
    return round(emi, 2)


def calculate_credit_score(customer: Customer) -> int:
    """
    Calculate credit score (0-100) based on historical loan data.
    Components:
      1. Past loans paid on time
      2. Number of loans taken in past
      3. Loan activity in current year
      4. Loan approved volume
      5. Current debt vs approved limit
    """
    loans = list(customer.loans.all())

   ## if current debt > approved limit, score = 0
    current_loans = [l for l in loans if l.end_date and l.end_date >= datetime.date.today()]
    current_debt_total = sum(float(l.loan_amount) for l in current_loans)
    if current_debt_total > customer.approved_limit:
        return 0

    if not loans:
        return 50  # Neutral score for new customer

  # Past loans paid on time 
    total_emis = sum(l.tenure for l in loans)
    total_paid_on_time = sum(l.emis_paid_on_time for l in loans)
    on_time_ratio = total_paid_on_time / total_emis if total_emis > 0 else 0
    score_on_time = on_time_ratio * 35

    #  Number of loans taken 

    num_loans = len(loans)
    if num_loans == 0:
        score_num_loans = 10
    elif num_loans <= 3:
        score_num_loans = 20
    elif num_loans <= 7:
        score_num_loans = 15
    elif num_loans <= 15:
        score_num_loans = 10
    else:
        score_num_loans = 5

    # Loan activity in current year 
    current_year = datetime.date.today().year
    loans_this_year = [
        l for l in loans
        if l.start_date and l.start_date.year == current_year
    ]
    num_loans_this_year = len(loans_this_year)
    if num_loans_this_year == 0:
        score_activity = 20  # No new risky behavior
    elif num_loans_this_year <= 2:
        score_activity = 15
    elif num_loans_this_year <= 4:
        score_activity = 10
    else:
        score_activity = 5  # Too many loans this year

    #  Loan approved volume vs approved limit 
    total_loan_volume = sum(float(l.loan_amount) for l in loans)
    volume_ratio = total_loan_volume / customer.approved_limit if customer.approved_limit > 0 else 0
    if volume_ratio <= 0.5:
        score_volume = 25
    elif volume_ratio <= 1.0:
        score_volume = 20
    elif volume_ratio <= 2.0:
        score_volume = 12
    elif volume_ratio <= 3.0:
        score_volume = 7
    else:
        score_volume = 3

    total_score = int(score_on_time + score_num_loans + score_activity + score_volume)
    return min(100, max(0, total_score))


def get_minimum_interest_rate(credit_score: int) -> Optional[float]:
    """Return minimum allowed interest rate based on credit score."""
    if credit_score > 50:
        return 0.0   # Any rate is fine
    elif credit_score > 30:
        return 12.0
    elif credit_score > 10:
        return 16.0
    else:
        return None  # Loan not approved


def check_loan_eligibility(
    customer: Customer,
    loan_amount: float,
    interest_rate: float,
    tenure: int,
) -> Tuple[bool, float, float, float]:
    """
    Check if a customer is eligible for a loan.

    Returns:
        (approval, interest_rate, corrected_interest_rate, monthly_installment)
    """
    credit_score = calculate_credit_score(customer)
    min_rate = get_minimum_interest_rate(credit_score)

    # Check if loan can be approved at all
    if min_rate is None:
        emi = calculate_compound_emi(loan_amount, interest_rate, tenure)
        return False, interest_rate, interest_rate, emi

    # Check if current EMIs exceed 50% of monthly salary
    today = datetime.date.today()
    active_loans = customer.loans.filter(end_date__gte=today)
    current_emis = sum(float(l.monthly_repayment) for l in active_loans)
    new_emi = calculate_compound_emi(loan_amount, interest_rate, tenure)

    if (current_emis + new_emi) > (0.5 * customer.monthly_salary):
        return False, interest_rate, interest_rate, new_emi

    # Determine corrected interest rate
    corrected_rate = interest_rate
    if min_rate > 0 and interest_rate < min_rate:
        corrected_rate = min_rate

    final_emi = calculate_compound_emi(loan_amount, corrected_rate, tenure)
    return True, interest_rate, corrected_rate, final_emi

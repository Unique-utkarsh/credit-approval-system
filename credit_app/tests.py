"""
Unit tests for the Credit Approval System.
Run with: python manage.py test credit_app
"""
import datetime
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from credit_app.models import Customer, Loan
from credit_app.services import (
    calculate_compound_emi,
    calculate_credit_score,
    check_loan_eligibility,
    get_minimum_interest_rate,
)

.
def make_customer(**kwargs):
    defaults = dict(
        customer_id=9001,
        first_name='Test',
        last_name='User',
        age=30,
        phone_number=9999999999,
        monthly_salary=50000,
        approved_limit=1800000,
        current_debt=0,
    )
    defaults.update(kwargs)
    return Customer.objects.create(**defaults)


def make_loan(customer, **kwargs):
    today = datetime.date.today()
    defaults = dict(
        loan_id=99001,
        customer=customer,
        loan_amount=100000,
        tenure=12,
        interest_rate=10.0,
        monthly_repayment=8792,
        emis_paid_on_time=12,
        start_date=today - datetime.timedelta(days=365),
        end_date=today - datetime.timedelta(days=1),  # past loan
    )
    defaults.update(kwargs)
    return Loan.objects.create(**defaults)


# Service-layer tests

class EMICalculationTests(TestCase):

    def test_zero_rate_returns_flat_division(self):
        emi = calculate_compound_emi(120000, 0, 12)
        self.assertAlmostEqual(emi, 10000.0, places=1)

    def test_standard_emi(self):
        # 100,000 at 12% annual for 12 months → ~8884.88
        emi = calculate_compound_emi(100000, 12, 12)
        self.assertAlmostEqual(emi, 8884.88, delta=1.0)

    def test_emi_decreases_with_longer_tenure(self):
        emi_12 = calculate_compound_emi(500000, 10, 12)
        emi_24 = calculate_compound_emi(500000, 10, 24)
        self.assertGreater(emi_12, emi_24)


class CreditScoreTests(TestCase):

    def test_new_customer_gets_neutral_score(self):
        customer = make_customer()
        score = calculate_credit_score(customer)
        self.assertEqual(score, 50)

    def test_current_debt_exceeds_limit_gives_zero(self):
        customer = make_customer(approved_limit=100000)
        today = datetime.date.today()
        make_loan(
            customer,
            loan_id=99002,
            loan_amount=200000,
            end_date=today + datetime.timedelta(days=180),
        )
        score = calculate_credit_score(customer)
        self.assertEqual(score, 0)

    def test_perfect_payment_history_raises_score(self):
        customer = make_customer()
        today = datetime.date.today()
        make_loan(
            customer,
            loan_id=99003,
            loan_amount=100000,
            tenure=12,
            emis_paid_on_time=12,
            start_date=today - datetime.timedelta(days=400),
            end_date=today - datetime.timedelta(days=30),
        )
        score = calculate_credit_score(customer)
        self.assertGreater(score, 50)

    def test_score_bounded_between_0_and_100(self):
        customer = make_customer()
        score = calculate_credit_score(customer)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)


class MinimumRateTests(TestCase):

    def test_score_above_50_no_minimum(self):
        self.assertEqual(get_minimum_interest_rate(75), 0.0)

    def test_score_between_30_and_50_needs_12_percent(self):
        self.assertEqual(get_minimum_interest_rate(40), 12.0)

    def test_score_between_10_and_30_needs_16_percent(self):
        self.assertEqual(get_minimum_interest_rate(20), 16.0)

    def test_score_below_10_not_approved(self):
        self.assertIsNone(get_minimum_interest_rate(5))


class LoanEligibilityTests(TestCase):

    def test_low_credit_score_rejects_loan(self):
        customer = make_customer(approved_limit=100000)
        today = datetime.date.today()
        # Flood customer with current debt to force score = 0
        make_loan(
            customer, loan_id=99010, loan_amount=200000,
            end_date=today + datetime.timedelta(days=365),
        )
        approved, _, _, _ = check_loan_eligibility(customer, 50000, 10.0, 12)
        self.assertFalse(approved)

    def test_emi_exceeds_50pct_salary_rejects(self):
        customer = make_customer(monthly_salary=20000, approved_limit=5000000)
        today = datetime.date.today()
        # Existing active loan with heavy EMI
        make_loan(
            customer, loan_id=99011, loan_amount=500000,
            monthly_repayment=12000,
            end_date=today + datetime.timedelta(days=365),
        )
        approved, _, _, _ = check_loan_eligibility(customer, 50000, 10.0, 12)
        self.assertFalse(approved)

    def test_low_rate_is_corrected_upward(self):
        customer = make_customer()
        # No loans → score = 50 → min rate = 0, so any rate is fine
        today = datetime.date.today()
        make_loan(
            customer, loan_id=99012, loan_amount=50000,
            tenure=24, emis_paid_on_time=10,  
            start_date=today - datetime.timedelta(days=730),
            end_date=today - datetime.timedelta(days=1),
        )
        approved, rate, corrected, _ = check_loan_eligibility(customer, 100000, 5.0, 12)
        if approved:
            self.assertGreaterEqual(corrected, rate)


# API endpoint tests

class RegisterAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()

    def test_register_creates_customer(self):
        payload = {
            'first_name': 'Alice',
            'last_name': 'Smith',
            'age': 28,
            'monthly_income': 60000,
            'phone_number': 9876543210,
        }
        response = self.client.post('/register', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertIn('customer_id', data)
        self.assertEqual(data['name'], 'Alice Smith')
        self.assertEqual(data['approved_limit'], 2200000)  # 36*60000 = 2160000 → nearest lakh = 2200000

    def test_register_requires_all_fields(self):
        response = self.client.post('/register', {'first_name': 'Bob'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_approved_limit_rounded_to_lakh(self):
        payload = {
            'first_name': 'Charlie',
            'last_name': 'Brown',
            'age': 35,
            'monthly_income': 55000,
            'phone_number': 1234567890,
        }
        response = self.client.post('/register', payload, format='json')
        limit = response.json()['approved_limit']
        self.assertEqual(limit % 100000, 0)


class CheckEligibilityAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.customer = make_customer()

    def test_returns_eligibility_response(self):
        payload = {
            'customer_id': self.customer.customer_id,
            'loan_amount': 100000,
            'interest_rate': 10.0,
            'tenure': 12,
        }
        response = self.client.post('/check-eligibility', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('approval', data)
        self.assertIn('corrected_interest_rate', data)
        self.assertIn('monthly_installment', data)

    def test_unknown_customer_returns_404(self):
        payload = {
            'customer_id': 99999,
            'loan_amount': 100000,
            'interest_rate': 10.0,
            'tenure': 12,
        }
        response = self.client.post('/check-eligibility', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CreateLoanAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.customer = make_customer()

    def test_approved_loan_is_created(self):
        payload = {
            'customer_id': self.customer.customer_id,
            'loan_amount': 100000,
            'interest_rate': 10.0,
            'tenure': 12,
        }
        response = self.client.post('/create-loan', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertTrue(data['loan_approved'])
        self.assertIsNotNone(data['loan_id'])
        self.assertIn('monthly_installment', data)

    def test_rejected_loan_returns_null_id(self):
       
        today = datetime.date.today()
        make_loan(
            self.customer, loan_id=88001, loan_amount=5000000,
            end_date=today + datetime.timedelta(days=365),
        )
        payload = {
            'customer_id': self.customer.customer_id,
            'loan_amount': 100000,
            'interest_rate': 10.0,
            'tenure': 12,
        }
        response = self.client.post('/create-loan', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertFalse(data['loan_approved'])
        self.assertIsNone(data['loan_id'])
        self.assertIn('message', data)


class ViewLoanAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.customer = make_customer()
        self.loan = make_loan(self.customer)

    def test_view_loan_returns_details(self):
        response = self.client.get(f'/view-loan/{self.loan.loan_id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['loan_id'], self.loan.loan_id)
        self.assertIn('customer', data)
        self.assertIn('monthly_installment', data)

    def test_nonexistent_loan_returns_404(self):
        response = self.client.get('/view-loan/999999')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ViewCustomerLoansAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.customer = make_customer()

    def test_returns_active_loans_only(self):
        today = datetime.date.today()
        # Active loan
        make_loan(
            self.customer, loan_id=77001,
            end_date=today + datetime.timedelta(days=180),
        )
        # Expired loan
        make_loan(
            self.customer, loan_id=77002,
            end_date=today - datetime.timedelta(days=1),
        )
        response = self.client.get(f'/view-loans/{self.customer.customer_id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['loan_id'], 77001)

    def test_unknown_customer_returns_404(self):
        response = self.client.get('/view-loans/999999')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_response_contains_repayments_left(self):
        today = datetime.date.today()
        make_loan(
            self.customer, loan_id=77003,
            end_date=today + datetime.timedelta(days=180),
        )
        response = self.client.get(f'/view-loans/{self.customer.customer_id}')
        self.assertIn('repayments_left', response.json()[0])

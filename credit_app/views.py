import datetime
import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from credit_app.models import Customer, Loan
from credit_app.serializers import (
    CheckEligibilityRequestSerializer,
    CheckEligibilityResponseSerializer,
    CreateLoanRequestSerializer,
    CustomerRegisterSerializer,
    CustomerResponseSerializer,
    LoanListItemSerializer,
    ViewLoanSerializer,
)
from credit_app.services import (
    calculate_compound_emi,
    check_loan_eligibility,
)

logger = logging.getLogger(__name__)


def _next_customer_id():
    """Generate the next available customer_id."""
    last = Customer.objects.order_by('-customer_id').first()
    return (last.customer_id + 1) if last else 1


def _next_loan_id():
    """Generate the next available loan_id."""
    last = Loan.objects.order_by('-loan_id').first()
    return (last.loan_id + 1) if last else 1


class RegisterView(APIView):
    """POST /register — Register a new customer."""

    def post(self, request):
        serializer = CustomerRegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        monthly_salary = data['monthly_income']

        # approved_limit
        raw_limit = 36 * monthly_salary
        approved_limit = round(raw_limit / 100000) * 100000

        customer_id = _next_customer_id()

        customer = Customer.objects.create(
            customer_id=customer_id,
            first_name=data['first_name'],
            last_name=data['last_name'],
            age=data['age'],
            phone_number=data['phone_number'],
            monthly_salary=monthly_salary,
            approved_limit=approved_limit,
            current_debt=0,
        )

        response_serializer = CustomerResponseSerializer(customer)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class CheckEligibilityView(APIView):
    """POST /check-eligibility — Check loan eligibility."""

    def post(self, request):
        serializer = CheckEligibilityRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        try:
            customer = Customer.objects.get(customer_id=data['customer_id'])
        except Customer.DoesNotExist:
            return Response(
                {'error': f"Customer with id {data['customer_id']} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        approval, interest_rate, corrected_rate, monthly_installment = check_loan_eligibility(
            customer,
            data['loan_amount'],
            data['interest_rate'],
            data['tenure'],
        )

        response_data = {
            'customer_id': customer.customer_id,
            'approval': approval,
            'interest_rate': interest_rate,
            'corrected_interest_rate': corrected_rate,
            'tenure': data['tenure'],
            'monthly_installment': monthly_installment,
        }

        response_serializer = CheckEligibilityResponseSerializer(data=response_data)
        response_serializer.is_valid()
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class CreateLoanView(APIView):
    """POST /create-loan — Process a new loan."""

    def post(self, request):
        serializer = CreateLoanRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        try:
            customer = Customer.objects.get(customer_id=data['customer_id'])
        except Customer.DoesNotExist:
            return Response(
                {'error': f"Customer with id {data['customer_id']} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        approval, interest_rate, corrected_rate, monthly_installment = check_loan_eligibility(
            customer,
            data['loan_amount'],
            data['interest_rate'],
            data['tenure'],
        )

        if not approval:
            return Response(
                {
                    'loan_id': None,
                    'customer_id': customer.customer_id,
                    'loan_approved': False,
                    'message': 'Loan not approved based on credit score or EMI constraints.',
                    'monthly_installment': round(monthly_installment, 2),
                },
                status=status.HTTP_200_OK,
            )

        # #Create the loan with dataa
        today = datetime.date.today()
        end_date = today.replace(
            year=today.year + data['tenure'] // 12,
            month=((today.month - 1 + data['tenure'] % 12) % 12) + 1,
        )

        loan = Loan.objects.create(
            loan_id=_next_loan_id(),
            customer=customer,
            loan_amount=data['loan_amount'],
            tenure=data['tenure'],
            interest_rate=corrected_rate,
            monthly_repayment=round(monthly_installment, 2),
            emis_paid_on_time=0,
            start_date=today,
            end_date=end_date,
        )

        return Response(
            {
                'loan_id': loan.loan_id,
                'customer_id': customer.customer_id,
                'loan_approved': True,
                'message': 'Loan approved successfully.',
                'monthly_installment': round(monthly_installment, 2),
            },
            status=status.HTTP_201_CREATED,
        )


class ViewLoanView(APIView):
    """GET /view-loan/<loan_id> — View a specific loan."""

    def get(self, request, loan_id):
        try:
            loan = Loan.objects.select_related('customer').get(loan_id=loan_id)
        except Loan.DoesNotExist:
            return Response(
                {'error': f"Loan with id {loan_id} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ViewLoanSerializer(loan)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ViewCustomerLoansView(APIView):
    """GET /view-loans/<customer_id> — View all loans for a customer."""

    def get(self, request, customer_id):
        try:
            customer = Customer.objects.get(customer_id=customer_id)
        except Customer.DoesNotExist:
            return Response(
                {'error': f"Customer with id {customer_id} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        today = datetime.date.today()
        loans = customer.loans.filter(end_date__gte=today)
        serializer = LoanListItemSerializer(loans, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

from rest_framework import serializers
from credit_app.models import Customer, Loan


class CustomerRegisterSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    age = serializers.IntegerField(min_value=0)
    monthly_income = serializers.IntegerField(min_value=0)
    phone_number = serializers.IntegerField()


class CustomerResponseSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    monthly_income = serializers.IntegerField(source='monthly_salary')

    class Meta:
        model = Customer
        fields = ['customer_id', 'name', 'age', 'monthly_income', 'approved_limit', 'phone_number']

    def get_name(self, obj):
        return obj.full_name


class CheckEligibilityRequestSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    loan_amount = serializers.FloatField(min_value=0)
    interest_rate = serializers.FloatField(min_value=0)
    tenure = serializers.IntegerField(min_value=1)


class CheckEligibilityResponseSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    approval = serializers.BooleanField()
    interest_rate = serializers.FloatField()
    corrected_interest_rate = serializers.FloatField()
    tenure = serializers.IntegerField()
    monthly_installment = serializers.FloatField()


class CreateLoanRequestSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    loan_amount = serializers.FloatField(min_value=0)
    interest_rate = serializers.FloatField(min_value=0)
    tenure = serializers.IntegerField(min_value=1)


class CreateLoanResponseSerializer(serializers.Serializer):
    loan_id = serializers.IntegerField(allow_null=True)
    customer_id = serializers.IntegerField()
    loan_approved = serializers.BooleanField()
    message = serializers.CharField(allow_blank=True)
    monthly_installment = serializers.FloatField()


class CustomerBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['customer_id', 'first_name', 'last_name', 'phone_number', 'age']


class ViewLoanSerializer(serializers.ModelSerializer):
    customer = CustomerBriefSerializer(read_only=True)
    loan_id = serializers.IntegerField()

    class Meta:
        model = Loan
        fields = [
            'loan_id', 'customer', 'loan_amount',
            'interest_rate', 'monthly_repayment', 'tenure'
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['monthly_installment'] = data.pop('monthly_repayment')
        return data


class LoanListItemSerializer(serializers.ModelSerializer):
    repayments_left = serializers.IntegerField(read_only=True)

    class Meta:
        model = Loan
        fields = [
            'loan_id', 'loan_amount', 'interest_rate',
            'monthly_repayment', 'repayments_left'
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['monthly_installment'] = data.pop('monthly_repayment')
        return data

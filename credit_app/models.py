from django.db import models


class Customer(models.Model):
    customer_id = models.IntegerField(unique=True, db_index=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    age = models.IntegerField(default=0)
    phone_number = models.BigIntegerField()
    monthly_salary = models.IntegerField()
    approved_limit = models.IntegerField()
    current_debt = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        db_table = 'customers'

    def __str__(self):
        return f"{self.first_name} {self.last_name} (ID: {self.customer_id})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Loan(models.Model):
    loan_id = models.IntegerField(unique=True, db_index=True)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='loans',
        to_field='customer_id'
    )
    loan_amount = models.DecimalField(max_digits=15, decimal_places=2)
    tenure = models.IntegerField(help_text="Tenure in months")
    interest_rate = models.DecimalField(max_digits=6, decimal_places=2)
    monthly_repayment = models.DecimalField(max_digits=12, decimal_places=2)
    emis_paid_on_time = models.IntegerField(default=0)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'loans'

    def __str__(self):
        return f"Loan {self.loan_id} - Customer {self.customer_id}"

    @property
    def repayments_left(self):
        from django.utils import timezone
        import datetime
        today = datetime.date.today()
        if self.end_date and self.end_date > today:
            months_left = (
                (self.end_date.year - today.year) * 12
                + (self.end_date.month - today.month)
            )
            return max(0, months_left)
        return 0

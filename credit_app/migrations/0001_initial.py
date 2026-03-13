from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Customer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('customer_id', models.IntegerField(db_index=True, unique=True)),
                ('first_name', models.CharField(max_length=100)),
                ('last_name', models.CharField(max_length=100)),
                ('age', models.IntegerField(default=0)),
                ('phone_number', models.BigIntegerField()),
                ('monthly_salary', models.IntegerField()),
                ('approved_limit', models.IntegerField()),
                ('current_debt', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
            ],
            options={'db_table': 'customers'},
        ),
        migrations.CreateModel(
            name='Loan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('loan_id', models.IntegerField(db_index=True, unique=True)),
                ('loan_amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('tenure', models.IntegerField(help_text='Tenure in months')),
                ('interest_rate', models.DecimalField(decimal_places=2, max_digits=6)),
                ('monthly_repayment', models.DecimalField(decimal_places=2, max_digits=12)),
                ('emis_paid_on_time', models.IntegerField(default=0)),
                ('start_date', models.DateField(blank=True, null=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('customer', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='loans',
                    to='credit_app.customer',
                    to_field='customer_id',
                )),
            ],
            options={'db_table': 'loans'},
        ),
    ]

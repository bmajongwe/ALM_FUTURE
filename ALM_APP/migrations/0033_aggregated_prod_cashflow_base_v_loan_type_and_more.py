# Generated by Django 4.1 on 2024-10-23 08:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ALM_APP', '0032_process_uses_behavioral_patterns'),
    ]

    operations = [
        migrations.AddField(
            model_name='aggregated_prod_cashflow_base',
            name='v_loan_type',
            field=models.CharField(max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='aggregatedcashflowbybuckets',
            name='v_loan_type',
            field=models.CharField(max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='product_level_cashflows',
            name='v_loan_type',
            field=models.CharField(max_length=50, null=True),
        ),
    ]

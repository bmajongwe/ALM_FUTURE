# Generated by Django 5.1.3 on 2025-01-30 14:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ALM_APP', '0064_functionexecutionstatus_created_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='ldn_financial_instrument',
            name='n_curr_payment_recd',
            field=models.DecimalField(decimal_places=2, max_digits=10, null=True),
        ),
    ]

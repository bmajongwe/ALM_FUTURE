# Generated by Django 5.1.3 on 2025-02-27 08:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ALM_APP', '0096_nsfrclassification'),
    ]

    operations = [
        migrations.CreateModel(
            name='NSFRStock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fic_mis_date', models.DateField()),
                ('v_nsfr_type', models.CharField(max_length=255)),
                ('v_prod_type_level', models.CharField(max_length=255)),
                ('v_prod_type', models.CharField(max_length=255)),
                ('amount_less_6_months', models.DecimalField(decimal_places=2, default=0.0, help_text='Amount for < 6 months horizon', max_digits=20)),
                ('amount_6_to_12_months', models.DecimalField(decimal_places=2, default=0.0, help_text='Amount for ≥6 months to <1 year horizon', max_digits=20)),
                ('amount_greater_1_year', models.DecimalField(decimal_places=2, default=0.0, help_text='Amount for ≥1 year horizon', max_digits=20)),
                ('funding_factor_less_6_months', models.DecimalField(decimal_places=2, default=0.0, help_text='ASF/RSF factor (%) for < 6 months horizon', max_digits=5)),
                ('funding_factor_6_to_12_months', models.DecimalField(decimal_places=2, default=0.0, help_text='ASF/RSF factor (%) for ≥6 months to <1 year horizon', max_digits=5)),
                ('funding_factor_greater_1_year', models.DecimalField(decimal_places=2, default=0.0, help_text='ASF/RSF factor (%) for ≥1 year horizon', max_digits=5)),
                ('calculated_sf_less_6_months', models.DecimalField(decimal_places=2, default=0.0, help_text='Calculated stable funding for < 6 months horizon', max_digits=20)),
                ('calculated_sf_6_to_12_months', models.DecimalField(decimal_places=2, default=0.0, help_text='Calculated stable funding for ≥6 months to <1 year horizon', max_digits=20)),
                ('calculated_sf_greater_1_year', models.DecimalField(decimal_places=2, default=0.0, help_text='Calculated stable funding for ≥1 year horizon', max_digits=20)),
                ('total_calculated_sf', models.DecimalField(decimal_places=2, default=0.0, help_text='Total Calculated Stable Funding', max_digits=20)),
            ],
            options={
                'db_table': 'nsfr_stock',
            },
        ),
    ]

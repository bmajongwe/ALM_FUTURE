# Generated by Django 5.1.3 on 2025-02-18 13:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ALM_APP', '0083_remove_hqlastock_max_hqla_percentage'),
    ]

    operations = [
        migrations.CreateModel(
            name='HQLAStockOutflow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fic_mis_date', models.DateField()),
                ('v_prod_type', models.CharField(max_length=255)),
                ('v_prod_code', models.CharField(max_length=50)),
                ('v_product_name', models.CharField(blank=True, max_length=255, null=True)),
                ('ratings', models.CharField(blank=True, max_length=50, null=True)),
                ('hqla_level', models.CharField(max_length=10)),
                ('secondary_grouping', models.CharField(blank=True, max_length=100, null=True)),
                ('n_amount', models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ('v_ccy_code', models.CharField(blank=True, max_length=10, null=True)),
                ('risk_weight', models.DecimalField(decimal_places=2, default=0.0, max_digits=5)),
                ('weighted_amount', models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ('adjusted_amount', models.DecimalField(decimal_places=2, default=0, max_digits=20)),
            ],
            options={
                'db_table': 'hqla_stock_outflow',
            },
        ),
        migrations.AddField(
            model_name='hqlaclassification',
            name='is_outflow',
            field=models.CharField(choices=[('Y', 'Yes'), ('N', 'No')], default='N', max_length=1),
        ),
        migrations.AddField(
            model_name='hqlaclassification',
            name='outflow_factor',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='hqlaclassification',
            name='secondary_grouping',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]

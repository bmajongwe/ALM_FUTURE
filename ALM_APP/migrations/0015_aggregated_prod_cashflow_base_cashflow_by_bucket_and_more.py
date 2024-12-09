# Generated by Django 4.1 on 2024-09-26 17:00

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ALM_APP', '0014_aggregated_prod_cashflow_base'),
    ]

    operations = [
        migrations.AddField(
            model_name='aggregated_prod_cashflow_base',
            name='cashflow_by_bucket',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='ALM_APP.aggregatedcashflowbybuckets'),
        ),
        migrations.AddField(
            model_name='aggregated_prod_cashflow_base',
            name='time_bucket_master',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='ALM_APP.timebucketmaster'),
        ),
        migrations.AddField(
            model_name='aggregatedcashflowbybuckets',
            name='time_bucket_master',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='ALM_APP.timebucketmaster'),
        ),
    ]
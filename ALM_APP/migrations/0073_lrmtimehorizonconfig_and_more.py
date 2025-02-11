# Generated by Django 5.1.3 on 2025-02-11 11:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ALM_APP', '0072_lrmselectionconfig'),
    ]

    operations = [
        migrations.CreateModel(
            name='LrmTimeHorizonConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=50, unique=True)),
                ('start_days', models.IntegerField(blank=True, null=True)),
                ('end_days', models.IntegerField(blank=True, null=True)),
                ('start_months', models.IntegerField(blank=True, null=True)),
                ('end_months', models.IntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'lrm_time_horizon_config',
            },
        ),
        migrations.RemoveField(
            model_name='lrmselectionconfig',
            name='selected_time_horizon',
        ),
        migrations.AddField(
            model_name='lrmselectionconfig',
            name='selected_time_horizons',
            field=models.JSONField(default=-1212),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='lrmselectionconfig',
            name='selection_purpose',
            field=models.CharField(choices=[('LCR', 'Liquidity Coverage Ratio'), ('NSFR', 'Net Stable Funding Ratio')], default=-1212, max_length=50),
            preserve_default=False,
        ),
    ]

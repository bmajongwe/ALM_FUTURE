# Generated by Django 4.1 on 2024-10-21 20:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ALM_APP', '0031_product_level_cashflows_record_count'),
    ]

    operations = [
        migrations.AddField(
            model_name='process',
            name='uses_behavioral_patterns',
            field=models.BooleanField(default=False),
        ),
    ]

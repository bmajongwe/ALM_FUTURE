# Generated by Django 5.1.3 on 2025-02-17 10:52

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ALM_APP', '0082_alter_hqlastock_v_product_name'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='hqlastock',
            name='max_hqla_percentage',
        ),
    ]

# Generated by Django 5.1.3 on 2025-02-12 14:26

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ALM_APP', '0075_hqlaclassification_hqlastock_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='hqlastock',
            old_name='process_names',
            new_name='v_product_name',
        ),
    ]

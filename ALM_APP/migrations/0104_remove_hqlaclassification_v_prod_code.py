# Generated by Django 5.1.3 on 2025-02-28 10:37

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ALM_APP', '0103_hqlaclassification_v_prod_type_level_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='hqlaclassification',
            name='v_prod_code',
        ),
    ]

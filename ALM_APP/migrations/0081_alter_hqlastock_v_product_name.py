# Generated by Django 5.1.3 on 2025-02-14 09:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ALM_APP', '0080_hqlaconfig_label'),
    ]

    operations = [
        migrations.AlterField(
            model_name='hqlastock',
            name='v_product_name',
            field=models.CharField(max_length=50),
        ),
    ]

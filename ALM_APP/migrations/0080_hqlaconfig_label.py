# Generated by Django 5.1.3 on 2025-02-13 10:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ALM_APP', '0079_hqlaconfig'),
    ]

    operations = [
        migrations.AddField(
            model_name='hqlaconfig',
            name='label',
            field=models.CharField(default='HQLA_Default', max_length=50, unique=True),
        ),
    ]

# Generated by Django 5.1.3 on 2025-01-16 13:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ALM_APP', '0059_log'),
    ]

    operations = [
        migrations.AddField(
            model_name='log',
            name='detailed_error',
            field=models.TextField(blank=True, null=True),
        ),
    ]

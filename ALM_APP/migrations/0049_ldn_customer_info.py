# Generated by Django 5.1.3 on 2025-01-07 07:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ALM_APP', '0048_liquiditygapresultsbase_v_product_splits_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Ldn_Customer_Info',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fic_mis_date', models.DateField()),
                ('v_party_id', models.CharField(max_length=50, unique=True)),
                ('v_partner_name', models.CharField(max_length=50)),
                ('v_party_type', models.CharField(max_length=50)),
                ('v_party_type_code', models.CharField(max_length=50)),
            ],
            options={
                'db_table': 'Ldn_Customer_Info',
            },
        ),
    ]

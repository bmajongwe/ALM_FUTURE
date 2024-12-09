# Generated by Django 4.1 on 2024-10-16 09:38

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('ALM_APP', '0028_timebucketdefinition_created_by_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductFilter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('field_name', models.CharField(max_length=50)),
                ('condition', models.CharField(max_length=50)),
                ('value', models.CharField(max_length=255)),
                ('created_by', models.CharField(default='System', max_length=50)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('modified_by', models.CharField(default='System', max_length=50)),
                ('modified_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddField(
            model_name='process',
            name='modified_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='process',
            name='modified_by',
            field=models.CharField(default='System', max_length=50),
        ),
        migrations.AddField(
            model_name='process',
            name='reated_by',
            field=models.CharField(default='System', max_length=50),
        ),
        migrations.AlterField(
            model_name='process',
            name='created_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name='process',
            name='filters',
            field=models.ManyToManyField(related_name='processes', to='ALM_APP.productfilter'),
        ),
    ]
# Generated by Django 5.1.6 on 2025-02-06 00:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plants', '0002_alter_users_latitude_alter_users_longitude'),
    ]

    operations = [
        migrations.AlterField(
            model_name='users',
            name='latitude',
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AlterField(
            model_name='users',
            name='longitude',
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
    ]

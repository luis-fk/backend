# Generated by Django 5.1.6 on 2025-05-05 23:10

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('political_culture', '0002_texts_content_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='texts',
            name='user_submitted_text',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='ChatHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.TextField()),
                ('role', models.CharField(choices=[('ai', 'AI'), ('human', 'Human')], max_length=10)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_histories', to='political_culture.users')),
            ],
        ),
        migrations.CreateModel(
            name='UserMemory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('memory', models.JSONField()),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='memory', to='political_culture.users')),
            ],
        ),
    ]

from typing import Any

from django.db import migrations, models

# Each app's Users table: the old keys kept the user's id in one of them.
USERS_MODELS = {
    "plants": ("plants", "Users"),
    "political-culture": ("political_culture", "Users"),
    "cfflch": ("cfflch", "Users"),
}


def keys_for_their_app(apps: Any, schema_editor: Any) -> None:
    """Each old key covers its app as the same user, and gets that user's person."""
    api_key = apps.get_model("api_keys", "ApiKey")
    for key in api_key.objects.all():
        users = apps.get_model(*USERS_MODELS[key.app])
        person = users.objects.filter(pk=key.user_id).first()
        key.users = {key.app: key.user_id}
        key.auth_user_id = person.auth_user_id if person else None
        key.save(update_fields=["users", "auth_user_id"])


def keys_back_to_one_app(apps: Any, schema_editor: Any) -> None:
    """Back to one app per key: a key that covers several keeps the first, in the
    apps' order (PostgreSQL's jsonb doesn't keep the keys' order)."""
    api_key = apps.get_model("api_keys", "ApiKey")
    for key in api_key.objects.all():
        key.app = next(app for app in USERS_MODELS if app in key.users)
        key.user_id = key.users[key.app]
        key.save(update_fields=["app", "user_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("api_keys", "0001_initial"),
        ("plants", "0001_initial"),
        ("political_culture", "0003_texts_selected_by"),
        ("cfflch", "0003_users"),
    ]

    operations = [
        migrations.AddField(
            model_name="apikey",
            name="auth_user_id",
            field=models.BigIntegerField(
                blank=True,
                help_text="The person: their id in the auth users table. Empty only "
                "on an old key whose user was already gone when keys started covering "
                "several apps.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="apikey",
            name="users",
            field=models.JSONField(
                default=dict,
                help_text="The person's id in each app's Users table, by app; the "
                "key works only in these apps.",
            ),
        ),
        # The old fields become optional before the conversion, so that migrating
        # back can add them again to a table that has keys, and then fill them in.
        migrations.AlterField(
            model_name="apikey",
            name="app",
            field=models.CharField(
                choices=[(app, app) for app in USERS_MODELS], max_length=20, null=True
            ),
        ),
        migrations.AlterField(
            model_name="apikey",
            name="user_id",
            field=models.BigIntegerField(
                help_text="The id in the app's Users table.", null=True
            ),
        ),
        migrations.RunPython(keys_for_their_app, keys_back_to_one_app),
        migrations.RemoveField(model_name="apikey", name="app"),
        migrations.RemoveField(model_name="apikey", name="user_id"),
    ]

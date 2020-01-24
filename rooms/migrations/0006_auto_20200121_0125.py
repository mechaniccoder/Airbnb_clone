# Generated by Django 2.2.5 on 2020-01-20 16:25

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('rooms', '0005_room_gusets'),
    ]

    operations = [
        migrations.AlterField(
            model_name='room',
            name='host',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rooms', to=settings.AUTH_USER_MODEL),
        ),
    ]

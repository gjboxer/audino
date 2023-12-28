# Generated by Django 4.2.3 on 2023-12-28 16:50

import core.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0005_remove_task_labels_label_task'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='job',
            options={'default_permissions': ()},
        ),
        migrations.AddField(
            model_name='job',
            name='type',
            field=models.CharField(choices=[('annotation', 'ANNOTATION'), ('ground_truth', 'GROUND_TRUTH')], default=core.models.JobType['ANNOTATION'], max_length=32),
        ),
        migrations.AlterField(
            model_name='job',
            name='stage',
            field=models.CharField(choices=[('annotation', 'ANNOTATION'), ('validation', 'VALIDATION'), ('acceptance', 'ACCEPTANCE')], default=core.models.StageChoice['ANNOTATION'], max_length=32),
        ),
        migrations.AlterField(
            model_name='job',
            name='state',
            field=models.CharField(choices=[('new', 'NEW'), ('in progress', 'IN_PROGRESS'), ('completed', 'COMPLETED'), ('rejected', 'REJECTED')], default=core.models.StateChoice['NEW'], max_length=32),
        ),
        migrations.AlterField(
            model_name='task',
            name='assignee',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assignees', to=settings.AUTH_USER_MODEL),
        ),
    ]

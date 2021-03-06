# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2017-05-05 20:23
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('issue_tracker', '0008_auto_20170505_1549'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='issuetag',
            options={'ordering': ['name']},
        ),
        migrations.AlterField(
            model_name='issue',
            name='issue_priority',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='issue_tracker.IssuePriority'),
        ),
        migrations.AlterField(
            model_name='issue',
            name='issue_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='issue_tracker.IssueType'),
        ),
        migrations.AlterField(
            model_name='issue',
            name='user_submitted_by',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
    ]

# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2017-12-04 17:32
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('units', '0002_029_to_030_first'),
    ]

    operations = [
        migrations.AlterField(
            model_name='unitavailabletimeedit',
            name='name',
            field=models.CharField(blank=True, help_text='A quick name or reason for the change', max_length=64, null=True),
        ),
    ]
# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-09-17 20:56
from __future__ import unicode_literals

from django.contrib.auth.management import create_permissions
from django.db import migrations


def add_attach_perms(apps, schema):


    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")

    try:
        perm = Permission.objects.get(name="Can add attachment")
    except:
        # during initial database creation the permission might not exist
        for app_config in apps.get_app_configs():
            app_config.models_module = True
            create_permissions(app_config, verbosity=0)
            app_config.models_module = None

        perm = Permission.objects.get(name="Can add attachment")

    for g in Group.objects.all():
        g.permissions.add(perm)


def rem_attach_perms(apps, schema):

    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")
    perm = Permission.objects.get(name="Can add attachment")

    for g in Group.objects.all():
        g.permissions.rem(perm)


class Migration(migrations.Migration):

    dependencies = [
        ('attachments', '0004_auto_20180906_0946'),
    ]

    operations = [
        migrations.RunPython(add_attach_perms, rem_attach_perms)
    ]

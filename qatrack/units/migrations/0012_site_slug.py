# Generated by Django 2.1.11 on 2019-11-29 04:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('units', '0011_auto_20190410_1101'),
    ]

    operations = [
        migrations.AddField(
            model_name='site',
            name='slug',
            field=models.SlugField(default='site-slug', help_text='Unique identifier made of lowercase characters and underscores for this site'),
            preserve_default=False,
        ),
    ]
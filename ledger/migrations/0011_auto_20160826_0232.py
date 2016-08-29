# -*- coding: utf-8 -*-
# Generated by Django 1.9.9 on 2016-08-26 02:32
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ledger', '0010_auto_20160825_2014'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='transactionrelatedobject',
            name='primary',
        ),
        migrations.AlterField(
            model_name='ledger',
            name='number',
            field=models.PositiveIntegerField(help_text='Unique numeric identifier for this ledger', unique=True),
        ),
    ]

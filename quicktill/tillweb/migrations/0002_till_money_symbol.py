# Generated by Django 2.1.4 on 2019-01-03 18:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tillweb', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='till',
            name='money_symbol',
            field=models.CharField(default='£', max_length=10),
            preserve_default=False,
        ),
    ]
# Generated by Django 4.0.4 on 2025-05-07 08:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('v1_forms', '0045_alter_questions_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='questions',
            name='type',
            field=models.IntegerField(choices=[(1, 'Geo'), (2, 'Administration'), (3, 'Text'), (4, 'Number'), (5, 'Option'), (6, 'Multiple_Option'), (7, 'Cascade'), (8, 'Photo'), (9, 'Date'), (10, 'Autofield'), (11, 'Attachment'), (12, 'Signature')]),
        ),
    ]

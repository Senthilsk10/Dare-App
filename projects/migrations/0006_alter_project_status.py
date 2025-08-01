# Generated by Django 5.1 on 2025-05-31 15:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0005_projectevaluatorpool_last_email_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='status',
            field=models.CharField(choices=[('CREATED', 'project created'), ('SYNOPSIS_SUBMITTED', 'Synopsis Submitted'), ('SYNOPSIS_APPROVED', 'Synopsis Approved by Guide'), ('ADMIN_NOTIFIED', 'Admin Notified'), ('EVALUATORS_ASSIGNED', 'Evaluators Pool Assigned'), ('EVALUATOR_SELECTION', 'Evaluator Selection in Progress'), ('EVALUATOR_CONFIRMED', 'Evaluator Confirmed'), ('PROJECT_DEVELOPMENT', 'Project Development Phase'), ('PROJECT_SUBMITTED', 'Project Submitted'), ('UNDER_EVALUATION', 'Under Evaluation'), ('EVALUATION_COMPLETED', 'Evaluation Completed'), ('VIVA_READY', 'Ready for Viva'), ('VIVA_SCHEDULED', 'Viva Scheduled'), ('VIVA_COMPLETED', 'Viva Completed'), ('PAYMENT_PENDING', 'Payment to Evaluator Pending'), ('COMPLETED', 'Project Completed')], default='CREATED', max_length=30),
        ),
    ]

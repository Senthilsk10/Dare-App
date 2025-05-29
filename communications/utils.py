from django.template import Template, Context
from django.core.mail import EmailMessage
from .models import EmailTemplate
from django.utils import timezone
def send_evaluator_approach_email(project, evaluator_pool):
    """
    Send approach email to evaluator using the 'Approach' template
    
    Args:
        project: Project instance
        evaluator_pool: ProjectEvaluatorPool instance
    """
    try:
        # Get the email template
        template = EmailTemplate.objects.get(name='Approach', is_active=True)
        
        # Prepare context variables
        context = {
            'recipient_name': evaluator_pool.evaluator.name,
            'recipient_location': evaluator_pool.evaluator.country,
            'candidate_name': project.student.user.get_full_name(),
            'roll_no': project.student.student_id,
            'department': project.student.course.department,
            'thesis_title': project.title,
            'supervisor_name': project.student.guide.user.get_full_name(),
            'consent_deadline': (timezone.now() + timezone.timedelta(days=15)).strftime('%d-%m-%Y'),
            'indian_remuneration': project.i_evaluator_payment_amount,
            'foreign_remuneration': project.f_evaluator_payment_amount,
            'institution': 'Annamalai University'  # Assuming this is constant
        }
        
        # Render templates with context
        subject = Template(template.subject_template).render(Context(context))
        body = Template(template.body_template).render(Context(context))
        
        # Create and send email
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email='careau2018@gmail.com',
            to=[evaluator_pool.evaluator.email],
            reply_to=['careau2018@gmail.com']
        )
        
        # TODO: Uncomment to actually send the email
        # email.send(fail_silently=False)
        
        # Return the email content for preview
        return {
            'status': 'success',
            'subject': subject,
            'body': body,
            'to': evaluator_pool.evaluator.email
        }
        
    except EmailTemplate.DoesNotExist:
        return {'status': 'error', 'message': 'Email template not found'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Q, Prefetch
from django.utils import timezone
from projects.models import Project, ProjectEvaluatorPool,WebhookLog
import json
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import timedelta
from .models import EmailCommunication
from .gmail_utils import send_mail_with_attachments, GoogleServiceManager, send_simple_email
 
# Django Views
from django.shortcuts import render
from django.http import HttpResponse

def initiate_google_auth(request):
    """View to initiate Google OAuth"""
    service_manager = GoogleServiceManager(request)
    auth_url = service_manager.get_authorization_url('combined')
    return redirect(auth_url)

def google_oauth_callback(request):
    """Handle Google OAuth callback"""
    authorization_code = request.GET.get('code')
    state = request.GET.get('state')
    
    if not authorization_code:
        return JsonResponse({'error': 'Authorization code not provided'}, status=400)
    
    service_manager = GoogleServiceManager(request)
    success = service_manager.handle_oauth_callback(authorization_code, state)
    
    if success:
        return JsonResponse({'message': 'Authentication successful'})
    else:
        return JsonResponse({'error': 'Authentication failed'}, status=400)

def send_email_view(request):
    """View to send email"""
    if request.method == 'POST':
        to_email = request.POST.get('to_email')
        subject = request.POST.get('subject')
        body = request.POST.get('body')
        drive_file_ids = request.POST.getlist('drive_file_ids')  # List of file IDs
        
        if drive_file_ids:
            result = send_mail_with_attachments(request, to_email, subject, body, drive_file_ids)
        else:
            result = send_simple_email(request, to_email, subject, body)
        
        return JsonResponse(result)
    
    return render(request, 'communications/send_email.html')
 
 
def awaiting_emails_v2(request):
    projects = Project.objects.filter(status='SYNOPSIS_APPROVED')
    evaluator_rows = []
    calendar_events = []
    
    for project in projects:
        for evaluator_pool in project.get_calender_evaluators():
            if not evaluator_pool:
                continue
                
            # Get email content
            email_content = evaluator_pool.send_approach_email()
            
            # Add to evaluator rows
            evaluator_data = {
                "project_title": project.title,
                "project_id": str(project.id),
                "type": evaluator_pool.evaluator.evaluator_type,
                "email": evaluator_pool.evaluator.email,
                "name": evaluator_pool.evaluator.name,
                "specialization": evaluator_pool.evaluator.specialization,
                "country": evaluator_pool.evaluator.country,
                "last_email_date": evaluator_pool.last_email_date.strftime('%Y-%m-%d %H:%M:%S') if evaluator_pool.last_email_date else "Never",
                "email_content": email_content,
                "project_pool_id": evaluator_pool.id,
                "priority_order": evaluator_pool.priority_order,
                "retry_count": evaluator_pool.retry_count
            }
            evaluator_rows.append(evaluator_data)
            
            # Create calendar event
            event_start = evaluator_pool.next_email_date if evaluator_pool.next_email_date else timezone.now()
            
            calendar_event = {
                "id": f"{str(project.id)}_{str(evaluator_pool.id)}",
                "title": f"{evaluator_pool.evaluator.name} - {project.title}",
                "start": event_start.isoformat(),
                "allDay": True,
                "extendedProps": {
                    "evaluator_email": evaluator_pool.evaluator.email,
                    "project_title": project.title,
                    "evaluator_type": evaluator_pool.evaluator.evaluator_type,
                    "email_content": email_content,
                    "project_pool_id": evaluator_pool.id
                }
            }
            calendar_events.append(calendar_event)
    
    print(evaluator_rows)
    print(calendar_events)
    # Return JSON response for API
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'evaluators': evaluator_rows,
            'calendar_events': calendar_events
        })
    
    # Return HTML response for web view
    return render(request, 'communications/awaiting_mails.html', {
        'evaluator_rows': evaluator_rows,
        'evaluator_rows_json': json.dumps(evaluator_rows),
        'calendar_events': json.dumps(calendar_events)
    })

@require_POST
@csrf_exempt
def send_email(request):
    data = json.loads(request.body)
    pool_id = data.get('project_pool_id')
    pool = get_object_or_404(ProjectEvaluatorPool, id=pool_id)
    result = pool.send_approach_email()
    attachments = [] #add default acceptance form if here..
    webhook_obj = WebhookLog.objects.filter(project=pool.project,file_type="SYNOPSIS").first()
    if webhook_obj:
        attachments.append(webhook_obj.file_id)
    
    try:
        message_id = send_mail_with_attachments(request, result['to'], result['subject'], result['body'], drive_file_ids=attachments)
        # here save the message id in the communication logs.
        if pool.retry_count < 1:
            EmailCommunication.objects.create(eval_pool=pool, email_type='INVITATION', subject=result['subject'], 
                                           body=result['body'], sent_date=timezone.now(), message_id=message_id)
        else:
            EmailCommunication.objects.create(eval_pool=pool, email_type='REMINDER', subject=result['subject'], 
                                           body=result['body'], sent_date=timezone.now(), message_id=message_id)
        
        pool.retry_count += 1
        pool.last_email_date = timezone.now()
        pool.next_email_date = timezone.now() + timedelta(days=15)
        pool.save()
        return JsonResponse({'success': True, 'result': message_id})
    except Exception as e:
        # Log the error but still save the communication
        error_message = str(e)
        if pool.retry_count < 1:
            EmailCommunication.objects.create(
                eval_pool=pool, 
                email_type='INVITATION', 
                subject=result['subject'], 
                body=result['body'], 
                sent_date=timezone.now(),
                status='FAILED',
                error_message=error_message
            )
        else:
            EmailCommunication.objects.create(
                eval_pool=pool, 
                email_type='REMINDER', 
                subject=result['subject'], 
                body=result['body'], 
                sent_date=timezone.now(),
                status='FAILED',
                error_message=error_message
            )
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Q, Prefetch,Max
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from projects.models import Project, ProjectEvaluatorPool,WebhookLog,VersionedProjectEvaluatorPool
import json
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import timedelta,datetime
from .models import EmailCommunication
from .gmail_utils import send_mail_with_attachments, GoogleServiceManager, send_simple_email
from communications.utils import send_thesis_submission_email
from collections import defaultdict
from django.utils.timezone import now
from .serializers import EvaluatorMailListSerializer,EvaluatorDetailSerializer
 
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
 
 
# Router view to switch between regular awaiting emails and project submission awaiting emails based on ?project=true query string

def awaiting_emails(request):
    """Route to the correct awaiting-emails view based on query string.

    If ?project=true is present, show the project-submission email list,
    otherwise default to the normal awaiting_emails_v2 list.
    """
    if request.GET.get('project', '').lower() == 'true':
        return awaiting_project_emails(request)
    return awaiting_emails_v2(request)

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
    
    if request.GET.get('api', '').lower() == 'true':
        return JsonResponse({
            'evaluators': evaluator_rows,
            'evaluator_rows_json': evaluator_rows,
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


@require_POST
@csrf_exempt
def send_project_email(request):
    """Send project submission / evaluation reminder email"""
    data = json.loads(request.body)
    pool_id = data.get('project_pool_id')
    pool = get_object_or_404(ProjectEvaluatorPool, id=pool_id)

    # generate email (reminder if already sent before)
    latest_comm = EmailCommunication.objects.filter(eval_pool=pool, email_type='PROJECT_SUBMISSION').order_by('-sent_date').first()
    reminder = bool(latest_comm)
    email_dict = send_thesis_submission_email(pool.project, pool, reminder=reminder)
    file_id = WebhookLog.objects.filter(project=pool.project,file_type="PROJECT").first().file_id
    try:
        message_id = send_mail_with_attachments(
            request,
            email_dict['to'],
            email_dict['subject'],
            email_dict['body'],
            drive_file_ids=[file_id]
        )

        EmailCommunication.objects.create(
            eval_pool=pool,
            email_type='PROJECT_SUBMISSION',
            subject=email_dict['subject'],
            body=email_dict['body'],
            sent_date=timezone.now(),
            message_id=message_id
        )

        pool.report_retry_count += 1
        pool.report_last_email_date = timezone.now()
        pool.report_next_email_date = timezone.now() + timedelta(days=45)
        pool.save()
        return JsonResponse({'success': True, 'result': message_id})
    except Exception as e:
        EmailCommunication.objects.create(
            eval_pool=pool,
            email_type='PROJECT_SUBMISSION',
            subject=email_dict.get('subject', ''),
            body=email_dict.get('body', ''),
            sent_date=timezone.now(),
            status='FAILED',
            error_message=str(e)
        )
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
def awaiting_project_emails(request):
    """View to list evaluators awaiting project-submission mails (45-day cadence)"""
    projects = Project.objects.filter(status='UNDER_EVALUATION')
    evaluator_rows, calendar_events = [], []

    for project in projects:
        # consider ALL evaluators in pool that are still active and below 3 retries
        for evaluator_pool in project.evaluator_pool.filter(report_retry_count__lt=3,evaluator__in=[project.assigned_foreign_evaluator,project.assigned_indian_evaluator]):
            if evaluator_pool.evaluator is None:
                continue
            
            print("evaluator_pool",evaluator_pool)

            latest_comm = EmailCommunication.objects.filter(
                eval_pool=evaluator_pool,
                email_type='PROJECT_SUBMISSION'
            ).order_by('-sent_date').first()

            need_email = False
            reminder = False
            last_email_date_str = "Never"

            if not latest_comm:
                need_email = True  # never sent before
            else:
                last_email_date_str = latest_comm.sent_date.strftime('%Y-%m-%d %H:%M:%S')
                if (timezone.now() - latest_comm.sent_date).days >= 45:
                    need_email = True
                    reminder = True
            # print("need_email",need_email)
            # print("reminder",reminder)

            email_content = send_thesis_submission_email(project, evaluator_pool, reminder=reminder)
            # email_content = email_preview.get('body', '')
            # print("email_content",email_content)

            evaluator_rows.append({
                "project_title": project.title,
                "project_id": str(project.id),
                "type": evaluator_pool.evaluator.evaluator_type,
                "email": evaluator_pool.evaluator.email,
                "name": evaluator_pool.evaluator.name,
                "specialization": evaluator_pool.evaluator.specialization,
                "country": evaluator_pool.evaluator.country,
                "last_email_date": last_email_date_str,
                "email_content": email_content,
                "project_pool_id": evaluator_pool.id,
                "priority_order": evaluator_pool.priority_order,
                "report_retry_count": evaluator_pool.report_retry_count
            })

            start_date = evaluator_pool.report_next_email_date or timezone.now()
            calendar_events.append({
                "id": f"{project.id}_{evaluator_pool.id}",
                "title": f"{evaluator_pool.evaluator.name} - {project.title}",
                "start": start_date.isoformat(),
                "allDay": True,
                "extendedProps": {
                    "evaluator_email": evaluator_pool.evaluator.email,
                    "project_title": project.title,
                    "evaluator_type": evaluator_pool.evaluator.evaluator_type,
                    "email_content": email_content,
                    "project_pool_id": evaluator_pool.id
                }
            })

    # AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'evaluators': evaluator_rows, 'calendar_events': calendar_events})

    # print("evaluator_rows",evaluator_rows)
    # print("calendar_events",calendar_events)
    if request.GET.get('api', '').lower() == 'true':
        return JsonResponse({
            'evaluators': evaluator_rows,
            'evaluator_rows_json': evaluator_rows,
            'calendar_events': calendar_events
        })
    return render(request, 'communications/awaiting_project_emails.html', {
        'evaluator_rows': evaluator_rows,
        'evaluator_rows_json': json.dumps(evaluator_rows),
        'calendar_events': json.dumps(calendar_events)
    })
    

# ==================================================================
# Version 3 for Rest-API based Emailing List and calendar Management
# ==================================================================

# helper for getting time , retry counts
def get_configuration(key):
    from communications.models import SystemConfiguration
    try:
        return int(SystemConfiguration.objects.get(key=key).value)
    except (SystemConfiguration.DoesNotExist, ValueError):
        return None
    

def is_blocked_by_higher_priority(entry, mail_type, retries):
    evaluator_type = entry.evaluator.evaluator_type
    project = entry.project

    higher_priority_qs = VersionedProjectEvaluatorPool.objects.filter(
        project=project,
        version=entry.version,
        evaluator__evaluator_type=evaluator_type,
        priority_order__lt=entry.priority_order
    )

    if mail_type == "approach":
        return any(hp.approach_mail_count < retries for hp in higher_priority_qs)
    else:
        return any(hp.report_mail_count < retries for hp in higher_priority_qs)


def get_eligible_email_counts_by_month():
    today = timezone.now().date()
    data = defaultdict(lambda: {"approach": 0, "project": 0})

    # Configs
    approach_wait = get_configuration("approach_wait_time")
    approach_retries = get_configuration("approach_retry_count")
    project_wait = get_configuration("evaluation_wait_time")
    project_retries = get_configuration("project_retry_count")

    if None in [approach_wait, approach_retries, project_wait, project_retries]:
        raise ValueError("Missing configuration values")

    # Latest version pool map
    latest_versions = VersionedProjectEvaluatorPool.objects.values("project").annotate(
        max_version=Max("version")
    )
    version_map = {v["project"]: v["max_version"] for v in latest_versions}

    qs = VersionedProjectEvaluatorPool.objects.filter(version__in=version_map.values())

    for entry in qs:
        project = entry.project

        # APPROACH MAIL LOGIC
        if project.status == "EVALUATOR_SELECTION":
            if not (project.assigned_indian_evaluator and project.assigned_foreign_evaluator):
                if entry.approach_mail_count < approach_retries:
                    last_sent = entry.last_approach_email_date
                    if not last_sent or (last_sent + timedelta(days=approach_wait)) <= today:
                        if not is_blocked_by_higher_priority(entry, "approach", approach_retries):
                            key = entry.next_approach_email_date.strftime("%Y-%m") if entry.next_approach_email_date else today.strftime("%Y-%m")
                            data[key]["approach"] += 1

        # PROJECT MAIL LOGIC
        if entry.report_mail_count < project_retries:
            last_sent = entry.last_evaluation_email_date
            if not last_sent or (last_sent + timedelta(days=project_wait)) <= today:
                if (entry.evaluator.evaluator_type == "INDIAN" and project.assigned_indian_evaluator) or \
                   (entry.evaluator.evaluator_type == "FOREIGN" and project.assigned_foreign_evaluator):
                    continue

                if not is_blocked_by_higher_priority(entry, "project", project_retries):
                    key = entry.next_evaluation_email_date.strftime("%Y-%m") if entry.next_evaluation_email_date else today.strftime("%Y-%m")
                    data[key]["project"] += 1

    return data




def get_eligible_entries_by_day(date_obj, mail_type):
    # Configs
    wait_key = "approach_wait_time" if mail_type == "approach" else "evaluation_wait_time"
    retry_key = "approach_retry_count" if mail_type == "approach" else "project_retry_count"

    wait_days = get_configuration(wait_key)
    max_retries = get_configuration(retry_key)

    if not wait_days or not max_retries:
        raise ValueError("Configuration missing")

    # Latest version pool map
    latest_versions = VersionedProjectEvaluatorPool.objects.values("project").annotate(
        max_version=Max("version")
    )
    version_map = {v["project"]: v["max_version"] for v in latest_versions}

    qs = VersionedProjectEvaluatorPool.objects.filter(version__in=version_map.values())
    eligible = []

    for entry in qs:
        project = entry.project
        if mail_type == "approach":
            if project.status != "EVALUATOR_SELECTION":
                continue
            if project.assigned_indian_evaluator and project.assigned_foreign_evaluator:
                continue
            if entry.approach_mail_count >= max_retries:
                continue
            if entry.next_approach_email_date and entry.next_approach_email_date.date() != date_obj.date():
                continue
            last_sent = entry.last_approach_email_date
            if not last_sent or (last_sent + timedelta(days=wait_days)) <= date_obj.date():
                if not is_blocked_by_higher_priority(entry, "approach", max_retries):
                    eligible.append(entry)

        else:  # project
            if entry.report_mail_count >= max_retries:
                continue
            if entry.next_evaluation_email_date and entry.next_evaluation_email_date.date() != date_obj.date():
                continue
            if (entry.evaluator.evaluator_type == "INDIAN" and project.assigned_indian_evaluator) or \
               (entry.evaluator.evaluator_type == "FOREIGN" and project.assigned_foreign_evaluator):
                continue
            last_sent = entry.last_evaluation_email_date
            if not last_sent or (last_sent + timedelta(days=wait_days)) <= date_obj.date():
                if not is_blocked_by_higher_priority(entry, "project", max_retries):
                    eligible.append(entry)

    return eligible


class MonthlyEmailCountAPI(APIView):
    """
    Returns eligible email counts (approach and project) grouped by month and year
    """

    def get(self, request):
        today = timezone.now().date()
        data = defaultdict(lambda: {"approach": 0, "project": 0})

        # Get config
        approach_wait = get_configuration("approach_wait_time")
        approach_retries = get_configuration("approach_retry_count")
        project_wait = get_configuration("evaluation_wait_time")
        project_retries = get_configuration("project_retry_count")

        if None in [approach_wait, approach_retries, project_wait, project_retries]:
            return Response({"error": "Missing configuration values."}, status=400)

        # Latest version mapping
        latest_versions = VersionedProjectEvaluatorPool.objects.values("project").annotate(
            max_version=Max("version")
        )
        version_map = {v["project"]: v["max_version"] for v in latest_versions}

        qs = VersionedProjectEvaluatorPool.objects.filter(version__in=version_map.values())

        for entry in qs:
            project = entry.project

            # ------------ APPROACH COUNT LOGIC ------------
            if project.status == "EVALUATOR_SELECTION":
                if not (project.assigned_indian_evaluator and project.assigned_foreign_evaluator):
                    if entry.approach_mail_count < approach_retries:
                        last_sent = entry.last_approach_email_date
                        if not last_sent or (last_sent + timedelta(days=approach_wait)) <= today:
                            if entry.next_approach_email_date:
                                is_this_month = True
                                key = entry.next_approach_email_date.strftime("%Y-%m")
                            else:
                                is_this_month = True
                                key = today.strftime("%Y-%m")

                            # Check priority block
                            higher_priority_qs = VersionedProjectEvaluatorPool.objects.filter(
                                project=project,
                                version=entry.version,
                                evaluator__evaluator_type=entry.evaluator.evaluator_type,
                                priority_order__lt=entry.priority_order
                            )

                            blocked = any(hp.approach_mail_count < approach_retries for hp in higher_priority_qs)
                            if not blocked:
                                data[key]["approach"] += 1

            # ------------ PROJECT COUNT LOGIC ------------
            if entry.report_mail_count < project_retries:
                last_sent = entry.last_evaluation_email_date
                if not last_sent or (last_sent + timedelta(days=project_wait)) <= today:
                    if entry.next_evaluation_email_date:
                        key = entry.next_evaluation_email_date.strftime("%Y-%m")
                    else:
                        key = today.strftime("%Y-%m")

                    # Skip if evaluator type already assigned
                    if (entry.evaluator.evaluator_type == "INDIAN" and project.assigned_indian_evaluator) or \
                       (entry.evaluator.evaluator_type == "FOREIGN" and project.assigned_foreign_evaluator):
                        continue

                    higher_priority_qs = VersionedProjectEvaluatorPool.objects.filter(
                        project=project,
                        version=entry.version,
                        evaluator__evaluator_type=entry.evaluator.evaluator_type,
                        priority_order__lt=entry.priority_order
                    )

                    blocked = any(hp.report_mail_count < project_retries for hp in higher_priority_qs)
                    if not blocked:
                        data[key]["project"] += 1

        return Response(data, status=status.HTTP_200_OK)


class MonthlyEmailListAPI(APIView):
    """
    Returns list of evaluators eligible for mailing in a given month (approach or project)
    """
    def get(self, request):
        year = int(request.GET.get("year", timezone.now().year))
        month = int(request.GET.get("month", timezone.now().month))
        mail_type = request.GET.get("type", "approach")

        if mail_type not in ["approach", "project"]:
            return Response({"error": "Invalid type. Must be 'approach' or 'project'."}, status=400)

        wait_key = "approach_wait_time" if mail_type == "approach" else "evaluation_wait_time"
        retry_key = "approach_retry_count" if mail_type == "approach" else "project_retry_count"

        wait_days = get_configuration(wait_key)
        max_retries = get_configuration(retry_key)

        if wait_days is None or max_retries is None:
            return Response({"error": "Configuration not found."}, status=400)

        today = timezone.now().date()

        # Get latest version for each project
        latest_versions = VersionedProjectEvaluatorPool.objects.values("project").annotate(
            max_version=Max("version")
        )
        version_map = {v["project"]: v["max_version"] for v in latest_versions}

        qs = VersionedProjectEvaluatorPool.objects.filter(version__in=version_map.values())

        eligible_evaluators = []

        for entry in qs:
            project = entry.project

            if mail_type == "approach":
                # Project must still need evaluators
                if project.status != "EVALUATOR_SELECTION":
                    continue

                if project.assigned_indian_evaluator and project.assigned_foreign_evaluator:
                    continue

                # Check retries
                if entry.approach_mail_count >= max_retries:
                    continue

                # Wait time before retry
                last_sent = entry.last_approach_email_date
                if last_sent and (last_sent + timedelta(days=wait_days)) > today:
                    continue

                # Check if date is relevant for this month
                if entry.next_approach_email_date and entry.next_approach_email_date.month != month:
                    continue

                # Allow only if all higher-priority (lower number) of same type are exhausted
                higher_priority_qs = VersionedProjectEvaluatorPool.objects.filter(
                    project=project,
                    version=entry.version,
                    evaluator__evaluator_type=entry.evaluator.evaluator_type,
                    priority_order__lt=entry.priority_order
                )
                print(higher_priority_qs)

                blocked = False
                for hp in higher_priority_qs:
                    if hp.approach_mail_count < max_retries:
                        blocked = True
                        break

                if not blocked:
                    eligible_evaluators.append(entry)

            elif mail_type == "project":
                if entry.report_mail_count >= max_retries:
                    continue

                last_sent = entry.last_evaluation_email_date
                if last_sent and (last_sent + timedelta(days=wait_days)) > today:
                    continue

                if entry.next_evaluation_email_date and entry.next_evaluation_email_date.month != month:
                    continue

                # Stop if evaluator of this type is already assigned
                if (
                    (entry.evaluator.evaluator_type == "INDIAN" and project.assigned_indian_evaluator) or
                    (entry.evaluator.evaluator_type == "FOREIGN" and project.assigned_foreign_evaluator)
                ):
                    continue

                # Allow only if all higher-priority (lower number) of same type are exhausted
                higher_priority_qs = VersionedProjectEvaluatorPool.objects.filter(
                    project=project,
                    version=entry.version,
                    evaluator__evaluator_type=entry.evaluator.evaluator_type,
                    priority_order__lt=entry.priority_order
                )

                blocked = False
                for hp in higher_priority_qs:
                    if hp.report_mail_count < max_retries:
                        blocked = True
                        break

                if not blocked:
                    eligible_evaluators.append(entry)

        serializer = EvaluatorMailListSerializer(eligible_evaluators, many=True)
        return Response(serializer.data, status=200)


class DailyEmailDetailsAPI(APIView):
    """
    Returns evaluator mail details for a specific date (approach/project)
    """
    def get(self, request):
        date_str = request.GET.get("date")
        mail_type = request.GET.get("type", "approach")
        print(date_str)

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            return Response({"error": "Invalid date format, expected YYYY-MM-DD."}, status=400)

        eligible_entries = get_eligible_entries_by_day(date_obj, mail_type)
        # return Response(eligible_entries, status=200)
        # print(eligible_entries)
        serializer = EvaluatorDetailSerializer(eligible_entries,context={'mail_type': mail_type}, many=True)
        # 
        return Response(serializer.data, status=200)

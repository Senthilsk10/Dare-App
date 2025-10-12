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
    

@require_POST
@csrf_exempt
def v3_send_email(request):
    data = json.loads(request.body)
    pool_id = data.get('project_pool_id')
    pool = get_object_or_404(VersionedProjectEvaluatorPool, id=pool_id)
    result = pool.approach_email_content
    attachments = [] #add default acceptance form if here..
    webhook_obj = WebhookLog.objects.filter(project=pool.project,file_type="SYNOPSIS").first()
    if webhook_obj:
        attachments.append(webhook_obj.file_id)
    
    try:
        message_id = send_mail_with_attachments(request, result['to'], result['subject'], result['body'], drive_file_ids=attachments)
        if not isinstance(message_id, str):
            raise Exception("Failed to send email")
        # here save the message id in the communication logs.
        if pool.approach_mail_count < 1:
            EmailCommunication.objects.create(eval_pool=pool, email_type='INVITATION', subject=result['subject'], 
                                           body=result['body'], sent_date=timezone.now(), message_id=message_id)
        else:
            EmailCommunication.objects.create(eval_pool=pool, email_type='REMINDER', subject=result['subject'], 
                                           body=result['body'], sent_date=timezone.now(), message_id=message_id)
        
        pool.approach_mail_count += 1
        pool.last_approach_email_date = timezone.now()
        pool.next_approach_email_date = timezone.now() + timedelta(days=get_configuration('approach_wait_time'))
        pool.save()
        return JsonResponse({'success': True, 'result': message_id})
    except Exception as e:
        # Log the error but still save the communication
        error_message = str(e)
        if pool.approach_mail_count < 1:
            EmailCommunication.objects.create(
                eval_pool=pool, 
                email_type='INVITATION', 
                subject=result['subject'], 
                body=result['body'], 
                sent_date=timezone.now(),
                status='FAILED',
                # error_message=error_message
            )
        else:
            EmailCommunication.objects.create(
                eval_pool=pool, 
                email_type='REMINDER', 
                subject=result['subject'], 
                body=result['body'], 
                sent_date=timezone.now(),
                status='FAILED',
                # error_message=error_message
            )
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_POST
@csrf_exempt
def v3_send_project_email(request):
    """Send project submission / evaluation reminder email"""
    data = json.loads(request.body)
    pool_id = data.get('project_pool_id')
    pool = get_object_or_404(VersionedProjectEvaluatorPool, id=pool_id)

    # generate email (reminder if already sent before)
    latest_comm = EmailCommunication.objects.filter(eval_pool=pool, email_type='PROJECT_SUBMISSION').order_by('-sent_date').first()
    reminder = bool(latest_comm)
    email_dict = pool.project_email_content
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

        pool.report_mail_count += 1
        pool.last_evaluation_email_date = timezone.now()
        pool.next_evaluation_email_date = timezone.now() + timedelta(days=get_configuration('evaluation_wait_time'))
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
        print(entry.evaluator.email,entry.last_approach_email_date)
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


def get_eligible_entries_by_month(year, month, mail_type):
    """Return list of eligible VersionedProjectEvaluatorPool entries for the given month."""
    # Config keys
    wait_key = "approach_wait_time" if mail_type == "approach" else "evaluation_wait_time"
    retry_key = "approach_retry_count" if mail_type == "approach" else "project_retry_count"

    wait_days = get_configuration(wait_key)
    max_retries = get_configuration(retry_key)

    if wait_days is None or max_retries is None:
        raise ValueError("Configuration missing")

    today = timezone.now().date()

    # Latest version per project
    latest_versions = VersionedProjectEvaluatorPool.objects.values("project").annotate(
        max_version=Max("version")
    )
    version_map = {v["project"]: v["max_version"] for v in latest_versions}

    qs = VersionedProjectEvaluatorPool.objects.filter(version__in=version_map.values())
    eligible = []
    if mail_type == "approach":
        qs = qs.filter(project__status="EVALUATOR_SELECTION")
    else:
        qs = qs.filter(project__status="UNDER_EVALUATION")
    for entry in qs:
        project = entry.project
        if mail_type == "approach":
            # Project must still need evaluators
            if project.status != "EVALUATOR_SELECTION":
                print(f"Skipped {entry.id}: Project status is {project.status}")
                continue

            if project.assigned_indian_evaluator and project.assigned_foreign_evaluator:
                print(f"Skipped {entry.id}: Both evaluators already assigned")
                continue

            # Retry count check
            if entry.approach_mail_count >= max_retries:
                print(f"Skipped {entry.id}: Reached max retries ({entry.approach_mail_count}/{max_retries})")
                continue

            # Wait time check
            last_sent = entry.last_approach_email_date
            if last_sent and (last_sent.date() + timedelta(days=wait_days)) > today:
                print(f"Skipped {entry.id}: Waiting period not yet over since last mail on {last_sent.date()}")
                continue

            # Month relevance check
            if entry.next_approach_email_date and (
                entry.next_approach_email_date.year != year or entry.next_approach_email_date.month != month
            ):
                print(f"Skipped {entry.id}: next_approach_email_date {entry.next_approach_email_date} not in {year}-{month}")
                continue

            # Priority check
            if is_blocked_by_higher_priority(entry, "approach", max_retries):
                print(f"Skipped {entry.id}: Blocked by higher priority evaluator")
                continue

            # Passed all checks
            eligible.append(entry)
            print(f"Included {entry.id}: Eligible for approach email")

        else:  # project mail
            if entry.report_mail_count >= max_retries:
                continue
            last_sent = entry.last_evaluation_email_date
            if last_sent and (last_sent.date() + timedelta(days=wait_days)) > today:
                continue
            if entry.next_evaluation_email_date and (
                entry.next_evaluation_email_date.year != year or entry.next_evaluation_email_date.month != month
            ):
                continue
            # Stop if evaluator already assigned of that type
            if (
                (entry.evaluator.evaluator_type == "INDIAN" and project.assigned_indian_evaluator) or
                (entry.evaluator.evaluator_type == "FOREIGN" and project.assigned_foreign_evaluator)
            ):
                continue
            if is_blocked_by_higher_priority(entry, "project", max_retries):
                continue
            eligible.append(entry)

    return eligible


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

        # Use consolidated monthly eligibility helper and return early
        try:
            eligible_entries = get_eligible_entries_by_month(year, month, mail_type)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

        serializer = EvaluatorMailListSerializer(eligible_entries, many=True)
        return Response(serializer.data, status=200)

        return Response(serializer.data, status=200)


class DailyEmailDetailsAPI(APIView):
    """
    Returns evaluator mail details for a specific date (approach/project)
    """
    def get(self, request):
        date_str = request.GET.get("date")
        mail_type = request.GET.get("type", "approach")

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            return Response({"error": "Invalid date format, expected YYYY-MM-DD."}, status=400)

        eligible_entries = get_eligible_entries_by_day(date_obj, mail_type)  
        serializer = EvaluatorDetailSerializer(eligible_entries,context={'mail_type': mail_type}, many=True)
        return Response(serializer.data, status=200)

    def post(self, request):
        try:
            project_pool_id = request.data.get("id")
            mail_type = request.data.get("type", "approach")
            date = request.data.get("next_date", "approach")
            if mail_type == 'approach':
                VersionedProjectEvaluatorPool.objects.filter(id=project_pool_id).update(
                next_approach_email_date=date
            )
            else:
                VersionedProjectEvaluatorPool.objects.filter(id=project_pool_id).update(
                    next_evaluation_email_date=date
                )
                
            return Response({"message": "Date updated successfully"}, status=200)
        except Exception as e:
            return Response({"error": str(e)}, status=400)
            
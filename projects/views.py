from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages
from django.db import transaction
import json

from .models import Project, WebhookLog, ProjectEvaluatorPool
from users.models import User, PhDStudent, Evaluator

@login_required
def my_projects(request):
    if request.user.role == User.Role.STUDENT:
        projects = Project.objects.filter(student__email=request.user.email)
        return render(request,'projects/projects.html', {'projects': projects})
    else:
        return HttpResponse('You are not authorized to view this page')

@login_required
def create_project(request):
    if request.method == "POST":
        title = request.POST.get('title')
        try:
            Project.objects.create(student=PhDStudent.objects.get(email=request.user.email),title=title)
        except Exception as e:
            messages.error(request, 'Failed to create new project student may create only one project')
            return redirect('projects:my_projects')
        
        return redirect('projects:my_projects')

@login_required
def project_detail(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    
    # Check if user has permission to view this project
    if not request.user.is_admin and request.user.email != project.student.email:
        return HttpResponseForbidden("You don't have permission to view this project")
    
    # Get available evaluators not already in the pool
    assigned_evaluators = project.evaluator_pool.all()
    context = {
        'project': project,
        'assigned_evaluators': assigned_evaluators,
    }
    return render(request, 'projects/project-detail.html', context)

@csrf_exempt
def synopsis_webhook(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            pr_id = data["form-details"]
            project = Project.objects.get(id=pr_id)
            project.status = "SYNOPSIS_SUBMITTED"
            project.save()
            WebhookLog.objects.create(project=project,file_type="SYNOPSIS",file_id=data['upload your synopsis PDF file'][0],raw_payload=data)
            return JsonResponse({"message": "success"}, status=200)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)

    return JsonResponse({"error": "Invalid request method"}, status=405)


@csrf_exempt
def project_webhook(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            pr_id = data["form-details"]
            project = Project.objects.get(id=pr_id)
            project.status = "PROJECT_SUBMITTED"
            project.save()
            WebhookLog.objects.create(project=project,file_type="PROJECT",file_id=data['upload your Project PDF file'][0],raw_payload=data)
            return JsonResponse({"message": "success"}, status=200)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)

    return JsonResponse({"error": "Invalid request method"}, status=405)

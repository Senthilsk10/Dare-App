# views.py
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from django.shortcuts import render
from datetime import datetime
from .models import AdminNotification
from .serializers import AdminNotificationSerializer, ProjectSerializer, EvaluatorSerializer, ProjectFullSerializer
from projects.models import Project
from users.models import Evaluator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from django.db import transaction

class NotificationPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class AdminNotificationListView(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = AdminNotificationSerializer
    pagination_class = NotificationPagination
    
    def get_queryset(self):
        queryset = AdminNotification.objects.all()
        
        # Filter by read status
        is_read = self.request.query_params.get('is_read')
        if is_read is not None:
            is_read_bool = is_read.lower() == 'true'
            queryset = queryset.filter(is_read=is_read_bool)
        
        # Date filters
        from_date = self.request.query_params.get('from_date')
        to_date = self.request.query_params.get('to_date')
        
        if from_date:
            try:
                from_date_obj = datetime.strptime(from_date, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date__gte=from_date_obj)
            except ValueError:
                pass
        
        if to_date:
            try:
                to_date_obj = datetime.strptime(to_date, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date__lte=to_date_obj)
            except ValueError:
                pass
        
        # Priority filter
        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        # Search filter (optional)
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | 
                Q(message__icontains=search) |
                Q(from_email__icontains=search)
            )
        
        return queryset

@csrf_exempt
def admin_notification_detail(request, pk):
    """
    Simplified notification detail view with no permission checks
    """
    from django.http import JsonResponse
    from django.views.decorators.http import require_http_methods
    from django.utils import timezone
    import json
    
    try:
        notification = AdminNotification.objects.get(pk=pk)
    except AdminNotification.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    
    if request.method == 'GET':
        data = {
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'is_read': notification.is_read,
            'created_at': notification.created_at.isoformat(),
            'read_at': notification.read_at.isoformat() if notification.read_at else None
        }
        return JsonResponse(data)
    
    elif request.method == 'PATCH':
        try:
            data = json.loads(request.body)
            project_id = data.get('project_id')
            try:
                project = Project.objects.get(id=project_id)
            except Project.DoesNotExist:
                return JsonResponse({'error': 'Project not found'}, status=404)
            from_email = data.get('email')
            assign_evaluator = data.get('assign_evaluator')
            
            # Print initial values
            print("\n=== BEFORE ASSIGNMENT ===")
            print("Project initial values:", ProjectFullSerializer(project).data)
            print("Evaluator pool initial values:", [
                {
                    'evaluator': pool.evaluator.email,
                    'evaluator_type': pool.evaluator.evaluator_type,
                    'retry_count': pool.retry_count
                } for pool in project.evaluator_pool.all()
            ])
            
            if 'is_read' in data and data['is_read']:
                notification.is_read = True
                notification.read_at = timezone.now()
                
                try:
                    with transaction.atomic():
                        if assign_evaluator:
                            evaluator = Evaluator.objects.get(email=from_email)
                            if evaluator.evaluator_type == 'FOREIGN':
                                project.assigned_foreign_evaluator = evaluator
                            else:
                                project.assigned_indian_evaluator = evaluator
                            
                            # Update evaluator pool
                            evaluator_pool = project.evaluator_pool.filter(evaluator=evaluator).first()
                            if evaluator_pool:
                                evaluator_pool.retry_count = 3
                                evaluator_pool.save()
                            
                            # Save project changes
                            project.save()
                            
                            # Print final values
                            print("\n=== AFTER ASSIGNMENT ===")
                            print("Project final values:", ProjectFullSerializer(project).data)
                            print("Evaluator pool final values:", [
                                {
                                    'evaluator': pool.evaluator.email,
                                    'evaluator_type': pool.evaluator.evaluator_type,
                                    'retry_count': pool.retry_count
                                } for pool in project.evaluator_pool.all()
                            ])
                            
                            # Remove test exception
                            # raise Exception("test")
                except Exception as e:
                    print("Exception ",e)
                
                
                # remove him from mailing list
                
                # found error :
                    # update project.file.processed =True and process_errors as ( is attachments then attachments ,if error then error message included ?)
                # evaluator found no errors then mark the project as completed , next to step to schedule for viva
                
                # evaluator enquired about payment like confirming or some thing like that.. i think we need to get the attachment for claim bill ...
                
                # others ..
                # notification.save()
                return JsonResponse({'status': 'success', 'message': 'Notification marked as read'})
            return JsonResponse({'status': 'no changes'})
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

class ProjectListView(generics.ListAPIView):
    serializer_class = ProjectSerializer
    
    def get_queryset(self):
        email = self.request.query_params.get('email')
        if not email:
            return Project.objects.all()

        return Project.objects.filter(
            evaluator_pool__evaluator__email=email
        ).distinct()

class EvaluatorListView(generics.ListAPIView):
    queryset = Evaluator.objects.all()
    serializer_class = EvaluatorSerializer

@api_view(['GET'])
def notification_counts(request):
    """Get counts of read and unread notifications"""
    unread_count = AdminNotification.objects.filter(is_read=False).count()
    read_count = AdminNotification.objects.filter(is_read=True).count()
    
    return Response({
        'unread_count': unread_count,
        'read_count': read_count,
        'total_count': unread_count + read_count
    })

def admin_notifications_template(request):
    """Render the admin notifications template"""
    return render(request, 'communications/admin_notifications.html')

# views.py
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from django.shortcuts import render
from datetime import datetime
from .models import AdminNotification
from .serializers import AdminNotificationSerializer, ProjectSerializer, EvaluatorSerializer
from projects.models import Project
from users.models import Evaluator

class NotificationPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class AdminNotificationListView(generics.ListAPIView):
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

class AdminNotificationDetailView(generics.RetrieveUpdateAPIView):
    queryset = AdminNotification.objects.all()
    serializer_class = AdminNotificationSerializer
    
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Update the notification
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        # If marking as read, set read_at timestamp
        if 'is_read' in request.data and request.data['is_read']:
            from django.utils import timezone
            instance.read_at = timezone.now()
        
        self.perform_update(serializer)
        
        return Response(serializer.data)

class ProjectListView(generics.ListAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer

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
    return render(request, 'admin_notifications.html')

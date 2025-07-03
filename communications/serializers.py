from rest_framework import serializers
from .models import AdminNotification
from projects.models import Project
from users.models import Evaluator

class AdminNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminNotification
        fields = ['id', 'title', 'notification_type', 'priority', 'from_email', 'created_at', 'message', 'project', 'project_id', 'is_read']

class ProjectSerializer(serializers.ModelSerializer):
    student_roll = serializers.CharField(source='student.student_id')
    department = serializers.CharField(source='student.course.department.name')
    assigned_foreign_evaluator = serializers.CharField(source='assigned_foreign_evaluator.email',default='Not Assigned') # what is the evaluator stil not assigned?
    assigned_indian_evaluator = serializers.CharField(source='assigned_indian_evaluator.email',default='Not Assigned')
    class Meta:
        model = Project
        fields = ['id', 'title','student_roll','department','assigned_foreign_evaluator','assigned_indian_evaluator','created_at','referel_id']

class EvaluatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evaluator
        fields = '__all__'


class ProjectFullSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = '__all__'
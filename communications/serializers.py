from rest_framework import serializers
from .models import AdminNotification
from projects.models import Project,VersionedProjectEvaluatorPool
from users.models import Evaluator
from communications.utils import send_evaluator_approach_email,send_thesis_submission_email

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
        
        

class EvaluatorMailListSerializer(serializers.ModelSerializer):
    evaluator_email = serializers.CharField(source='evaluator.email')
    evaluator_type = serializers.CharField(source='evaluator.evaluator_type')
    project_code = serializers.CharField(source='project.referel_id', read_only=True)
    student_id = serializers.CharField(source='project.student.student_id', read_only=True)

    class Meta:
        model = VersionedProjectEvaluatorPool
        fields = [
            'id',
            'evaluator_email',
            'evaluator_type',
            'project_code',
            'student_id',
            'priority_order',
            'next_approach_email_date',
            'next_evaluation_email_date',
            'approach_mail_count',
            'report_mail_count',
        ]


class EvaluatorDetailSerializer(serializers.ModelSerializer):
    evaluator_email = serializers.CharField(source='evaluator.email')
    project_code = serializers.CharField(source='project.referel_id')
    student_id = serializers.CharField(source='project.student.student_id')
    evaluator_type = serializers.CharField(source='evaluator.evaluator_type')
    email_content = serializers.SerializerMethodField()
    

    class Meta:
        model = VersionedProjectEvaluatorPool
        fields = [
            'id',
            'evaluator_email',
            'evaluator_type',
            'project_code',
            'student_id',
            'priority_order',
            'next_approach_email_date',
            'next_evaluation_email_date',
            'approach_mail_count',
            'report_mail_count',
            'email_content'
        ]

    def get_email_content(self, obj):
        mail_type = self.context.get('mail_type', 'approach')
        
        return send_evaluator_approach_email(obj.project, obj) if mail_type == 'approach' else send_thesis_submission_email(obj.project, obj)
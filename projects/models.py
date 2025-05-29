from django.db import models
from users.models import *
import uuid
# Create your models here.

class Project(models.Model):
    """PhD projects and their lifecycle"""
    STATUS_CHOICES = [
        ('SYNOPSIS_SUBMITTED', 'Synopsis Submitted'),
        ('SYNOPSIS_APPROVED', 'Synopsis Approved by Guide'),
        ('ADMIN_NOTIFIED', 'Admin Notified'),
        ('EVALUATORS_ASSIGNED', 'Evaluators Pool Assigned'),
        ('EVALUATOR_SELECTION', 'Evaluator Selection in Progress'),
        ('EVALUATOR_CONFIRMED', 'Evaluator Confirmed'),
        ('PROJECT_DEVELOPMENT', 'Project Development Phase'),
        ('PROJECT_SUBMITTED', 'Project Submitted'),
        ('UNDER_EVALUATION', 'Under Evaluation'),
        ('EVALUATION_COMPLETED', 'Evaluation Completed'),
        ('VIVA_READY', 'Ready for Viva'),
        ('VIVA_SCHEDULED', 'Viva Scheduled'),
        ('VIVA_COMPLETED', 'Viva Completed'),
        ('PAYMENT_PENDING', 'Payment to Evaluator Pending'),
        ('COMPLETED', 'Project Completed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.OneToOneField(PhDStudent, on_delete=models.CASCADE)
    title = models.CharField(max_length=500)
    guide_comments = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='SYNOPSIS_SUBMITTED')
    
    # Evaluator assignment
    assigned_foreign_evaluator = models.ForeignKey(
        Evaluator, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='foreign_evaluator'
    )
    assigned_indian_evaluator = models.ForeignKey(
        Evaluator, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='indian_evaluator'
    )
    
    # Evaluation
    evaluation_feedback = models.TextField(blank=True)
    evaluation_completed_date = models.DateTimeField(null=True, blank=True)
    
    # Viva
    viva_date = models.DateTimeField(null=True, blank=True)
    viva_venue = models.CharField(max_length=200, blank=True)
    viva_result = models.CharField(max_length=100, blank=True)
    
    # Payment tracking
    f_evaluator_payment_amount = models.DecimalField(max_digits=10, decimal_places=2, default=150)
    f_payment_completed_date = models.DateTimeField(null=True, blank=True)
    f_payment_reference = models.CharField(max_length=100, blank=True)
    i_evaluator_payment_amount = models.DecimalField(max_digits=10, decimal_places=2, default=900)
    i_payment_completed_date = models.DateTimeField(null=True, blank=True)
    i_payment_reference = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    referel_id = models.CharField(max_length=20, blank=True,editable=False)
    
    def get_evaluators(self):
        # Get evaluators, marking whether they are assigned (selected) or from pool (unselected)
        foreign_evaluator = self.assigned_foreign_evaluator or ProjectEvaluatorPool.objects.filter(
            project=self, 
            evaluator__evaluator_type='FOREIGN',
            retry_count__lt=3
        ).order_by('-priority_order').first()
        indian_evaluator = self.assigned_indian_evaluator or ProjectEvaluatorPool.objects.filter(
            project=self, 
            evaluator__evaluator_type='INDIAN',
            retry_count__lt=3
        ).order_by('-priority_order').first()
        
        return [
            {
                'evaluator': foreign_evaluator,
                'is_selected': bool(self.assigned_foreign_evaluator)
            },
            {
                'evaluator': indian_evaluator,
                'is_selected': bool(self.assigned_indian_evaluator)
            }
        ]
    
    def generate_referel_id(self):
        student_code = ''.join(filter(str.isalpha, self.student.name[:2].upper())) if self.student and hasattr(self.student, 'name') else "ST"
        guide_code = ''.join(filter(str.isalpha, self.student.guide.user.get_full_name()[:1].upper())) if self.student.guide and hasattr(self.student.guide.user, 'name') else "G"
        alpha_part = (student_code + guide_code).ljust(3, 'X')  # Ensure 3-letter code

        # Convert UUID to integer for consistent hashing
        id_int = int(self.id.hex, 16) if self.id else 0
        hash_part = str(id_int % 10000).zfill(6)
        return f"{alpha_part}-{hash_part}"
    
    def save(self, *args, **kwargs):
        if not self.id:
            self.referel_id = self.generate_referel_id()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.student.student_id} - {self.title[:50]}..."

class ProjectStatusHistory(models.Model):
    """Track project status changes for audit trail"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='status_history')
    previous_status = models.CharField(max_length=30, blank=True)
    new_status = models.CharField(max_length=30)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    change_reason = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-changed_at']
        verbose_name_plural = "Project status histories"
    
    def __str__(self):
        return f"{self.project.student.student_id}: {self.previous_status} -> {self.new_status}"




class ProjectEvaluatorPool(models.Model):
    """Pool of 10 evaluators assigned to each project (5 foreign + 5 indian)"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='evaluator_pool')
    evaluator = models.ForeignKey(Evaluator, on_delete=models.CASCADE)
    assigned_date = models.DateTimeField(auto_now_add=True)
    priority_order = models.IntegerField(help_text="1-5 for each type (foreign/indian) & Higher score = higher priority")
    retry_count = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['project', 'evaluator']
        ordering = ['evaluator__evaluator_type', 'priority_order']
    
    
    def send_approach_email(self):
        """
        Send approach email to the evaluator using the Approach template
        Returns the result of the email sending attempt
        """
        from communications.utils import send_evaluator_approach_email
        return send_evaluator_approach_email(self.project, self)
    
    def __str__(self):
        return f"{self.project.student.student_id} - {self.evaluator.name} (Priority: {self.priority_order})"


class WebhookLog(models.Model):
    """Log webhook requests from Google Forms"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    file_type = models.CharField(max_length=20, choices=[('SYNOPSIS', 'Synopsis'), ('PROJECT', 'Project')])
    file_id = models.CharField(max_length=200, help_text="Google Drive file ID")
    raw_payload = models.JSONField()
    guide_approval_date = models.DateTimeField(null=True, blank=True)
    processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Webhook - {self.student_email} - {self.file_name}"

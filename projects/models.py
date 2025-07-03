from django.db import models
from users.models import *
import uuid
# Create your models here.

class Project(models.Model):
    """PhD projects and their lifecycle"""
    STATUS_CHOICES = [
        ('CREATED','project created'),
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
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='CREATED')
    
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
    referel_id = models.CharField(max_length=20, blank=True)
    
    
    def get_assigned_evaluators(self):
        return [self.assigned_foreign_evaluator, self.assigned_indian_evaluator]
    
    def get_calender_evaluators(self):
        foreign = self.evaluator_pool.filter(evaluator__evaluator_type='FOREIGN', retry_count__lt=3).order_by('-priority_order').first()
        indian = self.evaluator_pool.filter(evaluator__evaluator_type='INDIAN', retry_count__lt=3).order_by('-priority_order').first()
        return [foreign, indian]    
            
    
    
    def get_evaluators(self):   
        # Get evaluators, marking whether they are assigned (selected) or from pool (unselected)
        f_mail_send = False
        i_mail_send = False
        foreign_evaluator = ProjectEvaluatorPool.objects.filter(
            project=self, 
            evaluator__evaluator_type='FOREIGN',
            retry_count__lt=3
        ).order_by('-priority_order').first()
        if isinstance(foreign_evaluator, ProjectEvaluatorPool):
            if foreign_evaluator.last_email_date is None:
                f_mail_send = True  # No email has ever been sent
            else:
                f_mail_send = (timezone.now() - foreign_evaluator.last_email_date) > timedelta(days=15)
        indian_evaluator = ProjectEvaluatorPool.objects.filter(
            project=self, 
            evaluator__evaluator_type='INDIAN',
            retry_count__lt=3,
        ).order_by('-priority_order').first()
        if isinstance(indian_evaluator, ProjectEvaluatorPool):
            if indian_evaluator.last_email_date is None:
                i_mail_send = True  # No email has ever been sent
            else:
                i_mail_send = (timezone.now() - indian_evaluator.last_email_date) > timedelta(days=15)
        return [
            {
                'evaluator': foreign_evaluator,
                'send_mail': f_mail_send 
            },
            {
                'evaluator': indian_evaluator,
                'send_mail': i_mail_send 
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
        if not self.referel_id:  # Changed to check for None or empty string
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
    report_retry_count = models.IntegerField(default=0, help_text="Retry count for project submission emails")
    last_email_date = models.DateTimeField(null=True, blank=True)
    report_last_email_date = models.DateTimeField(null=True, blank=True)
    next_email_date = models.DateTimeField(null=True, blank=True)
    report_next_email_date = models.DateTimeField(null=True, blank=True)
    
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
    
    def update_next_email_date(self):
        self.next_email_date = timezone.now() + timezone.timedelta(days=15)
        self.save()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Auto-unassign evaluator after 3 report retries
        if getattr(self, "report_retry_count", 0) >= 3:
            project = self.project
            if self.evaluator.evaluator_type == "FOREIGN":
                project.assigned_foreign_evaluator = None
            else:
                project.assigned_indian_evaluator = None
            project.save()
    
    def __str__(self):
        return f"{self.project.student.student_id} - {self.evaluator
    .name} (Priority: {self.priority_order})"


class WebhookLog(models.Model):
    """Log webhook requests from Google Forms"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    file_type = models.CharField(max_length=20, choices=[('SYNOPSIS', 'Synopsis'), ('PROJECT', 'Project')])
    file_id = models.CharField(max_length=200, help_text="Google Drive file ID")
    raw_payload = models.JSONField()
    guide_approval_date = models.DateTimeField(null=True, blank=True)
    processed = models.BooleanField(default=False)
    """
    processing error fields maintain that the evaluator or the guide has not approved the project
    use the text field to hold a json like object:
    {
        processed_by: "EVALUATOR" or "GUIDE"
        correction_file_id: "Google Drive file ID"
    }may be best if added those fields... i think not neccessary ofcourse we can make the admin to it..
    
    add a email communication to student if evaluator or guide has not approved the project - create a new template for it.
    """
    
    processing_error = models.TextField(blank=True) 
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.project.student.student_id} - {self.file_type}"
    

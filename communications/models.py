from django.db import models
import uuid
from projects.models import Project
from users.models import Evaluator
from django.contrib.auth.models import User

# Create your models here.
class EmailCommunication(models.Model):
    """Track all email communications with evaluators"""
    EMAIL_TYPE_CHOICES = [
        ('INVITATION', 'Evaluation Invitation'),
        ('REMINDER', 'Reminder'),
        ('PROJECT_SUBMISSION', 'Project Submission for Review'),
        ('FOLLOW_UP', 'Follow-up'),
        ('ACCEPTANCE', 'Acceptance Confirmation'),
        ('REJECTION', 'Rejection Notification'),
        ('EVALUATION_REQUEST', 'Evaluation Request'),
    ]
    
    STATUS_CHOICES = [
        ('SENT', 'Sent'),
        ('DELIVERED', 'Delivered'),
        ('OPENED', 'Opened'),
        ('REPLIED', 'Replied'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected'),
        ('BOUNCED', 'Bounced'),
        ('FAILED', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='emails')
    evaluator = models.ForeignKey(Evaluator, on_delete=models.CASCADE)
    email_type = models.CharField(max_length=20, choices=EMAIL_TYPE_CHOICES)
    subject = models.CharField(max_length=300)
    body = models.TextField()
    sent_date = models.DateTimeField() # fetch by if date not set to send these type of mails as considering it was waiting to send
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SENT')
    attempt_number = models.IntegerField(default=1, help_text="1st, 2nd, or 3rd attempt")
    response_date = models.DateTimeField(null=True, blank=True)
    response_content = models.TextField(blank=True)
    message_id = models.CharField(max_length=200, blank=True, help_text="Message Subject id we use to track the email")
    
    # Attachments tracking
    attachments_sent = models.JSONField(default=list, help_text="List of attachment file names")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-sent_date']
    
    def __str__(self):
        return f"{self.project.student.student_id} -> {self.evaluator.name} ({self.email_type})"


class AdminNotification(models.Model):
    """System notifications for admin dashboard"""
    NOTIFICATION_TYPE_CHOICES = [
        ('SYNOPSIS_APPROVAL', 'Synopsis Needs Approval'),
        ('EVALUATOR_ASSIGNMENT', 'Evaluator Assignment Required'),
        ('EVALUATOR_CONFIRMED', 'Evaluator Confirmed'),
        ('PROJECT_SUBMITTED', 'Project Submitted for Evaluation'),
        ('EVALUATION_COMPLETED', 'Evaluation Completed'),
        ('VIVA_READY', 'Project Ready for Viva'),
        ('PAYMENT_REQUIRED', 'Payment to Evaluator Required'),
        ('PROJECT_COMPLETED', 'Project Completed'),
        ('EMAIL_FAILED', 'Email Communication Failed'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.notification_type} - {self.project.student.student_id}"



# Additional utility models for system configuration
class SystemConfiguration(models.Model):
    """System-wide configuration settings"""
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.key}: {self.value[:50]}..."


class EmailTemplate(models.Model):
    """Email templates for different communication types"""
    name = models.CharField(max_length=100, unique=True)
    subject_template = models.CharField(max_length=300)
    body_template = models.TextField()
    variables_help = models.TextField(help_text="Available template variables")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

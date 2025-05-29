from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager, Group, Permission
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import uuid


class UserManager(BaseUserManager):
    """Define a model manager for User model with no username field."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """Create and save a User with the given email and password."""
        if not email:
            raise ValueError('The given email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular User with the given email and password."""
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        """Create and save a SuperUser with the given email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', User.Role.ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom user model with email as unique identifier and role-based access."""
    
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', _('Admin')
        HOD = 'HOD', _('Head of Department')
        GUIDE = 'GUIDE', _('Guide')
        STUDENT = 'STUDENT', _('Student')
    
    username = None
    email = models.EmailField(_('email address'), unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)
    phone = models.CharField(max_length=20, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    objects = UserManager()
    
    def __str__(self):
        return self.email
    
    @property
    def is_hod(self):
        return self.role == self.Role.HOD
    
    @property
    def is_guide(self):
        return self.role == self.Role.GUIDE
    
    @property
    def is_student(self):
        return self.role == self.Role.STUDENT
    
    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN or self.is_superuser


class Department(models.Model):
    """Academic departments offering PhD programs"""
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=10, unique=True)
    head_of_department = models.CharField(max_length=200)
    contact_email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class Course(models.Model):
    """PhD course structure"""
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    total_semesters = models.IntegerField(default=8)
    min_project_semester = models.IntegerField(default=4, help_text="Minimum semester to submit project synopsis")
    fee_per_semester = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} - {self.department.name}"


class Guide(models.Model):
    """Faculty members who can guide PhD students"""
    is_hod = models.BooleanField(default=False)
    email = models.EmailField(unique=True)
    employee_id = models.CharField(max_length=50, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    designation = models.CharField(max_length=100)
    specialization = models.TextField()
    phone = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    max_students = models.IntegerField(default=5, help_text="Maximum students this guide can handle")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.email} - {self.department.code}"
    
    @property
    def current_student_count(self):
        return self.phdstudent_set.filter(status__in=['ENROLLED', 'PROJECT_PHASE']).count()


class PhDStudent(models.Model):
    """PhD students in the system"""
    STATUS_CHOICES = [
        ('ENROLLED', 'Enrolled'),
        ('PROJECT_PHASE', 'Project Phase'),
        ('SYNOPSIS_SUBMITTED', 'Synopsis Submitted'),
        ('EVALUATOR_ASSIGNED', 'Evaluator Assigned'),
        ('PROJECT_SUBMITTED', 'Project Submitted'),
        ('UNDER_EVALUATION', 'Under Evaluation'),
        ('VIVA_READY', 'Ready for Viva'),
        ('VIVA_COMPLETED', 'Viva Completed'),
        ('COMPLETED', 'Completed'),
        ('DISCONTINUED', 'Discontinued'),
    ]
    
    student_id = models.CharField(max_length=50, unique=True)
    email = models.EmailField(unique=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    guide = models.ForeignKey(Guide, on_delete=models.SET_NULL, null=True, blank=True)
    enrollment_date = models.DateField()
    current_semester = models.IntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(12)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ENROLLED')
    phone = models.CharField(max_length=20)
    address = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.student_id} - {self.email}"
    
    @property
    def can_submit_synopsis(self):
        return self.current_semester >= self.course.min_project_semester


class SemesterFee(models.Model):
    """Semester-wise fee records for students"""
    PAYMENT_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('WAIVED', 'Waived'),
    ]
    
    student = models.ForeignKey(PhDStudent, on_delete=models.CASCADE)
    semester = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PENDING')
    payment_date = models.DateField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['student', 'semester']
    
    def __str__(self):
        return f"{self.student.student_id} - Semester {self.semester} - {self.payment_status}"


class Evaluator(models.Model):
    """Pool of evaluators for PhD projects"""
    EVALUATOR_TYPE_CHOICES = [
        ('FOREIGN', 'Foreign Evaluator'),
        ('INDIAN', 'Indian Evaluator'),
    ]
    
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    institution = models.CharField(max_length=300)
    designation = models.CharField(max_length=100)
    specialization = models.TextField()
    country = models.CharField(max_length=100)
    evaluator_type = models.CharField(max_length=10, choices=EVALUATOR_TYPE_CHOICES)
    is_active = models.BooleanField(default=True)
    priority_score = models.IntegerField(default=1, help_text="Higher score = higher priority")
    total_evaluations = models.IntegerField(default=0)
    average_response_time_days = models.IntegerField(default=7)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} - {self.institution} ({self.evaluator_type})"

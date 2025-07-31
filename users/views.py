from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, ListView, DetailView, UpdateView, CreateView, DeleteView
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.template.loader import render_to_string
from django.db.models import Q

# API ViewSets for SPA
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Course
from .serializers import CourseSerializer, GuideSerializer, PhDStudentSerializer, DepartmentSerializer

from .models import User, Course, Guide, PhDStudent,Department

# Manage Users (Admin) with DataTables filtering by user type
from django.contrib.auth.decorators import user_passes_test

def admin_required(view_func):
    decorated_view_func = login_required(user_passes_test(lambda u: u.is_admin)(view_func))
    return decorated_view_func

@admin_required
def manage_users(request):
    users = User.objects.all()
    return render(request, 'admin_manage_users.html', {'users': users})

# SPA entrypoint for AngularJS onboarding
from django.contrib.auth.decorators import login_required

@login_required
def onboarding_spa(request):
    return render(request, 'spa_base.html')

# Dummy views for sidebar URLs
@login_required
def department_dashboard(request):
    return HttpResponse('<h1>Department Dashboard - To be implemented</h1>')

@login_required
def manage_guides(request):
    return HttpResponse('<h1>Manage Guides - To be implemented</h1>')

@login_required
def student_approvals(request):
    return HttpResponse('<h1>Student Approvals - To be implemented</h1>')

@login_required
def department_reports(request):
    return HttpResponse('<h1>Department Reports - To be implemented</h1>')

@login_required
def my_students(request):
    return HttpResponse('<h1>My Students - To be implemented</h1>')

@login_required
def project_management(request):
    return HttpResponse('<h1>Project Management - To be implemented</h1>')

@login_required
def my_progress(request):
    return HttpResponse('<h1>My Progress - To be implemented</h1>')


class DashboardView(LoginRequiredMixin, TemplateView):
    """Main dashboard view that shows different content based on user role"""
    template_name = 'dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Add user-specific data to the context
        context['user'] = user
        
        if user.is_admin:
            # Admin dashboard data
            context['total_users'] = User.objects.count()
            context['total_students'] = PhDStudent.objects.count()
            context['total_guides'] = Guide.objects.count()
            
        elif user.is_hod:
            # HOD dashboard data
            guide = Guide.objects.filter(email=user.email).first()
            department = guide.department if guide else None
            context['department'] = department
            context['department_students'] = PhDStudent.objects.filter(
                course__department=department
            ).count() if department else 0
            context['department_guides'] = Guide.objects.filter(
                department=department
            ).count() if department else 0
            
        elif user.is_guide:
            # Guide dashboard data
            guide = Guide.objects.filter(email=user.email).first()
            context['guide'] = guide
            context['current_students'] = guide.phdstudent_set.count() if guide else 0
            context['max_students'] = guide.max_students if guide else 0
            
        elif user.is_student:
            # Student dashboard data
            student = PhDStudent.objects.filter(email=user.email).first()
            context['student'] = student
            context['guide'] = student.guide if student else None
            
        return context


class ProfileView(LoginRequiredMixin, UpdateView):
    """User profile view for updating personal information"""
    model = User
    fields = ['first_name', 'last_name', 'email', 'phone', 'profile_picture']
    template_name = 'profile.html'
    success_url = reverse_lazy('users:profile')
    
    def get_object(self, queryset=None):
        return self.request.user
    
    def form_valid(self, form):
        messages.success(self.request, _('Your profile has been updated successfully!'))
        return super().form_valid(form)


@login_required
def switch_theme(request):
    """Toggle between light and dark theme"""
    if 'dark_mode' in request.session:
        del request.session['dark_mode']
    else:
        request.session['dark_mode'] = True
    return redirect(request.META.get('HTTP_REFERER', 'users:dashboard'))

# DRF ViewSets for SPA
class CourseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = CourseSerializer
    def get_queryset(self):
        qs = Course.objects.all()
        user = self.request.user
        if user.is_admin:
            department = self.request.query_params.get('department')
            
            return qs.filter(department=department) if department else qs
        
        if user.is_hod:
            guide = Guide.objects.filter(email=user.email).first()
            dept = guide.department if guide else None
            return qs.filter(department=dept)
        return qs

class GuideViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = GuideSerializer
    def get_queryset(self):
        qs = Guide.objects.all()
        user = self.request.user
        if user.is_admin:
            department = self.request.query_params.get('department')
            
            return qs.filter(department=department) if department else qs
        
        if user.is_hod:
            guide = Guide.objects.filter(email=user.email).first()
            return qs.filter(department=guide.department) if guide else qs.none()
        return qs

class PhDStudentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = PhDStudentSerializer
    def get_queryset(self):
        qs = PhDStudent.objects.all()
        user = self.request.user
        if user.is_admin:
            department = self.request.query_params.get('department')
            
            return qs.filter(course__department__id=department) if department else qs
        
        if user.is_hod:
            guide = Guide.objects.filter(email=user.email).first()
            dept = guide.department if guide else None
            return qs.filter(course__department=dept)
        elif user.is_guide:
            return qs.filter(guide__email=user.email)
        return qs
    

class DepartmentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = DepartmentSerializer
    def get_queryset(self):
        qs = Department.objects.all()
        user = self.request.user
        if user.is_admin:
            department = self.request.query_params.get('department')
            
            return qs.filter(id=department) if department else qs
        
        if user.is_hod:
            guide = Guide.objects.filter(email=user.email).first()
            return qs.filter(id=guide.department.id) if guide else qs.none()
        return qs
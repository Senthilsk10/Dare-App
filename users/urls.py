from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'users'

urlpatterns = [
    # Authentication
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('password_change/', auth_views.PasswordChangeView.as_view(template_name='registration/password_change.html'), 
         name='password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='registration/password_change_done.html'), 
         name='password_change_done'),
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='registration/password_reset_form.html'), 
         name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), 
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'), 
         name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), 
         name='password_reset_complete'),
    
    # SPA onboarding entrypoint
    path('onboarding/', views.onboarding_spa, name='onboarding_spa'),

    # Dashboard
    path('', views.DashboardView.as_view(), name='dashboard'),
    
    # Profile
    path('profile/', views.ProfileView.as_view(), name='profile'),
    
    # Theme
    path('theme/switch/', views.switch_theme, name='switch_theme'),

    # Admin management URLs
    path('manage-users/', views.manage_users, name='manage_users'),

    # Dummy sidebar URLs
    path('department-dashboard/', views.department_dashboard, name='department_dashboard'),
    path('manage-guides/', views.manage_guides, name='manage_guides'),
    path('student-approvals/', views.student_approvals, name='student_approvals'),
    path('department-reports/', views.department_reports, name='department_reports'),
    path('my-students/', views.my_students, name='my_students'),
    path('project-management/', views.project_management, name='project_management'),
    path('my-progress/', views.my_progress, name='my_progress'),
]

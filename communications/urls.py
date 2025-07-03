from django.urls import path
from django.views.decorators.http import require_http_methods
from . import admin_notification_views as notify_views
from . import views

app_name = 'communications'

urlpatterns = [
    path('google/', views.initiate_google_auth, name='initiate_google_auth'),
    path('authcallback', views.google_oauth_callback, name='google_oauth_callback'),
    path('send-sample-email/', views.send_email_view, name='send_sample_email'),
    path('awaiting-mails/', views.awaiting_emails, name='awaiting_mails'),
    path('awaiting-project-emails/', views.awaiting_project_emails, name='awaiting_project_emails'),
    path('send-email/', views.send_email, name='send_email'),
    path('send-project-email/', views.send_project_email, name='send_project_email'),
    # API endpoints
    path('notifications/', notify_views.admin_notifications_template, name='admin_notifications'),
    path('api/admin-notifications/', notify_views.AdminNotificationListView.as_view(), name='api_admin_notifications'),
    path('api/admin-notifications/<int:pk>/', notify_views.admin_notification_detail, name='api_admin_notification_detail'),
    path('api/admin-notifications/counts/', notify_views.notification_counts, name='api_notification_counts'),
    path('api/projects/', notify_views.ProjectListView.as_view(), name='api_projects'),
    path('api/evaluators/', notify_views.EvaluatorListView.as_view(), name='api_evaluators'),
]
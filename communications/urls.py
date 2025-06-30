from django.urls import path
from . import views

app_name = 'communications'

urlpatterns = [
    path('google/', views.initiate_google_auth, name='initiate_google_auth'),
    path('authcallback', views.google_oauth_callback, name='google_oauth_callback'),
    path('send-sample-email/', views.send_email_view, name='send_sample_email'),
    path('awaiting-mails/', views.awaiting_emails_v2, name='awaiting_mails'),
    path('send-email/', views.send_email, name='send_email'),
    # path('send-email/<int:evaluator_pool_id>/', views.send_approach_email, name='send_approach_email'),
]
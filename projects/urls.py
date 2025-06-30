from django.urls import path
from . import views

app_name = 'projects'

urlpatterns = [
    path('my-projects/', views.my_projects, name='my_projects'),
    path('create_project/', views.create_project, name='create_project'),
    path('project_detail/<str:project_id>/', views.project_detail, name='project_detail'),
    path('synopsis-webhook/', views.synopsis_webhook, name='synopsis_webhook'),
    path('project-webhook/', views.project_webhook, name='project_webhook'),
]

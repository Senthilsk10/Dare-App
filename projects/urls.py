from django.urls import path
from . import views

app_name = 'projects'

urlpatterns = [
    path('my-projects/', views.my_projects, name='my_projects'),
]

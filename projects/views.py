from django.shortcuts import render
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required

@login_required
def my_projects(request):
    return HttpResponse('<h1>My Projects - To be implemented</h1>')

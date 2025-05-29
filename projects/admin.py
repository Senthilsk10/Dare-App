from django.contrib import admin
from .models import *
admin.site.register(Project)
admin.site.register(ProjectStatusHistory)
admin.site.register(ProjectEvaluatorPool)
admin.site.register(WebhookLog)
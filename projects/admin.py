from django.contrib import admin
from django.contrib.admin import ModelAdmin
from users.models import Evaluator
from .models import *
admin.site.register(ProjectStatusHistory)
admin.site.register(WebhookLog)


class ProjectEvaluatorPoolInline(admin.TabularInline):
    model = ProjectEvaluatorPool
    fields = ['evaluator', 'priority_order']
    extra = 1  # How many blank rows to show
    autocomplete_fields = ['evaluator']  # enables search + "add in place"
    
    
class ProjectAdmin(admin.ModelAdmin):
    inlines = [ProjectEvaluatorPoolInline]
    
    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        if 'student' in request.GET:
            initial['student'] = request.GET['student']
        return initial


admin.site.register(Project, ProjectAdmin)
# admin.site.register(ProjectEvaluatorPool)  # Optional: if you want to manage pools separately

# Ensure this exists
@admin.register(Evaluator)
class EvaluatorAdmin(admin.ModelAdmin):
    search_fields = ['name', 'email']  # whatever helps uniquely find them
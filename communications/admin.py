from django.contrib import admin
from .models import EmailCommunication, EmailTemplate

admin.site.register(EmailCommunication)
admin.site.register(EmailTemplate)

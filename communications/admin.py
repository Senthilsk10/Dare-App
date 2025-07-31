from django.contrib import admin
from .models import EmailCommunication, EmailTemplate, AdminNotification, SystemConfiguration

admin.site.register(EmailCommunication)
admin.site.register(EmailTemplate)
admin.site.register(AdminNotification)
admin.site.register(SystemConfiguration)

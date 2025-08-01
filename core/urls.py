"""
URL configuration for core project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from rest_framework import routers
from users.views import CourseViewSet, GuideViewSet, PhDStudentViewSet, DepartmentViewSet

router = routers.DefaultRouter()
router.register(r'students', PhDStudentViewSet, basename='students')
router.register(r'guides', GuideViewSet, basename='guides')
router.register(r'courses', CourseViewSet, basename='courses')
router.register(r'departments', DepartmentViewSet, basename='departments')

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Authentication
    path('accounts/', include('django.contrib.auth.urls')),
    
    # Users app
    path('', include('users.urls', namespace='users')),
    path('', include('projects.urls', namespace='projects')),   
    path('', include('communications.urls')),
    # Redirect root to dashboard
    path('', RedirectView.as_view(pattern_name='users:dashboard', permanent=False)),
    path('api/', include(router.urls)),
]

# Serve media and static files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # Debug toolbar
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass

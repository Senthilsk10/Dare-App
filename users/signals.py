from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from .models import User, Guide, PhDStudent


@receiver(post_save, sender=Guide)
def set_guide_role(sender, instance, created, **kwargs):
    """
    Set the user role to GUIDE when a Guide profile is created.
    If the Guide is marked as HOD, update their role to HOD.
    """
    if created:
        user = instance.user
        if instance.is_hod:
            user.role = User.Role.HOD
        else:
            user.role = User.Role.GUIDE
        user.save(update_fields=['role'])


@receiver(post_save, sender=PhDStudent)
def set_student_role(sender, instance, created, **kwargs):
    """
    Set the user role to STUDENT when a PhDStudent profile is created.
    """
    if created:
        user = instance.user
        user.role = User.Role.STUDENT
        user.save(update_fields=['role'])


@receiver(pre_save, sender=Guide)
def update_hod_status(sender, instance, **kwargs):
    """
    Handle HOD status changes and ensure only one HOD per department.
    """
    if instance.pk:  # Only for existing instances
        try:
            old_instance = Guide.objects.get(pk=instance.pk)
            # If this guide is being marked as HOD
            if instance.is_hod and not old_instance.is_hod:
                # Remove HOD status from other guides in the same department
                Guide.objects.filter(
                    department=instance.department,
                    is_hod=True
                ).exclude(pk=instance.pk).update(is_hod=False)
                # Update user role to HOD
                instance.user.role = User.Role.HOD
                instance.user.save(update_fields=['role'])
            # If HOD status is being removed
            elif not instance.is_hod and old_instance.is_hod:
                # Set role back to GUIDE
                instance.user.role = User.Role.GUIDE
                instance.user.save(update_fields=['role'])
        except Guide.DoesNotExist:
            pass  # New instance, nothing to do


def create_default_groups_and_permissions(sender, **kwargs):
    """
    Create default groups and assign permissions when the app is ready.
    This should be connected to the post_migrate signal.
    """
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType
    
    # Get or create groups
    admin_group, _ = Group.objects.get_or_create(name='Admin')
    hod_group, _ = Group.objects.get_or_create(name='HOD')
    guide_group, _ = Group.objects.get_or_create(name='Guide')
    student_group, _ = Group.objects.get_or_create(name='Student')
    
    # Get all permissions
    content_types = ContentType.objects.all()
    permissions = Permission.objects.filter(content_type__in=content_types)
    
    # Assign all permissions to admin group
    admin_group.permissions.set(permissions)
    
    # Assign permissions to HOD group (customize as needed)
    hod_permissions = permissions.filter(
        codename__in=[
            'view_phdstudent', 'change_phdstudent',
            'view_guide', 'change_guide',
            'view_department', 'change_department',
            'view_course', 'change_course',
        ]
    )
    hod_group.permissions.set(hod_permissions)
    
    # Assign permissions to Guide group
    guide_permissions = permissions.filter(
        codename__in=[
            'view_phdstudent', 'change_phdstudent',
            'view_guide', 'change_guide',
        ]
    )
    guide_group.permissions.set(guide_permissions)
    
    # Assign permissions to Student group
    student_permissions = permissions.filter(
        codename__in=[
            'view_phdstudent', 'change_phdstudent',
        ]
    )
    student_group.permissions.set(student_permissions)

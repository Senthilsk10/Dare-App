from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .models import PhDStudent, Guide, Department
import threading

User = get_user_model()

# ---------- STUDENT ----------
@receiver(post_save, sender=PhDStudent)
def sync_student_user(sender, instance, created, **kwargs):
    username = instance.mail
    password = str(instance.roll)

    if created:
        # Create user on student creation
        User.objects.create_user(
            username=username,
            password=password,
            role='student',
            first_name=instance.name
        )
    else:
        # Update user on student update
        try:
            user = User.objects.get(role='student', username=username)
            user.first_name = instance.name
            user.set_password(password)  # If roll number changes, update password
            user.save()
        except User.DoesNotExist:
            # In case user wasn't created before
            User.objects.create_user(
                username=username,
                password=password,
                role='STUDENT',
                first_name=instance.name
            )

@receiver(post_delete, sender=PhDStudent)
def delete_student_user(sender, instance, **kwargs):
    User.objects.filter(username=instance.mail, role='student').delete()


# ---------- GUIDE ----------
@receiver(post_save, sender=Guide)
def sync_guide_user(sender, instance, created, **kwargs):
    username = instance.email
    password = instance.phone

    def user_creation_task():
        # Create or update User for Guide in background
        try:
            user = User.objects.get(email=username)
            user.first_name = getattr(instance, 'name', user.first_name)
            user.set_password(password)
            user.role = User.Role.GUIDE
            user.save()
        except User.DoesNotExist:
            User.objects.create_user(
                email=username,
                password=password,
                role=User.Role.GUIDE,
                first_name=getattr(instance, 'name', '')
            )

    threading.Thread(target=user_creation_task).start()

    # --- HOD logic: Only one HOD per department ---
    if instance.is_hod:
        # Set all other guides in the department to is_hod=False
        Guide.objects.filter(department=instance.department, is_hod=True).exclude(pk=instance.pk).update(is_hod=False)
        # Optionally update Department.head_of_department field
        Department.objects.filter(pk=instance.department.pk).update(head_of_department=instance.email)


@receiver(post_delete, sender=Guide)
def delete_guide_user(sender, instance, **kwargs):
    User.objects.filter(username=instance.email, role='guide').delete()

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from users.models import Guide, PhDStudent

class Command(BaseCommand):
    help = 'Creates default groups and sets up permissions'

    def handle(self, *args, **options):
        # Create default groups
        guide_group, _ = Group.objects.get_or_create(name='Guide')
        student_group, _ = Group.objects.get_or_create(name='Student')
        hod_group, _ = Group.objects.get_or_create(name='HOD')
        
        self.stdout.write(self.style.SUCCESS('Successfully created default groups'))
        
        # Add HODs to HOD group
        hod_guides = Guide.objects.filter(is_hod=True)
        for guide in hod_guides:
            if guide.user:
                guide.user.groups.add(hod_group)
        
        self.stdout.write(self.style.SUCCESS('Updated HOD group members'))

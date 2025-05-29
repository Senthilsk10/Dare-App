from django.contrib.admin import site
from .models import PhDStudent,Guide,Department,Evaluator,User,Course,SemesterFee

site.register(Guide)
site.register(PhDStudent)
site.register(Department)
site.register(Evaluator) 
site.register(User)
site.register(Course)
site.register(SemesterFee)

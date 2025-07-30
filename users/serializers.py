from rest_framework import serializers
from .models import Course, Guide, PhDStudent, Department

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = '__all__'
class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = '__all__'

class GuideSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guide
        fields = '__all__'

class PhDStudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhDStudent
        fields = '__all__'

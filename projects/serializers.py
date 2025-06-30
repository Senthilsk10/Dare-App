from rest_framework import serializers

from .models import *
from users.models import Evaluator

class EvaluatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evaluator
        fields = '__all__'

class EvaluatorPoolSerializer(serializers.ModelSerializer):
    evaluator = EvaluatorSerializer()
    class Meta:
        model = ProjectEvaluatorPool
        fields = '__all__'



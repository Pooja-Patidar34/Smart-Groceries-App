from rest_framework import serializers
from .models import ExtractedIngredientsFromMail


class ExtractedIngredientsFromMailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtractedIngredientsFromMail
        fields = '__all__'


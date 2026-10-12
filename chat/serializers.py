from rest_framework import serializers
from .models import *


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = '__all__'




class SearchedMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'message', 'timestamp']  

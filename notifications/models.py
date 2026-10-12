from django.db import models
from accounts.models import User

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.CharField(max_length=255)
    type = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

class UserFCMToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="fcm_tokens")
    token = models.CharField(max_length=255, unique=True)  
    created_at = models.DateTimeField(auto_now_add=True)

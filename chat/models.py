from django.db import models
from accounts.models import User
from recipe_section.models import ListedMeal


class Chat(models.Model):
    meal = models.ForeignKey(ListedMeal, on_delete = models.CASCADE)
    seller_id = models.IntegerField(null = True, blank = True)
    buyer_id = models.IntegerField(null = True, blank = True)

class Message(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE)
    seller_id = models.IntegerField(null=True, blank=True)
    buyer_id = models.IntegerField(null=True, blank=True)
    message = models.TextField()
    message_type = models.CharField(max_length=20, choices=[
        ('text', 'Text'),
        ('file', 'File'),
        ('video', 'Video'),
        ('document', 'Document'),
        ('other', 'Other')
    ])
    read_status = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)



class ChatParticipants(models.Model):
    chat = models.ForeignKey(Chat,on_delete=models.CASCADE)
    user = models.ForeignKey(User,on_delete=models.CASCADE)
    left = models.DateTimeField() 
    role = models.CharField(max_length=30,null=True,blank=True)

    created_at =  models.DateTimeField(auto_now_add=True)
    updated_at =  models.DateTimeField(auto_now=True)

from django.db import models
from accounts.models import User




# Create your models here.
# class SupportTicket(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True)
#     issue_description = models.TextField()
#     status = models.CharField(max_length=20, choices=[('open', 'Open'), ('resolved', 'Resolved'), ('closed', 'Closed')])
#     created_at = models.DateTimeField(auto_now_add=True)
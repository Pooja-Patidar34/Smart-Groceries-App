from django.db import models
from transactions.models import Order
from accounts.models import User
from recipe_section.models import ListedMeal
class NewSubscription(models.Model):
    PLAN_CHOICES = [
        ('Trial', 'Trial'),
        ('Weekly', 'Weekly'),
        ('Monthly', 'Monthly'),
        ('Annually', 'Annually'),
    ]

    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=100, choices=PLAN_CHOICES)
    duration = models.IntegerField(help_text="Duration length (e.g., 7 days, 30 days)")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.duration} {self.plan_type}) - Rs.{self.price}"

          
class Refund(models.Model):
        STATUS_CHOICES=[
                ('pending','pending'),
                ('succeeded','succeeded'),
                ('failed','failed'),
        ]
        order=models.ForeignKey(Order,on_delete=models.CASCADE,related_name="refunds")
        requested_by=models.ForeignKey(User,on_delete=models.CASCADE,related_name='refund_requests')
        refund_id=models.CharField(max_length=255, null=True,blank=True)
        amount=models.DecimalField(max_digits=6, decimal_places=2)
        refund_charges=models.DecimalField(max_digits=6, decimal_places=2, default=0.0)
        reason=models.TextField(null=True, blank=True)
        status=models.CharField(max_length=255,choices=STATUS_CHOICES,default='pending')
        created_at=models.DateField(auto_now_add=True)
        processed_at=models.DateField(blank=True , null=True)


class Configure(models.Model):
    name = models.CharField(max_length=50,null=True,blank=True)
    value = models.DecimalField(max_digits=5, decimal_places=2, help_text="Commission %") 
    label = models.CharField(max_length=50)
    updated_at = models.DateTimeField(auto_now=True)
from django.db import models
from accounts.models import User
from recipe_section.models import ListedMeal

class Order(models.Model):
    orderid = models.CharField(max_length=100, unique=True)  
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders_made')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders_received')
    meal = models.ForeignKey(ListedMeal, on_delete=models.SET_NULL, null=True)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('completed', 'Completed'), ('disputed', 'Disputed')])
    payment_reference = models.CharField(max_length=255,null=True,blank=True)
    payment_intent_id = models.CharField(max_length=255,null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Payout(models.Model):
    payoutid = models.CharField(max_length=255, unique=True, null=True, blank=True)  # Stripe Payout ID
    transferid = models.CharField(max_length=255, null=True, blank=True)  # Stripe Transfer ID
    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    amount_received = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('on_hold', 'On Hold')
        ],
        default='pending'
    )
    
    payment_method = models.CharField(max_length=50, null=True, blank=True)
    payout_released_on = models.DateField(null=True, blank=True)
    payout_date = models.DateTimeField(null=True, blank=True)
    platform_commission = models.FloatField(default=0.0)
    failure_reason = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



class Dispute(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='dispute')
    raised_by = models.ForeignKey(User, on_delete=models.CASCADE)
    reason = models.TextField()
    send_amount_to = models.ForeignKey(User,on_delete = models.SET_NULL,null=True,blank=True,related_name='disputes_to_receive') 
    resolved = models.BooleanField(default=False)
    resolution_comment = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
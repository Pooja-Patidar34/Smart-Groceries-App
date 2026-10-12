
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
import pyotp
from datetime import timedelta
from django.utils import timezone
from django_ckeditor_5.fields import CKEditor5Field

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


    def __str__(self):
        return self.subscription_type + " "+ self.start_date


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, db_index=True)
    username = models.CharField(max_length=255)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_email_verified = models.BooleanField(default=False)
    gender = models.CharField(max_length=10,null=True,blank=True)
    contact = models.CharField(max_length=10,null=True,blank=True)
    measurement_type = models.CharField(max_length=50,null=True,blank=True)
    dob = models.DateField(null=True,blank=True)
    country = models.CharField(max_length=30,null=True,blank=True) 
    ip_address = models.GenericIPAddressField(null=True,blank=True)
    objects = CustomUserManager()
    connected_id = models.CharField(max_length=100,null=True,blank=True)
    capabilities_transfers = models.CharField(max_length=20,default="pending")
    kyc_status = models.CharField(max_length=40,null=True,blank=True)
    media_id = models.CharField(max_length=400,null=True,blank=True)
    last_logout = models.DateTimeField(null = True,blank = True)
    instacart_email = models.EmailField(unique=True,null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

class SubscriptionPlan(models.Model):
    # Choices for subscription type
    SUBSCRIPTION_CHOICES = [
        ('Trial', 'Trial'),
        ('Monthly', 'Monthly'),
        ('Annually', 'Annually'),
    ]

    # Choices for subscription status
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Expired', 'Expired'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    subscription_type = models.CharField(
        max_length=50,
        choices=SUBSCRIPTION_CHOICES
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.subscription_type}"



class UserOTP(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    otp = models.CharField(max_length=10)
    otp_secret = models.CharField(max_length=50)
    email = models.EmailField(null=True,blank=True)
    mobile = models.CharField(max_length=10,null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def is_valid(self):
        return timezone.now() <= self.created_at + timedelta(minutes=2)

    

class EatingStyle(models.Model):
    name = models.CharField(max_length=40,null = True,blank = True)


class EatingStyleData(models.Model):
    name = models.CharField(max_length=50)
    eatingstyle = models.ForeignKey(EatingStyle,on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)




class SubscriptionTransactions(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
    ]

    orderid = models.CharField(max_length=100, unique=True)  
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscription_activation_transactions')
    start_date = models.DateTimeField(null=True,blank=True)
    end_date = models.DateTimeField(null=True,blank=True)
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)  
    currency = models.CharField(max_length=10, null=True,blank=True)
    subscription_status = models.CharField(max_length=50,null=True,blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    subscription_type = models.CharField(max_length=50, choices=[
        ('Trial', 'Trial'),
        ('Monthly', 'Monthly'),
        ('Annually', 'Annually'),
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} | {self.orderid} | {self.status}"
    

class StaticData(models.Model):
    TYPE_CHOICES = [
        ('Terms and Conditions', 'Terms and Conditions'),
        ('Privacy', 'Privacy'),
        ('About_us', 'About Us'),
    ]
    CONTENT_TYPE_CHOICES = [
        ('text', 'Text'),
        ('number', 'Number'),
        ('ckeditor', 'CKEditor'),
    ]
    title = models.CharField(max_length=255,null=True,blank=True)
    type = models.CharField(max_length=50,choices=TYPE_CHOICES,help_text="Select the type of static content.")
    content_type=models.CharField(choices=CONTENT_TYPE_CHOICES, max_length=30,default="text")
    content = CKEditor5Field(config_name="default")
    is_active = models.BooleanField(default=True, help_text="Only one version should be active at a time.")
    created_at = models.DateTimeField(auto_now_add=True)


class UserTermsAcceptance(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="accepted_terms")
    static_data = models.ForeignKey(StaticData, on_delete=models.CASCADE)
    accepted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'static_data')
    
    def __str__(self):
        return f"{self.user} accepted on {self.accepted_at}"
    


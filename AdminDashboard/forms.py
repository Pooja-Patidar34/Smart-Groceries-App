from django import forms
from django.contrib.auth import get_user_model
from accounts.models import User
from AdminDashboard.models import NewSubscription
from accounts.models import StaticData

User = get_user_model()

class UserEditForm(forms.ModelForm):
    class Meta:
        model = User   
        fields=[
            'username',
            'email',
            'contact',
            'dob',
            'country',
            'is_email_verified',
            'is_active',
      
        ]

class NewSubscriptionForm(forms.ModelForm):
    class Meta:
        model=NewSubscription
        fields=[
            'name',
            'plan_type',
            'duration',
            'price',
            'description',
        ]

class StaticDataForm(forms.ModelForm):
    class Meta:
        model = StaticData
        fields = [
            'title',
            'type',
            'content',
            'is_active',
        ]
        widgets = {
            'type': forms.Select(choices=StaticData.TYPE_CHOICES),  # dropdown for type
        }
from django.db import models
from accounts.models import User


class UserPreference(models.Model):
    DIET_GOAL_CHOICES = [
        ('lose weight', 'Lose Weight'),
        ('gain weight', 'Gain Weight'),
        ('eat healthy', 'Eat Healthy'),
        ('maintain weight', 'Maintain Weight'),
    ]

    DIET_TYPE_CHOICES = [
        ('vegetarian', 'Vegetarian'),
        ('vegan', 'Vegan'),
        ('pescatarian', 'Pescatarian'),
        ('omnivore', 'Omnivore'),
        ('gluten_free','Gluten_Free')
    ]

    
    HEIGHT_UNIT_CHOICES = [
        ('ft', 'Feet'),
        ('cm', 'Centimeters'),
    ]
    WEIGHT_UNIT_CHOICES = [
        ('kg', 'Kilograms'),
        ('lbs', 'Pounds'),
    ]

    height = models.FloatField(null=True,blank=True)
    current_weight = models.FloatField(null=True,blank=True)
    target_weight = models.FloatField(null=True,blank=True)
    height_unit = models.CharField(max_length=2, choices = HEIGHT_UNIT_CHOICES)
    weight_unit = models.CharField(max_length=3, choices = WEIGHT_UNIT_CHOICES)
    user_id = models.OneToOneField(User, on_delete = models.CASCADE)
    diet_goal = models.CharField(max_length = 20, choices=DIET_GOAL_CHOICES)
    diet_type = models.CharField(max_length = 20, choices=DIET_TYPE_CHOICES)
    cooking_style = models.JSONField(null=True,blank=True)
    flavour_preferences = models.JSONField(null=True,blank=True)
    cuisine_preferences = models.JSONField(null=True,blank=True)
    allergies = models.JSONField(null=True,blank=True)
    weekly_budget = models.IntegerField(default=0,null=True,blank=True)
    monthly_budget = models.IntegerField(default=0,null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add = True)
    updated_at = models.DateTimeField(auto_now = True)

    def __str__(self):
        return self.user_id.username


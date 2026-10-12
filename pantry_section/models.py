from django.db import models
from accounts.models import User 
from recipe_section.models import Ingredient


class PantryItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity_available = models.IntegerField(default=0)
    expiry_date = models.DateField(null=True, blank=True)
    unit = models.CharField(max_length=15,null=True,blank=True)
    weight = models.IntegerField(default=1)
    image = models.ImageField(upload_to='pantry/', null = True, blank = True)
    media_id  = models.CharField(max_length=500,null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.ingredient.name} ({self.quantity_available}) for {self.user.username}"


class PantryGroup(models.Model):
    name = models.CharField(max_length=100, unique=True)
    icon = models.ImageField(upload_to='group_icons/', null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return self.name

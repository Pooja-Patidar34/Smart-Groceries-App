from django.db import models
from accounts.models import User
from recipe_section.models import Ingredient
    


class ShoppingListItem(models.Model):
    """
    It plays a central role in helping users buy missing ingredients across all their planned meals.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    required_quantity = models.CharField(max_length=50)
    is_purchased = models.BooleanField(default=False)
    is_delivered = models.BooleanField(default=False)  
    delivery_date = models.DateTimeField(null=True, blank=True)  
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.required_quantity} of {self.ingredient.name} for {self.user.username}"
    

class OrderSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ingredients = models.JSONField() 
    status = models.CharField(max_length=20, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ExtractedIngredientsFromMail(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    _from = models.EmailField(null=True,blank=True)
    _to = models.EmailField(null=True,blank=True)  
    ingredient_data = models.TextField(null=True, blank=True)
    gtp_response = models.JSONField(null=True, blank=True)
    is_read =models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)  
    updated_at = models.DateTimeField(auto_now=True)     

    def __str__(self):
        return f"Ingredients for {self.user.username}"


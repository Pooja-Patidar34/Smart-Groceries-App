from django.db import models
from accounts.models import User
from django.utils import timezone
from datetime import timedelta

class Ingredient(models.Model):
    name = models.CharField(max_length=100)
    category = models.TextField(null=True, blank=True)  
    nutrition_info = models.TextField(blank=True, null=True)
    group = models.ForeignKey('pantry_section.PantryGroup', on_delete=models.SET_NULL, null=True, blank=True)


    def __str__(self):
        return self.name

class Recipe(models.Model):
    title = models.CharField(max_length=100, db_index = True)
    description = models.TextField(max_length=1000)
    instructions = models.TextField(max_length=2000,null=True,blank=True)
    cooking_time = models.DurationField(help_text="Time required to cook, e.g., 00:30:00 for 30 minutes")
    image = models.ImageField(upload_to='recipes/', null=True, blank=True)

    # Nutrition information
    calories = models.PositiveIntegerField(null=True, blank=True, help_text="Total kilocalories (Kcal)")
    fat = models.FloatField(null=True, blank=True, help_text="Fat content in grams")
    carbohydrates = models.FloatField(null=True, blank=True, help_text="Carbohydrates in grams")
    protein = models.FloatField(null=True, blank=True, help_text="Protein in grams")
    vitamins = models.TextField(max_length=2000,null=True, blank=True)
    media_id = models.CharField(max_length=255,null=True,blank=True)

    is_vegetarian = models.BooleanField(default=False)
    is_spicy = models.BooleanField(default=False)

    # Optional tags/cuisine (enhancement for filtering)
    cuisine = models.CharField(max_length=50, null=True, blank=True, help_text="e.g. Indian or Italian")
    flavor_profile = models.CharField(max_length=50, null=True, blank=True, help_text="e.g. Sweet, Spicy, Umami")
    quantity = models.IntegerField(default=1)
    ingredients = models.ManyToManyField(Ingredient, through='RecipeIngredient')

    def __str__(self):
        return self.title

def default_expiry():
    return timezone.now() + timedelta(hours=6)

class ListedMeal(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    item_name = models.CharField(max_length=100, null=True,blank=True,db_index=True)
    ingredients = models.JSONField(null=True, blank=True)
    quantity = models.IntegerField(default=1) 
    price = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    available_from = models.DateTimeField(default=timezone.now)
    available_to = models.DateTimeField(default=timezone.now)
    expiry_date = models.DateTimeField(default=default_expiry)
    is_donation = models.BooleanField(default=False)
    pickup_address = models.CharField(max_length=255,null=True,blank=True)
    image = models.ImageField(upload_to='listed_meals/', null=True, blank=True)
    image_url = models.URLField(max_length=500, null=True, blank=True)
    media_id = models.CharField(max_length=200,null=True,blank=True)
    delivery_method = models.CharField(max_length=40,null=True,blank=True)
    diet_type = models.CharField(max_length=40,null=True,blank=True) 
    description = models.TextField(max_length=400,null=True,blank=True)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2,null=True,blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6,null=True,blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6,null=True,blank=True) 

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.item_name} by {self.user.email}"

class SavedRecipes(models.Model):
    recipe = models.ForeignKey(Recipe,on_delete=models.CASCADE)
    user = models.ForeignKey(User,on_delete=models.CASCADE)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity = models.CharField(max_length=50,null = True, blank = True)

    def __str__(self):
        return f"{self.quantity} of {self.ingredient.name} in {self.recipe.title}"
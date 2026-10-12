from django.db import models
from accounts.models import User
from recipe_section.models import Recipe


# Create your models here.
class MealPlan(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    plan_duration = models.CharField(max_length=15,null=True,blank=True)
    generated_meals = models.JSONField(null=True,blank=True)
    meals_per_day = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    budget = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Meal(models.Model):
    meal_plan = models.ForeignKey(MealPlan, on_delete=models.CASCADE)
    date = models.DateField()
    meal_type = models.CharField(max_length=10, choices=[('breakfast', 'Breakfast'), ('lunch', 'Lunch'), ('snack', 'Snack'), ('dinner', 'Dinner')])
    recipe = models.ForeignKey(Recipe, on_delete=models.SET_NULL, null=True)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    updated_at = models.DateTimeField(auto_now = True)

class MealRating(models.Model):
    user = models.ForeignKey(User, on_delete = models.CASCADE)
    meal = models.ForeignKey(Meal, on_delete = models.CASCADE, related_name='ratings')
    stars = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)])
    feedback = models.TextField(null = True, blank = True)
    
    created_at = models.DateTimeField(auto_now_add = True)
    updated_at = models.DateTimeField(auto_now = True)


    class Meta:
        unique_together = ('user', 'meal')  # user can rate a meal only once

    def __str__(self):
        return f"{self.user.username} rated {self.meal.recipe.title} {self.stars}★"
    

class UserSelectedMeals(models.Model):
    meal_plan = models.ForeignKey(MealPlan, on_delete=models.SET_NULL,null=True,blank=True)
    meal_type = models.CharField(max_length=15)
    selected_meals_json = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at =  models.DateTimeField(auto_now=True)


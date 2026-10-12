from django.urls import path
from . import views

urlpatterns = [
    path('generate-meals',views.MealGenerator.as_view()),
    path('user/generated-meals/',views.GetGeneratedPlan.as_view()),
    path('selected-meals',views.SelectMeals.as_view()),
    path('save-changes',views.SaveChanges.as_view()),
    path('meal-progress-bar',views.ProgressBarMeals.as_view()),
    path('is-meal-active',views.IsActiveMeal.as_view()),
    path('date-wise-meals',views.GetRecipes.as_view()),
    path('missing-ingredients',views.MissingIngredients.as_view()),
]
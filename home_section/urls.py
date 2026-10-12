from django.urls import path
from . import views



urlpatterns = [
    path('user/planned-meals',views.UserPlannedMeal.as_view()),
    path('meal/progressbar',views.MealProgressBar.as_view()),
    path('meal-details/<int:id>',views.MealDetail.as_view()),
    path('markascomplete',views.CompleteTheMeal.as_view()),
]

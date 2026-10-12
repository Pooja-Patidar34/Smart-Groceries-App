from django.urls import path
from .views import *
urlpatterns = [
    path('user/recipe',UserRecipes.as_view()),

    # Nearby recipe.
    path('listed-meals',ListMealAPIView.as_view()),
    path('listed-meal/detail/<int:id>',ListedMealdetail.as_view()),
    path('buy/meals',BuyListedMeal.as_view()),
    path('my-listedmeals',MyListedMeals.as_view()),
    path('my-listedmeals/<int:id>',MyListedMealsDetail.as_view()),

    #commission urls
    path('get-commission-data',GetCommissionData.as_view()),
]
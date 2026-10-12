from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from meal_planner.models import *
from .serializers import MealSerializer 
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from pantry_section.models import PantryItem
from recipe_section.models import RecipeIngredient
from django.db.models import Case, When, IntegerField
from meal_planner.serializer import GetRecipesSerializer

class UserPlannedMeal(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        meal_order = Case(
            When(meal_type="breakfast", then=0),
            When(meal_type="lunch", then=1),
            When(meal_type="snack", then=2),
            When(meal_type="dinner", then=3),
            output_field=IntegerField(),
        )

        user_meals = Meal.objects.filter(
            meal_plan__user=request.user,
            date=today
        ).order_by(meal_order, "created_at")   


        # pagination section
        paginator = PageNumberPagination()
        paginator.page_size = 10  

        result_page = paginator.paginate_queryset(user_meals, request)
        serializer = GetRecipesSerializer(result_page, many=True)


        data = {
            "ok": True,
            "count": paginator.page.paginator.count,
            "next": paginator.get_next_link(),
            "previous": paginator.get_previous_link(),
            "data": serializer.data
        }
        return Response(data, status = status.HTTP_200_OK)




class MealDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        user = request.user
        if not id:
            return Response({'ok': False, 'error': 'Id is missing.'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            meal = Meal.objects.select_related('recipe') \
                .prefetch_related('recipe__recipeingredient_set__ingredient') \
                .get(meal_plan__user=user, id=id)
        except Meal.DoesNotExist:
            return Response({'ok': False, 'error': 'Meal not found.'},
                            status=status.HTTP_404_NOT_FOUND)

        # Collect recipe ingredients
        recipe_ingredients = [
            {"name": ri.ingredient.name, "quantity_required": ri.quantity.split(' ')[0]}
            for ri in meal.recipe.recipeingredient_set.all()
        ]

        print(recipe_ingredients)

        # Preload pantry items for this user
        pantry_items = PantryItem.objects.filter(user=user) \
            .select_related("ingredient")
        pantry_dict = {p.ingredient.name.lower(): p for p in pantry_items}

        missing_ingredients = []
        available_ingredients = []

        for recipe_ing in recipe_ingredients:
            pantry_item = pantry_dict.get(recipe_ing["name"].lower())
            required_qty = recipe_ing["quantity_required"]
            available_qty = pantry_item.quantity_available if pantry_item else 0

            if not pantry_item or available_qty < int(required_qty) if required_qty.isnumeric() else 0:
                missing_ingredients.append({
                    "name": recipe_ing["name"],
                    "required_quantity": required_qty,
                    "available_quantity": available_qty,
                })
            else:
                available_ingredients.append({
                    "name": recipe_ing["name"],
                    "required_quantity": required_qty,
                    "available_quantity": available_qty,
                })

        serializer = MealSerializer(meal)

        data = {
            "available_ingredients": available_ingredients,
            "missing_ingredients": missing_ingredients,
            "other_data": serializer.data,
        }
        return Response({"ok": True, "data": data}, status=status.HTTP_200_OK)


class MealProgressBar(APIView):
    permission_classes = [IsAuthenticated]

    def get(self,request):
        meals = Meal.objects.filter(meal_plan__user = request.user, meal_plan__is_active = True)
        total_meals = meals.count() 
        completed_meals = meals.filter(is_completed = True).count()

        if total_meals > 0:
            completion_percentage = (completed_meals / total_meals) * 100
        else:
            completion_percentage = 0
        
        now = timezone.now()

        todays_meal = meals.filter(date = now.date(),is_completed = False)

        serializer = MealSerializer(todays_meal, many=True)
        return Response({
            "ok": True,
            "data": {
                "completion_percentage": round(completion_percentage, 2),
                "todays_meal": serializer.data
            }
        })



class CompleteTheMeal(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        id = request.data.get('id')
        if not id:
            return Response({'ok': False, 'error': 'Id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            meal = Meal.objects.get(id=id, meal_plan__user=request.user)
        except Meal.DoesNotExist:
            return Response({'ok': False, 'error': 'Record not found.'}, status=status.HTTP_404_NOT_FOUND)
        
        # Mark as completed
        meal.is_completed = True
        meal.save()

        # Loop over recipe ingredients
        recipe_ingredients = RecipeIngredient.objects.filter(recipe=meal.recipe)

        for ri in recipe_ingredients:
            try:
                pantry_item = PantryItem.objects.get(user=request.user, ingredient=ri.ingredient)
                if pantry_item.quantity_available >= ri.quantity:
                    pantry_item.quantity_available -= ri.quantity
                else:
                    pantry_item.quantity_available = 0  # not enough available, set to zero
                pantry_item.save()
            except PantryItem.DoesNotExist:
                pass

        return Response({'ok': True, 'message': 'Meal completed and pantry updated.'}, status=status.HTTP_200_OK)

        



        


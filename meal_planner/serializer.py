from rest_framework import serializers
from .models import *
from recipe_section.models import RecipeIngredient,Ingredient

class SelectMealsSerilizer(serializers.ModelSerializer):
    class Meta:
        model = UserSelectedMeals
        fields = '__all__'
    

from rest_framework import serializers

class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ['id', 'name', 'category', 'nutrition_info']


class RecipeIngredientSerializer(serializers.ModelSerializer):
    ingredient = IngredientSerializer()

    class Meta:
        model = RecipeIngredient
        fields = ['ingredient', 'quantity']


class RecipeSerializer(serializers.ModelSerializer):
    ingredients = RecipeIngredientSerializer(
        source='recipeingredient_set', many=True
    )
    signed_url = serializers.SerializerMethodField()


    class Meta:
        model = Recipe
        fields = [
            'id', 'title', 'description', 'instructions',
            'cooking_time', 'image',
            'calories', 'fat', 'carbohydrates', 'protein', 'vitamins',
            'is_vegetarian', 'is_spicy',
            'cuisine', 'flavor_profile', 'quantity',
            'ingredients',
            'signed_url'
        ]

    def get_signed_url(self, obj):
        """Generate signed URL from S3 API for each recipe image."""
        import requests, os

        if not obj.media_id: 
            return None

        url = f"{os.getenv('S3BUCKETUAPI')}/signed-url/{obj.media_id}?time_in_sec=3600"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get("data", {}).get("downloadUrl")
        except Exception:
            return None
        return None
class GetRecipesSerializer(serializers.ModelSerializer):
    recipe = RecipeSerializer()   

    class Meta:
        model = Meal
        fields = [
            'id', 'date', 'meal_type', 'is_completed',
            'created_at', 'updated_at',
            'recipe',
        ]

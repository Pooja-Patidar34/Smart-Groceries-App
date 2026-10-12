from rest_framework import serializers
from meal_planner.models import Meal, Recipe
import json
import ast


class RecipeSerializer(serializers.ModelSerializer):
    instructions = serializers.SerializerMethodField()
    class Meta:
        model = Recipe
        fields = '__all__'
    
    
    def get_instructions(self, obj):
        if not obj.instructions:
            return []

        text = obj.instructions.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            try:
                return ast.literal_eval(text)
            except Exception as e:
                return []
            
class MealSerializer(serializers.ModelSerializer):
    recipe = RecipeSerializer(read_only=True)

    class Meta:
        model = Meal
        fields = '__all__'

from rest_framework import serializers
from accounts.models import User
from .models import *
from django.db import transaction
from transactions.models import *
from AdminDashboard.models import NewSubscription

class UserDietPreferenceSerializer(serializers.Serializer):
    DIET_GOAL_CHOICES = [
        ('lose weight', 'Lose Weight'),
        ('gain weight', 'Gain Weight'),
        ('eat healthy', 'Eat Healthy'),
        ('maintain weight', 'Maintain Weight'),
    ]
    
    DIET_TYPE_CHOICES = [
        ('vegetarian', 'Vegetarian'),
        ('vegan', 'Vegan'),
        ('pescatarian', 'Pescatarian'),
        ('omnivore', 'Omnivore'),
        ('gluten_free','Gluten Free')
    ]

    username = serializers.CharField(max_length=255,required=False, allow_null=True, allow_blank=True)
    gender = serializers.CharField(max_length=10, required=False, allow_null=True, allow_blank=True)
    dob = serializers.DateField(required=False, allow_null=True)
    height = serializers.FloatField(required=False, allow_null=True)
    current_weight = serializers.FloatField(required=False, allow_null=True)
    target_weight = serializers.FloatField(required=False, allow_null=True)
    weekly_budget = serializers.IntegerField(required=False, allow_null=True)
    monthly_budget = serializers.IntegerField(required=False, allow_null=True)
    diet_goal = serializers.ChoiceField(choices = DIET_GOAL_CHOICES)
    diet_type = serializers.ChoiceField(choices = DIET_TYPE_CHOICES)
    
    allergic_food_item = serializers.JSONField(
        required=False,
        allow_null=True
    )

    cooking_style = serializers.JSONField(
        required=False,
        allow_null=True
    )

    flavours = serializers.JSONField(
        required=False,
        allow_null=True
    )

    cuisines = serializers.JSONField(
        required=False,
        allow_null=True
    )


    def validate(self, data):
        goal = data.get('diet_goal')
        current = data.get('current_weight')
        target = data.get('target_weight')

        if goal == 'gain weight' and current and target and target <= current:
            raise serializers.ValidationError("Target weight should be greater than current weight for gain goal.")
        if goal == 'lose weight' and current and target and target >= current:
            raise serializers.ValidationError("Target weight should be less than current weight for lose goal.")

        return data


    def create(self, validated_data):
        user = self.context.get('request').user
        user_obj = User.objects.get(id=user.id)

        # Update user fields if present
        user_fields = ['username', 'gender', 'dob', 'country']
        for field in user_fields:
            value = validated_data.get(field)
            if value is not None:
                setattr(user_obj, field, value)

        # Extract preference 
        height = validated_data.get('height')
        current_weight = validated_data.get('current_weight')
        target_weight = validated_data.get('target_weight')

        weekly_budget = validated_data.get('weekly_budget')
        monthly_budget = validated_data.get('monthly_budget')
        diet_goal = validated_data.get('diet_goal')
        diet_type = validated_data.get('diet_type')
        allergic_food_item = validated_data.get('allergic_food_item', [])
        cooking_style = validated_data.get('cooking_style', [])
        flavours = validated_data.get('flavours', [])
        cuisines = validated_data.get('cuisines', [])

        with transaction.atomic():
            # Save updated user data
            user_obj.save()

            # Create or get user preference
            user_preference, created = UserPreference.objects.update_or_create(
                user_id=user,  # lookup field to check if preference already exists
                defaults={
                    'diet_goal': diet_goal,
                    'diet_type': diet_type,
                    'weekly_budget': weekly_budget if weekly_budget else None,
                    'monthly_budget': monthly_budget if monthly_budget else None,
                    'height': height,
                    'current_weight': current_weight,
                    'target_weight': target_weight,
                    'cooking_style': cooking_style,
                    'flavour_preferences': flavours,
                    'cuisine_preferences': cuisines,
                    'allergies': allergic_food_item,
                }
            )

            
        return user_preference
    
    
    def update(self, instance, validated_data):
        user = self.context.get('request').user
        user_obj = User.objects.get(id=user.id)

        # Update user fields if present
        user_fields = ['username', 'gender', 'dob', 'country']
        for field in user_fields:
            value = validated_data.get(field)
            if value is not None:
                setattr(user_obj, field, value)

        # Preference fields
        preference_fields = {
            'height': validated_data.get('height'),
            'current_weight': validated_data.get('current_weight'),
            'target_weight': validated_data.get('target_weight'),
            'weekly_budget': validated_data.get('weekly_budget'),
            'monthly_budget': validated_data.get('monthly_budget'),
            'diet_goal': validated_data.get('diet_goal'),
            'diet_type': validated_data.get('diet_type'),
            'allergies': validated_data.get('allergic_food_item'),
            'cooking_style': validated_data.get('cooking_style'),
            'flavour_preferences': validated_data.get('flavours'),
            'cuisine_preferences': validated_data.get('cuisines')
        }

        with transaction.atomic():
            # Save updated user data
            user_obj.save()

            # Update existing preference instance
            for field, value in preference_fields.items():
                if value is not None:
                    setattr(instance, field, value)

            instance.save()

        return instance

    

class SetSystemMeasurementsSerializer(serializers.Serializer):
    measurement_type = serializers.CharField()

    def validate_measurement_type(self, value):
        if not value.strip():
            raise serializers.ValidationError("measurement_type can't be empty.")
        return value

    def create(self, validated_data):
        measurement_type = validated_data.get('measurement_type')
        user = self.context.get('request').user
        user.measurement_type = measurement_type
        user.save()

        return validated_data


class MyOrdersserializer(serializers.ModelSerializer):
    meal_name = serializers.CharField(source="meal.item_name", read_only=True)
    meal_image = serializers.ImageField(source="meal.image", read_only=True)
    seller_name = serializers.CharField(source="seller.username", read_only=True)

    class Meta:
        model = Order
        fields = "__all__" 
        extra_fields = ["meal_name", "meal_image", "seller_name"]

    def to_representation(self, instance):
        """Merge extra fields into the response"""
        rep = super().to_representation(instance)
        rep["meal_name"] = instance.meal.item_name if instance.meal else None
        rep["meal_image"] = (
            instance.meal.image.url if instance.meal and instance.meal.image else None
        )
        rep["seller_name"] = instance.seller.username
        return rep

class MyPayoutSerializer(serializers.ModelSerializer):
    orderid = serializers.CharField(source="order.orderid", read_only=True)
    item_name = serializers.CharField(source="order.meal.item_name", read_only=True)
    meal_image = serializers.ImageField(source="order.meal.image", read_only=True)

    class Meta:
        model = Payout
        fields = ['orderid','item_name','meal_image','status','payout_date','amount','id']

    
class NewSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewSubscription
        fields ='__all__'

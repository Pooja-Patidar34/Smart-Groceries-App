from rest_framework import serializers
from django.db import transaction
from recipe_section.models import Ingredient
from .models import PantryItem
import requests
from pantry_section.models import PantryGroup
from dotenv import load_dotenv
load_dotenv()
import os


class AddProductToPantrySerializer(serializers.Serializer):
    name = serializers.CharField(required = True)
    category = serializers.CharField(required=True, max_length=100)
    quantity_available = serializers.IntegerField(default = 1)
    unit = serializers.CharField(required = False, allow_null = True)
    expiry_date = serializers.DateField(required = False, allow_null = True)
    weight = serializers.IntegerField(default = 1)
    image = serializers.ImageField()
    
    def validate_category(self, value):
        value = value.strip().title()
        valid_groups = PantryGroup.objects.values_list("name", flat=True)
        if value not in valid_groups:
            raise serializers.ValidationError(
                f"Invalid category '{value}'. Please choose from {list(valid_groups)}."
            )
        return value
    
    def validate(self, attrs):
        """
        Custom validation that runs before create().
        Used for duplicate item checks, logical checks, etc.
        """
        user = self.context["request"].user
        name = attrs.get("name")
        category = attrs.get("category")

        # Find ingredient (if it already exists)
        group_obj = PantryGroup.objects.filter(name=category).first()
        if not group_obj:
            raise serializers.ValidationError({"category": "Invalid category."})

        # Check if item already exists for this user
        if PantryItem.objects.filter(user=user, ingredient__name=name).exists():
            raise serializers.ValidationError({"non_field_errors": ["Pantry item already exists."]})

        # Example of extra logical validation:
        if attrs.get("quantity_available") <= 0:
            raise serializers.ValidationError({"quantity_available": "Quantity must be greater than zero."})

        return attrs


    def create(self, validated_data):
        name = validated_data.pop("name")
        category = validated_data.pop("category")
        user = self.context["request"].user
        image_file = validated_data.pop("image", None)
        media_id = None

        if image_file:
            try:
                upload_url = os.getenv('S3BUCKETUAPI')
                files = {
                    "file": (
                        image_file.name,
                        image_file.read(),
                        image_file.content_type,
                    )
                }
                resp = requests.post(upload_url, files=files)

                if resp.status_code == 200:
                    resp_json = resp.json()
                    media_id = resp_json.get("data", {}).get("mediaId", {}).get("id")
                    print(media_id)
                    download_url = resp_json.get("data", {}).get("downloadUrl")
            except Exception as e:
                print(f"Media upload failed: {e}")

               
        with transaction.atomic():
            group_obj, _ = PantryGroup.objects.get_or_create(name=category)
            ingredient = Ingredient.objects.create(name=name, group=group_obj)



        # ---- Step 4: Create pantry item ----
        pantry_item = PantryItem.objects.create(
            user=user,
            ingredient=ingredient,
            media_id=media_id,
            image=image_file,
            **validated_data,
        )
        return pantry_item

class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Ingredient
        fields = ['name', 'category']

class PantrySerializer(serializers.ModelSerializer):
    ingredient = serializers.CharField(source='ingredient.name')
    category = serializers.CharField(source='ingredient.group.name', read_only=True)
    signed_image_url = serializers.SerializerMethodField()
    

    class Meta:
        model = PantryItem
        fields = [
            'id',
            'ingredient',  
            'category',    
            'quantity_available',
            'expiry_date',
            'unit',
            'weight',
            'created_at',
            'updated_at',
            'user',
            'signed_image_url'
        ]    
    

    def get_signed_image_url(self, obj):
        if not obj.media_id:
            return None

        try:
            url = f"{os.getenv('S3BUCKETUAPI')}/signed-url/{obj.media_id}?time_in_sec=3600"
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                data = response.json()
                return data.get("data", {}).get("downloadUrl") 
        except Exception as e:
            print(f"Signed URL fetch failed for media_id {obj.media_id}: {e}")

        
        return None


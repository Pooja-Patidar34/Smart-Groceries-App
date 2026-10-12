from rest_framework import serializers
from .models import ListedMeal
import boto3,requests
import os

from dotenv import load_dotenv
load_dotenv()

class ListedMealsSerializer(serializers.ModelSerializer):
    distance = serializers.SerializerMethodField()

    class Meta:
        model = ListedMeal
        fields = [
            'id',
            'item_name',
            'ingredients',
            'quantity',
            'price',
            # 'available_from',
            # 'available_to',
            'expiry_date',
            'is_donation',
            'image',
            'description',
            'diet_type',
            'pickup_address',
            'delivery_method',
            'distance',
            'latitude',
            'longitude',
            'commission_rate'
        ]
        
    def get_distance(self, obj):
        return round(getattr(obj, 'distance', None), 2) if hasattr(obj, 'distance') else None
   
    def validate(self, data):
        if not data.get('latitude',None):
            raise serializers.ValidationError('latitude is required.')
        
        if not data.get('longitude',None):
            raise serializers.ValidationError('longitude is required.')
        
        if not data.get('commission_rate',None):
            raise serializers.ValidationError('commission rate is required.')
        
        # if data['available_to'] <= data['available_from']:
        #     raise serializers.ValidationError("available_to must be after available_from.")

        # if data['expiry_date'] <= data['available_to']:
        #     raise serializers.ValidationError("expiry_date must be after available_to.")

        if data['is_donation'] and data.get('price'):
            raise serializers.ValidationError("Price is not required for free donation.")

        if not data['is_donation'] and (data.get('price') is None or data['price'] == 0):
            raise serializers.ValidationError("Paid meals must have a non-zero price.")

        return data

    def create(self, validated_data):
        image_file = validated_data.get("image")
        url = None

        if image_file:
            files = {
                "file": (image_file.name, image_file, image_file.content_type)
            }

            api_url = f"{os.getenv('S3BUCKETUAPI')}"
            response = requests.post(api_url, files=files)

            if response.status_code == 200:
                data = response.json()
                url = data.get('data', {}).get('downloadUrl')
                media_id = data.get('data', {}).get('mediaId').get('id')
                print("media_id:",media_id)
            else:
                raise serializers.ValidationError("Failed to upload image to external service.")

        user = self.context['user']
        validated_data['user'] = user
        if url:
            if hasattr(ListedMeal, "image_url") and url:
                validated_data['image_url'] = url
            if hasattr(ListedMeal, "media_id") and media_id:
                validated_data['media_id'] = media_id

  
        return ListedMeal.objects.create(**validated_data)


class ListedMealdetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListedMeal
        fields = '__all__'
    

class GetListedMealsSerializer(serializers.ModelSerializer):
    distance = serializers.SerializerMethodField()
    signed_image_url = serializers.SerializerMethodField()

    class Meta:
        model = ListedMeal
        fields = [
            'id',
            'item_name',
            'price',
            'is_donation',
            'created_at',
            'distance',
            'signed_image_url', 
        ]

    def get_distance(self, obj):
        distance = getattr(obj, 'distance', None)
        return round(distance, 2) if distance is not None else None

    def get_signed_image_url(self, obj):
        if not obj.media_id:
            return obj.image_url or None

        try:
            url = f"{os.getenv('S3BUCKETUAPI')}/signed-url/{obj.media_id}?time_in_sec=3600"
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                data = response.json()
                return data.get("data", {}).get("downloadUrl") 
        except Exception as e:
            print(f"Signed URL fetch failed for media_id {obj.media_id}: {e}")

        
        return obj.image_url or None

class MyListedMealDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListedMeal
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'user']

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from .serializers import *
from rest_framework import status
from rest_framework.response import Response
from .models import PantryItem, Ingredient
from django.db.models import Q
import requests
from collections import defaultdict



class AddProductToPantry(APIView):
    permission_classes = [IsAuthenticated]


    def post(self,request):
        serializer = AddProductToPantrySerializer(data = request.data,context={'request':request})

        if serializer.is_valid():
            try:
                items = serializer.save()
                return Response({'ok':True,"data":PantrySerializer(items).data},status=status.HTTP_200_OK)
            except Exception as e:
                return Response({'ok':False,"error":"Internal Server Error."},status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        error_dict = serializer.errors

        if 'non_field_errors' in error_dict:
            error_msg = error_dict['non_field_errors'][0]
        else:
            field, errors = next(iter(error_dict.items()))
            error_msg = f"{field}: {errors[0]}"

        return Response({'ok': False, "error": str(error_msg)}, status=status.HTTP_400_BAD_REQUEST)


    def get(self, request):
        search = request.GET.get('search')
        category = request.GET.get('category')

        query = Q(user=request.user)

        if search:
            query &= Q(ingredient__name__iexact=search) | Q(ingredient__name__icontains=search)

        if category and category != 'all':
            query &= Q(ingredient__group__name__iexact=category) | Q(ingredient__group__name__icontains=category)

        pantry_data = PantryItem.objects.filter(query).order_by('-created_at')
        serializer = PantrySerializer(pantry_data, many=True)

        return Response(
            {'ok': True, 'data': serializer.data},
            status=status.HTTP_200_OK
        )




class QuantityChange(APIView):
    permission_classes = [IsAuthenticated]

    def post(self,request):
        try:
            indication = request.data.get('indication')
            id  = request.data.get('id')
            try:
                pantry_obj = PantryItem.objects.get(id = id)
            except Exception:
                return Response({'ok':False,'error':'Invalid Id paased.'},status=status.HTTP_400_BAD_REQUEST)
            
            if indication == 'add':
                pantry_obj.quantity_available += 1
            
            elif indication == 'minus':
                pantry_obj.quantity_available -= 1
                if pantry_obj.quantity_available < 0:
                    return Response({'ok':False,'error':'Item cannot be less than 0.'},status=status.HTTP_400_BAD_REQUEST)
                    

            pantry_obj.save()
            return Response({'ok':True,'data':pantry_obj.quantity_available},status=status.HTTP_200_OK)
        except Exception:
            return Response({'ok':False,'error':'Server errro'},status =status.HTTP_500_INTERNAL_SERVER_ERROR)



class ScanProduct(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        barcode = request.data.get('barcode')
        if not barcode:
            return Response({'ok': False, 'error': 'Barcode is required.'}, status=400)

        product_info = (
            self.fetch_from_usda(barcode)
            or self.fetch_from_openfoodfacts(barcode)
            or self.fetch_from_nutritionix(barcode)
        )

        if not product_info:
            return Response({'ok': False, 'error': 'Product not found in any source.'}, status=400)
        
        category_from_gpt = self.get_product_category_from_gpt(product_info)

        ingredient, _ = Ingredient.objects.get_or_create(
            name=product_info['product_name'],
            defaults={
                'category': product_info.get('categories', ''),
                'nutrition_info': str(product_info.get('nutrient_levels', {}))
            }
        )
        try:
            group = PantryGroup.objects.get(name=category_from_gpt)
        except Exception as e:
            return Response({'ok':False,'data':'PantryGroup not found'},status=status.HTTP_400_BAD_REQUEST)
        ingredient.group = group
        ingredient.save()

        image_file_url = product_info.get('image_url')
        media_id = None

        if image_file_url:
            try:
                upload_url = os.getenv('S3BUCKETUAPI')
                resp_file = requests.get(image_file_url)
                if resp_file.status_code == 200:
                    files = {
                        "file": (
                            image_file_url.split("/")[-1],
                            resp_file.content,
                            resp_file.headers.get('Content-Type', 'image/jpeg')
                        )
                    }
                    resp = requests.post(upload_url, files=files)
                    if resp.status_code == 200:
                        data = resp.json().get("data", {})
                        media_id = data.get("mediaId", {}).get("id")
            except Exception as e:
                print(f"Media upload failed: {e}")
        

        obj, created = PantryItem.objects.get_or_create(
        user=request.user,
        ingredient=ingredient,
        defaults={
            "quantity_available": 1,
            "unit": product_info.get('unit'),
            "weight": product_info.get('product_quantity') or 1,
            "image": product_info.get('image_url'),
            "media_id": media_id,
        }
    )

        if not created:
            # If the item already exists, increase quantity
            obj.quantity_available += 1
            obj.save()

        serializer = PantrySerializer(obj)
        return Response({'ok': True, 'data': serializer.data}, status=status.HTTP_201_CREATED)

    def fetch_from_openfoodfacts(self, barcode):
        try:
            url = f"{os.getenv('OPENFOODFACTS_BASE_URL')}/{barcode}.json"
            res = requests.get(url)
            if res.status_code == 200:
                data = res.json()
                if 'product' in data:
                    product = data['product']
                    return {
                        'product_name': product.get('product_name', 'Unknown'),
                        'brands': product.get('brands'),
                        'unit':product.get('quantity'),
                        'categories': product.get('categories', ''),
                        'product_quantity': product.get('product_quantity'),
                        'nutrient_levels': product.get('nutrient_levels', {}),
                        'image_url': product.get('image_url'),
                    }
        except Exception as e:
            print("OpenFoodFacts error:", e)
        return None

    def fetch_from_nutritionix(self, barcode):
        try:
            url = f"{os.getenv('NUTRITIONIX_BASE_URL')}?upc={barcode}"
            headers = {
                'x-app-id': os.getenv('NUTRITIONIX_APP_ID'),
                'x-app-key': os.getenv('NUTRITIONIX_APP_KEY'),
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            res = requests.get(url, headers=headers)
            if res.status_code == 200:
                data = res.json()
                if data.get('foods'):
                    food = data['foods'][0]
                    return {
                        "product_name": food.get("food_name", "Unknown"),
                        "brands": food.get("brand_name"),
                        "product_quantity": food.get("serving_qty"),
                        "unit": food.get("serving_unit"),
                        "weight_grams": food.get("serving_weight_grams"),
                        "nutrient_levels": {
                            "calories": food.get("nf_calories"),
                            "total_fat": food.get("nf_total_fat"),
                            "protein": food.get("nf_protein"),
                        },
                        "image_url": food.get("photo", {}).get("highres") or food.get("photo", {}).get("thumb"),
                    }
        except Exception as e:
            print("Nutritionix error:", e)
        return None

    def fetch_from_usda(self, barcode):
        try:
            url = f"{os.getenv('USDA_BASE_URL')}?query={barcode}&dataType=Branded&api_key={os.getenv('USDA_API_KEY')}"
            res = requests.get(url)
            if res.status_code == 200:
                data = res.json()
                if data.get('foods'):
                    food = data['foods'][0]
                    nutrients = {
                        item.get('nutrientName'): f"{item.get('value')} {item.get('unitName')}"
                        for item in food.get('foodNutrients', [])
                        if item.get('nutrientName')
                    }
                    return {
                        'product_name': food.get('description', 'Unknown'),
                        'brands': food.get('brandOwner'),
                        'categories': food.get('foodCategory', ''),
                        'product_quantity': food.get('servingSize'),
                        'nutrient_levels': nutrients,
                        'image_url': None,
                    }
        except Exception as e:
            print("USDA error:", e)
        return None

    def get_product_category_from_gpt(self, product_info):
        data = list(PantryGroup.objects.all().values_list('name', flat=True))
        try:
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            f"You are a food categorization assistant. "
                            f"Given a product name, ingredients, and nutrition info, "
                            f"return the most suitable category from this list: {data}"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Product name: {product_info.get('product_name')}\n"
                            f"Ingredients: {product_info.get('ingredients_text', 'N/A')}\n"
                            f"Nutrition: {product_info.get('nutrient_levels', {})}\n"
                            f"Return only the category name."
                        ),
                    },
                ],
                "max_tokens": 10,
                "temperature": 0.3,
            }


            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {os.getenv('GPT_API_KEYS')}",
                "Content-Type": "application/json"
            }

            res = requests.post(url, json=payload, headers=headers)
            if res.status_code == 200:
                data = res.json()
                return data['choices'][0]['message']['content'].strip()
            else:
                print(f"[ERROR] GPT API failed: {res.text}")
                return None
        except Exception as e:
            print(f"[EXCEPTION] GPT categorization failed: {e}")
            return None

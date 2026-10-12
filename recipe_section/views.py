from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from meal_planner.models import Meal,MealPlan
from rest_framework.pagination import PageNumberPagination
from home_section.serializers import MealSerializer
from .serializers import *
from django.utils import timezone
import stripe
from django.conf import settings
from uuid import uuid4
from transactions.models import *
from django.db import transaction
from django.db.models import Q
from utils import *
import json
import os
from AdminDashboard.models import Configure
# from AdminDashboard.models import CommissionSetting
import http.client

from dotenv import load_dotenv
load_dotenv()

stripe.api_key = settings.STRIPE_SECRET_KEY



class UserRecipes(APIView):
    permission_classes = [IsAuthenticated]

    def get(self,request):
        
        meals = Meal.objects.filter(meal_plan__user = request.user,meal_plan__is_active = True).order_by('-id')

        paginator = PageNumberPagination()
        paginator.page_size = 10  

        result_page = paginator.paginate_queryset(meals, request)

        serializer = MealSerializer(result_page, many=True)

        return Response({
            "ok": True,
            "count": paginator.page.paginator.count,
            "next": paginator.get_next_link(),
            "previous": paginator.get_previous_link(),
            "data": serializer.data
        }, status=status.HTTP_200_OK)



class ListMealAPIView(APIView):
    permission_classes =[IsAuthenticated]
    def post(self, request):
        try:
            serializer = ListedMealsSerializer(data=request.data,context={'user': request.user})
            if serializer.is_valid():
                serializer.save() 
                return Response({
                    "ok": True,
                    "message": "Meal listed successfully"
                }, status=status.HTTP_201_CREATED)

            error_dict = serializer.errors

            if 'non_field_errors' in error_dict:
                error_msg = error_dict['non_field_errors'][0]
            else:
                field, errors = next(iter(error_dict.items()))
                error_msg = f"{field}: {errors[0]}"

            return Response({'ok': False, "error": str(error_msg)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'ok':False,'error':str(e)},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get(self, request):
        search = request.GET.get('search')
        sort_by = request.GET.get('sort_by')  
        meal_type = request.GET.get('meal_type')  
        diet_type = request.GET.get('diet_type')  
        distance_limit = request.GET.get('distance')  

        user_lat = request.GET.get('latitude')
        user_lon = request.GET.get('longitude')
        
        if not user_lat or not user_lon:
            return Response({'ok':False,'error':'co-ordinates are required'},status=status.HTTP_400_BAD_REQUEST)

        filters = Q()

        if search:
            filters &= Q(item_name__icontains=search)

        if meal_type == "donation":
            filters &= Q(is_donation=True)
        elif meal_type == "paid":
            filters &= Q(is_donation=False)

        if diet_type and diet_type.lower() != "all":
            filters &= Q(diet_type__iexact=diet_type)

        queryset = ListedMeal.objects.filter(filters).exclude(user = request.user)

        # If user location and distance is provided, filter by nearby meals
        nearby_meals = []
        if user_lat and user_lon and distance_limit:
            user_lat, user_lon = float(user_lat), float(user_lon)
            distance_limit = float(distance_limit)

            
            for meal in queryset:
                if meal.latitude is not None and meal.longitude is not None:
                    dist = haversine_distance(user_lat, user_lon, float(meal.latitude), float(meal.longitude))
                    if dist <= distance_limit:
                        meal.distance = dist
                        nearby_meals.append(meal)

        else:
            user_lat, user_lon = float(user_lat), float(user_lon)
            for meal in queryset:
                if meal.latitude is not None and meal.longitude is not None:
                    dist = haversine_distance(user_lat, user_lon, float(meal.latitude), float(meal.longitude))
                    meal.distance = dist
                    nearby_meals.append(meal)

        queryset = sorted(nearby_meals, key=lambda x: x.distance)

        # Sorting
        if sort_by == "price_high_to_low":
            queryset = sorted(queryset, key=lambda x: x.price, reverse=True)
        elif sort_by == "price_low_to_high":
            queryset = sorted(queryset, key=lambda x: x.price)
        elif sort_by == "recently":
            queryset = sorted(queryset, key=lambda x: x.created_at, reverse=True)
        elif sort_by in ["near", "far"] and user_lat and user_lon:
            reverse = sort_by == "far"
            queryset = sorted(queryset, key=lambda x: x.distance, reverse=reverse)

        serializer = GetListedMealsSerializer(queryset, many=True)
        return Response({'ok': True, 'data': serializer.data}, status=status.HTTP_200_OK)


class ListedMealdetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self,request,id):
        # id = request.data.get('id')
        
        try:
            listed_meal_obj = ListedMeal.objects.get(id = id)
            
        except Exception:
            return Response({'ok':False,'error':'Invalid Id'},status=status.HTTP_400_BAD_REQUEST)
        
        signed_image_url = None
        serializer = ListedMealdetailSerializer(listed_meal_obj)
        try:
            url = f"{os.getenv('S3BUCKETUAPI')}/signed-url/{listed_meal_obj.media_id}?time_in_sec=3600"
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                data = response.json()
                signed_image_url = data.get("data", {}).get("downloadUrl") 
        except Exception as e:
            print(f"Signed URL fetch failed for media_id {listed_meal_obj.media_id}: {e}")

        data = {
            'meal_detail':serializer.data,
            'donor_information':{
                'name':listed_meal_obj.user.username,
                'email':listed_meal_obj.user.email,
                'signed_image_url':signed_image_url
            }
        }
        return Response({'ok':True,'data':data},status=status.HTTP_200_OK)


class BuyListedMeal(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            amount = request.data.get('amount')
            meal_id = request.data.get('meal_id')
            try:
                listed_meal = ListedMeal.objects.get(id=meal_id)
            except Exception:
                return Response({'ok': False, 'error': 'Invalid meal id'}, status=status.HTTP_400_BAD_REQUEST)

            if not amount == listed_meal.price:
                return Response({'ok': False, "error": "amount should be equal to meal price"}, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                orderid = str(uuid4())

                order = Order.objects.create(
                    orderid=orderid,
                    buyer=request.user,
                    seller=listed_meal.user,
                    meal=listed_meal,
                    price=amount,
                    status='pending'
                )
                
                Payout.objects.create(
                    payoutid = str(uuid4().hex), 
                    order = order,
                    amount = amount,
                    status = 'pending',
                )


                # Create PaymentIntent instead of Checkout Session
                payment_intent = stripe.PaymentIntent.create(
                    amount = int(float(amount) * 100), 
                    currency = "eur",

                    automatic_payment_methods={
                        "enabled": True,
                    },
                    
                    metadata={
                        "user_id": str(request.user.id),
                        "orderid": orderid,
                        "purchase_type": "meal",
                        "meal_id": meal_id
                    },
                    receipt_email=request.user.email,
                )

                # Save payment_intent id in order for tracking
                order.payment_intent_id = payment_intent.id
                order.save()

            return Response({
                'ok': True,
                'data': {
                    "client_secret": payment_intent.client_secret,
                    "orderid": orderid
                }
            }, status=200)

        except Exception as e:
            return Response({'ok': False, "error": str(e)}, status=500)


class MyListedMeals(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        listed_meals = ListedMeal.objects.filter(
            user=request.user,
            quantity__gt=0,
            expiry_date__gte=timezone.now()
        ).order_by('-created_at')
        serializer = MyListedMealDetailSerializer(listed_meals, many=True)
        return Response({'ok': True, 'data': serializer.data}, status=status.HTTP_200_OK)

class MyListedMealsDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        try:
            listed_meal = ListedMeal.objects.get(id=id, user=request.user)  
        except ListedMeal.DoesNotExist:
            return Response({'ok': False, 'error': 'Meal not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = MyListedMealDetailSerializer(listed_meal)
        return Response({'ok': True, 'data': serializer.data}, status=status.HTTP_200_OK)

    
    def patch(self, request, id):
        """Partial update (only update provided fields)"""
        try:
            listed_meal = ListedMeal.objects.get(id=id, user=request.user)
        except ListedMeal.DoesNotExist:
            return Response({'ok': False, 'error': 'Meal not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = MyListedMealDetailSerializer(listed_meal, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'ok': True, 'data': serializer.data}, status=status.HTTP_200_OK)
        return Response({'ok': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)



class GetCommissionData(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        
        commission = Configure.objects.filter(label = 'COMMISSION').order_by('-updated_at').first()
        
        return Response({'ok': True, 'data': commission.value if commission else 0},status=status.HTTP_200_OK)


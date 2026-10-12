from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import *
import requests,threading
from datetime import timedelta,datetime
import json
from django.utils import timezone
from .helper import *
from recipe_section.models import RecipeIngredient,Recipe,Ingredient
from .serializer import *
from profile_section.models import UserPreference
from django.forms.models import model_to_dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from meal_planner.utils import *
import redis
import time
from pantry_section.models import PantryItem

r = redis.StrictRedis(host="127.0.0.1", port = 6379, db = 0, decode_responses = True)

PROCESSING_QUEUE = "processing_queue"
WAITING_QUEUE = "waiting_queue"
USERQUEUE_LIST = "usersqueue_list"
THREADQUEUE_LIST = "threadqueue_list"


MAX_PROCESSING = 8       # limit of concurrent jobs in processing queue
MAX_WORKERS = 8       # thread pool size

executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)




class SelectMeals(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        
        try:
            data = UserSelectedMeals.objects.filter(meal_plan__user=request.user)
            serialized = SelectMealsSerilizer(data, many=True)
            return Response({'ok': True, 'data': serialized.data,"message":'successful'}, status=status.HTTP_200_OK)
        except Exception:
            return Response({'ok': False, 'data': "server error","message":'error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

    def post(self,request):

        ids = request.data.get('id', [])  # Expecting a list of IDs
        meal_plan_id = request.data.get('meal_plan_id')

        if not ids or not meal_plan_id:
            return Response({"ok": False, "data": "Missing ID or meal_plan_id",'message':'error'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            meal_plan_obj = MealPlan.objects.get(id = meal_plan_id)
        except:
            return Response({'ok':False,'data':'No MealPlan matches the given query','message':'error'},status=status.HTTP_400_BAD_REQUEST)

        # Filter selected meals from JSONField
        selected_meals = [meal for meal in meal_plan_obj.generated_meals if meal.get("id") in ids]

        if not selected_meals:
            return Response({"ok": False, "data": "No meals found with provided ids",'message':'error'}, status=status.HTTP_404_NOT_FOUND)

        # Assuming all selected meals are of the same meal_type
        meal_type = selected_meals[0].get("meal_type", "unknown")

        UserSelectedMeals.objects.create(
            meal_plan = meal_plan_obj,
            meal_type = meal_type,
            selected_meals_json = selected_meals
        )

        return Response({"ok": True, "data": "Meals saved", "message": 'successful'},status=status.HTTP_200_OK)






class MealGenerator(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        
        try:
            UserPreference.objects.get(user_id = request.user)
        except Exception:
            return Response({'ok':False,'error':'Please set the user preference first.'},status=status.HTTP_400_BAD_REQUEST)
        
        start_date_str = request.data.get('start_date')
        
        if not start_date_str:
            return Response(
                {'ok': False, 'error': 'start_date is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Parse string into date
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {'ok': False, 'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if start_date < timezone.now().date():
            return Response(
                {'ok': False, 'error': 'start_date cannot be in the past'},
                status=status.HTTP_400_BAD_REQUEST
            )

        time_duration = request.data.get('plan_duration')
        
        if time_duration == '1 weeks':
            time_duration = 7
        else:
            time_duration = 14

        # Add timedelta
        expiry_date = start_date + timedelta(days=time_duration)

        
        mealplan = MealPlan.objects.filter(
            user=request.user, 
            is_active = True,
            end_date__gte=timezone.now()
        ).first()  
        if mealplan:
            return Response(
                {
                    'ok': True,
                    'data': {
                        "message": f"You have already generated meals till {mealplan.end_date}"
                    }
                },
                status=status.HTTP_200_OK
            )
        
        if r.get(f"user:{request.user.id}:mealplan"):
            return Response({'ok':True,"data":"meals are generating please wait"},status=status.HTTP_200_OK)
        
        payload = {
            "user_id": request.user.id,
            "data": request.data
        }
        # Enqueue user
        r.rpush(USERQUEUE_LIST, json.dumps(payload))

        # Pick first user (FIFO)
        new_user = r.lpop(USERQUEUE_LIST)
        if new_user:
            new_user = json.loads(new_user)
            week_type = new_user['data'].get('plan_duration')
            start_date = new_user['data'].get('start_date')
            mealsperday = new_user['data'].get('mealsperday')
            user_id = new_user['user_id']

            total_days = 7 if week_type == '1 weeks' else 14
            data = {
                "total_days": total_days,
                "pending": total_days,
                "success": 0,
                "failed": 0,
                "meals": [],
                "exclusion_list": [],
                "odd_meals": [],       
                "even_meals": [], 
                "new_user": new_user
            }
            r.set(f"user:{user_id}:mealplan", json.dumps(data))

            userPreference = model_to_dict(
                UserPreference.objects.get(user_id = request.user),
                exclude=["created_at", "updated_at"]
            )
            preferences_json = json.dumps(userPreference)

            arr = []
            if total_days == 7:
                total_days_arr = [1, 3, 5, 7, 2, 4, 6]
            else:
                total_days_arr = [1, 3, 5, 7, 9, 11, 13, 2, 4, 6, 8, 10, 12, 14]

            
            for i in total_days_arr:
                thread_queue_job = {
                    "user_id": user_id,
                    "day_index": i,
                    "start_date": str(start_date),
                    "mealsperday": mealsperday,
                    "preferences_json": preferences_json,
                }
                r.rpush(THREADQUEUE_LIST, json.dumps(thread_queue_job))

            # Kick off queue manager.
            
            thread = threading.Thread(
                target = AddThreadToProcessingOrWaiting_worker,
                args=(request,),
                daemon = True
            )
            thread.start()
        

            
        # r.delete('processing_queue')
        # r.delete('waiting_queue')
        # r.delete('usersqueue_list')
        # r.delete('threadqueue_list')


        return Response(
            {
                "ok": True, 
                "data": {
                    "data":{
                        'week_type':week_type,
                        "start_date":start_date,
                        'expiry_date':expiry_date.date(),
                        "mealsperday":mealsperday
                    },
                    "message":"Meals are generating please wait."
                }
            },
            status=status.HTTP_201_CREATED
        )




# def AddThreadToProcessingOrWaiting(request):
#     while True:
        
#         # 1 Try waiting queue first
#         job = r.lpop(WAITING_QUEUE)

#         # 2️If waiting queue empty, pull from main threadqueue list
#         if not job:
#             new_job = r.lpop(THREADQUEUE_LIST)
#             if new_job:
#                 r.rpush(WAITING_QUEUE, new_job)
#             time.sleep(0.2)
#             continue

#         job_data = json.loads(job)
#         user_id = job_data["user_id"]
#         day_index = job_data['day_index']

#         # 3️ Check processing queue capacity
#         if r.llen(PROCESSING_QUEUE) < MAX_PROCESSING:
#             mealplan_key = f"user:{user_id}:mealplan"
#             mealplan_data = json.loads(r.get(mealplan_key))
#             success_count = mealplan_data.get('success', 0)
#             total_days = mealplan_data.get('total_days', 7)

#             print("success_count", success_count)
#             print("total_days", total_days)
#             odd_data = []

#             # 4️Odd/Even day handling
#             if request.user.id == user_id and day_index % 2 == 0:
#             # if day_index % 2 == 0:
                
#                 if success_count < (total_days // 2):
#                     print("success count is less than",total_days//2)
#                     r.rpush(WAITING_QUEUE, json.dumps(job_data))
#                     time.sleep(0.5)
#                     continue
                    
                
#                 # Even day: process only if odd days done
#                 odd_meals = mealplan_data.get("odd_meals", [])
#                 for m in odd_meals:
#                     if m['day']+1 == day_index:
#                         odd_data = m['meals']
#                         break
                

#             # 5️ Push to processing queue and submit
#             r.rpush(PROCESSING_QUEUE, json.dumps(job_data))
#             get_executor().submit(safe_generate_meals, job_data, odd_data)
#             print("sent for execution..")

#         else:
#             # 6️ Processing full → push back to waiting
#             r.rpush(WAITING_QUEUE, json.dumps(job_data))

#         print("PROCESSING_QUEUE size:", r.llen(PROCESSING_QUEUE))
#         print("WAITING_QUEUE size:", r.llen(WAITING_QUEUE))
#         time.sleep(0.5)  # throttle loop

# constants: WAITING_QUEUE, PROCESSING_QUEUE, THREADQUEUE_LIST, MAX_PROCESSING

def AddThreadToProcessingOrWaiting_worker(request):
    """
    Long-running worker. Use BRPOPLPUSH to atomically move a job from waiting -> processing.
    If waiting empty, try THREADQUEUE_LIST -> WAITING_QUEUE refill.
    """
    while True:
        print("PROCESSING_QUEUE size:", r.llen(PROCESSING_QUEUE))
        print("WAITING_QUEUE size:", r.llen(WAITING_QUEUE))
        # Ensure processing queue has capacity before pulling
        if r.llen(PROCESSING_QUEUE) >= MAX_PROCESSING:
            time.sleep(0.2)
            continue

        # If waiting empty, try to pull from THREADQUEUE_LIST and push into WAITING_QUEUE
        if r.llen(WAITING_QUEUE) == 0:
            new_job = r.lpop(THREADQUEUE_LIST)
            if new_job:
                r.rpush(WAITING_QUEUE, new_job)

        # Atomically pop from waiting and push into processing; blocks up to 1s
        job_json = r.brpoplpush(WAITING_QUEUE, PROCESSING_QUEUE, timeout=1)
        if not job_json:
            time.sleep(0.1)
            continue

        # Submit the job
        try:
            job_data = json.loads(job_json)
        except Exception:
            # malformed job; remove it from processing
            r.lrem(PROCESSING_QUEUE, 0, job_json)
            continue

        # Optional: parity/odd-even check BEFORE executing:
        user_id = job_data['user_id']
        day_index = job_data['day_index']

        # Load mealplan atomically or via HGET/HGETALL
        mealplan_raw = r.get(f"user:{user_id}:mealplan")
        if not mealplan_raw:
            # nothing to do – cleanup processing slot
            r.lrem(PROCESSING_QUEUE, 0, job_json)
            continue

        mealplan = json.loads(mealplan_raw) if isinstance(mealplan_raw, str) else json.loads(mealplan_raw.decode('utf-8'))

        # Even-day logic: if day is even and odd prerequisites not met -> push back to waiting
        if day_index % 2 == 0:
            # how many odd days expected:
            odd_needed = mealplan['total_days'] // 2
            if mealplan.get('success', 0) < odd_needed:
                # move job back to waiting (atomically remove from processing then push to waiting)
                r.lrem(PROCESSING_QUEUE, 0, job_json)
                r.rpush(WAITING_QUEUE, job_json)
                time.sleep(0.2)
                continue

        # All checks pass -> submit to executor
        get_executor().submit(safe_generate_meals, job_data, [])  # pass exclusion if needed








def safe_generate_meals(job_data,exclusion_list):
    """Wrap generate_day_meals with cleanup + user tracking"""

    generate_day_meals(
        r,
        job_data["user_id"],
        job_data["day_index"],
        datetime.fromisoformat(job_data["start_date"]),
        job_data["mealsperday"],
        job_data["preferences_json"],
        exclusion_list  
    )
   

def get_executor():
    global executor
    if executor._shutdown:   
        executor = ThreadPoolExecutor(max_workers=8)
    return executor





class GetGeneratedPlan(APIView):
    permission_classes = [IsAuthenticated]

    VALID_MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"]

    def get(self, request):
        start_date = request.GET.get("start_date")
        meal_type = request.GET.get("meal_type")

        # Validate required params
        if not start_date:
            return Response({'ok':False, "error": "start_date is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not meal_type:
            return Response({'ok':False, "error": "meal_type is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate meal_type
        if meal_type not in self.VALID_MEAL_TYPES:
            return Response(
                {'ok':False, "error": f"Invalid meal_type. Allowed values: {', '.join(self.VALID_MEAL_TYPES)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate date format
        try:
            parsed_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Invalid start_date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch meal plan
        print(parsed_date)
        meal_plan = (
            MealPlan.objects.filter(user=request.user, start_date=parsed_date)
            .order_by("-created_at")
            .first()
        )
        if meal_plan.meals_per_day == 1:
            if meal_type not in  ["dinner"]:
                return Response({"ok":False,"error":f"Meal type should be dinner"},status=status.HTTP_400_BAD_REQUEST)

        if meal_plan.meals_per_day == 2:
            if meal_type not in ['dinner', 'lunch']:
                return Response({'ok':False,'error':'Meal type should be lunch or dinner'},status=status.HTTP_400_BAD_REQUEST)
        
        if meal_plan.meals_per_day == 3:
            if meal_type not in ['breakfast','lunch','dinner']:
                return Response({'ok':False,'error':'Meal type should be breakfast,lunch or dinner'},status=status.HTTP_400_BAD_REQUEST)

        if not meal_plan:
            return Response({"ok": False, "error": "Meal plan does not exist."}, status=status.HTTP_404_NOT_FOUND)

        if not meal_plan.generated_meals:
            return Response({"ok": False, "error": "No meals generated for this plan."}, status=status.HTTP_404_NOT_FOUND)

        meals = []
        for meal in meal_plan.generated_meals:
            if (
                (meal_type == "breakfast" and meal.get("is_breakfast"))
                or (meal_type == "lunch" and meal.get("is_lunch"))
                or (meal_type == "dinner" and meal.get("is_dinner"))
                or (meal_type == "snack" and meal.get("is_eveningsnack"))
            ):
                if not meal.get('media_id'):
                    meal['signed_url']= None
                    meals.append(meal)

                else:
                    url = f"{os.getenv('S3BUCKETUAPI')}/signed-url/{meal.get('media_id')}?time_in_sec=3600"
                    response = requests.get(url, timeout=5)

                    if response.status_code == 200:
                        data = response.json()
                        url = data.get("data", {}).get("downloadUrl")
                        meal['signed_url']= url
                        meals.append(meal)

        return Response({"ok": True, "data": meals}, status=status.HTTP_200_OK)


class SaveChanges(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        meals_info = request.data.get('meals_info')

        if not meals_info:
            return Response({'ok': False, 'error': 'meals_info is required.'},
                            status=status.HTTP_400_BAD_REQUEST)


        for item in meals_info:
            date = item.get("date")
            ids = item.get("ids", [])

            if not date or not ids:
                continue

            try:
                meal_plan = MealPlan.objects.get(user=request.user,is_active=True, start_date=date)
            except MealPlan.DoesNotExist:
                continue            
            # Filter only selected meals
            updated_meals = [
                meal for meal in meal_plan.generated_meals if meal["id"] in ids
            ]

            print(updated_meals)
            for meal in updated_meals:
                # ---------- Save Recipe ----------
                cooking_time_str = meal.get("cooking_time", "0 minutes")
                try:
                    minutes = int(cooking_time_str.split()[0])
                except:
                    minutes = 0
                cooking_time = timedelta(minutes=minutes)

                recipe,_ = Recipe.objects.get_or_create(
                    title=meal["title"],
                    defaults={
                        "description": meal.get("description", ""),
                        "instructions": meal.get("instructions", ""),
                        "cooking_time": cooking_time,
                        "calories": meal.get("calories"),
                        "fat": meal.get("fat"),
                        "carbohydrates": meal.get("carbohydrates"),
                        "media_id":meal.get('media_id'),
                        "protein": meal.get("protein"),
                        "vitamins": meal.get("vitamins"), 
                        "media_id":meal.get('media_id'),
                        "is_vegetarian": meal.get("is_vegetarian", False),
                        "is_spicy": meal.get("is_spicy", False),
                        "cuisine": meal.get("cuisine"),
                        "flavor_profile": meal.get("flavor_profile"),
                        "quantity": meal.get("quantity", 1),
                    }
                )

                # # Save image if created
                # if created and meal.get("image_url"):
                #     resp = requests.get(meal["image_url"])
                #     if resp.status_code == 200:
                #         recipe.image.save(
                #             f"{recipe.id}.jpg",
                #             ContentFile(resp.content),
                #             save=True
                #         )

                # ---------- Save Ingredients ----------
                ingredients = meal.get("ingredients", [])
                quantities = meal.get("ingredients_quantity", [])

                for name, qty in zip(ingredients, quantities):
                    ingredient = Ingredient.objects.create(name=name)
                    RecipeIngredient.objects.create(
                        recipe = recipe,
                        ingredient =ingredient,
                        quantity = qty
                    )

                # ---------- Create Meal ----------
                # meal_type = meal.get("meal_type", "breakfast")  
                
                if meal.get('is_breakfast') == True:
                    meal_type = 'breakfast'
                
                elif meal.get('is_lunch') == True:
                    meal_type = 'lunch'
                
                elif meal.get('is_dinner') == True:
                    meal_type = 'dinner'

                else:
                    meal_type = "snack"
                
                existing_meal = Meal.objects.filter(
                    meal_plan=meal_plan,
                    date=date,
                    meal_type=meal_type,
                    recipe=recipe
                ).first()

                if existing_meal:
                    # Already added
                    continue  

                Meal.objects.create(
                    meal_plan=meal_plan,
                    date=date,
                    meal_type=meal_type,
                    recipe = recipe 
                )


        return Response(
            {"ok": True, "data": {"message":"Meals saved successfully"}},
            status=status.HTTP_200_OK
        )

class ProgressBarMeals(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get all active mealplans (in case there are multiple)
        mealplans = MealPlan.objects.filter(user=request.user, is_active=True).order_by('start_date').values_list('id',flat=True)
        # If no active meal plan exists
        if not mealplans:
            return Response(
                {
                    "ok": True,
                    "data": {
                        "progress": 0,
                        "mealsperday": 0,
                        "plan_duration": None,
                        "total_meals": 0,
                        "saved_meals": 0,
                        "start_date": None
                    },
                    "message": "No active meal plan found."
                },
                status=status.HTTP_200_OK
            )
        # Count meals linked to these mealplans
        completed_meals = Meal.objects.filter(meal_plan__in=mealplans).count()

        mealsplanobj = MealPlan.objects.get(id = mealplans[0])        
        if mealsplanobj.plan_duration == '1 weeks':
            total_days = 7
        else:
            total_days = 14
        
        mealsperday = mealsplanobj.meals_per_day
        total_meals = total_days*mealsperday

        progress = (completed_meals/total_meals)*100

        return Response(
            {
                'ok': True,
                'data': {
                'progress' :progress,
                "mealsperday":mealsplanobj.meals_per_day,
                "plan_duration":mealsplanobj.plan_duration,
                "total_meals":total_meals,
                "saved_meals":completed_meals,
                "start_date":mealsplanobj.start_date


            }
        },
        status=status.HTTP_200_OK)


class IsActiveMeal(APIView):
    permission_classes = [IsAuthenticated]

    def get(self,request):
        active_meal_plan = MealPlan.objects.filter(user=request.user, is_active=True).first()
        print(active_meal_plan)
        if not active_meal_plan:
            return Response({'ok':False,'error':False},status=status.HTTP_400_BAD_REQUEST)
        return Response({'ok':True,'data':True})
    
class GetRecipes(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        generate_date = request.GET.get('generated_date_meal')

        if not generate_date:
            return Response(
                {"ok": False, "error": "generate_date is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        meals = Meal.objects.filter(
            meal_plan__user=request.user,  
            date=generate_date
        )
        serializer = GetRecipesSerializer(meals, many=True)
        return Response(
            {"ok": True, "data": serializer.data},
            status=status.HTTP_200_OK
        )

class MissingIngredients(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        print(user.id)

        meals = Meal.objects.filter(
            meal_plan__user=user,
            is_completed=False
        ).select_related('recipe')
        # .prefetch_related('recipe__recipeingredient_set__ingredient')

        recipe_ingredients = []

        for meal in meals:
            for ri in meal.recipe.recipeingredient_set.all():
                recipe_ingredients.append({
                    "name": ri.ingredient.name,
                    "quantity_required": ri.quantity
                })

        missing_ingredients = []

        for recipe_ing in recipe_ingredients:
            pantry_item = PantryItem.objects.filter(
                user=request.user,
                ingredient__name__iexact=recipe_ing["name"]  
            ).first()

            if not pantry_item or pantry_item.quantity_available < recipe_ing["quantity_required"]:
                missing_ingredients.append({
                    "name": recipe_ing["name"],
                    "required_quantity": recipe_ing["quantity_required"],
                    "available_quantity": pantry_item.quantity_available if pantry_item else 0
                })

        return Response({'ok':True,'data':missing_ingredients},status=status.HTTP_200_OK)


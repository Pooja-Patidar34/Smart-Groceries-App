import os
import threading
from datetime import timedelta,datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests, json, re
from meal_planner.models import MealPlan
from accounts.models import User
from django.utils import timezone

lock = threading.Lock()   

from celery import shared_task



@shared_task
def task_add_images_to_meals(meal_plan_ids):
    from io import BytesIO
    import uuid
    from .utils import getUnsplashImages
    from dotenv import load_dotenv
    load_dotenv()
    for meal_plan_id in meal_plan_ids:
        try:
            meal_plan = MealPlan.objects.get(id=meal_plan_id)
            meals = meal_plan.generated_meals  

            for recipe in meals:
                
                # Step 1: Get Unsplash image
                image_url = getUnsplashImages({
                    "title": recipe.get("title", ""),
                    "description": recipe.get("description", ""),
                    "cuisine": recipe.get("cuisine", ""),
                    "is_breakfast": recipe.get("is_breakfast", False),
                    "is_lunch": recipe.get("is_lunch", False),
                    "is_eveningsnack": recipe.get("is_eveningsnack", False),
                    "is_dinner": recipe.get("is_dinner", False),
                })
                if not image_url:
                    continue
                # pick the first image URL (or handle multiple if needed)
                if isinstance(image_url, list):
                    if image_url:

                        image_url = image_url[0]
                else:
                    image_url = image_url
                

                if image_url:

                    img_response = requests.get(image_url, stream=True)
                    if img_response.status_code == 200:
                        file_name = f"{uuid.uuid4()}.jpg"
                        file_content = BytesIO(img_response.content)  
                        
                        files = {
                            "file": (file_name, file_content, "image/jpeg")
                        }

                        api_url = os.getenv("S3BUCKETUAPI")
                        response = requests.post(api_url, files=files)

                        if response.status_code == 200:
                            data = response.json()
                            url = data.get("data", {}).get("downloadUrl")
                            media_id = data.get("data", {}).get("mediaId", {}).get("id")

                            print("media_id:", media_id)
                            recipe['media_id'] = media_id
                            recipe['image_url'] = url  
                        else:
                            print("Failed to upload image to S3 for recipe:", recipe.get("title"))



            # Step 3: Save updated meals with Supabase URLs
            meal_plan.generated_meals = meals
            meal_plan.save()
        except MealPlan.DoesNotExist:
            continue


@shared_task
def deactivate_expired_mealplans():
    today = timezone.localdate()  # Current date
    expired_plans = MealPlan.objects.filter(is_active=True, end_date__lt=today)
    count = expired_plans.update(is_active=False)
    return f"{count} meal plans deactivated."

import os
import uuid
from django.core.mail import send_mail
import threading
from datetime import timedelta,datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests, json, re
from notifications.models import Notification, UserFCMToken
from notifications.utils import send_fcm_notification
from pantry_section.models import PantryItem
from .models import *
from django.conf import settings
lock = threading.Lock()   
import time
from django.utils.timezone import now
from .tasks import task_add_images_to_meals
from dotenv import load_dotenv
load_dotenv()


def generate_day_meals(r, user_id, day_offset, start_date, mealsperday, preferences_json, exclusion_list):
    """
    Generates meal recipes for a specific day using OpenAI API.
    Ensures exact counts per meal type:
    - 4 meals/day → 12 recipes (3 breakfast, 3 lunch, 3 snack, 3 dinner)
    - 3 meals/day → 9 recipes (3 breakfast, 3 lunch, 3 dinner)
    - 2 meals/day → 6 recipes (3 lunch, 3 dinner)
    - 1 meal/day  → 3 recipes (3 dinner)
    """
    try:
        # --- Setup ---
        date = (start_date + timedelta(days=day_offset - 1)).date().isoformat()
# --- Fetch expiring pantry items ---
        # from datetime import datetime, timedelta
        # from django.utils.timezone import now

        expiring_items = PantryItem.objects.filter(
            user_id=user_id,
            expiry_date__gte=now().date(),  # not expired
            expiry_date__lte=now().date() + timedelta(days=3)  # expiring within 3 days
        ).select_related("ingredient")

        expiring_ingredients = [item.ingredient.name for item in expiring_items]

        meal_config = {
            4: {
                "expected_count": 12,
                "categories": [
                    ("Breakfast", "is_breakfast", True),
                    ("Lunch", "is_lunch", True),
                    ("Evening Snack", "is_eveningsnack", True),
                    ("Dinner", "is_dinner", True),
                ],
            },
            3: {
                "expected_count": 9,
                "categories": [
                    ("Breakfast", "is_breakfast", True),
                    ("Lunch", "is_lunch", True),
                    ("Dinner", "is_dinner", True),
                ],
            },
            2: {
                "expected_count": 6,
                "categories": [
                    ("Lunch", "is_lunch", True),
                    ("Dinner", "is_dinner", True),
                ],
            },
            1: {
                "expected_count": 3,
                "categories": [
                    ("Dinner", "is_dinner", True),
                ],
            },
        }

        config = meal_config.get(mealsperday)
        if not config:
            raise ValueError(f"Invalid mealsperday: {mealsperday}")

        expected_count = config["expected_count"]
        id_start = (day_offset * expected_count) + 1

        # --- Build exclusion text ---
        exclusion_text = ""
        if exclusion_list:
            exclusion_text = (
                f"- Absolutely no recipe title should be repeated from this exclusion list: {exclusion_list}.\n"
                f"- If any recipe conflicts, replace it with a new unique one.\n"
                f"- Output must always contain exactly {expected_count} recipes.\n"
            )

        # --- Build category instructions ---
        category_lines = []
        for name, field, include in config["categories"]:
            if include:
                category_lines.append(f"- 3 {name} ({field} true)")
            else:
                category_lines.append(f"- No {name} ({field} false)")

        # --- Prompt ---
        expiring_text = ""
        if expiring_ingredients:
            expiring_text = (
                f"\n- Prioritize using these ingredients as they will expire soon: "
                f"{', '.join(expiring_ingredients)}.\n"
                f"- Try to include at least one expiring ingredient in each meal if possible.\n"
                f"- Avoid using expired or unrelated ingredients.\n"
            )
        prompt = f"""
        You MUST generate exactly {expected_count} meals for {date}.
        {chr(10).join(category_lines)}
        - No recipe should belong to more than one category.

        Do NOT use vague or qualitative quantities such as:
        "to taste", "as needed", "optional", "few", "pinch", "dash", or "some".
        
        Only use measurable quantities with numbers and units 
        like "1 tsp", "2 tbsp", "100g", "1 cup", "3 slices", "250 ml", etc.

        User preferences: {preferences_json}
        {exclusion_text}
        {expiring_text}
        """
        # ---- Payload with schema ----
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a helpful meal planner."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "meal_plan",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "recipes": {
                                "type": "array",
                                "minItems": expected_count,
                                "maxItems": expected_count,
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "integer"},
                                        "date": {"type": "string", "format": "date"},
                                        "title": {"type": "string"},
                                        "image_url": {
                                        "type": "string",
                                        "nullable": True
                                        },


                                        "description": {"type": "string"},
                                        "instructions": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "Step-by-step instructions for preparing the recipe."
                                        },
                                        "cooking_time": {"type": "string"},
                                        "calories": {"type": "integer"},
                                        "fat": {"type": "integer"},
                                        "carbohydrates": {"type": "integer"},
                                        "fiber": {"type": "integer"},
                                        "diet tags": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "Tags for images"
                                        },
                                        "protein": {"type": "integer"},
                                        "vitamins": {"type": "string"},
                                        "is_vegetarian": {"type": "boolean"},
                                        "is_spicy": {"type": "boolean"},
                                        "is_breakfast": {"type": "boolean"},
                                        "is_lunch": {"type": "boolean"},
                                        "is_eveningsnack": {"type": "boolean"},
                                        "is_dinner": {"type": "boolean"},
                                        "cuisine": {"type": "string"},
                                        "flavor_profile": {"type": "string"},
                                        "ingredients": {
                                            "type": "array",
                                            "items": {"type": "string"}
                                        },
                                        "ingredients_quantity": {
                                            "type": "array",
                                            "items": {"type": "string"}
                                        }
                                    },
                                    "required": [
                                        "id","date","title","description","instructions",
                                        "cooking_time","calories","fat","carbohydrates",
                                        "protein","vitamins","is_vegetarian","is_spicy",
                                        "is_breakfast","is_lunch","is_eveningsnack",
                                        "is_dinner","cuisine","flavor_profile",
                                        "ingredients","ingredients_quantity"
                                    ]
                                }
                            }
                        },
                        "required": ["recipes"],
                    }
                }
            }
        }

        # ---- API call ----
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {os.getenv('GPT_API_KEYS')}",
            "Content-Type": "application/json"
        }
        res = requests.post(url, json=payload, headers=headers)
        if res.status_code != 200:
            print(f"[ERROR] API failed for {date}")
            

        try:
            # content = res.json()['choices'][0]['message']['content']
            # cleaned = re.sub(r'^```(?:json)?\n|\n```$', '', content.strip())
            # meals = json.loads(cleaned)
            content = res.json()['choices'][0]['message']
            if "parsed" in content:
                meals = content["parsed"]["recipes"]
            else:
                meals = json.loads(content["content"])["recipes"]

        except Exception as e:
            print(f"[ERROR] JSON decode failed for {date}")
            

        if isinstance(meals, dict) and "recipes" in meals:
            meals = meals["recipes"]



        # ---- Filter duplicates ----
        unique_meals, new_titles = [], []
        for idx, meal in enumerate(meals, start=id_start):
            title = meal["title"].strip().lower()
            # if title not in exclusion_set and title not in new_titles:
            meal["id"] = idx 
            unique_meals.append(meal)
            new_titles.append(title)
        
        # if len(unique_meals) != expected_count:
        #     print(f"[RETRY] Got {len(unique_meals)} instead of {expected_count}")
        #     generate_day_meals(r, user_id, day_offset, start_date, mealsperday, preferences_json, exclusion_list)

    
    except Exception as e:
        print(e)
        user_data = r.get(f"user:{user_id}:mealplan")

        if user_data:
            # If client returns str → directly load
            if isinstance(user_data, str):
                user_data = json.loads(user_data)
            else:  # if bytes → decode first
                user_data = json.loads(user_data.decode("utf-8"))

            # user_data = json.loads(user_data.decode("utf-8"))  # decode + load

            # Safe updates with defaults
            user_data['failed'] = user_data.get('failed') + 1

            # Save back to Redis
            r.set(f"user:{user_id}:mealplan", json.dumps(user_data))
            r.rpush('processing_queue', json.dumps(user_data))
        # print(e)

        # # Atomic update on failure
        # r.hincrby(f"user:{user_id}:mealplan", "failed", 1)
        # r.rpush("processing_queue", f"user:{user_id}:mealplan")


    else:
        expected_count = meal_config.get(mealsperday, {}).get('expected_count', 0)
        unique_meals = validate_and_fix(unique_meals,mealsperday, expected_count)
        # if len(unique_meals) == expected_count:
        user_data = r.get(f"user:{user_id}:mealplan")

        if user_data:
            # If client returns str → directly load
            if isinstance(user_data, str):
                user_data = json.loads(user_data)
            else:  # if bytes → decode first
                user_data = json.loads(user_data.decode("utf-8"))


            meal_plan = MealPlan.objects.create(
                user_id = user_id,  
                start_date = date,
                end_date = (
                    datetime.fromisoformat(user_data['new_user']['data'].get('start_date'))
                    + timedelta(days=user_data['total_days'] - 1)
                ).date(),
                budget = user_data['new_user']['data'].get('budget'),
                plan_duration = user_data['new_user']['data'].get('plan_duration'),
                meals_per_day = user_data['new_user']['data'].get('mealsperday'),
                generated_meals = unique_meals
            )
            # Safe updates with defaults
            user_data['success'] = user_data.get('success') + 1
            user_data['pending'] = user_data.get('pending') - 1

            user_data.setdefault('meals', []).append(unique_meals)
            user_data.setdefault("odd_meals", []).append({
                "day": day_offset,
                "meals": new_titles
            })
            user_data.setdefault('exclusion_list', []).extend(new_titles)

            # Save back to Redis
            r.set(f"user:{user_id}:mealplan", json.dumps(user_data))
            
            task_add_images_to_meals.delay([meal_plan.id])
            r.lpop('processing_queue')
            # if user_data['success']==user_data['total_days']:
            #     r.lpop('usersqueue_list')
            print(f"[OK] {date}: generated {len(unique_meals)} unique meals")
            return {"date": date, "meals": unique_meals, "titles": new_titles}
        
        # meal_plan = MealPlan.objects.create(
        #     user_id=user_id,
        #     start_date=date,
        #     end_date=(
        #         datetime.fromisoformat(r.hget(f"user:{user_id}:mealplan", "start_date").decode("utf-8"))
        #         + timedelta(days=int(r.hget(f"user:{user_id}:mealplan", "total_days")) - 1)
        #     ).date(),
        #     budget=r.hget(f"user:{user_id}:mealplan", "budget").decode("utf-8"),
        #     plan_duration=r.hget(f"user:{user_id}:mealplan", "plan_duration").decode("utf-8"),
        #     meals_per_day=r.hget(f"user:{user_id}:mealplan", "mealsperday").decode("utf-8"),
        #     generated_meals=unique_meals
        # )

        # # ✅ Atomic counters
        # r.hincrby(f"user:{user_id}:mealplan", "success", 1)
        # r.hincrby(f"user:{user_id}:mealplan", "pending", -1)

        # # ✅ Atomic list updates
        # r.rpush(f"user:{user_id}:meals", json.dumps(unique_meals))
        # r.rpush(f"user:{user_id}:odd_meals", json.dumps({"day": day_offset, "meals": new_titles}))
        # r.rpush(f"user:{user_id}:exclusion_list", *new_titles)

        # task_add_images_to_meals.delay([meal_plan.id])
        # print(f"[OK] {date}: generated {len(unique_meals)} unique meals")
        # return {"date": date, "meals": unique_meals, "titles": new_titles}




    finally:
            # Free slot from processing queue
            r.lpop('processing_queue')

            # Check user status
            user_data = r.get(f"user:{user_id}:mealplan")
            if user_data:
                user_data = json.loads(user_data)
                total = user_data["total_days"]
                done = user_data["success"] + user_data["failed"]

                if done == total:  # All jobs finished
                    if user_data["failed"] > 0:
                        # Re-enqueue the user for retry
                        print(f"[RETRY] User {user_id} had {user_data['failed']} failed jobs. Re-enqueuing...")
                        r.rpush('processing_queue', json.dumps(user_data))
                    else:
                        r.delete(f"user:{user_id}:mealplan")

                        try:
                            # Notification.objects.create(
                            #             user=item.user,
                            #             type=notif_type,
                            #             message=(
                            #                 f"Your {item.name} will expire in {days_left} days."
                            #                 if days_left > 0 else f"Your {item.ingredient.name} has expired."
                            #             )
                            #         )
                            #     send_fcm_notification(sub.user, "Pantry Alert", notif_type)
                            user = User.objects.get(id=user_id)
                            Notification.objects.create(
                                user = user,
                                message = 'Your Meals are successfully generated.',
                                type = 'Meals Notification'
                            )

                            send_mail(
                                subject='Meal preparation Done.',
                                message=f'Delicious Meals are waiting for you.',
                                from_email=settings.EMAIL_HOST_USER,
                                recipient_list=[user.email],
                                fail_silently=False,
                            )
                            tokens = UserFCMToken.objects.filter(user = user).values_list('token',flat=True)
                            send_fcm_notification(tokens, "Meals Notification","Your Meals are successfully generated.")
                            print(f"[DONE] User {user_id} completed successfully.")
                        except Exception as e:
                            print(e)
                        
            # r.lpop("processing_queue")

            # # Final completion check
            # total = int(r.hget(f"user:{user_id}:mealplan", "total_days") or 0)
            # success = int(r.hget(f"user:{user_id}:mealplan", "success") or 0)
            # failed = int(r.hget(f"user:{user_id}:mealplan", "failed") or 0)

            # if success + failed == total:
            #     if failed > 0:
            #         print(f"[RETRY] User {user_id} had {failed} failed jobs. Re-enqueuing...")
            #         r.rpush("processing_queue", f"user:{user_id}:mealplan")
            #     else:
            #         print(f"[DONE] User {user_id} completed successfully")



import random

counter = 0

def build_unsplash_query(title, cuisine=None, meal_type=None):
    """
    Build a better query string for Unsplash to get food-specific images.
    """
    query = f"{title} Recipe for {meal_type}"
    return query.strip()


def getUnsplashImages(meal, num_images = 5):
    """
    Get multiple Unsplash images for a meal.
    Tries title+cuisine+meal_type first, then falls back if needed.
    """
    global counter
    counter += 1
    if counter >= 50:   
        return []

    access_key = os.getenv('UNSPLASH_ACCESS_KEY')
    url = os.getenv('UNSPLASH_URL')

    # 🔹 Build primary query
    title = meal.get("title", "")
    cuisine = meal.get("cuisine", "")
    meal_type = (
        "breakfast" if meal.get("is_breakfast") else
        "lunch" if meal.get("is_lunch") else
        "snack" if meal.get("is_eveningsnack") else
        "dinner" if meal.get("is_dinner") else ""
    )
    query = build_unsplash_query(title, cuisine, meal_type)
    print(query)
    params = {
        "query": query,
        "page": 1,
        "per_page": num_images,  
        "order_by": "relevant",
        "orientation": "squarish",   
        "content_filter": "high",
        "lang": "en"
    }
    headers = {"Authorization": f"Client-ID {access_key}"}
    results = []
    r = requests.get(url, params=params, headers=headers)

    if r.status_code == 200:
        data = r.json()
        results = data.get("results", [])
        if results:
            results =  [res["urls"]["regular"] for res in results[:num_images]]
    return suggest_best_images(meal,results)


import os
import requests
import json
import time

def call_openai_api(prompt, max_retries=5, retry_delay=2):
    """
    Calls OpenAI ChatCompletion API via HTTP and returns a parsed JSON list.
    Retries if the response is invalid.
    """
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {os.getenv('GPT_API_KEYS')}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 1200
    }

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # GPT reply content
            content = data["choices"][0]["message"]["content"]

            # Extract JSON array from the response
            import re
            match = re.search(r'(\[.*\])', content, re.DOTALL)
            if match:
                parsed = json.loads(match.group(1))
                if isinstance(parsed, list):
                    return parsed
                else:
                    raise ValueError("GPT returned JSON but it's not a list.")
            else:
                raise ValueError("No JSON array found in GPT response.")

        except (requests.RequestException, ValueError, json.JSONDecodeError) as e:
            print(f"❌ Attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                time.sleep(retry_delay)
            else:
                raise RuntimeError(f"Failed to get valid JSON from GPT after {max_retries} attempts.")

    return []


from collections import defaultdict

config = {
    "categories": ["breakfast", "lunch", "dinner", "eveningsnack"]
}

def validate_and_fix(meals,mealsperday ,expected_count=12):
    category_count = defaultdict(list)

    # Group meals by boolean flags
    for m in meals:
        for cat in config["categories"]:
            if m.get(f"is_{cat}", False):  
                category_count[cat].append(m)

    fixed_meals = []

    for cat in config["categories"]:
        items = category_count.get(cat, [])

        if len(items) < 3:
            # Missing meals → regenerate
            missing = 3 - len(items)
            print(f"⚠️ {cat} missing {missing}, calling GPT...")
            if mealsperday == 1:
                if cat == 'dinner':

                    extra_meals = call_openai_api(
                        f"""
                        Generate {missing} unique {cat} recipes in JSON.
                        Each recipe must include these fields:
                        - id (integer, auto-increment or random unique number)
                        - title (string)
                        - description (string)
                        - cuisine (string, e.g. Italian, Indian)
                        - calories (integer)
                        - protein (integer)
                        - fat (integer)
                        - carbohydrates (integer)
                        - vitamins (string, comma-separated)
                        - is_breakfast, is_lunch, is_dinner, is_eveningsnack 
                        (set only "is_{cat}" = true, all others = false)
                        - is_spicy (boolean)
                        - is_vegetarian (boolean)
                        - flavor_profile (string)
                        - image_url (null or a placeholder string)
                        - date (today's date in YYYY-MM-DD format)
                        - ingredients (list of ingredient names)
                        - ingredients_quantity (list of quantities, same length as ingredients)
                        - cooking_time (string, e.g. "20 minutes")
                        - instructions (array of strings, each representing one step)
                        
                        Do NOT use vague or qualitative quantities such as:
                        "to taste", "as needed", "optional", "few", "pinch", "dash", or "some".
                        
                        Only use measurable quantities with numbers and units 
                        like "1 tsp", "2 tbsp", "100g", "1 cup", "3 slices", "250 ml", etc.
                        
                        Output must be a strict JSON array of {missing} objects.
                        """
                    )


                    items.extend(extra_meals[:missing])
            elif mealsperday == 2:
                if cat in ['lunch','dinner']:
                    extra_meals = call_openai_api(
                        f"""
                        Generate {missing} unique {cat} recipes in JSON.
                        Each recipe must include these fields:
                        - id (integer, auto-increment or random unique number)
                        - title (string)
                        - description (string)
                        - cuisine (string, e.g. Italian, Indian)
                        - calories (integer)
                        - protein (integer)
                        - fat (integer)
                        - carbohydrates (integer)
                        - vitamins (string, comma-separated)
                        - is_breakfast, is_lunch, is_dinner, is_eveningsnack 
                        (set only "is_{cat}" = true, all others = false)
                        - is_spicy (boolean)
                        - is_vegetarian (boolean)
                        - flavor_profile (string)
                        - image_url (null or a placeholder string)
                        - date (today's date in YYYY-MM-DD format)
                        - ingredients (list of ingredient names)
                        - ingredients_quantity (list of quantities, same length as ingredients)
                        - cooking_time (string, e.g. "20 minutes")
                        - instructions (array of strings, each representing one step)

                        Do NOT use vague or qualitative quantities such as:
                        "to taste", "as needed", "optional", "few", "pinch", "dash", or "some".
                        
                        Only use measurable quantities with numbers and units 
                        like "1 tsp", "2 tbsp", "100g", "1 cup", "3 slices", "250 ml", etc.

                        Output must be a strict JSON array of {missing} objects.
                        """
                    )
                    items.extend(extra_meals[:missing])
            elif mealsperday == 3:
                if cat in ['breakfast','lunch','dinner']:
                    extra_meals = call_openai_api(
                        f"""
                        Generate {missing} unique {cat} recipes in JSON.
                        Each recipe must include these fields:
                        - id (integer, auto-increment or random unique number)
                        - title (string)
                        - description (string)
                        - cuisine (string, e.g. Italian, Indian)
                        - calories (integer)
                        - protein (integer)
                        - fat (integer)
                        - carbohydrates (integer)
                        - vitamins (string, comma-separated)
                        - is_breakfast, is_lunch, is_dinner, is_eveningsnack 
                        (set only "is_{cat}" = true, all others = false)
                        - is_spicy (boolean)
                        - is_vegetarian (boolean)
                        - flavor_profile (string)
                        - image_url (null or a placeholder string)
                        - date (today's date in YYYY-MM-DD format)
                        - ingredients (list of ingredient names)
                        - ingredients_quantity (list of quantities, same length as ingredients)
                        - cooking_time (string, e.g. "20 minutes")
                        - instructions (array of strings, each representing one step)

                        Do NOT use vague or qualitative quantities such as:
                        "to taste", "as needed", "optional", "few", "pinch", "dash", or "some".
                        
                        Only use measurable quantities with numbers and units 
                        like "1 tsp", "2 tbsp", "100g", "1 cup", "3 slices", "250 ml", etc.

                        Output must be a strict JSON array of {missing} objects.
                        """
                    )
                    items.extend(extra_meals[:missing])
            else:
                extra_meals = call_openai_api(
                        f"""
                        Generate {missing} unique {cat} recipes in JSON.
                        Each recipe must include these fields:
                        - id (integer, auto-increment or random unique number)
                        - title (string)
                        - description (string)
                        - cuisine (string, e.g. Italian, Indian)
                        - calories (integer)
                        - protein (integer)
                        - fat (integer)
                        - carbohydrates (integer)
                        - vitamins (string, comma-separated)
                        - is_breakfast, is_lunch, is_dinner, is_eveningsnack 
                        (set only "is_{cat}" = true, all others = false)
                        - is_spicy (boolean)
                        - is_vegetarian (boolean)
                        - flavor_profile (string)
                        - image_url (null or a placeholder string)
                        - date (today's date in YYYY-MM-DD format)
                        - ingredients (list of ingredient names)
                        - ingredients_quantity (list of quantities, same length as ingredients)
                        - cooking_time (string, e.g. "20 minutes")
                        - instructions (array of strings, each representing one step)

                        Do NOT use vague or qualitative quantities such as:
                        "to taste", "as needed", "optional", "few", "pinch", "dash", or "some".
                        
                        Only use measurable quantities with numbers and units 
                        like "1 tsp", "2 tbsp", "100g", "1 cup", "3 slices", "250 ml", etc.
                        
                        Output must be a strict JSON array of {missing} objects.
                        """
                    )
                items.extend(extra_meals[:missing])
        elif len(items) > 3:
            # Too many → trim
            items = items[:3]

        fixed_meals.extend(items)

    # Safety trim
    if len(fixed_meals) > expected_count:
        fixed_meals = fixed_meals[:expected_count]

    return fixed_meals

def suggest_best_images(recipe: dict, image_urls: list):
    """
    Given recipe details and candidate image URLs, ask GPT to select the best matching images.
    Uses OpenAI's REST API directly.
    """
    prompt = f"""
    You are a food expert and image evaluator.

    Task:
    - Analyze the given recipe details.
    - Evaluate each candidate image URL based on how well it represents the dish.
    - Assign a relevance score (1-10) to each image, where 10 = perfect match.
    - Return only the image URL with the **highest score**.
    - Also include a short reason for why it best matches.

    Format your response as JSON:
    {{
      "best_image": "<single URL>",
      "reason": "<short explanation>",
      "rankings": [
        {{ "url": "<url1>", "score": <int> }},
        {{ "url": "<url2>", "score": <int> }},
        ...
      ]
    }}

    ---

    Recipe:
    Title: {recipe.get("title")}
    Cuisine: {recipe.get("cuisine")}
    Meal type: {"breakfast" if recipe.get("is_breakfast") else "lunch" if recipe.get("is_lunch") else "snack" if recipe.get("is_eveningsnack") else "dinner" if recipe.get("is_dinner") else ""}
    Description: {recipe.get("description")}


    Candidate Images:
    {image_urls}
    """

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {os.getenv('GPT_API_KEYS')}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a food expert and image-matching assistant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4
    }

    res = requests.post(url, headers=headers, json=payload)

    if res.status_code != 200:
        return {"best_images": [], "reason": f"Error: {res.status_code}, {res.text}"}

  
    reply = res.json()["choices"][0]["message"]["content"]

    # Strip code fences if present
    if reply.startswith("```"):
        reply = reply.strip("```").replace("json", "", 1).strip()

    try:
        data = json.loads(reply)  
        print(data)
        best_images = data.get("best_image", [])
        print("best_image:",best_images)
        print("ANIL")
        if best_images and len(best_images) > 0:
            print("AMAN")
            return best_images  
        else:
            print("SATYAPAL")
            return []
                   
    except json.JSONDecodeError:
        print("hi nitin")
        return {"best_images": [], "reason": "Failed to parse GPT response"}


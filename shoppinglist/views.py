from django.shortcuts import render
from rest_framework.permissions import AllowAny,IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import http.client
import json
import os
from meal_planner.models import *
from collections import defaultdict
from recipe_section.models import *
from pantry_section.models import *
from .models import *
from rest_framework.permissions import AllowAny
import re
import requests
from .models import ExtractedIngredientsFromMail
from .serializers import ExtractedIngredientsFromMailSerializer
from pantry_section.models import PantryGroup
from dotenv import load_dotenv
load_dotenv()

class MissingIngredientsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        print(user)

        meals = Meal.objects.filter(
            meal_plan__user=user,
            is_completed=False
        ).select_related('recipe').prefetch_related('recipe__recipeingredient_set__ingredient')

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
                ingredient__name__iexact=recipe_ing["name"]  # Exact match to avoid wrong matches
            ).first()

            if not pantry_item or pantry_item.quantity_available < recipe_ing["quantity_required"]:
                missing_ingredients.append({
                    "name": recipe_ing["name"],
                    "required_quantity": recipe_ing["quantity_required"],
                    "available_quantity": pantry_item.quantity_available if pantry_item else 0
                })

        print(missing_ingredients)


        line_items = []
        for item in missing_ingredients:
            line_items.append({
                "name": item['name'],
                "quantity":item['required_quantity'] - item['available_quantity']
            })



        instacart_payload = {
            "title": "Shopping List from Cuokka",
            "line_items": line_items,
            "landing_page_configuration": {
                "partner_linkback_url": f"https://7987d12a480e.ngrok-free.app/shoppinglist/instacart/callback/{request.user.id}", 
                "enable_pantry_items": True
            }
        }

        headers = {
            'Accept': "application/json",
            'Content-Type': "application/json",
            'Authorization': f"Bearer {os.getenv('INSTACART_API_KEY')}"
        }

        try:
            # Step 6: Send Request to Instacart
            conn = http.client.HTTPSConnection("connect.dev.instacart.tools")
            conn.request("POST", "/idp/v1/products/products_link",
                         json.dumps(instacart_payload), headers)
            res = conn.getresponse()
            data = res.read()
            data.decode("utf-8")

            if res.status != 200:
                return Response({
                    'ok':False,
                    'error': 'Failed to fetch Instacart link',
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            OrderSession.objects.create(user = request.user,ingredients = line_items)
            return Response({
                'ok': True,
                'data': json.loads(data.decode("utf-8"))
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'ok':False,
                'error': 'An error occurred while connecting to Instacart',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class InstacartCallbackView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request,id):
        user = User.objects.get(id = id)
        latest_session = OrderSession.objects.filter(user=user,status = 'pending').order_by('-created_at').first()
        
        if latest_session:
            latest_session.status = 'ordered'
            latest_session.save()

            for i in latest_session.ingredients:
                
                try:
                    ingre = Ingredient.objects.get(name__incontains = i['name'])
                    pantry_obj = PantryItem.objects.get(user = user,ingredient = ingre)
                    pantry_obj.quantity_available+=i['quantity']
                    pantry_obj.save()
                except:
                    ing = Ingredient.objects.create(name = i['name'])
                    PantryItem.objects.create(user = user, ingredient = ing, quantity_available = i['quantity'])


        return Response({'ok':True,'data':'success'},status=status.HTTP_200_OK)
    


class MissingIngredientsForRecipe(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        
        user = request.user

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



        line_items = []
        for item in missing_ingredients:
            line_items.append({
                "name": item['name'],
                "quantity":item['required_quantity'] 
            })



        instacart_payload = {
            "title": "Shopping List from Cuokka",
            "line_items": line_items,
            "landing_page_configuration": {
                "partner_linkback_url": f"https://7987d12a480e.ngrok-free.app/shoppinglist/instacart/callback/{request.user.id}", 
                "enable_pantry_items": True
            }
        }

        headers = {
            'Accept': "application/json",
            'Content-Type': "application/json",
            'Authorization': f"Bearer {os.getenv('INSTACART_API_KEY')}"
        }

        try:
            # Step 6: Send Request to Instacart
            conn = http.client.HTTPSConnection("connect.dev.instacart.tools")
            conn.request("POST", "/idp/v1/products/products_link",
                         json.dumps(instacart_payload), headers)
            res = conn.getresponse()
            data = res.read()
            data.decode("utf-8")

            if res.status != 200:
                return Response({
                    'ok':False,
                    'error': 'Failed to fetch Instacart link',
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            OrderSession.objects.create(user = request.user,ingredients = line_items)
            return Response({
                'ok': True,
                'data': json.loads(data.decode("utf-8"))
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'ok':False,
                'error': 'An error occurred while connecting to Instacart',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class EmailWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            # Get incoming data
            data = request.data.get("data")
            _to = request.data.get('to')
            _from =  request.data.get('from')
            if _from != "Instacart <orders@instacart.com>":
                return Response({'ok':False,'error':"Invalid Address it must be Instacart <orders@instacart.com>"})
            
            user = User.objects.get(instacart_email = _to)
            ExtractedIngredientsFromMail.objects.create(
                user = user,
                _from = _from,
                _to = _to,
                ingredient_data = data
            )

            # Return the structured JSON data
            return Response({
                "ok": True,
                "data": "Ingredients saved"
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            print(f"[ERROR] Exception: {e}")
            return Response({"ok":False,"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ListMails(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        extracted_mails_data = ExtractedIngredientsFromMail.objects.filter(
            user=request.user, is_read=False
        )
        serializer = ExtractedIngredientsFromMailSerializer(
            extracted_mails_data, many=True
        )
        return Response({"ok":True,"data":serializer.data},status=status.HTTP_200_OK)


class SaveIngredients(APIView):
    permission_classes = [IsAuthenticated]

    def post(self,request):
        try:
            id = request.data.get('id')
            data = ExtractedIngredientsFromMail.objects.get(id = id)
            if data.gtp_response:
                return Response({'ok':True,'data':data.gtp_response},status=status.HTTP_200_OK)
            
            # Enhanced prompt for better structured ingredient extraction
            prompt = (
                "You are a food and grocery expert specializing in analyzing shopping receipts "
                "and identifying purchased ingredients.\n\n"
                "### Task:\n"
                "From the given receipt details, extract a structured list of food or grocery items "
                "that were actually **purchased or delivered**.\n"
                "Exclude refunded, replaced, promotional, or adjustment details.\n\n"
                "### Format:\n"
                "Return the data strictly in **valid JSON** format, as shown below:\n\n"
                "{\n"
                "  \"purchased_items\": [\n"
                "    {\"name\": \"item name\", \"quantity\": \"optional quantity\", \"category\": \"optional category\"},\n"
                "    ...\n"
                "  ]\n"
                "}\n\n"
                f"### Receipt Details:\n{data.ingredient_data}\n"
            )

            # Payload for OpenAI API
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are a helpful food data extraction assistant."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2
            }

            headers = {
                "Authorization": f"Bearer {os.getenv('GPT_API_KEYS')}",
                "Content-Type": "application/json",
            }

            # Call OpenAI API
            res = requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)

            if res.status_code != 200:
                return Response({
                    "ok":False,
                    "error": "OpenAI API call failed",
                }, status= res.status_code)

            # Extract model response safely
            try:
                raw_content = res.json()["choices"][0]["message"]["content"].strip()
                # Remove markdown code block markers if present
                cleaned_content = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_content, flags=re.MULTILINE)
                extracted_data = json.loads(cleaned_content)
            except Exception as e:
                return Response({
                    "ok":False,
                    "error": "Failed to parse model response as JSON"
                }, status = status.HTTP_500_INTERNAL_SERVER_ERROR)


            purchased_items = extracted_data.get("purchased_items", [])

            pantry_data = list(PantryGroup.objects.all().values_list('name', flat=True))
            
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a food categorization assistant. "
                            "You will be given a list of purchased grocery products with names,categories and quantities. "
                            f"Choose the most appropriate category for each product from this list: {pantry_data}."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "You are a food and grocery categorization expert.\n\n"
                                "### Task:\n"
                                "Given a list of purchased grocery products with their names, categories and quantities, "
                                "assign each product to the most suitable category from the provided pantry category list below.\n\n"
                                f"### Pantry Categories:\n{pantry_data}\n\n"
                                "### Format:\n"
                                "Return the data strictly in **valid JSON** format, as shown below:\n\n"
                                "[\n"
                                "  {\n"
                                "    \"name\": \"item name\",\n"
                                "    \"category\": \"selected category from the list\",\n"
                                "    \"quantity\": \"product quantity\",\n"
                                "  },\n"
                                "  ...\n"
                                "]\n\n"
                                "Do not include any text, markdown formatting, or explanation outside the JSON array.\n\n"
                                f"### Purchased Items:\n{json.dumps(purchased_items, indent=2)}"
                        )
                    },
                ],
                "temperature": 0.2,  

            }

            res = requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers={
                "Authorization": f"Bearer {os.getenv('GPT_API_KEYS')}",
                "Content-Type": "application/json"
            })

            if res.status_code == 200:
                response_data = res.json()
                content = response_data["choices"][0]["message"]["content"].strip()

                try:
                    categorized_data = json.loads(content)
                except json.JSONDecodeError: # GPT returned invalid JSON, raw response
                    categorized_data = []
            else:
                return Response({"ok" : False,"error": f"GPT API returned status code {res.status_code}."}, status = status.HTTP_502_BAD_GATEWAY)

            if not categorized_data:
                return Response({'ok':False,'error':'GPT returned invalid JSON'},status=status.HTTP_400_BAD_REQUEST)

           
            

            final_output = []

            for item in categorized_data:
                name = item.get("name")
                quantity_text = item.get("quantity")

                # 1. Find ingredient
                ingredient = Ingredient.objects.filter(name__iexact=name).first()
                pantry_item = None

                if ingredient:
                    pantry_item = PantryItem.objects.filter(user=request.user, ingredient=ingredient).first()

                # 2. If pantry exists → attach quantities
                if pantry_item:
                    
                    # 3. Prepare GPT prompt
                    gpt_prompt = f"""
                        You are a quantity calculation assistant.

                        Pantry quantity: {pantry_item.quantity_available} {pantry_item.unit}
                        New item quantity: {quantity_text}

                        TASK:
                        1. Convert both quantities to the SAME unit.
                        2. Add them.
                        3. Respond ONLY with the final number and unit.

                        FORMAT (must follow strictly):
                        <value>

                        Examples:
                        "6.361"
                        "12.5"
                        "3"

                        Do NOT explain anything. Do NOT add extra text.
                        """


                    # ----- GPT CALL -----
                    payload = {
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": "You are a quantity calculation assistant."},
                            {"role": "user", "content": gpt_prompt},
                        ]
                    }

                    headers = {
                        "Authorization": f"Bearer {os.getenv('GPT_API_KEYS')}",
                        "Content-Type": "application/json",
                    }

                    gpt_response = requests.post(
                        "https://api.openai.com/v1/chat/completions",
                        json=payload,
                        headers=headers
                    )

                    # If API error
                    if gpt_response.status_code != 200:
                        item["gpt_error"] = "GPT API failed"
                        item["gpt_quantity_result"] = None
                    else:
                        gpt_data = gpt_response.json()
                        result = gpt_data["choices"][0]["message"]["content"]
                        item["gpt_quantity_result"] = result
                    
                    item['pantry_data_exists'] = {
                        "existing_quantity" : pantry_item.quantity_available,
                        "existing_unit" : pantry_item.unit,
                        # 'gpt_quantity_result' : result
                    }

                else:
                    # No pantry item found
                    item['pantry_data_exists'] = {}


                final_output.append(item)
            
            data.is_read = True
            data.gtp_response = final_output
            data.save()
            
            # return final_output
            return Response({
                'ok': True,
                'data': final_output
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({'ok':False,'error':str(e)},status=status.HTTP_400_BAD_REQUEST)

class ExtractQuantity(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            id = request.GET.get('id')
            if not id:
                return Response({'ok':False,'error':"Id is required."},status=status.HTTP_400_BAD_REQUEST)
            try:
                data = ExtractedIngredientsFromMail.objects.get(id=id)
            except Exception as e:
                return Response({'ok':False,'error':str(e)},status=status.HTTP_404_NOT_FOUND)

            pantry_group = PantryGroup.objects.all().values_list('name', flat=True)
            # Exclude expired pantry items
            pantry_items = PantryItem.objects.filter(
                user=request.user,
                expiry_date__gt=timezone.now()
            ).select_related('ingredient')

            # Convert pantry list to JSON-friendly format
            pantry_list = [
                {
                    "name": item.ingredient.name,
                    "available_quantity": item.quantity_available,
                    "unit": item.unit or "",
                }
                for item in pantry_items
            ]

            # Prompt for GPT
            prompt = (
                "You are a food and grocery expert specializing in analyzing shopping receipts "
                "and pantry data.\n\n"
                "### Task:\n"
                "From the given receipt details, extract a **structured list of food or grocery items** that were "
                "actually purchased or delivered.\n\n"
                "### Instructions:\n"
                "1. Each item should include: `name`, `quantity`, `unit` (if applicable), and optionally `category`.\n"
                "2. Convert all quantities into **numerical counts** wherever possible:\n"
                "   - If a weight or volume is mentioned (e.g., '1 kg tomato', '500 grams onions', '2 liters milk'), "
                "     estimate the approximate count (e.g., '1 kg tomato' ≈ 10-12 tomatoes).\n"
                "   - If it's unclear, make your **best realistic estimation** based on your food knowledge.\n"
                "   - You may assume standard grocery conversions like:\n"
                "       • 1 kg of tomatoes ≈ 10-12 tomatoes\n"
                "       • 1 kg of potatoes ≈ 6-8 potatoes\n"
                "       • 1 liter of milk ≈ 1 unit\n"
                "       • 1 bunch of coriander ≈ 1 unit\n"
                "       • 1 packet ≈ 1 unit unless quantity is specified\n"
                "   - The goal is to provide an approximate `quantity` in a **numeric form**, not textual.\n\n"
                "3. If no quantity is specified at all, default to `quantity = 1`.\n"
                "4. If the item already exists in the pantry list (given below), consider that quantity as the base quantity.\n"
                "   You may increase or merge it with the new quantity as needed.\n\n"
                "### Pantry Items (for reference):\n"
                f"{json.dumps(pantry_list, indent=2)}\n\n"
                "### Output Format:\n"
                "Return **strictly valid JSON** (no markdown, no explanations) in this format:\n"
                "{\n"
                "  \"purchased_items\": [\n"
                "    {\"name\": \"item name\", \"quantity\": number, \"unit\": \"optional unit\", \"category\": \"optional\"}\n"
                "  ]\n"
                "}\n\n"
                f"### Receipt Details:\n{data.ingredient_data}\n"
                f"Also here is the list of categores based on that suggest a relevant category {pantry_group}\n"
            )

            # Payload for OpenAI API
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are a helpful food data extraction assistant."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2
            }

            headers = {
                "Authorization": f"Bearer {os.getenv('GPT_API_KEYS')}",
                "Content-Type": "application/json",
            }

            # Call OpenAI API
            res = requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
            if res.status_code != 200:
                return Response({
                    "ok": False,
                    "error": "OpenAI API call failed",
                    "details": res.text
                }, status=res.status_code)

            # Parse GPT Response
            try:
                raw_content = res.json()["choices"][0]["message"]["content"].strip()
                cleaned_content = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_content, flags=re.MULTILINE)
                extracted_data = json.loads(cleaned_content)
            except Exception as e:
                print(f"[ERROR] JSON decode failed: {e}")
                return Response({
                    "ok": False,
                    "error": "Failed to parse model response as JSON"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            purchased_items = extracted_data.get("purchased_items", [])


            # Update Pantry Items
            for item in purchased_items:
                name = item.get("name", "").strip()
                quantity = item.get("quantity", 1)
                unit = item.get("unit", "")
                if not name:
                    continue

                # Try to find or create Ingredient
                # Normalize ingredient name to avoid duplicates like "Milk" vs "milk"
                normalized_name = name.strip().title()

                # Try to find existing ingredient ignoring case
                ingredient_obj = Ingredient.objects.filter(name__iexact=normalized_name).first()

                # If not found, create new one
                if not ingredient_obj:
                    ingredient_obj = Ingredient.objects.create(name=normalized_name)

                # Handle possible duplicates safely
                existing_items = PantryItem.objects.filter(user=request.user, ingredient=ingredient_obj)

                if existing_items.exists():
                    # Merge quantities across duplicates if any
                    pantry_item = existing_items.first()
                    total_quantity = pantry_item.quantity_available + quantity

                    # Optionally merge and delete duplicates
                    if existing_items.count() > 1:
                        for dup in existing_items[1:]:
                            total_quantity += dup.quantity_available
                            dup.delete()

                    pantry_item.quantity_available = total_quantity
                    pantry_item.save()
                else:
                    # Create new pantry item
                    PantryItem.objects.create(
                        user=request.user,
                        ingredient=ingredient_obj,
                        quantity_available=quantity,
                        unit=unit
)


            return Response({
                'ok': True,
                'data': extracted_data,
                "purchased_items":purchased_items
            }, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"[ERROR] {str(e)}")
            return Response({'ok': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class QuantityAction(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            id = request.data.get('id')
            if not id:
                return Response({'ok': False, 'error': 'Id is required.'}, status=status.HTTP_400_BAD_REQUEST)

            title = request.data.get('title')
            quantity = request.data.get('quantity')
            user = request.user

            if not title or not quantity:
                return Response({"ok": False, "error": "Missing title or quantity."}, status=400)

            # Convert quantity to int if numeric
            quantity = int(quantity)

            extracted_mail_obj = ExtractedIngredientsFromMail.objects.get(id=id)

            # Get or create Ingredient
            ingredient, _ = Ingredient.objects.get_or_create(name=title)

            # Get or create PantryItem for user
            pantry, created = PantryItem.objects.get_or_create(
                user=user,
                ingredient=ingredient,
                defaults={"quantity_available": quantity}
            )

            # If already exists, increase quantity
            if not created:
                pantry.quantity_available += quantity
                pantry.save()

            # ---- Update the gtp_response to mark ingredient as added ----
            gtp_response = extracted_mail_obj.gtp_response or []

            for item in gtp_response:
                # Simple title match
                if item.get("name") == title:
                    item["is_added_to_pantry"] = True
                    break

            # Save updated JSON back
            extracted_mail_obj.gtp_response = gtp_response
            extracted_mail_obj.save(update_fields=["gtp_response"])

            return Response({
                "ok": True,
                "data": {
                    "quantity_available": pantry.quantity_available,
                    "updated_ingredient": title
                }
            }, status=200)

        except Exception as e:
            return Response({"ok": False, "error": str(e)}, status=500)

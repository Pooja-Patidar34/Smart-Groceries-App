from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Notification,UserFCMToken
from accounts.models import SubscriptionTransactions
from pantry_section.models import PantryItem
from meal_planner.models import Meal,MealPlan
from .utils import *



@shared_task
def check_expiries():
    from .utils import send_fcm_notification

    try:
        print("nitin")
        now = timezone.now().date()

        # --- Subscription / Trial expiry ---
        subscriptions = SubscriptionTransactions.objects.filter(
            end_date__isnull=False,
            status="succeeded"  
        ).exclude(subscription_status = 'expired')
        print("transactions")
        print(subscriptions)
        print("transactions")
        for sub in subscriptions:
            days_left = (sub.end_date.date() - now).days
            notif_type = "Subscription Alert"

            if days_left in [7, 3, 1, 0]:
                # Prevent duplicates
                message = f"Your {sub.subscription_type} subscription will expire in {days_left} days." if days_left > 0 else f"Your {sub.subscription_type} subscription has expired."
                noti_obj = Notification.objects.filter(
                    user=sub.user,
                    type=notif_type
                ).exists()

                if days_left == 0:
                    sub.subscription_status = 'expired'
                    sub.save()

                if not noti_obj:
      
                    noti_obj = Notification.objects.create(
                        user=sub.user,
                        type=notif_type,
                        message = message
                    )
                tokens = UserFCMToken.objects.filter(user = sub.user).values_list('token', flat = True)
                send_fcm_notification(tokens, notif_type, message,image_url=None,route = f"https://api.cuokkaapp.com/notifications/get-notification-detail?id={noti_obj.id}")


        # --- Pantry expiry ---
        pantry_items = PantryItem.objects.filter(expiry_date__isnull=False)
        print("pantry")
        print(pantry_items)
        print("pantry")
        for item in pantry_items:
            days_left = (item.expiry_date - now).days
            notif_type = "Pantry Alert"

            if days_left in [7, 3, 1, 0]:
                message = "Your {item.name} will expire in {days_left} days." if days_left > 0 else f"Your {item.ingredient.name} has expired."

                exists = Notification.objects.filter(
                    user=item.user,
                    type=notif_type
                ).exists()
                
                if days_left == 0:
                    item.expiry_date = now
                    if item.quantity_available:
                        item.quantity_available -= 1
                    item.save()


                if not exists:
                    Notification.objects.create(
                        user=item.user,
                        type=notif_type,
                        message=message
                    )
                tokens = UserFCMToken.objects.filter(user = sub.user).values_list('token', flat = True)

                send_fcm_notification(tokens, notif_type, message, image_url=None)

    except Exception as e:
        print(e)
    

# from django.utils import timezone
# from datetime import timedelta


@shared_task
def meals_going_to_finish():
    try:
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)

        # Get meal plans ending tomorrow
        ending_plans = MealPlan.objects.filter(end_date=tomorrow, is_active=True)

        for plan in ending_plans:
            user = plan.user
            message = f"Your meal plan will end on {plan.end_date}. Renew now to continue enjoying meals."

            # Example: send notification (depends on your notification system)
            # Avoid duplicates
            if not Notification.objects.filter(user=user,type="Meals Alert",message=message).exists():
                noti_obj = Notification.objects.create(
                    user=user,
                    message=message,
                    type="Meals Alert"
                )
                tokens = UserFCMToken.objects.filter(user = user).values_list('token', flat = True)

                send_fcm_notification(
                    tokens, 
                    title="Meals Alert", 
                    message=f"Your meal plan will end on {plan.end_date}. Renew now to continue enjoying meals.",
                    route = f"https://api.cuokkaapp.com/notifications/get-notification-detail?id={noti_obj.id}"
                )
            
    except Exception as e:
        print(f"Error in meals_going_to_finish: {e}")

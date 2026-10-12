# tasks.py
from celery import shared_task
from datetime import date, timedelta
from django.utils import timezone
from pantry_section.models import PantryItem
from notifications.models import Notification, UserFCMToken  # adjust import as per your structure
from notifications.utils import send_fcm_notification  # you must have this utility function


@shared_task
def pantry_expiry_alert():
    today = date.today()
    upcoming_date = today + timedelta(days=3)

    # Items expiring today or within next 3 days
    expiring_items = PantryItem.objects.filter(expiry_date__lte=upcoming_date, expiry_date__isnull=False)

    for item in expiring_items:
        user = item.user
        item_name = item.ingredient.name
        expiry_date = item.expiry_date

        if expiry_date < today:
            message = f"Your item '{item_name}' has expired on {expiry_date}."
            notif_type = "Pantry Alert"
        else:
            message = f"Your item '{item_name}' will expire on {expiry_date}. Please use it soon."
            notif_type = "Pantry Alert"

        # Check if notification already sent for this item recently
        if Notification.objects.filter(user=user, message=message, type=notif_type).exists():
            continue  # avoid duplicates

        # Create notification in DB
        noti_obj = Notification.objects.create(
            user=user,
            message=message,
            type=notif_type
        )

        # Get FCM tokens
        tokens = UserFCMToken.objects.filter(user=user).values_list('token', flat=True)
        if tokens:
            send_fcm_notification(
                list(tokens),
                notif_type,
                message,
                image_url=None,
                route=f"https://api.cuokkaapp.com/notifications/get-notification-detail?id={noti_obj.id}"
            )

    return f"Processed {expiring_items.count()} pantry items for expiry notifications."

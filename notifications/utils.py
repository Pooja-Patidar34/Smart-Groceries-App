from firebase_admin import messaging
from .models import Notification, UserFCMToken

def send_fcm_notification(tokens, title, body,image_url = None,route=None):
    tokens = list(tokens)
    for token in tokens:
        message = messaging.Message(
            notification = messaging.Notification(
                title = title,
                body = body
            ),
            token = token,
            data={
                "route": route if route else " "
            }
        )

        # ✅ Fix: use `.objects` not `.object`
        user_fcm = UserFCMToken.objects.filter(token=token).first()
        print("hi nitin")
        print(user_fcm)
        if user_fcm:
            Notification.objects.create(
                user=user_fcm.user,
                message=body,
                type=title
            )
        print(message)
        response = messaging.send(message)
        print(response)
        print(f"Sent to {token}, response: {response}")

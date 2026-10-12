from rest_framework.response import Response
from rest_framework.views import APIView
from .utils import *
from rest_framework.permissions import IsAuthenticated
from .models import *
from .serializer import *
from rest_framework import status
from .utils import send_fcm_notification


class GetNotifications(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
        serializer = NotificationSerializer(notifications, many=True)
        return Response({"ok":True,"data":serializer.data}, status=status.HTTP_200_OK)

class GetNotificationDetails(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notification_id = request.query_params.get('id')
        
        if not notification_id:
            return Response(
                {"ok":False,"error": "Notification ID is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        notification = Notification.objects.filter(
            user=request.user,
            id=notification_id
        ).first()

        if not notification:
            return Response(
                {"ok":False,"error": "Notification not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = NotificationSerializer(notification)
        return Response({"ok":True,"data":serializer.data}, status=status.HTTP_200_OK)



class Send(APIView):
    permission_classes = [IsAuthenticated]

    def post(self,request):
        try:
            tokens = UserFCMToken.objects.filter(user = request.user).values_list('token',flat=True)
            if not tokens:
                return Response({'ok':False,'error': 'No FCM tokens found for this user'}, status=status.HTTP_404_NOT_FOUND)
            
            print(list(tokens))
            send_fcm_notification(list(tokens),"Subscription Alert",'How are you Arya ?',"https://cuokka.hktechlabs.com/media/listed_meals/Screenshot_from_2025-08-04_14-28-09.png")
            return Response({'ok':True},status = status.HTTP_200_OK)
        except Exception as e:
            return Response({'ok':True,'error':str(e)},status=status.HTTP_200_OK)
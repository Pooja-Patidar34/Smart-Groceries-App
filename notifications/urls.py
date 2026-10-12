from django.urls import path
from . import views

urlpatterns = [
    path('get-notifications',views.GetNotifications.as_view()),
    path('get-notification-detail',views.GetNotificationDetails.as_view()),
    path('send',views.Send.as_view()),
]
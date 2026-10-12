from django.urls import path
from .views import *

urlpatterns = [
    path('send-message/', SendMessageAPIView.as_view(), name='send-message'),
    path('get-message/', GetMessagesAPIView.as_view(), name='get-message'),
    path('search', SearchText.as_view()),
    path('mark-as-read', SetReadStatus.as_view()),
    path('count-unread-messages', CountMessages.as_view()),
    path('delete-messages', DeleteMessage.as_view()),
]

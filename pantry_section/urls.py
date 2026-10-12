from django.urls import path
from .views import *
urlpatterns = [
    path('addtopantry',AddProductToPantry.as_view()),
    path('change-quantity',QuantityChange.as_view()),
    path('scan-product',ScanProduct.as_view()),
]

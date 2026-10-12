from django.urls import path
from .views import *



urlpatterns = [
    path("buy/missing-product", MissingIngredientsAPIView.as_view()),
    path('instacart/callback', InstacartCallbackView.as_view(), name='instacart-callback'),
    path("buy/missing-products-recipe", MissingIngredientsForRecipe.as_view()),
    path('email-webhook/', EmailWebhookView.as_view(), name='email_webhook'),
    path('list-mails',ListMails.as_view()),
    path('save-ingredients/', SaveIngredients.as_view(), name='email_data'),
    path('extract-quantity',ExtractQuantity.as_view()),
    path('quantity-action/', QuantityAction.as_view(), name='quantity-action'),
]

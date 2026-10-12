from django.urls import path
from . import views

urlpatterns = [
    path('user-preference',views.UserDietPreference.as_view()),
    path('update-userdietpreference',views.UpdateUserDietPreference.as_view()),
    path('get-userdietpreference',views.GetUserDietPreference.as_view()),
    path('searchpreference',views.SearchPreference.as_view()),
    path('add-measurement',views.SetSystemMeasurements.as_view()),
    path('account-details',views.AccountsDetails.as_view()),
    path('account-details/myorders',views.MyOrders.as_view()),
    path('account-details/myorders/details/<int:id>',views.MyOrdersDetails.as_view()),
    path('account-details/payout',views.MyPayout.as_view()),
    path('account-details/payout/details/<int:id>',views.MyPayoutsDetails.as_view()),
    path('account-details/edit/change-email',views.ChangeEmail.as_view()),
    path('account-details/edit/resend-otp',views.ResendOtp.as_view()),
    path('account-details/edit/verify-otp',views.VerifyNewEmail.as_view()),
    path('account-details/edit/change-password',views.ChangePassword.as_view()),
    path('account/delete-account',views.DeleteAccount.as_view()),
    path('account/clear-data',views.ClearData.as_view()),
    path('new-subscription-model',views.ShowSubscriptionModelDetails.as_view()),
    path('account/logout',views.LogoutView.as_view()),
    path('account/raise-dispute',views.RaiseDispute.as_view()),
    path('account/subscription',views.OneTimePaymentView.as_view()),
    path('account/webhook/',views.stripe_webhook),

    
]

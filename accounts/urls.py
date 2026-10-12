from django.urls import path
from . import views



urlpatterns = [
    path('google/login',views.GoogleSocialLoginView.as_view()),
    path('apple/login',views.AppleLoginAPIView.as_view()),
    path('login',views.LoginAPIView.as_view()),
    path("signup",views.SignUp.as_view()),
    path('google/firebase-login',views.FirebaseLoginAPIView.as_view()),
    path("send-otp",views.ForgotPassword.as_view()),
    path("resend-otp",views.ResendOtp.as_view()),
    path("verify-otp",views.VerifyForgotOtp.as_view()),
    path("forgot-password/confirm",views.ForgotPasswordConfirm.as_view()),
    path('fcm',views.SaveFCMTokenView.as_view()),
    path('success',views.success,name="success"),
    path('error',views.error,name="error"),
    path("api/token/refresh/", views.RefreshTokenAPIView.as_view()),
    path('set-bank-details',views.CreateConnectedAccountView.as_view()),
    path('delete-fcm',views.DeleteFCMTokenView.as_view()),
    path('upload-profile-pic',views.ProfilePicture.as_view()),
    path('terms-and-conditions/', views.TermsAndConditionsAPIView.as_view(), name='terms-and-conditions'),
    path('about-us/', views.AboutUs.as_view(), name='about-us'),
    path('privacy-policy/', views.PrivacyPolicy.as_view(), name='privacy-policy'),
    path('set-instacart-mail',views.SetInstacartMail.as_view())

]

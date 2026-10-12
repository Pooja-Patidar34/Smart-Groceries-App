from django.shortcuts import render
from rest_framework.views import APIView 
from rest_framework.permissions import AllowAny,IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from google.oauth2 import id_token
from accounts.models import *
from google.auth.transport import requests
from rest_framework_simplejwt.tokens import RefreshToken
import os
from django.db import transaction
from django.core.mail import send_mail
from .serializer import *
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken,TokenError
from jwt import PyJWKClient, get_unverified_header
import jwt
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import pyotp
from firebase_admin import auth as firebase_auth
import logging
from dotenv import load_dotenv
import http.client
import json
from .throttles import *
from rest_framework.exceptions import Throttled
import stripe
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from profile_section.models import UserPreference
from notifications.models import UserFCMToken
from django.urls import reverse
from accounts.models import User

from .models import StaticData
from .serializer import StaticDataSerializer
stripe.api_key = settings.STRIPE_SECRET_KEY

load_dotenv()
from django.contrib.auth import get_user_model
User = get_user_model()

logger = logging.getLogger('accounts')





class GoogleSocialLoginView(APIView):
    def post(self, request, *args, **kwargs):
        """
        Google social login API view.

        Parameters:
        token (str): Google OAuth access token.

        Returns:
        Response: A Response object containing the status and data (JWT tokens or error message).

        Raises:
        ValueError: If the provided token is invalid.
        Exception: If any other server error occurs.
        """
        try:
            token = request.data.get('token')
            if not token:
                return Response({"error": "Token is required"}, status=status.HTTP_400_BAD_REQUEST)
            try:
                CLIENT_ID = os.getenv('google_client_id')
                # Verify the token
                idinfo = id_token.verify_oauth2_token(token, requests.Request(), CLIENT_ID)
                # idinfo now contains user's Google profile details
                google_id = idinfo['sub']
                email = idinfo['email']
                name = idinfo['name']

                with transaction.atomic():
                    # Check or create user
                    user, created = User.objects.get_or_create(email=email, defaults={"username": name})
                    if created:
                        record = {
                            'user': user,
                            "subscription_type": "Trial",  
                            "start_date": timezone.now(),
                            "end_date": timezone.now() + timedelta(days=14),
                            "status": "Active",  
                        }

                        SubscriptionPlan.objects.create(**record)

                    refresh = RefreshToken.for_user(user)
                    access_token = refresh.access_token
                
                    data = {
                        "refresh": str(refresh),
                        "access": str(access_token)
                    }
                return Response({"ok":True,"message":"successful",'data':data},status=status.HTTP_200_OK)
            except ValueError as e:
                return Response({"ok":False, "message":"error",'data':"Invalid Token"}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"ok":False,"message":"error",'data':"Server Error"},status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        """
        Handle user login requests.

        This method processes a login request by validating the provided email and password.
        If the credentials are valid and the user's email is verified, it generates and returns
        a JWT refresh and access token pair for the user. If the credentials are invalid or the
        user's email is not verified, it returns an appropriate error response.

        Args:
            request (HttpRequest): The HTTP request object containing login data.

        Returns:
            Response: A Response object containing the status and data (JWT tokens or error message).

        Raises:
            User.DoesNotExist: If the provided email is not associated with any user.
        """


        serialized_data = LoginAPIViewSerializer(data=request.data)

        if serialized_data.is_valid():
            email = serialized_data.validated_data.get('email')
            password = serialized_data.validated_data.get('password')
            try:
                user = User.objects.get(email = email)
                user.last_login = timezone.now()
                user.save()
                if not user.is_active:
                    return Response({'ok':False, 'error':'Your account is deleted.'},status=status.HTTP_400_BAD_REQUEST)
                if not user.is_email_verified:
                    return Response({'ok':False,'error':'please verify email.'},status=status.HTTP_400_BAD_REQUEST)

                credentials = user.check_password(password)
                if credentials:
                    subscription_obj = SubscriptionTransactions.objects.filter(user=user).order_by('-created_at').first()

                    refresh = RefreshToken.for_user(user)
                    access_token = refresh.access_token

                    data = {
                        "refresh": str(refresh),
                        "access": str(access_token),
                        "subscription_expired": (
                            subscription_obj.end_date and subscription_obj.end_date < timezone.now()
                        ) if subscription_obj else True,
                        "email_verification": getattr(user, "is_email_verified", False),
                        "has_preference_done": UserPreference.objects.filter(user_id=user).exists(),
                        "username":user.username
                    }
            
                    return Response({"ok":True,'data':data}, status=status.HTTP_200_OK)
                return Response({"ok":False,'error':"Invalid Credentials"},status=status.HTTP_400_BAD_REQUEST)
                
            except User.DoesNotExist:
                return Response({"ok":False,'error':"Invalid Credentials"},status=status.HTTP_400_BAD_REQUEST)

        return Response({"ok":False,'error':"Server error"}, status=status.HTTP_400_BAD_REQUEST)


    
    
class SignUp(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            serialized_data = SignUpSerializer(data=request.data, context={'request':request})

            with transaction.atomic():
                if serialized_data.is_valid():
                    user = serialized_data.save()

                    # Create a trial subscription
                    # Create a trial subscription
                    order_id = f"TRIAL-{user.id}-{int(timezone.now().timestamp())}"
                    record = {
                        'user': user,
                        "orderid": order_id,
                        'subscription_status':'Active',
                        "subscription_type": "Trial",
                        "start_date": timezone.now(),
                        "end_date": timezone.now() + timedelta(days=13),
                        "status": "succeeded",  
                        "amount": 0,            
                    }
                    SubscriptionTransactions.objects.create(**record)


                    totp = pyotp.TOTP(pyotp.random_base32(), interval=120)
                    otp = totp.now()

                    UserOTP.objects.update_or_create(
                        user = user,
                        defaults = {
                            'otp': 111111,
                            'otp_secret': totp.secret,
                            'created_at': timezone.now()
                        }
                    )

                    # Send OTP to user's email
                    send_mail(
                        subject='Your OTP Code',
                        message=f'Your OTP is {111111}. It is valid for 2 minute.',
                        from_email=settings.EMAIL_HOST_USER,
                        recipient_list=[user.email],
                        fail_silently=False,
                    )
                    refresh = RefreshToken.for_user(user)
                    access_token = refresh.access_token
                    data = {
                        "refresh": str(refresh),
                        "access": str(access_token)
                    }
                    return Response({
                        "ok": True,
                        "data": data
                    }, status=status.HTTP_201_CREATED)

                error_dict = serialized_data.errors
                field, errors = next(iter(error_dict.items()))
                error_msg = f"{errors[0].replace('"','')}"
                return Response({'ok': False,"error":error_msg},status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({'ok':False,'error':str(e)},status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AppleLoginAPIView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        """
        Apple login API view.

        Parameters:
        identity_token (str): Apple authentication token.
        email (str): User's email.
        username (str): User's username.

        Returns:
        Response: A Response object containing the status and data (JWT tokens or error message).

        Raises:
        ValueError: If the provided token is invalid.
        Exception: If any other server error occurs.
        """

        identity_token = request.data.get('token')
        email = request.data.get('email')
        username = request.data.get('username')

        
        if not identity_token:
            return Response({'ok':False,'message':'Token missing','data': None},status=status.HTTP_400_BAD_REQUEST)
        try:
            get_unverified_header(identity_token)
        except Exception as e:
            return Response({'ok':False,'message':'Invalid token format','data': None}, status=400)

        try:
            # Get Apple's public keys
            jwks_client = PyJWKClient("https://appleid.apple.com/auth/keys")
            signing_key = jwks_client.get_signing_key_from_jwt(identity_token)

            # Decode the token
            jwt.decode(
                identity_token,
                signing_key.key,
                algorithms=["RS256"],
                audience=settings.APPLE_CLIENT_ID,
                issuer="https://appleid.apple.com"
            )

            # Get or create user
            user, created = User.objects.get_or_create(
                email = email,
                defaults={
                    "username": username
                }
            )
            if created:
                record = {
                    'user': user,
                    "subscription_type": "Trial",  
                    "start_date": timezone.now(),
                    "end_date": timezone.now() + timedelta(days=14),
                    "status": "Active",  
                }

                SubscriptionPlan.objects.create(**record)
                user.email = email
                user.save()

            
            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token
            

            data = {
                "refresh": str(refresh),
                "access": str(access_token)
            }

            return Response(
                {'ok':True,'message': "successful",'data':data},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response({'ok':False,'message':'error','data':None}, status=status.HTTP_400_BAD_REQUEST)



class VerifyEmail(APIView):
    permission_classes = [AllowAny]

    def post(self,request):
        email = request.data.get('email')
        otp = request.data.get('otp')

        try:
            user = User.objects.get(email=email)
            user_otp = UserOTP.objects.get(user=user)

            if user_otp.is_valid() and otp == user_otp.otp:
                user.is_email_verified = True
                user.save()
                return Response({"ok": True, "message":"successful","data": "OTP verified successfully."}, status=200)
            else:
                return Response({"ok": False,"message":"error", "data": "Invalid or expired OTP."}, status=400)

        except User.DoesNotExist:
            return Response({"ok": False,"message":"error", "data": "User not found."}, status=404)
        except UserOTP.DoesNotExist:
            return Response({"ok": False,"message":"error", "data": "OTP not generated."}, status=404)



class FirebaseLoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        gmail_data = request.data.get("gmail_data")
        email = gmail_data.get('email')
        name = gmail_data.get('name')
        try:
            # decoded_token = firebase_auth.verify_id_token(firebase_token)
            # email = decoded_token['email']
            # uid = decoded_token['uid']
            # name = decoded_token.get('name', '')

            # user, created = User.objects.get_or_create(email=email, defaults={
            #     "username": name.lower(),
            # })

            with transaction.atomic():
                # Check or create user
                user, created = User.objects.get_or_create(email=email, defaults={
                    "username": name.lower(),
                    'ip_address':get_client_ip(request)
                })
                if created:
                    order_id = f"TRIAL-{user.id}-{int(timezone.now().timestamp())}"
                    record = {
                        'user': user,
                        "orderid": order_id,
                        'subscription_status':'Active',
                        "subscription_type": "Trial",
                        "start_date": timezone.now(),
                        "end_date": timezone.now() + timedelta(days=13),
                        "status": "succeeded",  
                        "amount": 0,            
                    }
                    SubscriptionTransactions.objects.create(**record)

                refresh = RefreshToken.for_user(user)
                access_token = refresh.access_token
            
                data = {
                    "refresh": str(refresh),
                    "access": str(access_token)
                }
                refresh = RefreshToken.for_user(user)
            
                return Response({
                    "ok": True,
                    'data':data
                }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"ok": False,'error':str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ForgotPassword(APIView):
    # throttle_classes = [UserResendOtpPerMinute or UserResendOtpPerDay]
    permission_classes = [AllowAny]

    def throttled(self, request, wait):
        raise Throttled(detail={
            "ok": False,
            "error": f"Retry after {wait} seconds."
        })

    def post(self,request):
        serialized_data = ForgotPasswordSerializer(data  = request.data)
        
        if serialized_data.is_valid():
            email = serialized_data.validated_data.get('email')
            
            try:
                user = User.objects.get(email = email)
            
            except User.DoesNotExist:
                return Response({'ok':False,'error':"User does not exists."},status=status.HTTP_400_BAD_REQUEST)
            
            totp = pyotp.TOTP(pyotp.random_base32(), interval=60)
            # otp = totp.now()

            UserOTP.objects.update_or_create(
                user=user,
                defaults={
                    'otp': 111111,
                    'otp_secret': totp.secret,
                    'created_at': timezone.now()
                }
            )

            send_mail(
                subject='Your OTP Code',
                message=f'Your OTP is {111111}. It is valid for 2 minute.',
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[email],
                fail_silently=False,
            )

            return Response({"ok":True,"data":"Otp Send Successfully."},status=status.HTTP_200_OK)
        
        error_dict = serialized_data.errors
        field, errors = next(iter(error_dict.items()))
        error_msg = f"{field}: {errors[0].replace('"','')}"
        return Response({'ok': False,"error":error_msg},status=status.HTTP_400_BAD_REQUEST)



class ResendOtp(APIView):
    # throttle_classes = [UserResendOtpPerMinute or UserResendOtpPerDay]
    permission_classes = [AllowAny]

    def throttled(self, request, wait):
        raise Throttled(detail={
            "ok": False,
            "error": f"Retry after {wait} seconds."
        })

    def post(self,request):
        serialized_data = ForgotPasswordSerializer(data  = request.data)
        
        if serialized_data.is_valid():
            email = serialized_data.validated_data.get('email')
            
            try:
                user = User.objects.get(email = email)
            
            except User.DoesNotExist:
                return Response({'ok':False,'error':"User does not exists."},status=status.HTTP_400_BAD_REQUEST)
            
            totp = pyotp.TOTP(pyotp.random_base32(), interval=60)
            # otp = totp.now()

            UserOTP.objects.update_or_create(
                user=user,
                defaults={
                    'otp': 111111,
                    'otp_secret': totp.secret,
                    'created_at': timezone.now()
                }
            )

            send_mail(
                subject='Your OTP Code',
                message=f'Your OTP is {111111}. It is valid for 2 minute.',
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[email],
                fail_silently=False,
            )

            return Response({"ok":True,"data":"Otp Send Successfully."},status=status.HTTP_200_OK)
        
        error_dict = serialized_data.errors
        field, errors = next(iter(error_dict.items()))
        error_msg = f"{field}: {errors[0].replace('"','')}"
        return Response({'ok': False,"error":error_msg},status=status.HTTP_400_BAD_REQUEST)



class VerifyForgotOtp(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializered_data = VerifyForgotOtpSerializer(data=request.data)

        if serializered_data.is_valid():
            otp = serializered_data.validated_data.get('otp')
            if otp != '111111':
                return Response({'ok':False,'error':'invalid otp'},status=status.HTTP_400_BAD_REQUEST)
            email = serializered_data.validated_data.get('email')

            try:
                user = User.objects.get(email=email)
                user_otp = UserOTP.objects.get(user=user)
            except (User.DoesNotExist, UserOTP.DoesNotExist):
                return Response({
                    "ok": False,
                    "error": "Invalid email or OTP not found."
                }, status=status.HTTP_400_BAD_REQUEST)

            # totp = pyotp.TOTP(user_otp.otp_secret, interval=120)

            # if user_otp.is_valid() and totp.verify(otp, valid_window=1):
            
            user.is_email_verified = True
            user.save()
            return Response({
                "ok": True,
                "data": "OTP verified successfully."
            }, status=status.HTTP_200_OK)
            # else:
            #     return Response({
            #         "ok": False,
            #         "error": "Invalid or expired OTP."
            #     }, status=status.HTTP_400_BAD_REQUEST)

        error_dict = serializered_data.errors
        field, errors = next(iter(error_dict.items()))
        error_msg = f"{field}: {errors[0].replace('"','')}"
        return Response({
            'ok': False,
            "error": error_msg
        }, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordConfirm(APIView):
    permission_classes = [AllowAny]

    def post(self,request):
        serialized_data = ForgotPasswordConfirmSerializer(data = request.data)
        
        if serialized_data.is_valid():
            serialized_data.save()
            return Response({'ok':True,'data':'Password set successful.'})
        

        error_dict = serialized_data.errors
        _, errors = next(iter(error_dict.items()))
        error_msg = errors[0]
        return Response({'ok': False, "error": error_msg}, status=status.HTTP_400_BAD_REQUEST)
    



class SaveFCMTokenView(APIView):
    permission_classes = [IsAuthenticated]  

    def post(self, request):
        token = request.data.get("token")
        if not token:
            return Response({"error": "Token is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Prevent duplicates for same user
        UserFCMToken.objects.update_or_create(
            user=request.user,
            defaults={"token": token}
        )

        return Response({'ok':True,'data':'Fcm Token Created successfully '}, status=status.HTTP_201_CREATED)


class RefreshTokenAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if refresh_token is None:
            return Response(
                {"ok":False,"error": "Refresh token is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            refresh = RefreshToken(refresh_token)
            access_token = str(refresh.access_token)

            return Response(
                {
                    "ok":True,
                    "data":{
                        "access": access_token,
                        "refresh": str(refresh)
                    }
                },
                status=status.HTTP_200_OK
            )
        except TokenError:
            return Response(
                {'ok':False,"error": "Invalid or expired refresh token"},
                status=status.HTTP_401_UNAUTHORIZED
            )





class CreateConnectedAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Build absolute URLs dynamically
        refresh_url = request.build_absolute_uri(reverse('success'))
        return_url = request.build_absolute_uri(reverse('error'))

        account_link = stripe.AccountLink.create(
            account=request.user.connected_id,
            refresh_url=refresh_url,
            return_url=return_url,
            type="account_onboarding",
        )

        return Response({"ok": True, "data": account_link.url}, status=status.HTTP_200_OK)




class DeleteFCMTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get("token")
        if not token:
            return Response({"ok":False,"error": "Token is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Try to delete the token for this user
        deleted_count, _ = UserFCMToken.objects.filter(user=request.user, token=token).delete()

        # if deleted_count == 0:
        #     return Response({"ok":False, "error": "Token not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response({"ok": True, "data": "FCM Token deleted successfully"}, status=status.HTTP_200_OK)



class ProfilePicture(APIView):
    permission_classes=[IsAuthenticated]

    def post(self,request):
        profile_pic = request.FILES.get('profile_pic')
        username = request.data.get('username')
        # contact = request.data.get('contact')
        

        # if not contact:
        #     return Response({'ok':True,'error':'Contact is required'},status=status.HTTP_400_BAD_REQUEST)
        
        # if not profile_pic:
        #     return Response({'ok':False,'error':'Profile picture is required.'},status=status.HTTP_400_BAD_REQUEST)

        if not username:
            return Response({'ok':False,'error':'username is required.'},status=status.HTTP_400_BAD_REQUEST)

        if request.user.username != username:
            if User.objects.filter(username = username).exists():
                return Response({'ok':False,'error':'username already exists'},status=status.HTTP_400_BAD_REQUEST)
        

        # else:
        #     User.objects.filter(username = username).exists():
        #     return Response({'ok':False,'error':'username already exists'},status=status.HTTP_400_BAD_REQUEST)
        
        media_id = None
        try:
            upload_url = os.getenv('S3BUCKETUAPI')
            files = {
                "file": (
                    profile_pic.name,
                    profile_pic.read(),
                    profile_pic.content_type,
                )
            }
            import requests
            resp = requests.post(upload_url, files=files)
            
            if resp.status_code != 200:
                return Response({'ok': False, 'error': 'Failed to upload profile picture.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            if resp.status_code == 200:
                resp_json = resp.json()
                media_id = resp_json.get("data", {}).get("mediaId", {}).get("id")
                print(media_id)
        except Exception as e:
            print(f"Media upload failed: {e}")
        
        request.user.username = username
        request.user.media_id = media_id
        # request.user.contact = contact
        request.user.save()
        return Response({'ok':True,'data':'User information updated successfully.'},status=status.HTTP_200_OK)




class TermsAndConditionsAPIView(APIView):
    """
    API endpoint to retrieve the active Terms and Conditions content.
    """
    def get(self, request):
        try:
            terms = StaticData.objects.filter(
                type='Terms and Conditions',
                is_active=True
            ).latest('created_at')

            serializer = StaticDataSerializer(terms)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except StaticData.DoesNotExist:
            return Response(
                {"ok":False,"error": "No active Terms and Conditions found."},
                status=status.HTTP_404_NOT_FOUND
            )


class AboutUs(APIView):
    """
    API endpoint to retrieve the active Terms and Conditions content.
    """
    def get(self, request):
        try:
            about_us = StaticData.objects.filter(
                type='About Us',
                is_active=True
            ).latest('created_at')

            serializer = StaticDataSerializer(about_us)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except StaticData.DoesNotExist:
            return Response(
                {"ok":False,"error": "No active Terms and Conditions found."},
                status=status.HTTP_404_NOT_FOUND
            )

class PrivacyPolicy(APIView):
    """
    API endpoint to retrieve the active Terms and Conditions content.
    """
    def get(self, request):
        try:
            privacy_policy = StaticData.objects.filter(
                type='Privacy Policy',
                is_active=True
            ).latest('created_at')

            serializer = StaticDataSerializer(privacy_policy)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except StaticData.DoesNotExist:
            return Response(
                {"ok":False,"error": "No active Terms and Conditions found."},
                status=status.HTTP_404_NOT_FOUND
            )


class SetInstacartMail(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        insta_email = request.data.get('insta_email')

        if not insta_email:
            return Response({"ok":False, "error": "insta_email is required"}, status=status.HTTP_400_BAD_REQUEST)

        request.user.instacart_email = insta_email
        request.user.save()

        return Response({"ok":True,"data": "Instacart email updated successfully"}, status=status.HTTP_200_OK)




    
@csrf_exempt
@api_view(['GET','POST'])
@permission_classes([AllowAny])
def success(request):

    return Response({'ok':"success"})


@csrf_exempt
@api_view(['GET','POST'])
@permission_classes([AllowAny])
def error(request):
    return Response({'ok':"failed"})
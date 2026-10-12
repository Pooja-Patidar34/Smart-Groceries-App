from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import AllowAny,IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import *
from .serializers import *
from rest_framework import status
from django.core.paginator import Paginator, EmptyPage
from accounts.models import *
from meal_planner.models import *
from recipe_section.models import *
from transactions.models import *
from django.core.mail import send_mail
import stripe
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from accounts.throttles import *
from rest_framework.exceptions import Throttled
from accounts.serializer import ForgotPasswordSerializer
from uuid import uuid4
from pantry_section.models import PantryItem
from shoppinglist.models import OrderSession
from notifications.models import Notification
from AdminDashboard.models import NewSubscription,Refund


stripe.api_key = settings.STRIPE_SECRET_KEY



class UserDietPreference(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):

        serialized_data = UserDietPreferenceSerializer(data = request.data, context={'request':request})
        if serialized_data.is_valid():
            serialized_data.save()
            return Response({'ok':True,"data":"Preferences set successfully."},status=status.HTTP_200_OK)
        
        error_dict = serialized_data.errors
        field, errors = next(iter(error_dict.items()))
        error_msg = f"{errors[0].replace('"','')}"
        return Response({'ok': False,"error":error_msg},status=status.HTTP_400_BAD_REQUEST)
    
    
    def put(self, request):
        preference = UserPreference.objects.get(user_id=request.user)
        serializer = UserDietPreferenceSerializer(preference, data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({'ok': True, "data": "Preferences updated successfully."}, status=status.HTTP_200_OK)

        error_dict = serializer.errors
        field, errors = next(iter(error_dict.items()))
        error_msg = f"{errors[0].replace('"','')}"
        return Response({'ok': False, "error": error_msg}, status=status.HTTP_400_BAD_REQUEST)


class UpdateUserDietPreference(APIView):
    permission_classes = [IsAuthenticated]

    def put(self,request):
        serialized_data = UserDietPreferenceSerializer(data = request.data, context={'request':request})
        if serialized_data.is_valid():
            serialized_data.save()
            return Response({'ok':True,"data":"Preferences set successfully."},status=status.HTTP_200_OK)
        
        error_dict = serialized_data.errors
        field, errors = next(iter(error_dict.items()))
        error_msg = f"{errors[0].replace('"','')}"
        return Response({'ok': False,"error":error_msg},status=status.HTTP_400_BAD_REQUEST)

class GetUserDietPreference(APIView):
    permission_classes = [IsAuthenticated]

    def get(self,request):
        user_obj = UserPreference.objects.get(user_id = request.user)
        serialized_data = UserDietPreferenceSerializer(user_obj)

        return Response({'ok':True,"data":serialized_data.data},status=status.HTTP_200_OK)
        
        
    

class SearchPreference(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        category = request.data.get('category')
        search_data = request.data.get('data')
        page_number = int(request.data.get('page', 1))

        queryset = EatingStyleData.objects.filter(
            eatingstyle__name=category,
            name__icontains=search_data
        ).values_list('name', flat=True)

        paginator = Paginator(queryset, 5)

        try:
            page = paginator.page(page_number)
        except EmptyPage:
            return Response({
                "ok": False,
                "error": "Page out of range",
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "ok": True,
            "data": list(page),
            "total_pages": paginator.num_pages,
            "current_page": page.number,
            "next_page": page.next_page_number() if page.has_next() else None,
            "previous_page": page.previous_page_number() if page.has_previous() else None,
        }, status=status.HTTP_200_OK)

class SetSystemMeasurements(APIView):
    permission_classes = [IsAuthenticated]

    def post(self,request):
        serializer = SetSystemMeasurementsSerializer(data = request.data, context={'request':request})
        if serializer.is_valid():
            serializer.save()
            return Response({'ok': True, 'data': 'Value set successfully.'}, status=status.HTTP_200_OK)

        error_dict = serializer.errors
        field, errors = next(iter(error_dict.items()))
        error_msg = f"{field} : {errors[0].replace('"','')}"
        return Response({'ok': False,"error":error_msg},status=status.HTTP_400_BAD_REQUEST)

class AccountsDetails(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = User.objects.get(id=request.user.id)

        user_information = {
            'email': user.email,
            "username":user.username,
            'created_at': user.created_at.strftime('%d-%m-%Y')  
        }

        recipe_finished = Meal.objects.filter(meal_plan__user = request.user,is_completed = True).count()
        recipe_generated = Meal.objects.filter(meal_plan__user = request.user).count()
        shopping_list = ListedMeal.objects.filter(user = request.user).count()
        saved_recipes = SavedRecipes.objects.filter(user = request.user).count()
        statistics = {
            'recipe_finished' : recipe_finished,
            'shopping_list':shopping_list,
            'saved_recipes':saved_recipes,
            'recipe_generated':recipe_generated
            
        }
        data = {
            "user_information" : user_information,
            "statistics" : statistics,
        }
        return Response({'ok': True, 'data': data}, status=status.HTTP_200_OK)



class MyOrders(APIView):
    permission_classes  = [IsAuthenticated]

    def get(self,request):
        orders = Order.objects.filter(buyer = request.user)
        serializer = MyOrdersserializer(orders,many=True)
        return Response({'ok':True,'data':serializer.data},status=status.HTTP_200_OK)
    
class MyOrdersDetails(APIView):
    permission_classes = [IsAuthenticated]

    def get(self,request,id):
        
        try:
            order_obj = Order.objects.get(id = id)
        except Exception:
            return Response({'ok': False, 'error' : 'Order id not found.'},status = status.HTTP_400_BAD_REQUEST)
        
        order_details = {
            'order_id':order_obj.orderid,
            'date':order_obj.created_at,
            'status':order_obj.status,
            'price':order_obj.price,
            'payment_reference':order_obj.payment_reference
        }

        seller_info = {
            'name':order_obj.meal.user.username,
            'email':order_obj.meal.user.email,
            'pickup_address':order_obj.meal.pickup_address,
        }

        delivery_info = {
            'type':order_obj.meal.delivery_method,
            'delivery_status':order_obj.status,
            'scheduled_for':order_obj.meal.available_from

        }
        data={
            'order_details':order_details,
            'seller_info':seller_info,
            'delivery_info':delivery_info
        }

        return Response({'ok':True,'data':data},status=status.HTTP_200_OK)

class MyPayout(APIView):
    permission_classes  = [IsAuthenticated]

    def get(self,request):
        orders = Payout.objects.filter(order__seller = request.user)
        serializer = MyPayoutSerializer(orders, many = True)
        return Response({'ok':True,'data':serializer.data},status = status.HTTP_200_OK)
    

class MyPayoutsDetails(APIView):
    permission_classes = [IsAuthenticated]
    def get(self,request,id):
        try:
            try:
                payout_obj = Payout.objects.get(id= id)
            except Exception:
                return Response({'ok':False,'error':'Id not found'},status=status.HTTP_400_BAD_REQUEST)
            
            recipe_image = {
                'image': payout_obj.order.meal.image.url if payout_obj.order.meal.image else None,
                'recipe_name':payout_obj.order.meal.item_name,
                'amount':payout_obj.order.price
            }
            payout_summary = {
                'payout_id':payout_obj.payoutid,
                'date_of_payout':payout_obj.payout_date,
                'status':payout_obj.status,
            }

            order_information = {
                'order_id':payout_obj.order.orderid,
                'ordered_date':payout_obj.order.created_at,
                'buyer':payout_obj.order.buyer.username,
                'delivery_status':payout_obj.order.status
            }
            
            payout_details={
                'order_value':payout_obj.amount,
                'platform_commission':'0.50',
                'refund_deducted':0,
                'amount_received':payout_obj.amount,
                'commission':payout_obj.platform_commission,
                'amount_received':payout_obj.amount_received,
                'payment_method':payout_obj.payment_method,
                'payout_released_on':payout_obj.payout_released_on
            }

            data = {
                'recipe_image':recipe_image,
                'payout_summary':payout_summary,
                'order_information':order_information,
                'payout_details':payout_details
            }

            return Response({'ok':True,'data':data},status=status.HTTP_200_OK)
    
        except Exception:
            return Response({'ok':False,'error':'server errro'},status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class ChangeEmail(APIView):
    permission_classes = [IsAuthenticated]

    def post(self,request):
        email = request.data.get('email')
        if not email:
            return Response({'ok':False,'error':'email is required'},status=status.HTTP_400_BAD_REQUEST)

        totp = pyotp.TOTP(pyotp.random_base32(), interval=120)
        otp = totp.now()
        

        UserOTP.objects.update_or_create(
            user = request.user,
            defaults = {
                'otp': otp,
                'otp_secret': totp.secret,
                'email':email,
                'created_at': timezone.now()
            }
        )

        send_mail(
            subject='Your OTP Code',
            message=f'Your OTP to change email is {otp}. It is valid for 2 minute.',
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[request.user.email],
            fail_silently=False,
        )
        return Response({'ok':True,'data':'Email sent successfully'},status=status.HTTP_200_OK)


class ResendOtp(APIView):
    throttle_classes = [UserResendOtpPerMinute or UserResendOtpPerDay]
    permission_classes = [IsAuthenticated]

    def throttled(self, request, wait):
        raise Throttled(detail={
            "ok": False,
            "error": f"Retry after {wait} seconds."
        })

    def post(self,request):
        serialized_data = ForgotPasswordSerializer(data  = request.data)
        
        if serialized_data.is_valid():
            email = serialized_data.validated_data.get('email')

            totp = pyotp.TOTP(pyotp.random_base32(), interval=60)
            otp = totp.now()

            UserOTP.objects.update_or_create(
                user=request.user,
                defaults={
                    'otp': otp,
                    'otp_secret': totp.secret,
                    'created_at': timezone.now()
                }
            )

            send_mail(
                subject='Forgot Password OTP Code',
                message=f'Your OTP is {otp}. It is valid for 1 minute.',
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[email],
                fail_silently=False,
            )

            return Response({"ok":True,"data":"Otp Send Successfully."},status=status.HTTP_200_OK)
        
        error_dict = serialized_data.errors
        field, errors = next(iter(error_dict.items()))
        error_msg = f"{field}: {errors[0].replace('"','')}"
        return Response({'ok': False,"error":error_msg},status=status.HTTP_400_BAD_REQUEST)




class VerifyNewEmail(APIView):
    permission_classes = [IsAuthenticated]

    def post(self,request):
        otp = request.data.get('otp')
        if not otp:
            return Response({'ok':False,'error':'otp is required'}, status = status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(email=request.user.email)
            user_otp = UserOTP.objects.get(user=user)
        except (User.DoesNotExist, UserOTP.DoesNotExist):
            return Response({
                "ok": False,
                "error": "Invalid email or OTP not found."
            }, status=status.HTTP_400_BAD_REQUEST)

        totp = pyotp.TOTP(user_otp.otp_secret, interval=120)

        if user_otp.is_valid() and totp.verify(otp, valid_window=1):
            
            user.is_email_verified = True
            user.email = user_otp.email
            user.save()
            return Response({
                "ok": True,
                "data": "OTP verified successfully."
            }, status=status.HTTP_200_OK)

        return Response({'ok':False,'error':'Invalid otp'},status=status.HTTP_400_BAD_REQUEST)
    
class ChangePassword(APIView):
    permission_classes = [IsAuthenticated]

    def post(self,request):
        old_password = request.data.get('old_password')
        new_password =  request.data.get('new_password')
        confirm_new_password = request.data.get('confirm_new_password')

        if new_password != confirm_new_password:
            return Response({'ok':False,'error':'Password is not matching'},status=status.HTTP_400_BAD_REQUEST)
        

        user= request.user
        if not user.check_password(old_password):
            return Response({'ok':False,'error':'Invalid Old password.'},status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new_password)
        user.save()
        return Response({'ok':True,'data':'Password changed successfully'},status=status.HTTP_200_OK)




class DeleteAccount(APIView):
    permission_classes = [IsAuthenticated]

    def post(self,request):
        user = request.user
        user.is_active = False
        user.save()
        return Response({'ok':True,'data':'Account deleted successfully.'},status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'ok': True, 'message': 'Logout successful.'}, status=status.HTTP_200_OK)
        except KeyError:
            return Response({'ok': False, 'error': 'Refresh token not provided.'}, status=status.HTTP_400_BAD_REQUEST)
        except TokenError:
            return Response({'ok': False, 'error': 'Invalid or expired token.'}, status=status.HTTP_400_BAD_REQUEST)





class RaiseDispute(APIView):
    permission_classes = [IsAuthenticated]

    def post(self,request):
        reason = request.data.get('reason')
        order_id = request.data.get('order_id')
        print(order_id)

        

        if not reason:
            return Response({'ok':False,'error':'Please fill the form.'},status = status.HTTP_400_BAD_REQUEST)
        
        if not order_id:
            return Response({'ok':False,'error':'order id is required.'},status = status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.get(id = order_id)
        except Exception:
            return Response({'ok':False,'error':'Invalid order id.'},status = status.HTTP_400_BAD_REQUEST)

        
        if Dispute.objects.filter(raised_by = request.user,order = order).exists():
            return Response({'ok':False,'error':'You have already raised the dispute.'},status=status.HTTP_400_BAD_REQUEST)

        Dispute.objects.create(order = order,raised_by = request.user,reason = reason)
        return Response({'ok':True,'data':'Dispute raised successfully.'},status=status.HTTP_200_OK)



class ClearData(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        try:
            
            UserPreference.objects.filter(user_id = request.user).delete()
            orders = Order.objects.filter(buyer=request.user)
            order_ids = list(orders.values_list("id", flat=True))
            orders.delete()
            Payout.objects.filter(order_id__in=order_ids).delete()
            Dispute.objects.filter(raised_by = request.user).delete()
            PantryItem.objects.filter(user = request.user).delete()
            OrderSession.objects.filter(user = request.user).delete()
            Notification.objects.filter(user = request.user).delete()

            return Response({'ok':True,'data':'Data cleared successfully.'},status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'ok':False,'error':str(e)},status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ShowSubscriptionModelDetails(APIView):
    permission_classes = [IsAuthenticated]

    def get(self,request):
        new_subscription = NewSubscription.objects.all()
        serializer = NewSubscriptionSerializer(new_subscription,many=True)
        return Response({'ok':True,'data':serializer.data},status=status.HTTP_200_OK)




class OneTimePaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            subscription_type = request.data.get('subscription_type')
            amount = int(float(request.data.get('amount')) * 100)  # Stripe expects amount in cents
            
            orderid = str(uuid4())

            # Create payment intent
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency="eur",
                metadata={
                    "user_id": str(request.user.id),
                    "subscription_type": subscription_type,
                    "orderid": orderid,
                },
                receipt_email=request.user.email,
            )

            # Save transaction in DB
            SubscriptionTransactions.objects.create(
                orderid=orderid,
                user=request.user,
                amount=amount / 100,  # store as decimal in DB
                currency="eur",
                subscription_type=subscription_type,
                stripe_payment_intent_id=intent.id,
                status="pending",
            )

            return Response(
                {"ok": True, "data": {"client_secret": intent.client_secret}},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"ok": False, "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )



import logging

logger = logging.getLogger("my_section")


from rest_framework.decorators import api_view, permission_classes
@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def stripe_webhook(request):
    try:
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        event = None
        logger.info("stripe_webhook called")



        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            return HttpResponse(status=400)  
        except stripe.error.SignatureVerificationError:
            return HttpResponse(status=400)  

        logger.info(f"Received Stripe event: {event['type']}")
        logger.info("Nitin Called stripe_webhook")
        
        # ---- Handle Events ---- #
        if event["type"] == "payment_intent.succeeded":
            intent = event["data"]["object"]
            orderid = intent["metadata"].get("orderid")
            payment_intent_id = intent["id"]

            try:
                order = Order.objects.get(orderid=orderid)
                order.status = "completed"  
                order.payment_reference = intent.get("charges", {}).get("data", [{}])[0].get("id")  # charge id
                order.payment_intent_id = payment_intent_id
                order.save()
            except Order.DoesNotExist:
                try:
                    txn = SubscriptionTransactions.objects.get(orderid=orderid)
                    txn.status = "succeeded"
                    txn.stripe_payment_intent_id = payment_intent_id
                    txn.save()
                except Exception as e:
                    pass

        elif event["type"] == "payment_intent.payment_failed":
            intent = event["data"]["object"]
            orderid = intent["metadata"].get("orderid")
            payment_intent_id = intent["id"]

            try:
                order = Order.objects.get(orderid=orderid)
                order.status = "failed"  # or keep "pending" if you want retry
                order.payment_intent_id = payment_intent_id
                order.save()
            except Order.DoesNotExist:
                pass
        
        

        elif event["type"] == "account.updated":
            logger.info("after account.updated")
            account_obj = event["data"]["object"]
            account_id = account_obj["id"]
            import json
            try:
                logger.info(f"Received account.updated event for account_id={account_id}")

                # fetch the full account to avoid partial payloads
                acct = stripe.Account.retrieve(account_id)

                transfers_status = acct.get("capabilities", {}).get("transfers", "pending")
                logger.info(f"Transfers capability for {account_id}: {transfers_status}")

                # verification_status = acct.get("individual", {}).get("verification", {}).get("status", "pending")
                # logger.info(f"Verification status for {account_id}: {verification_status}")

                try:
                    user_profile = User.objects.get(connected_id=account_id)
                    logger.info(f"Found user with connected_id={account_id}, updating profile.")

                    user_profile.capabilities_transfers = transfers_status
                    # user_profile.kyc_status = verification_status
                    user_profile.save()

                    logger.info(f"Updated user {user_profile.id} with transfers_status={transfers_status}")
                except User.DoesNotExist:
                    logger.warning(f"No User found with connected_id={account_id}")

            except Exception as e:
                logger.error(f"Error handling account.updated for {account_id}: {str(e)}", exc_info=True)
        
        elif event["type"] == "payout.paid":
            payout_obj = event["data"]["object"]
            payoutid = payout_obj["id"]

            try:
                payout = Payout.objects.get(payoutid=payoutid)
                payout.status = "completed"
                payout.payout_date = timezone.now()
                payout.save()
            except Payout.DoesNotExist:
                pass

        elif event["type"] == "payout.failed":
            payout_obj = event["data"]["object"]
            payoutid = payout_obj["id"]

            try:
                payout = Payout.objects.get(payoutid=payoutid)
                payout.status = "failed"
                payout.save()
            except Payout.DoesNotExist:
                pass
        
        elif event["type"] == "transfer.created":
            transfer = event["data"]["object"]
            try:
                payout = Payout.objects.get(transferid=transfer["id"])
                payout.status = "created"
                payout.payout_date = timezone.now()
                payout.save()
            except Payout.DoesNotExist:
                pass
        
        elif event['type'] == 'transfer.paid':
            transfer = event['data']['object']
            try:
                payout = Payout.objects.get(transferid=transfer['id'])
                payout.status = "transferred"
                payout.payout_date = timezone.now()
                payout.save()
            except Payout.DoesNotExist:
                pass

        elif event['type'] == 'transfer.failed':
            transfer = event['data']['object']
            try:
                payout = Payout.objects.get(transferid=transfer['id'])
                payout.status = "failed"
                payout.failure_reason = transfer.get('failure_message', '')
                payout.save()
            except Payout.DoesNotExist:
                pass
        
        elif event["type"] in ["refund.created", "refund.updated", "refund.succeeded", "refund.failed"]:
            refund_obj = event["data"]["object"]
            refund_id = refund_obj["id"]
            payment_intent = refund_obj.get("payment_intent")
            refund_status = refund_obj.get("status", "pending")
            refund_reason = refund_obj.get("reason", "")
            refund_amount = refund_obj.get("amount", 0) / 100  # Stripe sends in cents

            try:
                # Find related order via payment_intent
                order = Order.objects.get(payment_intent_id=payment_intent)
            except Order.DoesNotExist:
                logger.warning(f"No order found for payment_intent={payment_intent}")
                return HttpResponse(status=200)

            try:
                # Check if refund already exists
                refund = Refund.objects.get(refund_id=refund_id)
            except Refund.DoesNotExist:
                # Create new refund
                refund = Refund.objects.create(
                    order=order,
                    requested_by=order.buyer,  # assuming buyer requested refund
                    refund_id=refund_id,
                    amount=refund_amount,
                    reason=refund_reason,
                    status=refund_status,
                )

            # Update refund status & timestamp
            refund.status = refund_status
            refund.processed_at = timezone.now().date()
            refund.save()

            # Optionally mark order as refunded
            if refund_status == "succeeded":
                order.status = "refunded"
                order.save()

        return HttpResponse(status=200)
    except Exception as e:
        logger.info("stripe_webhook called and error occurred")
        logger.info(f"Received Stripe event: {str(e)}")
        return HttpResponse(status=500)

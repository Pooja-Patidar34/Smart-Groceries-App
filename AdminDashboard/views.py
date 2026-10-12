from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth import authenticate, login, get_user_model,logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.sessions.models import Session
from django.utils import timezone
from profile_section.models import UserPreference
from django.core.paginator import Paginator
from .forms import UserEditForm,NewSubscriptionForm
import csv
from django.http import HttpResponse
from accounts.models import User,SubscriptionTransactions,SubscriptionPlan
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.conf import settings
from transactions.models import Order,Dispute,Payout
from recipe_section.models import ListedMeal
from pantry_section.models import PantryItem
import stripe
from AdminDashboard.models import NewSubscription,Refund
from decimal import Decimal
from django.urls import resolve
from notifications.utils import send_fcm_notification
from django.http import JsonResponse
from notifications.models import Notification,UserFCMToken
from django.db.models.functions import TruncDate
import datetime,json
from datetime import timedelta
from accounts.models import StaticData
from .forms import StaticDataForm
from transactions.models import Payout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from notifications.utils import send_fcm_notification 
from .models import Configure
from decimal import Decimal
from django.db.models import Sum, F, Count, Q, DecimalField, ExpressionWrapper
from django.shortcuts import render
from transactions.models import Payout
from django.utils.dateparse import parse_date
import stripe
from shoppinglist.models import ExtractedIngredientsFromMail



stripe.api_key = settings.STRIPE_SECRET_KEY


User = get_user_model()


def is_superuser(user):
    return user.is_superuser


def admin_login(request):
    if request.method == "POST":
        email = request.POST.get("email") 
        password = request.POST.get("password")
        user = authenticate(request, email=email, password=password)
        if user is not None and user.is_staff and user.is_superuser:
            login(request, user)
            return redirect("admin_dashboard")
        else:
            messages.error(request, "Invalid email or password, or you are not an admin.")
            return redirect("admin_login")
    return render(request, "AdminDashboard/adminlogin.html")


def is_admin(user):
    return user.is_staff 


@login_required

@user_passes_test(is_admin)
def dashboard(request):
    return render(request, "AdminDashboard/admindashboard.html")


@login_required
def admin_logout(request):
    logout(request)
    return redirect("admin_login")


@login_required
def AllUser(request):
    search_query = request.GET.get('q', '').strip()
    users_list = User.objects.filter(Q(username__icontains=search_query) | Q(email__icontains=search_query)).order_by('-created_at')

    paginator = Paginator(users_list, 4) 
    page_number = request.GET.get("page")
    users = paginator.get_page(page_number)
    current_url_name = resolve(request.path_info).url_name
    return render(request,"AdminDashboard/allusers.html",{"users": users, "query": search_query,"current_url_name":current_url_name})


@login_required(login_url='/accounts/login/')
def all_registered_users(request):
    search_query = request.GET.get('q', '').strip()
    users_list = User.objects.exclude(id=request.user.id)

    if search_query:
        users_list = users_list.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query)
        ).order_by("-created_at")
    paginator = Paginator(users_list, 6)
    page_number = request.GET.get('page')
    users = paginator.get_page(page_number)
    current_url_name = resolve(request.path_info).url_name
    return render(request, "AdminDashboard/allregisteredusers.html", {"users": users,"current_url_name":current_url_name,'search_query':search_query})


@login_required(login_url='/accounts/login/')
def all_logged_in_users(request):
    search_query = request.GET.get('q', '').strip()
    users_list = User.objects.filter(is_active=True) 

    if search_query:
        users_list = users_list.filter(
            Q(username__icontains=search_query) | Q(email__icontains=search_query)
        ).order_by('-created_at')
    paginator = Paginator(users_list, 6)
    page_number = request.GET.get('page')
    users = paginator.get_page(page_number)

    current_url_name = resolve(request.path_info).url_name
    return render(request,"AdminDashboard/all_logged_users.html",{"users": users,"current_url_name": current_url_name,"search_query": search_query})


@login_required
def user_profile(request, user_id):
    user = get_object_or_404(User, id=user_id)
    try:
        preferences = UserPreference.objects.get(user_id=user)
    except UserPreference.DoesNotExist:
        preferences = None
    return render(request, "AdminDashboard/user_profile.html", {"user": user,"preferences": preferences})


@login_required
def block_user(request, user_id):
    user=get_object_or_404(User, id=user_id)

    if request.user == user:
        messages.error(request,"You can't Suspend yourself")
        return redirect('AllUser')
    if user.is_superuser:
        messages.error(request,"You can't Suspend Superuser")
        return redirect('AllUser')
    
    user.is_active=False
    user.save()
    messages.success(request,f"User {user.username} has been Suspend successfully !!")
    return redirect('AllUser')


login_required
def unblock_user(request, user_id):
    user=get_object_or_404(User, id=user_id)
    if request.user==user:
        messages.error(request,"You can't Unsuspend a superuser (they are always active).")
        return redirect('AllUser')
    
    user.is_active=True
    user.save()
    messages.success(request,f"User {user.username} has been Unsuspend successfully")
    return redirect('AllUser')


@login_required
def edit_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, f"User {user.username}'s profile updated successfully!")
            return redirect('AllUser')
    else:
        form = UserEditForm(instance=user)
    return render(request, 'AdminDashboard/edit_user.html', {'form': form, 'user': user})


@login_required
def subscription_transaction(request):
    query = request.GET.get('q', '').strip()
    transactions = SubscriptionTransactions.objects.filter(
        orderid__icontains=query
    ).select_related("user").order_by('-created_at')

    paginator = Paginator(transactions, 4)
    page_number = request.GET.get("page")
    transactions = paginator.get_page(page_number)

    current_url_name = resolve(request.path_info).url_name
    return render(request, 'AdminDashboard/subscription_transactions.html', {'transactions': transactions,'query': query,'current_url_name': current_url_name})


@login_required
def custom_logout(request):
    if request.user.is_authenticated:
        request.user.last_logout = timezone.now()
        request.user.save()
    logout(request)
    return redirect('login') 


@login_required
def export_users_csv(request):
    if not request.user.is_staff: 
        return HttpResponse("Unauthorized", status=401) 
    response = HttpResponse( content_type="text/csv", headers={"Content-Disposition": 'attachment; filename="users.csv"'}, ) 
    writer = csv.writer(response) 
    writer.writerow([ 
        "ID", "Username", 
        "Email", "Gender", 
        "Contact", "DOB", 
        "Is Active", "Is Email Verified", 
        "Created At" ])
    user=User.objects.all().values_list( 
        "id", "username", 
        "email", "gender",
        "contact", "dob", 
        "is_active", "is_email_verified",
        "created_at" )
    writer.writerow(user) 
    return response


@login_required
def export_users_pdf(request):
    if not request.user.is_staff:
        return HttpResponse("Unauthorized", status=401)
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="users.pdf"'
    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    # Title
    p.setFont("Helvetica-Bold", 14)
    p.drawString(200, height - 50, "User Report")
    # Table headers
    p.setFont("Helvetica-Bold", 10)
    headers = [
        "ID", "Username", "Email", "Gender", "Contact",
        "DOB", "Is Active", "Is Email Verified", "Created At"
    ]
    x = 50
    y = height - 100
    for head in headers:
        p.drawString(x, y, head)
        x += 70
    # User data
    p.setFont("Helvetica", 9)
    y -= 20
    for user in User.objects.all():
        x = 50
        row = [
            str(user.id), user.username, user.email, user.gender or "",
            user.contact or "", str(user.dob or ""), str(user.is_active),
            str(user.is_email_verified), str(user.created_at.strftime("%Y-%m-%d"))
        ]
        for col in row:
            p.drawString(x, y, col[:12])  
            x += 70
        y -= 20
        if y < 50:  
            p.showPage()
            y = height - 100
    p.save()
    return response



token_generator = PasswordResetTokenGenerator()
def send_password_reset_link(request, user_id):
    user = User.objects.get(id=user_id)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = token_generator.make_token(user)

    reset_url = request.build_absolute_uri(
        reverse("reset_password_confirm", kwargs={"uidb64": uid, "token": token})
    )
    send_mail(
        subject="Password Reset Request",
        message=f"Hi {user.username},\n\nClick the link below to reset your password:\n{reset_url}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )
    messages.success(request, f"Password reset link sent to {user.email}")
    return redirect("AllUser")  


@login_required
def reset_password_confirm(request, uidb64, token):

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and token_generator.check_token(user, token):
        if request.method == "POST":
            new_password = request.POST.get("new_password")
            confirm_password = request.POST.get("confirm_password")

            if new_password != confirm_password:
                messages.error(request, "Passwords do not match")
            else:
                user.set_password(new_password)
                user.save()
                messages.success(request, "Password changed successfully!")
                return redirect("admin_login")  # redirect after success
        return render(request, "AdminDashboard/reset_password_confirm.html", {"uidb64": uidb64, "token": token})
    else:
        messages.error(request, "Invalid or expired link")
        return redirect("admin_login")

@login_required
def all_orders(request):
    orders = Order.objects.select_related("buyer", "seller", "meal").order_by("-created_at")
    paginator = Paginator(orders, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "AdminDashboard/all_orders.html", {
        "orders": page_obj, 
        "page_obj": page_obj,
        "current_url_name": resolve(request.path_info).url_name
    })

@login_required
def list_meal(request):
    search_query = request.GET.get("q", "").strip().lower()

    meals = ListedMeal.objects.select_related("user").order_by("-created_at")
    if search_query:
        meals = meals.filter(
            Q(item_name__istartswith=search_query) |
            Q(user__email__istartswith=search_query)
            
        )

    paginator = Paginator(meals, 2)
    page_number = request.GET.get("page")
    meals_page = paginator.get_page(page_number)
    current_url_name = resolve(request.path_info).url_name

    return render(
        request,
        "AdminDashboard/list_meals.html",
        {
            "meals": meals_page,
            "query": search_query, 
            "current_url_name": current_url_name,
        }
    )



@login_required
def pantry_list(request):
    query = request.GET.get("q", "").strip()
    pantries = (PantryItem.objects.select_related("user", "ingredient").filter(Q(user__username__icontains=query) | Q(ingredient__name__icontains=query)).order_by("-created_at"))

    paginator = Paginator(pantries, 3)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    current_url_name = resolve(request.path_info).url_name
    return render(request,"AdminDashboard/pantry_list.html",{"page_obj": page_obj,"query": query,"current_url_name": current_url_name})

@login_required
def subscription_list(request):
    subscriptions = NewSubscription.objects.all()
    current_url_name = resolve(request.path_info).url_name
    return render(request, "AdminDashboard/list.html", {"subscriptions": subscriptions,"current_url_name":current_url_name})


@login_required
def subscription_create(request):
    if request.method == "POST":
        form = NewSubscriptionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("subscription_list")
    else:
        form = NewSubscriptionForm()
    current_url_name = resolve(request.path_info).url_name
    return render(request, "AdminDashboard/create_subscription.html", {"form": form,'current_url_name':current_url_name})

@login_required(login_url='/accounts/login/')
def subscription_update(request, pk):
    subscription = get_object_or_404(NewSubscription, pk=pk)

    if request.method == "POST":
        subscription.name = request.POST.get("name")
        subscription.price = request.POST.get("price")
        subscription.duration = request.POST.get("duration")
        subscription.description = request.POST.get("description")
        plan_type = request.POST.get("plan_type")
        if plan_type:                   
            subscription.plan_type = plan_type

        subscription.save() 
        return redirect("subscription_list")

    return render(request, "AdminDashboard/subscription_update.html", {"subscription": subscription})

@login_required
def subscription_delete(request, pk):
    subscription = get_object_or_404(NewSubscription, pk=pk)
    if request.method == "POST":
        subscription.delete()
        return redirect("subscription_list")
    return render(request, "AdminDashboard/subscription_delete.html", {"subscription": subscription})


@login_required
def pending_refunds(request):
    refunds = Refund.objects.filter(status="pending").order_by('-created_at')
    return render(request, 'AdminDashboard/pending_refunds.html', {'refunds': refunds})


@login_required
def process_refund(request, refund_id):
    refund = get_object_or_404(Refund, id=refund_id)
    print(refund_id)
    order = refund.order
    order_amount = order.price

    # if request.method == 'POST':
    refund_charges = Decimal(request.POST.get('refund_charges', '0.0'))
    refunded_amount = max(order_amount - refund_charges, 0)

    try:
        with transaction.atomic():
            stripe_refund_id = None
            if order.payment_intent_id:
                stripe_refund = stripe.Refund.create(
                    payment_intent=order.payment_intent_id,
                    amount=int(refunded_amount * 100),
                    reason='requested_by_customer'
                )
                stripe_refund_id = stripe_refund.id

            # Update the existing Refund object
            refund.amount = refunded_amount
            refund.refund_charges = refund_charges
            refund.refund_id = stripe_refund_id
            refund.status = 'pending'
            refund.processed_at = timezone.now()
            refund.save()

            messages.success(request, "Refund processed successfully.")
    except Exception as e:
        print("error",e)
        messages.error(request, f"Refund failed: {str(e)}")

    return redirect('pending_refunds')




login_required
def all_refunds(request):
    refunds=Refund.objects.all().order_by('-created_at')
    return render(request,'AdminDashboard/all_refunds.html',{'refunds':refunds})


@login_required
def notify_expired_subscription(request):
    sub = SubscriptionTransactions.objects.filter(subscription_status='expired')
    notified_users = []

    for s in sub:
        tokens = UserFCMToken.objects.filter(user=s.user).values_list("token", flat=True)
        if tokens:
            send_fcm_notification(
                tokens, 
                "Subscription Expired",
                "Your subscription has expired. Please renew to continue.",
                "https://yourcdn.com/expired.png"
            )
            notified_users.append(s.user.username)

    return JsonResponse({"status": "success", "message": f"Notification sent to {notified_users}"})


@login_required
def user_metrics(request):
    total_registered = User.objects.count()
    active_users = User.objects.filter(is_active=True, is_superuser=False, is_staff=False).count()
    today = timezone.now()
    one_month_ago = today - timedelta(days=60)
    new_signups = User.objects.filter(created_at__gte=one_month_ago).count()

    signup_data = (
        User.objects.filter(created_at__gte=one_month_ago)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )
    labels = [item["date"].strftime("%Y-%m-%d") for item in signup_data if item["date"]]
    data = [item["count"] for item in signup_data if item["date"]]

    return render(request, "AdminDashboard/user_metrics.html", {
        "total_registered": total_registered,
        "active_users": active_users,
        "new_signups": new_signups,
        "labels": json.dumps(labels),
        "data": json.dumps(data)
    })



@login_required
def new_signups(request):
    today = timezone.now()
    one_month_ago = today - timedelta(days=60)
    query = request.GET.get("q", "").strip()

    new_signup = (
        User.objects.filter(created_at__gte=one_month_ago)
        .filter(Q(username__icontains=query) | Q(email__icontains=query))
        .order_by('-created_at')  # Newest first
    )

    paginator = Paginator(new_signup, 4)
    page_number = request.GET.get("page")
    new_signups = paginator.get_page(page_number)

    current_url_name = resolve(request.path_info).url_name
    return render(
        request,
        "AdminDashboard/new_signups.html",
        {
            "new_signups": new_signups,
            "current_url_name": current_url_name,
            "query": query,
        },
    )


@login_required
def dispute(request):
    # Fetch filters from query params
    q = request.GET.get('q', '').strip()
    resolved_filter = request.GET.get('resolved', '')
    from_date = request.GET.get('from_date', '')
    to_date = request.GET.get('to_date', '')

    # Base queryset
    disputes = Dispute.objects.all().order_by('-created_at')

    # Search by username or email
    if q:
        disputes = disputes.filter(
            Q(raised_by__username__icontains=q) |
            Q(raised_by__email__icontains=q)
        )
    print(disputes)
    # Filter by resolved status
    if resolved_filter == 'true':
        disputes = disputes.filter(resolved=True)
    elif resolved_filter == 'false':
        disputes = disputes.filter(resolved=False)

    # Date filters
    if from_date:
        disputes = disputes.filter(created_at__date__gte=parse_date(from_date))
    if to_date:
        disputes = disputes.filter(created_at__date__lte=parse_date(to_date))

    # Add current URL name for sidebar highlighting or nav active state
    current_url_name = resolve(request.path_info).url_name

    context = {
        'dispute': disputes,
        'current_url_name': current_url_name,
        'search_query': q,
        'resolved_filter': resolved_filter,
        'from_date': from_date,
        'to_date': to_date,
    }

    return render(request, 'AdminDashboard/dispute.html', context)

@login_required
def subscription_analytics(request):
    total_active_subscription=SubscriptionTransactions.objects.filter(status='Active').count()
    total_expired_subscription=SubscriptionTransactions.objects.filter(status='Expired').count()
    total_trial_subscription=SubscriptionTransactions.objects.filter(subscription_type='Trial').count()
    return render(request,'AdminDashboard/subscription_analytics.html',
    {
            'total_active_subscription':total_active_subscription,
            'total_expired_subscription':total_expired_subscription,
            'total_trial_subscription':total_trial_subscription
    })

@login_required
def active_subscription(request):
    query=request.GET.get("q", "").strip()
    actives=(SubscriptionTransactions.objects.select_related("user").filter(status='Active').filter(Q(user__id__icontains=query) | Q(user__email__icontains=query)).order_by("-created_at"))
    paginator = Paginator(actives, 5)
    active = paginator.get_page(request.GET.get("page"))
    return render(request,'AdminDashboard/active_subscription.html',{'active':active,"query": query})

@login_required
def expired_subscription(request):
    expired=SubscriptionTransactions.objects.filter(status='Expired')
    return render(request,'AdminDashboard/expired_subscription.html',{'expired':expired})

@login_required
def trial_subscription(request):
    query = request.GET.get("q", "").strip()
    trials = (SubscriptionTransactions.objects.select_related("user").filter(subscription_type="Trial").filter(
            Q(user__id__icontains=query) | Q(user__email__icontains=query)).order_by("-created_at"))
    paginator = Paginator(trials, 5)
    trial = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "AdminDashboard/trial_subscription.html",
        {"trial": trial, "query": query},
    )


@login_required
def show_termsandconditions(request):
    query = request.GET.get("q", "").strip() 
    show_terms = StaticData.objects.all().order_by("-created_at").filter(Q(title__icontains=query) | Q(type__icontains=query))
    paginator = Paginator(show_terms, 3)  
    page_number = request.GET.get("page")
    terms = paginator.get_page(page_number)
    return render(
        request,
        "AdminDashboard/show_termsandconditions.html",
        {"terms": terms, "query": query},  
    )


@login_required
def edit_termsandcondition(request, pk):
    terms = get_object_or_404(StaticData, pk=pk)

    if request.method == 'POST':
        content = request.POST.get("content")
        terms.content = content
        terms.save()
        return redirect('show_termsandconditions')

    return render(request, 'AdminDashboard/edit_termsandconditions.html', {'terms': terms})

@login_required
def payout_lists(request):
    payouts = (
        Payout.objects.filter(
            order__status="completed",
            payout_released_on__isnull=True
        )
        .exclude(status="transferred")     # Already paid payouts hide
        .filter(
            Q(order__dispute__resolved=True) | Q(order__dispute__isnull=True)
        )
    )

    for payout in payouts:
        try:
            dispute = payout.order.dispute
            if dispute.resolved and dispute.send_amount_to == payout.order.seller:
                payout.recipient = payout.order.seller
            else:
                payout.recipient = payout.order.buyer
        except Dispute.DoesNotExist:
            payout.recipient = payout.order.seller

    return render(request, "AdminDashboard/payouts.html", {"payouts": payouts})


@login_required
def payout_view(request, id):
    if request.method == "POST":
        payout = Payout.objects.get(id=id)
        if payout.status == "transferred":
            messages.error(request, "This payout has already been transferred!")
            return redirect("payout_lists")

        amount = int((payout.amount / 10) * 100)

        try:
            transfer = stripe.Transfer.create(
                amount=1 * 100,
                currency="eur",
                destination=payout.order.seller.connected_id,
                description=f"Transfer for payout #{payout.id}"
            )

            payout.payoutid = transfer.id
            payout.status = "transferred"
            payout.payout_date = timezone.now()
            payout.save()

            messages.success(request, f"Transfer successful! ID: {transfer.id}")

        except Exception as e:
            payout.status = "failed"
            payout.failure_reason = str(e)
            payout.save()
            messages.error(request, f"Error: {str(e)}")

        return redirect("payout_lists")

    return redirect("payout_lists")

def is_admin(user):
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(is_admin)
def notify_form(request):
    """Render simple page where admin can send notifications."""
    return render(request, "AdminDashboard/notify_all.html")



@csrf_exempt
@login_required
@user_passes_test(is_admin)
@require_POST
def notify_all_users(request):
    """Send a custom notification to all users."""
    title = request.POST.get("title")
    message = request.POST.get("message")
    image_url = request.POST.get("image_url", None)

    if not title or not message:
        return JsonResponse({"status": "error", "message": "Title and message are required."}, status=400)

    tokens = list(UserFCMToken.objects.values_list("token", flat=True))
    print(tokens)
    if not tokens:
        return JsonResponse({"status": "error", "message": "No FCM tokens found."}, status=404)

    send_fcm_notification(tokens, title, message, image_url)
    return JsonResponse({"status": "success", "message": f"Notification sent to {len(tokens)} users."})

def set_commission(request):
    if request.method == 'POST':
        rate = request.POST.get('rate')
        commission_id = request.POST.get('commission_id')

        if commission_id: 
            commission = Configure.objects.get(id=commission_id)
            commission.value = rate
            commission.save()
            messages.success(request, 'Commission rate updated successfully!')
        else:  
            Configure.objects.create(value=rate)
            messages.success(request, 'New commission rate added!')

        return redirect('set_commission')

    commissions = Configure.objects.all().order_by('-updated_at')
    return render(request, 'AdminDashboard/set_commission.html', {'commissions': commissions})


def commission_report(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Exclude refunded orders
    refunded_order_ids = Refund.objects.filter(status='succeeded').values_list('order_id', flat=True)

    # Base query
    orders = Order.objects.filter(status='completed').exclude(id__in=refunded_order_ids).select_related('meal', 'seller', 'buyer')

    # Apply date filters
    if start_date:
        orders = orders.filter(created_at__date__gte=parse_date(start_date))

    if end_date:
        orders = orders.filter(created_at__date__lte=parse_date(end_date))

    # Commission per order (using meal commission_rate)
    order_commissions = []
    for order in orders:
        meal_rate = order.meal.commission_rate if order.meal and order.meal.commission_rate else Decimal('0')
        commission_amount = (order.price * meal_rate / Decimal('100')) if order.price else Decimal('0')
        order_commissions.append({
            'orderid': order.orderid,
            'seller_email': order.seller.email,
            'seller_name': order.seller.username,
            'buyer_email': order.buyer.email,
            'meal_name': order.meal.item_name if order.meal else '-',
            'price': order.price,
            'commission_earned': commission_amount,
            'created_at': order.created_at,
        })

    # Summary by seller (sum of commissions per seller)
    seller_commissions = {}
    for oc in order_commissions:
        seller_email = oc['seller_email']
        if seller_email not in seller_commissions:
            seller_commissions[seller_email] = {
    'seller_name': oc['seller_name'],
    'seller_email': seller_email,   # <-- Add this
    'total_orders': 0,
    'total_sales': Decimal('0'),
    'commission_earned': Decimal('0'),
}
        seller_commissions[seller_email]['total_orders'] += 1
        seller_commissions[seller_email]['total_sales'] += oc['price'] or Decimal('0')
        seller_commissions[seller_email]['commission_earned'] += oc['commission_earned']

    seller_commissions_list = list(seller_commissions.values())

    return render(request, 'AdminDashboard/commission_report.html', {
        'order_commissions': order_commissions,
        'seller_commissions': seller_commissions_list,
        'start_date': start_date,
        'end_date': end_date,
    })



def detailed_commission_report(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Exclude refunded orders
    refunded_order_ids = Refund.objects.filter(status='succeeded').values_list('order_id', flat=True)

    # Base query
    orders = Order.objects.filter(status='completed').exclude(id__in=refunded_order_ids).select_related('meal', 'seller', 'buyer')
    payouts = Payout.objects.filter(status='completed').exclude(order_id__in=refunded_order_ids).select_related('order__meal', 'order__seller')

    # Apply date filters
    if start_date:
        orders = orders.filter(created_at__date__gte=parse_date(start_date))
        payouts = payouts.filter(payout_date__date__gte=parse_date(start_date))
    if end_date:
        orders = orders.filter(created_at__date__lte=parse_date(end_date))
        payouts = payouts.filter(payout_date__date__lte=parse_date(end_date))

    # Commission per order (using meal commission_rate)
    order_commissions = []
    for order in orders:
        meal_rate = order.meal.commission_rate if order.meal and order.meal.commission_rate else Decimal('0')
        commission_amount = (order.price * meal_rate / Decimal('100')) if order.price else Decimal('0')
        order_commissions.append({
            'orderid': order.orderid,
            'seller_email': order.seller.email,
            'seller_name': order.seller.username,
            'buyer_email': order.buyer.email,
            'meal_name': order.meal.item_name if order.meal else '-',
            'price': order.price,
            'commission_earned': commission_amount,
            'created_at': order.created_at,
        })

    # Summary by seller (sum of commissions per seller)
    seller_commissions = {}
    for oc in order_commissions:
        seller_email = oc['seller_email']
        if seller_email not in seller_commissions:
            seller_commissions[seller_email] = {
                'seller_name': oc['seller_name'],
                'total_orders': 0,
                'total_sales': Decimal('0'),
                'commission_earned': Decimal('0'),
            }
        seller_commissions[seller_email]['total_orders'] += 1
        seller_commissions[seller_email]['total_sales'] += oc['price'] or Decimal('0')
        seller_commissions[seller_email]['commission_earned'] += oc['commission_earned']

    seller_commissions_list = list(seller_commissions.values())

    # Realized commissions from payouts
    payout_commissions = []
    for payout in payouts:
        seller_email = payout.order.seller.email
        payout_commissions.append({
            'seller_email': seller_email,
            'seller_name': payout.order.seller.username,
            'total_payouts': 1,
            'total_sales': payout.amount or Decimal('0'),
            'commission_earned': payout.platform_commission or Decimal('0'),
        })

    # Aggregate payouts per seller
    payout_summary = {}
    for pc in payout_commissions:
        seller_email = pc['seller_email']
        if seller_email not in payout_summary:
            payout_summary[seller_email] = {
                'seller_name': pc['seller_name'],
                'total_payouts': 0,
                'total_sales': Decimal('0'),
                'commission_earned': Decimal('0'),
                'seller_email': seller_email, 
            }
        payout_summary[seller_email]['total_payouts'] += pc['total_payouts']
        payout_summary[seller_email]['total_sales'] += pc['total_sales']
        payout_summary[seller_email]['commission_earned'] += pc['commission_earned']

    payout_commissions_list = list(payout_summary.values())

    return render(request, 'AdminDashboard/detailed_commission_report.html', {
        'order_commissions': order_commissions,
        'seller_commissions': seller_commissions_list,
        'payout_commissions': payout_commissions_list,
        'start_date': start_date,
        'end_date': end_date,
    })



@login_required
def resolve_dispute(request, pk):
    dispute = get_object_or_404(Dispute, id=pk)

    if request.method == 'POST':
        resolution_comment = request.POST.get('resolution_comment', '').strip()
        send_amount_to = request.POST.get('send_amount_to', '').strip()  # 'buyer' or 'owner'

        if resolution_comment and send_amount_to in ['buyer', 'owner']:
            dispute.resolution_comment = resolution_comment
            dispute.resolved = True
            dispute.resolved_at = timezone.now()

            # Assign the correct user to send_amount_to
            if send_amount_to == 'buyer':
                dispute.send_amount_to = dispute.order.buyer
                # Create a Refund
                Refund.objects.create(
                    order=dispute.order,
                    requested_by=dispute.order.buyer,
                    amount=dispute.order.price,
                    status='pending',
                    reason=dispute.reason,
                )
            elif send_amount_to == 'owner':
                dispute.send_amount_to = dispute.order.seller
                # Create a Payout
                Payout.objects.create(
                    order=dispute.order,
                    amount=dispute.order.price,
                    status='pending',
                )

            dispute.save()
            messages.success(request, "Dispute marked as resolved successfully.")
        else:
            messages.error(request, "Please fill all required fields correctly.")

    return redirect('dispute')


@login_required
def refunds_chargeback(request):
    current_url_name = resolve(request.path_info).url_name

    # --------------------------
    # REFUND DETAILS
    # --------------------------
    refunds = Refund.objects.select_related('order', 'requested_by').order_by('-created_at')

    total_refunds = refunds.aggregate(total=Sum('amount'))['total'] or 0
    total_refund_charges = refunds.aggregate(total=Sum('refund_charges'))['total'] or 0
    total_loss = total_refunds + total_refund_charges

    # --------------------------
    # PAYOUT DETAILS (UPCOMING / SUCCESSFUL / FAILED)
    # --------------------------
    payouts = Payout.objects.select_related('order').all()

    upcoming_amount = payouts.filter(Q(status='pending') | Q(status='on_hold')).aggregate(total=Sum('amount'))['total'] or 0
    successful_amount = payouts.filter(status='completed').aggregate(total=Sum('amount'))['total'] or 0
    failed_amount = payouts.filter(status='failed').aggregate(total=Sum('amount'))['total'] or 0

    total_payout_amount = upcoming_amount + successful_amount + failed_amount

    # Platform commission total
    total_commission = payouts.aggregate(total=Sum('platform_commission'))['total'] or 0

    context = {
        'current_url_name': current_url_name,
        'refunds': refunds,
        'total_refunds': total_refunds,
        'total_refund_charges': total_refund_charges,
        'total_loss': total_loss,
        'upcoming_amount': upcoming_amount,
        'successful_amount': successful_amount,
        'failed_amount': failed_amount,
        'total_payout_amount': total_payout_amount,
        'total_commission': total_commission,
    }

    return render(request, 'AdminDashboard/refunds_chargeback.html', context)


def seller_meals_report(request, email):
    seller = get_object_or_404(User, email=email)
    meals = ListedMeal.objects.filter(
        user=seller,
        order__status='completed'   
    ).distinct()
    print(meals)
    return render(request, 'AdminDashboard/seller_meals_report.html', {
        'seller': seller,
        'meals': meals,
    })



@login_required
def instacart_management(request):
    obj = ExtractedIngredientsFromMail.objects.all()
    return render(request, 'AdminDashboard/instacartmanagement.html', {'objects': obj})



def instacart_ingredients_details(request, id):
    all_details = ExtractedIngredientsFromMail.objects.filter(user__id=id)

    filtered_details = []
    for item in all_details:
        gtp_data = item.gtp_response or []

        if isinstance(gtp_data, list):
            for obj in gtp_data:
                if isinstance(obj, dict) and obj.get("is_added_to_pantry") == True:
                    filtered_details.append(item)
                    break  
    
    print(filtered_details)
    return render(request, 'AdminDashboard/instacartingredientsdetails.html', {'details': filtered_details})

from transactions.models import Order
from accounts.models import User
from AdminDashboard.models import NewSubscription
def order_counts(request):
    total_orders = Order.objects.count()
    return {
        "total_orders": total_orders
    }

def user_counts(request):
    total_users=User.objects.count()
    return{
        "total_users":total_users
        }

def subscription_counts(request):
    total_subscriptions=NewSubscription.objects.count()
    return{
        "total_subscriptions":total_subscriptions
    }
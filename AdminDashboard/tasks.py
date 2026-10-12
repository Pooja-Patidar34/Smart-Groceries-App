# app/tasks.py
from celery import shared_task

@shared_task
def run_nightly_payouts():
    import stripe
    from django.conf import settings
    from django.utils import timezone
    from datetime import timedelta
    from transactions.models import Payout
    from AdminDashboard.models import Configure

    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Fetch configuration values
    probation_days = Configure.objects.get(label="PROBATION").value
    commission_percent = Configure.objects.get(label="COMMISSION").value

    # Get all pending payouts
    payouts = Payout.objects.filter(status="pending")

    for payout in payouts:
        order = payout.order

        # Check if the order is past probation period
        if order.created_at <= timezone.now() - timedelta(days=probation_days):

            # Calculate commission
            commission_amount = (payout.amount * commission_percent) / 100
            final_transfer_amount = payout.amount - commission_amount

            # Convert to cents (Stripe expects smallest currency unit)
            stripe_amount = int(final_transfer_amount * 100)

            try:
                # Create transfer to seller’s Stripe connected account
                transfer = stripe.Transfer.create(
                    amount=stripe_amount,
                    currency="eur",
                    destination=order.seller.connected_id,
                    description=f"Payout for order #{order.id}",
                    metadata={
                        "user_id": str(order.seller.id),
                        "order_id": str(order.id)
                    }
                )

                # Update payout record
                payout.transferid = transfer.id
                payout.status = "transferred"
                payout.payout_date = timezone.now()
                payout.save()

                print(f"Transfer successful for payout {payout.id}")

            except Exception as e:
                payout.status = "failed"
                payout.failure_reason = str(e)
                payout.save()
                print(f"Error for payout {payout.id}: {str(e)}")

        else:
            print(f"Payout {payout.id} still in probation period.")

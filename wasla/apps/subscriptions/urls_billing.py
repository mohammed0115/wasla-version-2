"""
URL routing for SaaS recurring billing API.

Registers all ViewSets and endpoints:
- Subscriptions (CRUD + actions)
- Invoices (read-only)
- Billing cycles (read-only)
- Payment methods
- Webhooks
- Dunning management
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views_billing import (
    SubscriptionViewSet,
    InvoiceViewSet,
    BillingCycleViewSet,
    PaymentMethodViewSet,
    WebhookViewSet,
    DunningViewSet,
)

# Create a router and register viewsets
router = DefaultRouter()
router.register(r'subscriptions', SubscriptionViewSet, basename='subscription')
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'billing-cycles', BillingCycleViewSet, basename='billing-cycle')
router.register(r'payment-methods', PaymentMethodViewSet, basename='payment-method')
router.register(r'webhooks', WebhookViewSet, basename='webhook')
router.register(r'dunning', DunningViewSet, basename='dunning')

# URL patterns
app_name = 'subscriptions_billing'

urlpatterns = [
    path('', include(router.urls)),
]

"""
API Endpoints Structure:

SUBSCRIPTIONS:
  GET     /subscriptions/                    - List all subscriptions
  POST    /subscriptions/                    - Create new subscription
  GET     /subscriptions/{id}/               - Get subscription details
  PUT     /subscriptions/{id}/               - Update subscription (fields like billing_cycle_anchor)
  DELETE  /subscriptions/{id}/               - Cancel subscription
  POST    /subscriptions/{id}/change_plan/   - Change subscription plan with proration
  POST    /subscriptions/{id}/cancel/        - Cancel with reason
  POST    /subscriptions/{id}/suspend/       - Suspend (admin only)
  POST    /subscriptions/{id}/reactivate/    - Reactivate (admin only)
  POST    /subscriptions/{id}/add_grace_period/ - Add grace period
  GET     /subscriptions/{id}/billing_status/ - Get billing status

INVOICES (Read-only):
  GET     /invoices/                         - List all invoices (filtered by tenant)
  GET     /invoices/{id}/                    - Get invoice details

BILLING CYCLES (Read-only):
  GET     /billing-cycles/                   - List billing cycles
  GET     /billing-cycles/{id}/              - Get cycle details

PAYMENT METHODS:
  GET     /payment-methods/                  - Get subscription's payment method
  POST    /payment-methods/                  - Create/update payment method

WEBHOOKS:
  POST    /webhooks/                         - Receive webhook events from payment provider
                                               Supports: Stripe, PayMob, Custom providers

DUNNING:
  GET     /dunning/{id}/                     - Get dunning status for subscription
  POST    /dunning/{id}/retry/               - Manually retry failed dunning attempt

QUERY PARAMETERS:

Subscriptions List:
  ?state=active|past_due|grace|suspended|cancelled
  ?plan_id={plan_id}
  ?created_after={date}
  ?created_before={date}
  ?page={page_number}
  ?page_size={size}

Invoices List:
  ?subscription_id={subscription_id}
  ?status=issued|overdue|paid|partial|draft|void
  ?issued_after={date}
  ?issued_before={date}
  ?overdue_only=true
  ?page={page_number}

Billing Cycles List:
  ?subscription_id={subscription_id}
  ?status=pending|billed|paid|failed
  ?period_after={date}
  ?period_before={date}

REQUEST EXAMPLES:

1. Create Subscription:
   POST /subscriptions/
   {
     "plan_id": "uuid",
     "billing_cycle_anchor": 1,
     "currency": "SAR"
   }
   Response: {
     "id": "uuid",
     "state": "active",
     "next_billing_date": "2024-03-01",
     "plan": {...},
     "tenant": {...}
   }

2. Change Plan:
   POST /subscriptions/{id}/change_plan/
   {
     "plan_id": "new_plan_uuid",
     "effective_date": "2024-02-15"
   }
   Response: {
     "subscription": {...},
     "proration": {
       "upgrade_amount": 10.00,
       "downgrade_amount": 0.00,
       "net_proration": 10.00
     }
   }

3. Cancel Subscription:
   POST /subscriptions/{id}/cancel/
   {
     "reason": "Too expensive",
     "immediately": false
   }
   Response: {
     "id": "uuid",
     "state": "cancelled",
     "cancelled_at": "2024-02-20T10:30:00Z",
     "cancellation_reason": "Too expensive"
   }

4. Webhook Event:
   POST /webhooks/
   {
     "type": "payment.succeeded",
     "provider": "stripe",
     "event_id": "evt_1234567890",
     "timestamp": "2024-02-20T10:30:00Z",
     "data": {...}
   }

5. Get Billing Status:
   GET /subscriptions/{id}/billing_status/
   Response: {
     "state": "active",
     "next_billing_date": "2024-03-01",
     "outstanding_balance": 0.00,
     "outstanding_invoices": [],
     "payment_method_status": "valid",
     "days_until_next_billing": 9,
     "is_overdue": false,
     "grace_period_active": false
   }

RESPONSE FORMATS:

Success Response (200, 201):
  {
    "success": true,
    "data": {...},
    "message": "Operation completed successfully"
  }

Error Response (400, 404, 500):
  {
    "success": false,
    "error": "Error code/type",
    "message": "Human-readable error message",
    "details": {...}  // Optional detailed error info
  }

PAGINATION:
  Default page size: 20
  Max page size: 100
  Format: /resource/?page=1&page_size=50
  Response includes: pagination metadata (next, previous, count, total_pages)

FILTERING:
  Multiple values: ?status=active,past_due
  Date range: ?created_after=2024-01-01&created_before=2024-02-01
  Exclude: Most filters support negation with ! prefix

AUTHENTICATION:
  Header: Authorization: Bearer {token}
  Methods: Token auth, JWT (depends on Django settings)
  Webhook auth: HMAC signature in header (X-Webhook-Signature)

RATE LIMITING:
  Per-user: 1000 requests/hour
  Per-IP: 100 requests/minute
  Webhook endpoints: 10000 requests/hour (higher limit for webhooks)

CORS:
  Enabled for: https://yourdomain.com
  Methods: GET, POST, PUT, DELETE, OPTIONS
  Credentials: Allowed
"""

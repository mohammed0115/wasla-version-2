"""
URL configuration for subscription web interface.

This module defines URL patterns for the customer-facing and admin billing interfaces.
It includes routes for dashboard, subscription management, invoices, payment methods,
and plan changes.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views_web import (
    # Dashboard
    billing_dashboard,
    
    # Subscriptions
    subscription_detail,
    
    # Invoices
    invoice_list,
    invoice_detail,
    invoice_download,
    
    # Payment Methods
    payment_method,
    
    # Plan Changes
    plan_change,
    
    # Admin
    admin_billing_dashboard,
    
    # API/AJAX
    proration_calculator,
    
    # Webhooks
    payment_webhook,
)
from .views.onboarding import (
    onboarding_plan_select,
    onboarding_subdomain_select,
    onboarding_payment_method,
    onboarding_checkout,
    onboarding_manual_payment,
    onboarding_success,
    onboarding_payment_callback,
    onboarding_dashboard_redirect,
    go_to_dashboard,
)

app_name = 'subscriptions'

urlpatterns = [
    # ========================================================================
    # Customer-Facing Routes
    # ========================================================================
    
    # Dashboard
    path(
        'dashboard/',
        billing_dashboard,
        name='dashboard'
    ),

    # Onboarding flow
    path(
        'onboarding/plan/',
        onboarding_plan_select,
        name='onboarding_plan'
    ),
    path(
        'onboarding/subdomain/',
        onboarding_subdomain_select,
        name='onboarding_subdomain'
    ),
    path(
        'onboarding/payment-method/',
        onboarding_payment_method,
        name='onboarding_payment_method'
    ),
    path(
        'onboarding/checkout/',
        onboarding_checkout,
        name='onboarding_checkout'
    ),
    path(
        'onboarding/manual-payment/',
        onboarding_manual_payment,
        name='onboarding_manual_payment'
    ),
    path(
        'onboarding/success/',
        onboarding_success,
        name='onboarding_success'
    ),
    path(
        'onboarding/payment/callback/',
        onboarding_payment_callback,
        name='onboarding_payment_callback'
    ),
    path(
        'onboarding/dashboard/<int:store_id>/',
        onboarding_dashboard_redirect,
        name='onboarding_dashboard'
    ),
    path(
        'go-to-dashboard/',
        go_to_dashboard,
        name='go_to_dashboard'
    ),
    
    # Subscription Management
    path(
        'subscription/',
        subscription_detail,
        name='subscription-detail'
    ),
    path(
        'subscription/<uuid:subscription_id>/',
        subscription_detail,
        name='subscription-detail-by-id'
    ),
    
    # Invoices
    path(
        'invoices/',
        invoice_list,
        name='invoice-list'
    ),
    path(
        'invoices/<uuid:invoice_id>/',
        invoice_detail,
        name='invoice-detail'
    ),
    path(
        'invoices/<uuid:invoice_id>/download/',
        invoice_download,
        name='invoice-download'
    ),
    
    # Payment Methods
    path(
        'payment-method/',
        payment_method,
        name='payment-method'
    ),
    
    # Plan Changes
    path(
        'plan-change/',
        plan_change,
        name='plan-change'
    ),
    path(
        'plan-change/<uuid:subscription_id>/',
        plan_change,
        name='plan-change-by-id'
    ),
    
    # ========================================================================
    # Admin Routes
    # ========================================================================
    
    path(
        'admin/dashboard/',
        admin_billing_dashboard,
        name='admin-dashboard'
    ),
    
    # ========================================================================
    # API/AJAX Routes
    # ========================================================================
    
    path(
        'api/proration/',
        proration_calculator,
        name='proration-api'
    ),
    
    # ========================================================================
    # Webhook Routes
    # ========================================================================
    
    path(
        'webhooks/payment/',
        payment_webhook,
        name='payment-webhook'
    ),
]

# Documentation for these endpoints:
# 
# CUSTOMER ROUTES:
# ================
#
# GET /billing/dashboard/
#   Main billing overview dashboard
#   - Shows subscription status
#   - Outstanding balance
#   - Recent invoices (last 5)
#   - Billing history
#   - Quick action buttons
#   Requires: Authentication
#   Returns: HTML dashboard page
#
# GET /billing/subscription/
#   View and manage current subscription
#   - Current plan details
#   - Subscription items
#   - Plan features
#   - Manage actions (cancel, grace period)
#   Requires: Authentication
#   Returns: HTML subscription detail page
#
# POST /billing/subscription/
#   Submit subscription actions
#   Parameters:
#     - action: 'cancel' or 'grace_period'
#     - cancel_reason: (optional) reason for cancellation
#     - grace_days: (optional) days for grace period extension
#   Requires: Authentication, POST
#   Returns: Redirect to subscription detail
#
# GET /billing/invoices/
#   View all invoices with filtering
#   Query Parameters:
#     - status: 'all', 'issued', 'overdue', 'paid', 'partial'
#     - overdue_only: 'on' to show only overdue invoices
#     - page: pagination page number
#   Requires: Authentication
#   Returns: HTML invoice list with pagination
#
# GET /billing/invoices/<id>/
#   View detailed invoice
#   - Line items breakdown
#   - Amount summary
#   - Payment information
#   - Dunning attempt history
#   - Proration details
#   Requires: Authentication, invoice ownership
#   Returns: HTML invoice detail page
#
# GET /billing/invoices/<id>/download/
#   Download invoice as PDF
#   Requires: Authentication, invoice ownership
#   Returns: PDF file download
#
# GET /billing/payment-method/
#   View and update payment method
#   - Current payment method
#   - Add/update payment form
#   - Payment method types (card, bank)
#   - Security information
#   Requires: Authentication
#   Returns: HTML payment method page
#
# POST /billing/payment-method/
#   Update payment method
#   Parameters:
#     - method_type: 'card' or 'bank'
#     - token: (encrypted) payment token from provider
#     - provider: payment provider identifier
#     - save_for_later: 'on' to save for future use
#     - agree_terms: must be 'on'
#   Requires: Authentication, POST
#   Returns: Redirect to payment method page
#
# GET /billing/plan-change/
#   View available plans and plan comparison
#   - Current plan highlighted
#   - All active plans displayed
#   - Proration calculation
#   - Feature comparison table
#   - Plan change form
#   Requires: Authentication
#   Returns: HTML plan change page
#
# POST /billing/plan-change/
#   Submit plan change request
#   Parameters:
#     - new_plan_id: UUID of new plan
#   Requires: Authentication, POST
#   Returns: Redirect to subscription detail
#
# ADMIN ROUTES:
# =============
#
# GET /billing/admin/dashboard/
#   Admin billing analytics dashboard
#   - Total MRR (Monthly Recurring Revenue)
#   - Active subscriptions count
#   - Overdue subscriptions count
#   - Suspended subscriptions count
#   - Recent invoices
#   - Recent payments
#   Requires: Authentication, staff permissions
#   Returns: HTML admin dashboard page
#
# API/AJAX ROUTES:
# ================
#
# POST /billing/api/proration/
#   Calculate proration for plan change (AJAX)
#   Parameters:
#     - subscription_id: UUID of subscription
#     - new_plan_id: UUID of new plan
#   Requires: Authentication, AJAX request, POST
#   Returns: JSON with proration details
#   Example Response:
#     {
#       "success": true,
#       "current_price": 99.00,
#       "new_price": 149.00,
#       "proration_amount": 50.00,
#       "proration_type": "charge"
#     }
#
# WEBHOOK ROUTES:
# ===============
#
# POST /billing/webhooks/payment/
#   Receive payment provider webhook events
#   - Payment succeeded
#   - Payment failed
#   - Refund processed
#   - Subscription events
#   Headers:
#     - X-Webhook-Signature: HMAC-SHA256 signature for verification
#   Body: JSON webhook payload from payment provider
#   Requires: Valid webhook signature
#   Returns: JSON success response
#   Security: CSRF exempt, but signature verified
#
# QUERY PARAMETER EXAMPLES:
# =========================
#
# Filter invoices by status:
#   GET /billing/invoices/?status=overdue
#   GET /billing/invoices/?status=paid
#
# Show only overdue invoices:
#   GET /billing/invoices/?overdue_only=on
#
# Pagination:
#   GET /billing/invoices/?page=2
#
# Combined filters:
#   GET /billing/invoices/?status=issued&page=1
#
# RESPONSE FORMATS:
# =================
#
# HTML Pages (Web Interface):
# - dashboard.html: Main billing overview
# - subscription_detail.html: Subscription management
# - invoice_list.html: Invoice listing with filters
# - invoice_detail.html: Detailed invoice view
# - payment_method.html: Payment method management
# - plan_change.html: Plan comparison and change
# - admin_dashboard.html: Admin analytics
#
# JSON Responses (AJAX):
# - proration_calculator: Proration amount information
# - payment_webhook: Success acknowledgement
#
# STATUS CODES:
# =============
#
# 200 OK: Successful request
# 302 Found: Redirect after POST (successful action)
# 400 Bad Request: Invalid parameters or AJAX request
# 403 Forbidden: Access denied (admin, ownership, signature)
# 404 Not Found: Resource not found
#
# ERROR HANDLING:
# ===============
#
# All views catch exceptions and display user-friendly messages via Django messages framework
# AJAX views return JSON error responses with status 400
# Authentication required views redirect to login
# Staff-only views return 403 Forbidden for non-staff users
# Ownership checks prevent cross-tenant access

from django.urls import path
from . import views

app_name = 'admin_portal'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.dashboard_view, name='dashboard'),

    path('tenants/', views.tenants_view, name='tenants'),
    path('tenants/<int:tenant_id>/', views.tenant_detail_view, name='tenant_detail'),
    path('tenants/<int:tenant_id>/publish/', views.tenant_publish_view, name='tenant_publish'),
    path('tenants/<int:tenant_id>/set-active/', views.tenant_set_active_view, name='tenant_set_active'),

    path('stores/', views.stores_view, name='stores'),
    path('stores/<int:store_id>/', views.store_detail_view, name='store_detail'),
    path('stores/<int:store_id>/set-active/', views.store_set_active_view, name='store_set_active'),

    path('payments/', views.payments_view, name='payments'),
    path('payments/transactions/', views.payment_transactions_view, name='payment_transactions'),
    path('payments/transactions/create/', views.payment_transaction_create_view, name='payment_transaction_create'),
    path('subscriptions/', views.subscriptions_view, name='subscriptions'),
    path('settlements/', views.settlements_view, name='settlements'),

    path('invoices/', views.invoices_view, name='invoices'),
    path('invoices/<int:invoice_id>/mark-paid/', views.invoice_mark_paid_view, name='invoice_mark_paid'),

    path('webhooks/', views.webhooks_view, name='webhooks'),
    path('performance/', views.performance_monitoring_view, name='performance_monitoring'),
]

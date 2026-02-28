from django.urls import path
from . import views
from apps.plugins.views.web import (
    plugins_dashboard_view,
    plugin_registry_list_view,
    plugin_registry_create_view,
    plugin_registry_detail_view,
    plugin_scopes_view,
    plugin_subscriptions_view,
    plugin_event_deliveries_view,
    installed_plugins_view,
)

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
    path('payments/transactions/<int:transaction_id>/approve-create-store/', views.payment_transaction_approve_create_store_view, name='payment_transaction_approve_create_store'),
    path('subscriptions/', views.subscriptions_view, name='subscriptions'),
    path('settlements/', views.settlements_view, name='settlements'),

    path('invoices/', views.invoices_view, name='invoices'),
    path('invoices/<int:invoice_id>/mark-paid/', views.invoice_mark_paid_view, name='invoice_mark_paid'),

    path('webhooks/', views.webhooks_view, name='webhooks'),
    path('performance/', views.performance_monitoring_view, name='performance_monitoring'),

    # Plugin Management Routes
    path('plugins/', plugins_dashboard_view, name='plugins_dashboard'),
    path('plugins/registry/', plugin_registry_list_view, name='plugin_registry_list'),
    path('plugins/registry/create/', plugin_registry_create_view, name='plugin_registry_create'),
    path('plugins/registry/<int:registration_id>/', plugin_registry_detail_view, name='plugin_registry_detail'),
    path('plugins/registry/<int:registration_id>/scopes/', plugin_scopes_view, name='plugin_scopes'),
    path('plugins/subscriptions/', plugin_subscriptions_view, name='plugin_subscriptions'),
    path('plugins/deliveries/', plugin_event_deliveries_view, name='plugin_event_deliveries'),
    path('plugins/installed/', installed_plugins_view, name='installed_plugins'),
]

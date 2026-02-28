"""
Analytics dashboard URL patterns.

Provides:
- Merchant KPI endpoints
- Revenue chart endpoints
- Admin executive dashboard
- CSV export endpoints
"""

from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # Merchant Dashboard
    path('merchant/kpi/', views.merchant_kpi_view, name='merchant_kpi_json'),
    path('merchant/dashboard/', views.merchant_dashboard_view, name='merchant_dashboard'),
    path('merchant/revenue-chart/', views.revenue_chart_data_view, name='revenue_chart'),
    path('merchant/funnel/', views.funnel_analysis_view, name='funnel_analysis'),

    # CSV Exports
    path('merchant/export/kpi.csv', views.export_kpi_csv_view, name='export_kpi_csv'),
    path('merchant/export/revenue.csv', views.export_revenue_csv_view, name='export_revenue_csv'),
    path('merchant/export/funnel.csv', views.export_funnel_csv_view, name='export_funnel_csv'),

    # Admin Executive Dashboard
    path('admin/dashboard/', views.admin_executive_dashboard_view, name='admin_dashboard'),
    path('admin/kpi/', views.admin_kpi_json_view, name='admin_kpi_json'),
    path('admin/export/kpi.csv', views.export_admin_kpi_csv_view, name='export_admin_kpi_csv'),
]

"""
Dashboard API views and endpoints.

Provides:
- Merchant dashboard KPIs (JSON)
- Revenue chart data (JSON)
- Admin executive dashboard
- CSV export of metrics
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_page
from django.core.paginator import Paginator
from django.utils import timezone

from apps.analytics.application.dashboard_services import (
    MerchantDashboardService,
    RevenueChartService,
    AdminExecutiveDashboardService,
    EventTrackingService,
    FunnelAnalysisService,
)
from apps.analytics.utils import resolve_store_id


# ============================================================================
# Merchant Dashboard Endpoints
# ============================================================================

@login_required
@require_http_methods(["GET"])
def merchant_kpi_view(request):
    """
    Get merchant KPIs for current store.

    Returns JSON:
    {
        "revenue_today": "1234.50",
        "orders_today": 12,
        "conversion_rate": 3.45,
        "low_stock_products": [...],
        ...
    }
    """
    store_id = resolve_store_id(request)
    if not store_id:
        return JsonResponse({'error': 'No store associated'}, status=400)

    kpi = MerchantDashboardService.get_merchant_kpis(store_id)

    return JsonResponse({
        'revenue_today': str(kpi.revenue_today),
        'orders_today': kpi.orders_today,
        'conversion_rate': round(kpi.conversion_rate, 2),
        'low_stock_products': kpi.low_stock_products,
        'revenue_7d': str(kpi.revenue_7d),
        'revenue_30d': str(kpi.revenue_30d),
        'orders_7d': kpi.orders_7d,
        'orders_30d': kpi.orders_30d,
        'avg_order_value': str(kpi.avg_order_value),
        'cart_abandonment_rate': round(kpi.cart_abandonment_rate, 2),
        'timestamp': kpi.timestamp.isoformat(),
    })


@login_required
@require_http_methods(["GET"])
def merchant_dashboard_view(request):
    """
    Render merchant dashboard page with KPIs.

    Query params:
    - tab: 'overview', 'products', 'analytics' (default: overview)
    """
    from django.shortcuts import render

    store_id = resolve_store_id(request)
    if not store_id:
        return HttpResponse('No store associated', status=400)

    tab = request.GET.get('tab', 'overview')

    kpi = MerchantDashboardService.get_merchant_kpis(store_id)
    revenue_chart = RevenueChartService.get_revenue_chart(store_id, days=7)
    funnel = FunnelAnalysisService.get_conversion_funnel(store_id, days=7)

    context = {
        'kpi': kpi,
        'revenue_chart': revenue_chart,
        'funnel': funnel,
        'tab': tab,
    }

    return render(request, 'analytics/merchant_dashboard.html', context)


# ============================================================================
# Revenue Chart API Endpoints
# ============================================================================

@login_required
@require_http_methods(["GET"])
def revenue_chart_data_view(request):
    """
    Get revenue chart data.

    Query params:
    - days: 7 or 30 (default: 7)
    
    Returns JSON:
    {
        "period": "7d",
        "points": [
            {"date": "2024-01-01", "revenue": "1234.50", "orders": 10, "avg_order_value": "123.45"},
            ...
        ],
        "total_revenue": "8675.50",
        "total_orders": 70,
        "avg_daily_revenue": "1239.36"
    }
    """
    store_id = resolve_store_id(request)
    if not store_id:
        return JsonResponse({'error': 'No store associated'}, status=400)

    days = int(request.GET.get('days', 7))
    chart = RevenueChartService.get_revenue_chart(store_id, days=days)

    return JsonResponse({
        'period': chart.period,
        'points': [
            {
                'date': p.date,
                'revenue': str(p.revenue),
                'orders': p.orders,
                'avg_order_value': str(p.avg_order_value),
            }
            for p in chart.points
        ],
        'total_revenue': str(chart.total_revenue),
        'total_orders': chart.total_orders,
        'avg_daily_revenue': str(chart.avg_daily_revenue),
        'timestamp': chart.timestamp.isoformat(),
    })


# ============================================================================
# Admin Executive Dashboard
# ============================================================================

def admin_executive_dashboard_view(request):
    """
    Render admin executive dashboard.

    Requires admin permission.
    """
    from django.shortcuts import render
    from apps.admin_portal.decorators import admin_permission_required

    if not request.user.is_staff:
        return HttpResponse('Unauthorized', status=403)

    kpi = AdminExecutiveDashboardService.get_admin_kpis()

    context = {
        'gmv': kpi.gmv,
        'mrr': kpi.mrr,
        'active_stores': kpi.active_stores,
        'churn_rate': round(kpi.churn_rate, 2),
        'total_customers': kpi.total_customers,
        'avg_order_value': kpi.avg_order_value,
        'conversion_rate': round(kpi.conversion_rate, 2),
        'top_products': kpi.top_products,
        'top_merchants': kpi.top_merchants,
        'payment_success_rate': round(kpi.payment_success_rate, 2),
    }

    return render(request, 'admin_portal/executive_dashboard.html', context)


@require_http_methods(["GET"])
def admin_kpi_json_view(request):
    """
    Get admin KPIs as JSON.

    Requires admin permission.
    """
    if not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    kpi = AdminExecutiveDashboardService.get_admin_kpis()

    return JsonResponse({
        'gmv': str(kpi.gmv),
        'mrr': str(kpi.mrr),
        'active_stores': kpi.active_stores,
        'churn_rate': round(kpi.churn_rate, 2),
        'total_customers': kpi.total_customers,
        'avg_order_value': str(kpi.avg_order_value),
        'conversion_rate': round(kpi.conversion_rate, 2),
        'top_products': kpi.top_products,
        'top_merchants': kpi.top_merchants,
        'payment_success_rate': round(kpi.payment_success_rate, 2),
        'timestamp': kpi.timestamp.isoformat(),
    })


# ============================================================================
# Funnel Analysis
# ============================================================================

@login_required
@require_http_methods(["GET"])
def funnel_analysis_view(request):
    """
    Get conversion funnel data.

    Query params:
    - days: 7 or 30 (default: 7)
    
    Returns JSON with conversion funnel stages.
    """
    store_id = resolve_store_id(request)
    if not store_id:
        return JsonResponse({'error': 'No store associated'}, status=400)

    days = int(request.GET.get('days', 7))
    funnel = FunnelAnalysisService.get_conversion_funnel(store_id, days=days)

    return JsonResponse({
        'product_views': funnel.product_views,
        'add_to_cart': funnel.add_to_cart,
        'checkout_started': funnel.checkout_started,
        'purchase_completed': funnel.purchase_completed,
        'view_to_cart_rate': round(funnel.view_to_cart_rate, 2),
        'cart_to_checkout_rate': round(funnel.cart_to_checkout_rate, 2),
        'checkout_to_purchase_rate': round(funnel.checkout_to_purchase_rate, 2),
        'overall_conversion_rate': round(funnel.overall_conversion_rate, 2),
    })


# ============================================================================
# CSV Export Endpoints
# ============================================================================

@login_required
@require_http_methods(["GET"])
def export_kpi_csv_view(request):
    """
    Export merchant KPIs as CSV.

    Query params:
    - period: 'today', '7d', '30d' (default: '7d')
    """
    store_id = resolve_store_id(request)
    if not store_id:
        return HttpResponse('No store associated', status=400)

    period = request.GET.get('period', '7d')
    kpi = MerchantDashboardService.get_merchant_kpis(store_id)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="kpi-export-{datetime.now().date()}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Metric', 'Value'])
    writer.writerow(['Revenue Today', f"{kpi.revenue_today:.2f}"])
    writer.writerow(['Orders Today', kpi.orders_today])
    writer.writerow(['Revenue 7 Days', f"{kpi.revenue_7d:.2f}"])
    writer.writerow(['Revenue 30 Days', f"{kpi.revenue_30d:.2f}"])
    writer.writerow(['Orders 7 Days', kpi.orders_7d])
    writer.writerow(['Orders 30 Days', kpi.orders_30d])
    writer.writerow(['Average Order Value', f"{kpi.avg_order_value:.2f}"])
    writer.writerow(['Conversion Rate', f"{kpi.conversion_rate:.2f}%"])
    writer.writerow(['Cart Abandonment Rate', f"{kpi.cart_abandonment_rate:.2f}%"])

    return response


@login_required
@require_http_methods(["GET"])
def export_revenue_csv_view(request):
    """
    Export revenue chart as CSV.

    Query params:
    - days: 7 or 30 (default: 7)
    """
    store_id = resolve_store_id(request)
    if not store_id:
        return HttpResponse('No store associated', status=400)

    days = int(request.GET.get('days', 7))
    chart = RevenueChartService.get_revenue_chart(store_id, days=days)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="revenue-{days}d-{datetime.now().date()}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Date', 'Revenue', 'Orders', 'Average Order Value'])

    for point in chart.points:
        writer.writerow([
            point.date,
            f"{point.revenue:.2f}",
            point.orders,
            f"{point.avg_order_value:.2f}",
        ])

    writer.writerow([])
    writer.writerow(['Summary', ''])
    writer.writerow(['Total Revenue', f"{chart.total_revenue:.2f}"])
    writer.writerow(['Total Orders', chart.total_orders])
    writer.writerow(['Average Daily Revenue', f"{chart.avg_daily_revenue:.2f}"])

    return response


@login_required
@require_http_methods(["GET"])
def export_funnel_csv_view(request):
    """
    Export conversion funnel as CSV.

    Query params:
    - days: 7 or 30 (default: 7)
    """
    store_id = resolve_store_id(request)
    if not store_id:
        return HttpResponse('No store associated', status=400)

    days = int(request.GET.get('days', 7))
    funnel = FunnelAnalysisService.get_conversion_funnel(store_id, days=days)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="funnel-{days}d-{datetime.now().date()}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Stage', 'Count', 'Rate'])
    writer.writerow(['Product Views', funnel.product_views, '100%'])
    writer.writerow(['Added to Cart', funnel.add_to_cart, f"{funnel.view_to_cart_rate:.2f}%"])
    writer.writerow(['Checkout Started', funnel.checkout_started, f"{funnel.cart_to_checkout_rate:.2f}%"])
    writer.writerow(['Purchase Completed', funnel.purchase_completed, f"{funnel.checkout_to_purchase_rate:.2f}%"])

    writer.writerow([])
    writer.writerow(['Overall Conversion Rate', f"{funnel.overall_conversion_rate:.2f}%"])

    return response


@require_http_methods(["GET"])
def export_admin_kpi_csv_view(request):
    """
    Export admin KPIs as CSV.

    Requires admin permission.
    """
    if not request.user.is_staff:
        return HttpResponse('Unauthorized', status=403)

    kpi = AdminExecutiveDashboardService.get_admin_kpis()

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="admin-kpi-{datetime.now().date()}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Metric', 'Value'])
    writer.writerow(['GMV (Gross Merchandise Volume)', f"{kpi.gmv:.2f}"])
    writer.writerow(['MRR (Monthly Recurring Revenue)', f"{kpi.mrr:.2f}"])
    writer.writerow(['Active Stores', kpi.active_stores])
    writer.writerow(['Churn Rate', f"{kpi.churn_rate:.2f}%"])
    writer.writerow(['Total Customers', kpi.total_customers])
    writer.writerow(['Average Order Value', f"{kpi.avg_order_value:.2f}"])
    writer.writerow(['Conversion Rate', f"{kpi.conversion_rate:.2f}%"])
    writer.writerow(['Payment Success Rate', f"{kpi.payment_success_rate:.2f}%"])

    writer.writerow([])
    writer.writerow(['Top Products', ''])
    for product in kpi.top_products:
        writer.writerow([
            product['name'],
            f"{product['revenue']:.2f}",
            product['quantity_sold']
        ])

    writer.writerow([])
    writer.writerow(['Top Merchants', ''])
    for merchant in kpi.top_merchants:
        writer.writerow([
            merchant['name'],
            f"{merchant['revenue']:.2f}",
            merchant['order_count']
        ])

    return response

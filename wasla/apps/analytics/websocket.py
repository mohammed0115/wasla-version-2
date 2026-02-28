"""
Real-time WebSocket support for analytics dashboard.

Provides real-time KPI updates using Django Channels.
"""

from __future__ import annotations

import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.cache import cache
from asgiref.sync import sync_to_async

from apps.analytics.application.dashboard_services import (
    MerchantDashboardService,
    FunnelAnalysisService,
    RevenueChartService,
)


class DashboardConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time dashboard updates."""

    async def connect(self):
        """Handle WebSocket connection."""
        self.store_id = self.scope['url_route']['kwargs'].get('store_id')
        self.group_name = f'dashboard_{self.store_id}'

        # Join group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send initial data
        await self._send_kpi_update()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            action = data.get('action')

            if action == 'update_kpi':
                await self._send_kpi_update()
            elif action == 'update_chart':
                days = data.get('days', 7)
                await self._send_revenue_chart(days)
            elif action == 'update_funnel':
                days = data.get('days', 7)
                await self._send_funnel_update(days)
        except Exception as e:
            await self.send(json.dumps({'error': str(e)}))

    async def _send_kpi_update(self):
        """Send KPI update to WebSocket."""
        kpi = await sync_to_async(self._get_kpi_data)()
        await self.send(json.dumps({
            'type': 'kpi_update',
            'data': {
                'revenue_today': str(kpi.revenue_today),
                'orders_today': kpi.orders_today,
                'conversion_rate': round(kpi.conversion_rate, 2),
                'avg_order_value': str(kpi.avg_order_value),
                'cart_abandonment_rate': round(kpi.cart_abandonment_rate, 2),
                'low_stock_count': len(kpi.low_stock_products),
                'timestamp': kpi.timestamp.isoformat(),
            }
        }))

    async def _send_revenue_chart(self, days: int):
        """Send revenue chart update."""
        chart = await sync_to_async(self._get_revenue_chart)(days)
        await self.send(json.dumps({
            'type': 'chart_update',
            'data': {
                'period': chart.period,
                'points': [
                    {
                        'date': p.date,
                        'revenue': str(p.revenue),
                        'orders': p.orders,
                    }
                    for p in chart.points
                ],
                'total_revenue': str(chart.total_revenue),
                'total_orders': chart.total_orders,
            }
        }))

    async def _send_funnel_update(self, days: int):
        """Send funnel update."""
        funnel = await sync_to_async(self._get_funnel_data)(days)
        await self.send(json.dumps({
            'type': 'funnel_update',
            'data': {
                'product_views': funnel.product_views,
                'add_to_cart': funnel.add_to_cart,
                'checkout_started': funnel.checkout_started,
                'purchase_completed': funnel.purchase_completed,
                'view_to_cart_rate': round(funnel.view_to_cart_rate, 2),
                'cart_to_checkout_rate': round(funnel.cart_to_checkout_rate, 2),
                'checkout_to_purchase_rate': round(funnel.checkout_to_purchase_rate, 2),
            }
        }))

    def _get_kpi_data(self):
        """Get KPI data (sync function)."""
        return MerchantDashboardService.get_merchant_kpis(self.store_id, cache_ttl=60)

    def _get_revenue_chart(self, days: int):
        """Get revenue chart data (sync function)."""
        return RevenueChartService.get_revenue_chart(self.store_id, days=days, cache_ttl=60)

    def _get_funnel_data(self, days: int):
        """Get funnel data (sync function)."""
        return FunnelAnalysisService.get_conversion_funnel(self.store_id, days=days, cache_ttl=60)

    async def kpi_broadcast(self, event):
        """Broadcast KPI update to group."""
        await self.send(json.dumps({
            'type': 'kpi_broadcast',
            'data': event['data']
        }))

    async def order_notification(self, event):
        """Notify about new order."""
        await self.send(json.dumps({
            'type': 'order_notification',
            'data': event['data']
        }))


class AdminDashboardConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for admin real-time dashboard."""

    async def connect(self):
        """Handle connection to admin dashboard."""
        self.group_name = 'admin_dashboard'

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send initial data
        await self._send_admin_kpi()

    async def disconnect(self, close_code):
        """Handle disconnection."""
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """Handle incoming messages."""
        try:
            data = json.loads(text_data)
            action = data.get('action')

            if action == 'update_admin_kpi':
                await self._send_admin_kpi()
        except Exception as e:
            await self.send(json.dumps({'error': str(e)}))

    async def _send_admin_kpi(self):
        """Send admin KPI update."""
        from apps.analytics.application.dashboard_services import AdminExecutiveDashboardService

        kpi = await sync_to_async(AdminExecutiveDashboardService.get_admin_kpis)()
        await self.send(json.dumps({
            'type': 'admin_kpi_update',
            'data': {
                'gmv': str(kpi.gmv),
                'mrr': str(kpi.mrr),
                'active_stores': kpi.active_stores,
                'churn_rate': round(kpi.churn_rate, 2),
                'total_customers': kpi.total_customers,
                'conversion_rate': round(kpi.conversion_rate, 2),
                'payment_success_rate': round(kpi.payment_success_rate, 2),
            }
        }))

    async def admin_broadcast(self, event):
        """Broadcast admin update."""
        await self.send(json.dumps({
            'type': 'admin_broadcast',
            'data': event['data']
        }))


def broadcast_kpi_update(store_id: int, kpi_data: dict) -> None:
    """
    Broadcast KPI update to all connected WebSocket clients.

    Args:
        store_id: Store ID
        kpi_data: KPI data to broadcast
    """
    from channels.layers import get_channel_layer
    import asyncio

    channel_layer = get_channel_layer()
    asyncio.run(channel_layer.group_send(
        f'dashboard_{store_id}',
        {
            'type': 'kpi_broadcast',
            'data': kpi_data
        }
    ))


def broadcast_order_notification(store_id: int, order_id: int, order_value: float) -> None:
    """
    Broadcast new order notification.

    Args:
        store_id: Store ID
        order_id: Order ID
        order_value: Order value
    """
    from channels.layers import get_channel_layer
    import asyncio

    channel_layer = get_channel_layer()
    asyncio.run(channel_layer.group_send(
        f'dashboard_{store_id}',
        {
            'type': 'order_notification',
            'data': {
                'order_id': order_id,
                'order_value': order_value,
                'message': f'New order #{order_id} for ${order_value:.2f}'
            }
        }
    ))


def broadcast_admin_update(kpi_data: dict) -> None:
    """
    Broadcast admin KPI update.

    Args:
        kpi_data: KPI data to broadcast
    """
    from channels.layers import get_channel_layer
    import asyncio

    channel_layer = get_channel_layer()
    asyncio.run(channel_layer.group_send(
        'admin_dashboard',
        {
            'type': 'admin_broadcast',
            'data': kpi_data
        }
    ))

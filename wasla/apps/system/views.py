"""
Health Check & Status Endpoints
For monitoring, load balancers, and Kubernetes probes
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.db import connection
from django.core.cache import cache
from django.apps import apps
import logging

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Basic health check endpoint
    Returns 200 if service is running
    """
    return Response({
        'status': 'healthy',
        'service': 'WASLA API',
        'version': '1.0.0',
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def detailed_health_check(request):
    """
    Detailed health check with dependency status
    Used by monitoring and orchestration tools
    """
    checks = {
        'database': _check_database(),
        'cache': _check_cache(),
        'migrations': _check_migrations(),
    }
    
    # Overall status
    all_healthy = all(check['status'] == 'ok' for check in checks.values())
    
    return Response({
        'status': 'healthy' if all_healthy else 'degraded',
        'timestamp': __import__('django.utils.timezone', fromlist=['now']).now(),
        'checks': checks,
    }, status=status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE)


def _check_database() -> dict:
    """Check database connectivity"""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        return {
            'status': 'ok',
            'message': 'Database connected',
        }
    except Exception as e:
        logger.error(f'Database check failed: {str(e)}')
        return {
            'status': 'error',
            'message': str(e),
        }


def _check_cache() -> dict:
    """Check cache connectivity"""
    try:
        cache.set('health_check', 'ok', 10)
        if cache.get('health_check') == 'ok':
            cache.delete('health_check')
            return {
                'status': 'ok',
                'message': 'Cache connected',
            }
        else:
            return {
                'status': 'error',
                'message': 'Cache set/get failed',
            }
    except Exception as e:
        logger.warning(f'Cache check failed: {str(e)}')
        return {
            'status': 'warning',
            'message': str(e),
        }


def _check_migrations() -> dict:
    """Check if all migrations are applied"""
    try:
        from django.core.management import call_command
        from io import StringIO
        
        out = StringIO()
        call_command('showmigrations', '--plan', stdout=out)
        
        output = out.getvalue()
        if '[X]' in output and '[ ]' not in output:
            return {
                'status': 'ok',
                'message': 'All migrations applied',
            }
        else:
            return {
                'status': 'warning',
                'message': 'Pending migrations detected',
            }
    except Exception as e:
        logger.error(f'Migration check failed: {str(e)}')
        return {
            'status': 'error',
            'message': str(e),
        }


@api_view(['GET'])
@permission_classes([AllowAny])
def service_status(request):
    """
    Service status endpoint
    Returns current state and statistics
    """
    from apps.orders.models import Order
    from apps.catalog.models import Product
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    return Response({
        'service': 'WASLA API',
        'status': 'operational',
        'stats': {
            'total_users': User.objects.count(),
            'total_products': Product.objects.count(),
            'total_orders': Order.objects.count(),
        },
    }, status=status.HTTP_200_OK)

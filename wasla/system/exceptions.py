"""
Error Handling Middleware & Exception Classes
Provides global error handling, logging, and consistent API error responses
"""

import logging
import json
import traceback
from typing import Optional, Dict, Any
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import APIException
from django.http import JsonResponse
from django.core.exceptions import ValidationError, ObjectDoesNotExist, PermissionDenied as DjangoPermissionDenied
from django.db import IntegrityError, transaction
import sentry_sdk

logger = logging.getLogger(__name__)


class APIErrorCode:
    """Standard error codes for API responses"""
    VALIDATION_ERROR = 'VALIDATION_ERROR'
    NOT_FOUND = 'NOT_FOUND'
    UNAUTHORIZED = 'UNAUTHORIZED'
    PERMISSION_DENIED = 'PERMISSION_DENIED'
    CONFLICT = 'CONFLICT'
    RATE_LIMITED = 'RATE_LIMITED'
    SERVER_ERROR = 'SERVER_ERROR'
    PAYMENT_ERROR = 'PAYMENT_ERROR'
    WEBHOOK_ERROR = 'WEBHOOK_ERROR'


class WaslaAPIException(APIException):
    """Base exception for all WASLA API errors"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'An error occurred'
    default_code = APIErrorCode.SERVER_ERROR

    def __init__(self, detail: Optional[str] = None, code: Optional[str] = None, 
                 status_code: Optional[int] = None, extra_data: Optional[Dict] = None):
        if detail is not None:
            self.detail = detail
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.extra_data = extra_data or {}


class ValidationError(WaslaAPIException):
    """Raised when input validation fails"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = APIErrorCode.VALIDATION_ERROR


class NotFoundError(WaslaAPIException):
    """Raised when resource is not found"""
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Resource not found'
    default_code = APIErrorCode.NOT_FOUND


class UnauthorizedError(WaslaAPIException):
    """Raised when user is not authenticated"""
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = 'Authentication required'
    default_code = APIErrorCode.UNAUTHORIZED


class PermissionDeniedError(WaslaAPIException):
    """Raised when user lacks permission"""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Permission denied'
    default_code = APIErrorCode.PERMISSION_DENIED


class ConflictError(WaslaAPIException):
    """Raised on resource conflict (duplicate, state conflict)"""
    status_code = status.HTTP_409_CONFLICT
    default_code = APIErrorCode.CONFLICT


class RateLimitedError(WaslaAPIException):
    """Raised when user exceeds rate limit"""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = 'Too many requests'
    default_code = APIErrorCode.RATE_LIMITED


class PaymentError(WaslaAPIException):
    """Raised for payment processing errors"""
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = 'Payment processing failed'
    default_code = APIErrorCode.PAYMENT_ERROR


class WebhookError(WaslaAPIException):
    """Raised for webhook processing errors"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Webhook processing failed'
    default_code = APIErrorCode.WEBHOOK_ERROR


class ErrorResponseFormatter:
    """Formats error responses consistently"""
    
    @staticmethod
    def format_exception(exception: Exception, request_id: str) -> Dict[str, Any]:
        """Format exception into API response"""
        if isinstance(exception, WaslaAPIException):
            return {
                'success': False,
                'error': {
                    'code': exception.code,
                    'message': str(exception.detail),
                    'status_code': exception.status_code,
                    'request_id': request_id,
                    **(exception.extra_data or {})
                }
            }
        
        elif isinstance(exception, DjangoPermissionDenied):
            return {
                'success': False,
                'error': {
                    'code': APIErrorCode.PERMISSION_DENIED,
                    'message': str(exception),
                    'status_code': status.HTTP_403_FORBIDDEN,
                    'request_id': request_id,
                }
            }
        
        elif isinstance(exception, ObjectDoesNotExist):
            return {
                'success': False,
                'error': {
                    'code': APIErrorCode.NOT_FOUND,
                    'message': f'{exception.__class__.__name__} not found',
                    'status_code': status.HTTP_404_NOT_FOUND,
                    'request_id': request_id,
                }
            }
        
        elif isinstance(exception, IntegrityError):
            # Log the full error for debugging
            logger.warning(f'IntegrityError: {str(exception)}')
            return {
                'success': False,
                'error': {
                    'code': APIErrorCode.CONFLICT,
                    'message': 'Resource already exists or constraint violation',
                    'status_code': status.HTTP_409_CONFLICT,
                    'request_id': request_id,
                }
            }
        
        else:
            # Generic server error
            return {
                'success': False,
                'error': {
                    'code': APIErrorCode.SERVER_ERROR,
                    'message': 'Internal server error',
                    'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR,
                    'request_id': request_id,
                }
            }


class ErrorHandlingMiddleware:
    """
    Middleware for global error handling
    Catches unhandled exceptions and formats responses
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Add request ID for tracking
        request.request_id = self._generate_request_id()
        
        try:
            response = self.get_response(request)
            return response
        
        except WaslaAPIException as e:
            return self._handle_api_exception(e, request)
        
        except Exception as e:
            return self._handle_generic_exception(e, request)
    
    def _handle_api_exception(self, exception: WaslaAPIException, request) -> JsonResponse:
        """Handle known API exceptions"""
        logger.warning(
            f'API Exception: {exception.code} - {exception.detail}',
            extra={'request_id': request.request_id}
        )
        
        error_data = ErrorResponseFormatter.format_exception(exception, request.request_id)
        return JsonResponse(
            error_data,
            status=exception.status_code
        )
    
    def _handle_generic_exception(self, exception: Exception, request) -> JsonResponse:
        """Handle unexpected exceptions"""
        logger.error(
            f'Unhandled Exception: {str(exception)}',
            extra={
                'request_id': request.request_id,
                'traceback': traceback.format_exc()
            },
            exc_info=True
        )
        
        # Send to Sentry if configured
        if hasattr(sentry_sdk, 'capture_exception'):
            sentry_sdk.capture_exception(exception)
        
        error_data = ErrorResponseFormatter.format_exception(exception, request.request_id)
        return JsonResponse(error_data, status=500)
    
    @staticmethod
    def _generate_request_id() -> str:
        """Generate unique request ID for tracking"""
        import uuid
        return str(uuid.uuid4())


class ExceptionDetailsMiddleware:
    """Adds request context to exceptions for better logging"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            # Log request details with exception
            logger.error(
                f'{request.method} {request.path}',
                extra={
                    'user': request.user.id if request.user.is_authenticated else 'anonymous',
                    'ip': self._get_client_ip(request),
                    'method': request.method,
                    'path': request.path,
                    'query_params': dict(request.GET),
                }
            )
            raise
    
    @staticmethod
    def _get_client_ip(request) -> str:
        """Extract client IP from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR', 'unknown')

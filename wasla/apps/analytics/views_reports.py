"""
API views for analytics report management.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import JsonResponse, FileResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from apps.analytics.models_reports import ScheduledReport, ReportLog, ReportService
from apps.analytics.utils import resolve_store_id


class ScheduledReportViewSet(viewsets.ModelViewSet):
    """ViewSet for managing scheduled reports."""

    serializer_class = None  # Would be ScheduledReportSerializer in real app
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter reports by user's store or admin status."""
        user = self.request.user
        if user.is_staff:
            return ScheduledReport.objects.all()
        # Filter by store_id for merchants
        store_id = resolve_store_id(self.request)
        if not store_id:
            return ScheduledReport.objects.none()
        return ScheduledReport.objects.filter(store_id=store_id)

    @action(detail=False, methods=['post'])
    def create_report(self, request):
        """Create a new scheduled report."""
        try:
            data = request.data
            report = ReportService.create_scheduled_report(
                report_type=data.get('report_type'),
                frequency=data.get('frequency'),
                email_recipients=data.get('email_recipients', []),
                store_id=data.get('store_id') if request.user.is_staff else resolve_store_id(request),
                is_admin=request.user.is_staff and data.get('is_admin', False),
                delivery_format=data.get('delivery_format', 'html_email'),
            )
            return Response({
                'id': report.id,
                'message': 'Report created successfully',
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({
                'error': str(e),
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def test_send(self, request, pk=None):
        """Send a test report immediately."""
        try:
            report = self.get_object()

            # Generate report
            if report.is_admin:
                report_log = ReportService.generate_admin_report(report)
            else:
                report_log = ReportService.generate_merchant_report(report)

            # Send test
            if ReportService.send_report(report_log):
                return Response({
                    'message': f'Test report sent to {report.email_recipients}',
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': 'Failed to send test report',
                    'details': report_log.error_message,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'error': str(e),
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle report active status."""
        report = self.get_object()
        report.is_active = not report.is_active
        report.save()
        return Response({
            'is_active': report.is_active,
            'message': f'Report is now {"active" if report.is_active else "inactive"}',
        })

    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        """Get report logs for a scheduled report."""
        report = self.get_object()
        logs = ReportLog.objects.filter(scheduled_report=report).order_by('-generated_at')[:50]
        return Response({
            'logs': [
                {
                    'id': log.id,
                    'status': log.status,
                    'generated_at': log.generated_at.isoformat(),
                    'sent_at': log.sent_at.isoformat() if log.sent_at else None,
                    'error_message': log.error_message,
                } for log in logs
            ]
        })

    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """Update multiple reports at once."""
        report_ids = request.data.get('ids', [])
        is_active = request.data.get('is_active')

        updated = ScheduledReport.objects.filter(id__in=report_ids).update(is_active=is_active)
        return Response({
            'updated': updated,
            'message': f'{updated} reports updated',
        })


@login_required
@require_http_methods(['GET', 'POST'])
def api_scheduled_reports(request):
    """API endpoint for scheduled reports list."""
    if request.method == 'GET':
        # List scheduled reports
        store_id = resolve_store_id(request)
        queryset = ScheduledReport.objects.filter(
            store_id=store_id if not request.user.is_staff else None
        )
        if request.user.is_staff:
            queryset = ScheduledReport.objects.all()

        reports = []
        for report in queryset:
            reports.append({
                'id': report.id,
                'report_type': report.get_report_type_display(),
                'frequency': report.get_frequency_display(),
                'is_active': report.is_active,
                'next_send_at': report.next_send_at.isoformat(),
                'last_sent_at': report.last_sent_at.isoformat() if report.last_sent_at else None,
                'email_recipients': report.email_recipients,
            })

        return JsonResponse({'reports': reports})

    elif request.method == 'POST':
        # Create new report
        try:
            data = request.POST
            report = ReportService.create_scheduled_report(
                report_type=data.get('report_type'),
                frequency=data.get('frequency'),
                email_recipients=data.getlist('email_recipients'),
                store_id=resolve_store_id(request) if not request.user.is_staff else None,
                is_admin=request.user.is_staff and data.get('is_admin') == 'on',
                delivery_format=data.get('delivery_format', 'html_email'),
            )
            return JsonResponse({
                'id': report.id,
                'message': 'Report scheduled successfully',
            }, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_http_methods(['GET', 'POST', 'DELETE'])
def api_scheduled_report_detail(request, report_id):
    """API endpoint for individual scheduled report."""
    try:
        report = ScheduledReport.objects.get(id=report_id)

        # Check permissions
        if not request.user.is_staff and report.store_id != resolve_store_id(request):
            return JsonResponse({'error': 'Permission denied'}, status=403)

        if request.method == 'GET':
            return JsonResponse({
                'id': report.id,
                'report_type': report.get_report_type_display(),
                'frequency': report.get_frequency_display(),
                'is_active': report.is_active,
                'email_recipients': report.email_recipients,
                'next_send_at': report.next_send_at.isoformat(),
                'last_sent_at': report.last_sent_at.isoformat() if report.last_sent_at else None,
            })

        elif request.method == 'POST':
            # Update report
            data = request.POST
            if 'is_active' in data:
                report.is_active = data.get('is_active') == 'on'
            if 'email_recipients' in data:
                report.email_recipients = data.getlist('email_recipients')
            report.save()
            return JsonResponse({'message': 'Report updated'})

        elif request.method == 'DELETE':
            report.delete()
            return JsonResponse({'message': 'Report deleted'})

    except ScheduledReport.DoesNotExist:
        return JsonResponse({'error': 'Report not found'}, status=404)


@login_required
@require_http_methods(['POST'])
def api_test_report(request, report_id):
    """Send a test report immediately."""
    try:
        report = ScheduledReport.objects.get(id=report_id)

        # Check permissions
        if not request.user.is_staff and report.store_id != resolve_store_id(request):
            return JsonResponse({'error': 'Permission denied'}, status=403)

        # Generate and send
        if report.is_admin:
            report_log = ReportService.generate_admin_report(report)
        else:
            report_log = ReportService.generate_merchant_report(report)

        if ReportService.send_report(report_log):
            return JsonResponse({
                'message': f'Test report sent to {report.email_recipients}',
            })
        else:
            return JsonResponse({
                'error': 'Failed to send report',
                'details': report_log.error_message,
            }, status=400)

    except ScheduledReport.DoesNotExist:
        return JsonResponse({'error': 'Report not found'}, status=404)


@login_required
@require_http_methods(['GET'])
def api_report_logs(request, report_id):
    """Get logs for a scheduled report."""
    try:
        report = ScheduledReport.objects.get(id=report_id)

        # Check permissions
        if not request.user.is_staff and report.store_id != resolve_store_id(request):
            return JsonResponse({'error': 'Permission denied'}, status=403)

        logs = ReportLog.objects.filter(
            scheduled_report=report
        ).order_by('-generated_at')[:100]

        return JsonResponse({
            'logs': [
                {
                    'id': log.id,
                    'status': log.get_status_display(),
                    'generated_at': log.generated_at.isoformat(),
                    'sent_at': log.sent_at.isoformat() if log.sent_at else None,
                    'error_message': log.error_message,
                } for log in logs
            ]
        })

    except ScheduledReport.DoesNotExist:
        return JsonResponse({'error': 'Report not found'}, status=404)

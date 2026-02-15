from __future__ import annotations

from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView

from cart.interfaces.api.responses import api_response
from tenants.models import StoreDomain


class DomainProvisionQueueAPI(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        domain_id = int(request.data.get("domain_id") or 0)
        domain = StoreDomain.objects.filter(id=domain_id).first()
        if not domain:
            return api_response(success=False, errors=["domain_not_found"], status_code=404)
        domain.status = StoreDomain.STATUS_PENDING_VERIFICATION
        domain.save(update_fields=["status"])
        return api_response(success=True, data={"queued": True, "domain_id": domain_id})

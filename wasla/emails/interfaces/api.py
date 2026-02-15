from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from emails.application.use_cases.send_email import SendEmailCommand, SendEmailUseCase


class EmailTestAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not getattr(request.user, "is_staff", False):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        tenant = getattr(request, "tenant", None)
        tenant_id = getattr(tenant, "id", None) if tenant is not None else None
        if not isinstance(tenant_id, int):
            return Response({"detail": "Tenant required"}, status=status.HTTP_400_BAD_REQUEST)

        to_email = (request.data or {}).get("to_email") or getattr(request.user, "email", "")
        if not to_email:
            return Response({"detail": "to_email required"}, status=status.HTTP_400_BAD_REQUEST)

        log = SendEmailUseCase.execute(
            SendEmailCommand(
                tenant_id=tenant_id,
                to_email=to_email,
                template_key="welcome",
                context={"full_name": getattr(request.user, "username", "")},
                idempotency_key=f"email_test:{tenant_id}:{to_email}".lower(),
                metadata={"event": "email_test"},
            )
        )
        return Response({"id": log.id, "status": log.status}, status=status.HTTP_201_CREATED)


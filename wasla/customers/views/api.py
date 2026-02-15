from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..serializers import CustomerSerializer
from ..services.customer_service import CustomerService

class CustomerCreateAPI(APIView):
    def post(self, request):
        serializer = CustomerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            tenant = getattr(request, "tenant", None)
            tenant_id = getattr(tenant, "id", None) if tenant is not None else None
            data = dict(serializer.validated_data)
            if isinstance(tenant_id, int):
                data["store_id"] = tenant_id
            customer = CustomerService.create_customer(**data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(CustomerSerializer(customer).data, status=status.HTTP_201_CREATED)

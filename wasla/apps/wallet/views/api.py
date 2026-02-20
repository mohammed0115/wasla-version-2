
from rest_framework.views import APIView
from rest_framework.response import Response
from ..services.wallet_service import WalletService
from ..serializers import WalletSerializer
from apps.tenants.guards import require_store, require_tenant

class WalletDetailAPI(APIView):
    def get(self, request, store_id):
        store = require_store(request)
        tenant = require_tenant(request)
        if int(store.id) != int(store_id):
            return Response({"detail": "Not found"}, status=404)
        wallet = WalletService.get_or_create_wallet(store.id, tenant_id=tenant.id)
        return Response(WalletSerializer(wallet).data)

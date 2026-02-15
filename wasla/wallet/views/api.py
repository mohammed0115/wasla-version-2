
from rest_framework.views import APIView
from rest_framework.response import Response
from ..services.wallet_service import WalletService
from ..serializers import WalletSerializer

class WalletDetailAPI(APIView):
    def get(self, request, store_id):
        wallet = WalletService.get_or_create_wallet(store_id)
        return Response(WalletSerializer(wallet).data)

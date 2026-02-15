from rest_framework.response import Response


def api_response(*, success: bool, data=None, errors=None, status_code: int = 200):
    return Response({"success": success, "data": data, "errors": errors or []}, status=status_code)

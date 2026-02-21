from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect

from .models import Store


def get_merchant_store(request: HttpRequest) -> Store | None:
    """Resolve merchant's store.

    Current assumption (V2): 1 merchant user -> 1 store.
    """
    if not request.user.is_authenticated:
        return None
    return Store.objects.filter(owner=request.user).first()


def merchant_required(view_func):
    """Decorator: require login and store ownership."""

    @login_required
    def _wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        store = get_merchant_store(request)
        if store is None:
            return redirect("accounts:login")
        request.merchant_store = store  # type: ignore[attr-defined]
        return view_func(request, *args, **kwargs)

    return _wrapped

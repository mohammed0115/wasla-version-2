from __future__ import annotations

from django.http import HttpResponseRedirect

from apps.accounts.application.usecases.resolve_onboarding_state import resolve_onboarding_state


class OnboardingFlowMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and self._should_guard(request.path):
            destination = resolve_onboarding_state(request)
            if destination and destination != request.path:
                return HttpResponseRedirect(destination)
        return self.get_response(request)

    @staticmethod
    def _should_guard(path: str) -> bool:
        return (
            path == "/dashboard/"
            or path.startswith("/store/setup")
            or path.startswith("/dashboard/setup")
            or path.startswith("/store/create")
        )

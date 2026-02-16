from accounts.application.usecases.resolve_onboarding_state import resolve_onboarding_state


def resolve_next_destination(request) -> str:
    return resolve_onboarding_state(request)

from __future__ import annotations

from .infrastructure import InfrastructureReadinessChecker
from .payments import PaymentsReadinessChecker
from .security import SecurityReadinessChecker
from .settlements import SettlementReadinessChecker
from .ux_i18n import UXI18nReadinessChecker


def default_checkers():
    return [
        PaymentsReadinessChecker(),
        SettlementReadinessChecker(),
        SecurityReadinessChecker(),
        UXI18nReadinessChecker(),
        InfrastructureReadinessChecker(),
    ]

class SettlementError(Exception):
    pass


class LedgerError(SettlementError):
    pass


class SettlementNotFoundError(SettlementError):
    pass


class InvalidSettlementStateError(SettlementError):
    pass

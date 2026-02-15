class CheckoutError(Exception):
    pass


class EmptyCartError(CheckoutError):
    pass


class InvalidCheckoutStateError(CheckoutError):
    pass


class InvalidAddressError(CheckoutError):
    pass

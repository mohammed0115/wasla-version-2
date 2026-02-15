class CartError(Exception):
    pass


class CartNotFoundError(CartError):
    pass


class InvalidQuantityError(CartError):
    pass


class CartAccessDeniedError(CartError):
    pass

class VisualSearchError(Exception):
    pass


class InvalidImageError(VisualSearchError):
    pass


class NoResultsFoundError(VisualSearchError):
    pass

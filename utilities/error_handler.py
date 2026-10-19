from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    """DRF's handler, but errors raised as a bare message list become {"detail": "..."}.

    Clients can then rely on every error body being an object: either
    {"detail": "..."} or {"<field>": ["...", ...]}.
    """
    response = drf_exception_handler(exc, context)
    if response is not None and isinstance(response.data, list):
        response.data = {"detail": " ".join(str(message) for message in response.data)}
    return response

"""Layer 1 request parsing helper shared by the domain controllers.

Django only populates ``request.POST`` for POST requests. The personA and event
log REST APIs also accept PUT/PATCH/DELETE bodies (jQuery-serialized forms), so
this helper normalizes form access across every HTTP verb. Contains zero
business rules.
"""

from django.http import HttpRequest, QueryDict

FORM_CONTENT_TYPE = "application/x-www-form-urlencoded"


def request_params(request: HttpRequest) -> QueryDict:
    """Return the form parameters of a request regardless of HTTP verb."""
    if request.method == "POST":
        return request.POST

    if request.content_type != FORM_CONTENT_TYPE:
        return QueryDict(mutable=True)

    body = request.body or b""
    return QueryDict(body.decode("utf-8", "surrogateescape"), encoding="utf-8")
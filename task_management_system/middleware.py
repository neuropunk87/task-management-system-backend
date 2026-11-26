from ipaddress import ip_address, ip_network

from django.conf import settings
from django.http import HttpResponseNotFound
from django.urls import Resolver404, resolve

from users.access import is_system_admin


class GetRemoteAddrMiddleware:
    """Use X-Forwarded-For only when an explicitly trusted proxy appended it."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            peer = ip_address(request.META.get("REMOTE_ADDR", ""))
            trusted_peer = any(
                peer in ip_network(network) for network in settings.TRUSTED_PROXY_IPS
            )
        except ValueError:
            trusted_peer = False
        if settings.TRUST_X_FORWARDED_FOR and trusted_peer:
            forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
            addresses = [item.strip() for item in forwarded.split(",") if item.strip()]
            if len(addresses) >= settings.TRUSTED_PROXY_COUNT:
                candidate = addresses[-settings.TRUSTED_PROXY_COUNT]
                try:
                    request.META["REMOTE_ADDR"] = str(ip_address(candidate))
                except ValueError:
                    pass
        # DRF and other consumers must never re-parse the untrusted chain.
        for header in (
            "HTTP_X_FORWARDED_FOR", "HTTP_FORWARDED", "HTTP_X_FORWARDED_HOST",
            "HTTP_X_FORWARDED_PORT", "HTTP_X_FORWARDED_BY",
        ):
            request.META.pop(header, None)
        if not (
            trusted_peer
            and settings.TRUST_X_FORWARDED_PROTO
            and request.META.get("HTTP_X_FORWARDED_PROTO") in {"http", "https"}
        ):
            request.META.pop("HTTP_X_FORWARDED_PROTO", None)
        return self.get_response(request)


def client_ip(request):
    """Share the middleware's validated address with the login lockout backend."""
    try:
        return str(ip_address(request.META.get("REMOTE_ADDR", "")))
    except ValueError:
        return None


class RoleBasedAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            resolver_match = resolve(request.path)
        except Resolver404:
            return self.get_response(request)

        if resolver_match.app_name == "admin":
            if resolver_match.url_name in {"login", "logout", "jsi18n"}:
                return self.get_response(request)
            if not is_system_admin(request.user):
                return HttpResponseNotFound("Page not found")
        return self.get_response(request)


class PrivateAPIResponseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            response["Cache-Control"] = "private, no-store"
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

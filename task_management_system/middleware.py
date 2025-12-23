from django.http import HttpResponseNotFound
from django.urls import resolve


class GetRemoteAddrMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
            request.META['REMOTE_ADDR'] = ip
        return self.get_response(request)


class RoleBasedAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/secretadmin/') and resolve(request.path).url_name != 'login':
            if not request.user.is_authenticated:
                return HttpResponseNotFound("Page not found")
            elif not request.user.is_superuser and request.user.role not in ['superadmin', 'admin']:
                return HttpResponseNotFound("Page not found")
        return self.get_response(request)

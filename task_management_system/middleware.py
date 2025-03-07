from django.http import HttpResponseNotFound
from django.urls import resolve


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

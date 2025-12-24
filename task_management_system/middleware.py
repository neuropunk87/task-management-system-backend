from django.http import HttpResponseNotFound
from django.urls import resolve, Resolver404


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
        # ---------------------Hardcoding--------------------
        # if request.path.startswith('/secretadmin/') and resolve(request.path).url_name != 'login':
        #     if not request.user.is_authenticated:
        #         return HttpResponseNotFound("Page not found")
        #     elif not request.user.is_superuser and request.user.role not in ['superadmin', 'admin']:
        #         return HttpResponseNotFound("Page not found")
        # return self.get_response(request)
        # ---------------------------------------------------
        try:
            resolver_match = resolve(request.path)
        except Resolver404:
            return self.get_response(request)
        if resolver_match.app_name == 'admin':
            if resolver_match.url_name in ['login', 'logout', 'jsi18n']:
                return self.get_response(request)
            if not request.user.is_authenticated:
                return HttpResponseNotFound("Page not found")
            user_role = getattr(request.user, 'role', None)
            is_allowed = (
                    request.user.is_superuser or
                    user_role in ['superadmin', 'admin']
            )
            if not is_allowed:
                return HttpResponseNotFound("Page not found")
        return self.get_response(request)

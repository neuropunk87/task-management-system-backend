from django.urls import path

from users.views import (
    ChangePasswordView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    LogoutView,
    TelegramLinkView,
    UpdateAvatarView,
    UserDetailView,
    UserListView,
    UserProfileView,
    UserRegistrationView,
)


urlpatterns = [
    path("register/", UserRegistrationView.as_view(), name="user-registration"),
    path("login/", CustomTokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("logout", LogoutView.as_view(), name="logout"),
    path("token/refresh/", CustomTokenRefreshView.as_view(), name="token-refresh"),
    path("profile/", UserProfileView.as_view(), name="user-profile"),
    path(
        "profile/change-password/",
        ChangePasswordView.as_view(),
        name="change-password",
    ),
    path("profile/avatar/", UpdateAvatarView.as_view(), name="update-avatar"),
    path("profile/telegram-link/", TelegramLinkView.as_view(), name="telegram-link"),
    path("list/", UserListView.as_view(), name="user-list"),
    path("user/<int:pk>/", UserDetailView.as_view(), name="user-detail"),
]

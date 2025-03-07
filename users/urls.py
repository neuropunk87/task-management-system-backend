from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from users.views import (
    UserRegistrationView, CustomTokenObtainPairView, LogoutView, UserProfileView, ChangePasswordView, UpdateAvatarView,
    UserListView, UserDetailView
)


urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='user-registration'),
    path('login/', CustomTokenObtainPairView.as_view(), name='token-obtain-pair'),
    path('logout', LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('profile/change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('profile/avatar/', UpdateAvatarView.as_view(), name='update-avatar'),
    path('list/', UserListView.as_view(), name='user-list'),
    path('user/<int:pk>/', UserDetailView.as_view(), name='user-detail'),
]

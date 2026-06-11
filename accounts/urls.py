from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.routers import DefaultRouter
from . import views

# Router pour les routes admin des utilisateurs
router = DefaultRouter()
router.register(r'admin/users', views.AdminUserViewSet, basename='admin-user')

urlpatterns = [
    # Authentification
    path('register', views.RegisterView.as_view(), name='register'),
    path('login', views.login_view, name='login'),
    path('verify-otp', views.verify_otp_view, name='verify_otp'),
    path('resend-otp', views.resend_otp_view, name='resend_otp'),
    path('token/refresh', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Profil
    path('profile', views.get_profile_view, name='profile'),
    path('profile/update', views.update_profile_view, name='update_profile'),
    
    # Routes admin pour gérer les utilisateurs
    path('', include(router.urls)),
]
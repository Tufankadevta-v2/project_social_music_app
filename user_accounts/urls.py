from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

app_name = 'user_accounts'

router = DefaultRouter()

urlpatterns = [
	# Authentication endpoints (Token-based)
	path('send-otp/', views.send_otp, name='send_otp'),
	path('verify-otp/', views.verify_otp, name='verify_otp'),
	path('register/', views.register_user, name='register_user'),
	path('login/', views.login_user, name='login_user'),
	path('logout/', views.logout_user, name='logout_user'),
	
	# JWT Authentication endpoints
	path('jwt/login/', views.jwt_login, name='jwt_login'),
	path('jwt/refresh/', views.jwt_refresh, name='jwt_refresh'),
	path('jwt/logout/', views.jwt_logout, name='jwt_logout'),
	path('jwt/token/', views.CustomTokenObtainPairView.as_view(), name='jwt_token_obtain_pair'),
	path('jwt/token/refresh/', TokenRefreshView.as_view(), name='jwt_token_refresh'),
	
	# User profile
	path('profile/', views.user_profile, name='user_profile'),
	
	# Privacy settings
	path('privacy/', include('user_accounts.privacy_urls')),
	
	# Router URLs
	path('', include(router.urls)),
]
from django.urls import path

from .views import (
    
    google_auth, 
    UserRegisterView,
    OTPVerificationView,
    SignInView,
    SendOTPEmailView,
    UserInfoView,
    ForgotPasswordView,
    ChangePasswordView,
    UpdateProfileView,

)
urlpatterns = [
    path('google-auth/', google_auth, name='google_auth'),
    path('register/', UserRegisterView.as_view(), name='user_register'),
    path('signin/', SignInView.as_view(), name='signin'),
    path('user/', UserInfoView.as_view(), name='user_info'),
    path('send-otp/', SendOTPEmailView.as_view(), name='send_otp'),
    path('verify-otp/', OTPVerificationView.as_view(), name='verify_otp'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot_password'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('user/update-profile/', UpdateProfileView.as_view(), name='update_profile'),
    
]
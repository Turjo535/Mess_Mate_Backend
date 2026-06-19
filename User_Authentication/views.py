from time import timezone
from django.shortcuts import render,get_object_or_404
from django.utils import timezone 
from rest_framework import serializers, status
from firebase_admin import auth as firebase_auth
from rest_framework.decorators import api_view
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import OpenApiResponse, extend_schema, OpenApiExample, inline_serializer
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser


# local imports
from .models import UserModel, OTPModel
from .serializers import FirebaseTokenSerializer, UserRegisterSerializer, UpdateProfileSerializer
from .email import send_otp_email

# Create your views here.

@extend_schema(request=FirebaseTokenSerializer)
@api_view(['POST'])
def google_auth(request):
    id_token = request.data.get('id_token')
    if not id_token:
        return Response({'error': 'ID token required'}, status=400)

    try:
        decoded = firebase_auth.verify_id_token(id_token)
    except Exception:
        return Response({'error': 'Invalid or expired token'}, status=401)

    uid           = decoded.get('uid')
    email         = decoded.get('email', '')
    name          = decoded.get('name', '')
    picture       = decoded.get('picture', '')      # profile picture URL
    email_verified = decoded.get('email_verified', False)  # active status

    
    if not email_verified:
        return Response({'error': 'Email not verified'}, status=403)


    user, created = UserModel.objects.get_or_create(
        unique_id=uid,
        defaults={
            'email': email,
            'name': name,
            'profile_picture_url': picture,
            'is_active': email_verified,
        }
    )

    # Update name & picture in case they changed on Google
    if not created:
        user.name            = name
        user.profile_picture_url = picture
        user.is_active       = email_verified
        user.save(update_fields=['name', 'profile_picture_url', 'is_active'])

    refresh = RefreshToken.for_user(user)
    return Response({
        'access':  str(refresh.access_token),
        'refresh': str(refresh),
        'created': created,
        'user': {
            'uid':             uid,
            'email':           email,
            'name':            name,
            'profile_picture': picture,
            'email_verified':  email_verified,
        }
    })

# Resister User API View
class UserRegisterView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=["auth"],
        summary="Register a new user",
        request={"multipart/form-data": UserRegisterSerializer},
        responses={
            201: OpenApiResponse(
                description="User registered successfully.",
                response={"type": "object", "properties": {"message": {"type": "string"}}},
            ),
            400: OpenApiResponse(
                description="Validation error.",
                response={"type": "object", "additionalProperties": {"type": "array", "items": {"type": "string"}}},
            ),
        },
    )
    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            send_otp_email(serializer.instance)
            return Response({'message': 'User registered successfully. Please check your email for the verification code.'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SignInView(APIView):
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    @extend_schema(
        summary="User Sign In",
        description="Authenticate user with email and password, returning JWT tokens upon success.",
        request={
            "application/json": inline_serializer(
                name="SignInInput",
                fields={
                    "email": serializers.EmailField(required=True),
                    "password": serializers.CharField(required=True, write_only=True)
                }
            )
        },
        responses={
            200: OpenApiResponse(description="Sign in successful, returns access and refresh tokens."),
            400: OpenApiResponse(description="Email and password are required."),
            401: OpenApiResponse(description="Invalid credentials."),
            403: OpenApiResponse(description="Account is not active. Please verify your email."),
            404: OpenApiResponse(description="User not found.")
        }
    )
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        if not email or not password:
            return Response({'error': 'Email and password are required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = UserModel.objects.get(email=email)
            if not user.check_password(password):
                return Response({'error': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)
            if user.is_active == False:
                return Response({'error': 'Account is not active. Please verify your email.'}, status=status.HTTP_403_FORBIDDEN)
            refresh = RefreshToken.for_user(user)
            return Response({
                "message": "Sign in successful.",
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            })
        except UserModel.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        

        
# User Information API View
class UserInfoView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get User Information",
        description="Retrieves the authenticated user's information.",
        responses={
            200: OpenApiResponse(description="User information retrieved successfully."),
            401: OpenApiResponse(description="Authentication credentials were not provided or are invalid.")
        }
    )
    def get(self, request):
        user = request.user  
        data = {
            'id': user.id,
            'email': user.email,
            'name': user.name,
        }
        if user.profile_picture:
            data['profile_picture'] = user.profile_picture.url
        elif user.profile_picture_url:
            data['profile_picture_url'] = user.profile_picture_url
        else:
            data['profile_picture'] = None

        return Response(data, status=status.HTTP_200_OK)
        return Response({'error': 'Authentication credentials were not provided or are invalid.'}, status=status.HTTP_401_UNAUTHORIZED)


# send OTP email API View
class SendOTPEmailView(APIView):
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @extend_schema(
        summary="Send OTP Email",
        description="Sends a One-Time Passcode (OTP) to the user's registered email for verification.",
        request={
            "application/json": inline_serializer(
                name="SendOTPInput",
                fields={
                    "email": serializers.EmailField(required=True)
                }
            )
        },
        responses={
            200: OpenApiResponse(description="OTP email sent successfully."),
            400: OpenApiResponse(description="Email is required."),
            404: OpenApiResponse(description="User not found.")
        }
    )
    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = UserModel.objects.get(email=email)
            send_otp_email(user)
            return Response({'message': 'OTP email sent successfully.'})
        except UserModel.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

# OTP Verification API View
class OTPVerificationView(APIView):
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @extend_schema(
        summary="Verify Registration OTP",
        description="Validates the 6-digit passcode against the database and checks the 15-minute expiration window.",
         request={
            "application/json": inline_serializer(
                name="VerifyOTPInput",
                fields={
                    "email": serializers.EmailField(required=True),
                    "otp": serializers.CharField(required=True, max_length=6)
                }
            )
        },
        responses={
            200: OpenApiResponse(description="OTP verified successfully. Account is now active."),
            400: OpenApiResponse(description="Invalid OTP or passcode has expired.")
        }
    )
    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')
        

        if not email or not otp:
            return Response({'error': 'OTP are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = UserModel.objects.get(email=email)
            otp_record = OTPModel.objects.filter(user=user, otp=otp).latest('created_at')
            otp_records= OTPModel.objects.filter(user=user).all()
            if otp_record and (timezone.now() - otp_record.created_at).total_seconds() < 900:  
                user.is_active = True
                user.save()
                otp_records.delete()  
                return Response({'message': 'Email verified successfully.'})
            else:
                return Response({'error': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)
        except UserModel.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)


class ForgotPasswordView(APIView):
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @extend_schema(
        summary="Forgot Password",
        description="Sends a password reset link to the user's registered email.",
        request={
            "application/json": inline_serializer(
                name="ForgotPasswordInput",
                fields={
                    "email": serializers.EmailField(required=True),
                    "otp": serializers.CharField(required=True, max_length=6),
                    "new_password": serializers.CharField(required=True, write_only=True),
                    "confirm_password": serializers.CharField(required=True, write_only=True)
                }
            )
        },
        responses={
            200: OpenApiResponse(description="Password reset link sent successfully."),
            400: OpenApiResponse(description="All fields are required."),
            404: OpenApiResponse(description="User not found.")
        }
    )
    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')
        if not email or not otp or not new_password or not confirm_password:
            return Response({'error': 'All fields are required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = UserModel.objects.get(email=email)
            otp_record = OTPModel.objects.filter(user=user, otp=otp).latest('created_at')
            otp_records= OTPModel.objects.filter(user=user).all()
            if otp_record and (timezone.now() - otp_record.created_at).total_seconds() < 900:
                if new_password != confirm_password:
                    return Response({'error': 'Passwords do not match.'}, status=status.HTTP_400_BAD_REQUEST)
                user.set_password(new_password)
                user.save()
                otp_records.delete()
                return Response({'message': 'Password reset successfully.'})
            else:
                return Response({'error': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)
        except UserModel.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @extend_schema(
        summary="Change Password",
        description="Allows authenticated users to change their password.",
        request={
            "application/json": inline_serializer(
                name="ChangePasswordInput",
                fields={
                    "current_password": serializers.CharField(required=True, write_only=True),
                    "new_password": serializers.CharField(required=True, write_only=True),
                    "confirm_password": serializers.CharField(required=True, write_only=True)
                }
            )
        },
        responses={
            200: OpenApiResponse(description="Password changed successfully."),
            400: OpenApiResponse(description="All fields are required or passwords do not match."),
            401: OpenApiResponse(description="Authentication credentials were not provided or are invalid.")
        }
    )
    def post(self, request):
        user = request.user
        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')

        if not current_password or not new_password or not confirm_password:
            return Response({'error': 'All fields are required.'}, status=status.HTTP_400_BAD_REQUEST)

        if not user.check_password(current_password):
            return Response({'error': 'Current password is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)

        if new_password != confirm_password:
            return Response({'error': 'New passwords do not match.'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({'message': 'Password changed successfully.'})
    
class UpdateProfileView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UpdateProfileSerializer
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        summary="Update User Profile",
        description="Allows authenticated users to update their profile information.",
        request={"multipart/form-data": UpdateProfileSerializer},
        responses={
            200: OpenApiResponse(description="Profile updated successfully."),
            400: OpenApiResponse(description="Validation error."),
            401: OpenApiResponse(description="Authentication credentials were not provided or are invalid.")
        },
    )
    def patch(self, request):
        user = request.user

        data = request.data.copy()

    
        for key in list(data.keys()):
            if data[key] == "" or data[key] is None:
                data.pop(key)

   
        if 'profile_picture' in data and not data['profile_picture']:
            data.pop('profile_picture')

        serializer = self.serializer_class(user, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Profile updated successfully.'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
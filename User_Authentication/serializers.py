# serializers.py
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import UserModel


class FirebaseTokenSerializer(serializers.Serializer):
    id_token = serializers.CharField(required=True)


@extend_schema_field(OpenApiTypes.BINARY)
class SwaggerImageField(serializers.ImageField):
    pass


class UserRegisterSerializer(serializers.ModelSerializer):
    profile_picture = SwaggerImageField(required=False, allow_null=True)
    password = serializers.CharField(write_only=True, required=True)
    confirm_password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = UserModel
        fields = ['unique_id', 'email', 'name', 'profile_picture', 'password', 'confirm_password']
        extra_kwargs = {
            'unique_id': {'required': False, 'allow_null': True},
        }

    def validate(self, data):
        password = data.get('password')
        confirm_password = data.get('confirm_password')
        email = data.get('email')
        unique_id = data.get('unique_id')

        if password != confirm_password:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        if email and UserModel.objects.filter(email=email).exists():
            raise serializers.ValidationError({"email": "A user with this email already exists."})
        if unique_id and UserModel.objects.filter(unique_id=unique_id).exists():
            raise serializers.ValidationError({"unique_id": "This identifier is already registered."})
        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)

class UpdateProfileSerializer(serializers.ModelSerializer):
    profile_picture = SwaggerImageField(required=False, allow_null=True)

    class Meta:
        model = UserModel
        fields = ['name', 'phone', 'date_of_birth', 'permanent_address', 'profession', 'institution', 'profile_picture']
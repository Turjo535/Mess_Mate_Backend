from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin

from .manager import CustomUserManager


class UserModel(AbstractBaseUser, PermissionsMixin):
    # Primary Key (Linked with Firebase Auth UID string)
    unique_id = models.CharField(max_length=128, serialize=False, unique=True, null=True, blank=True)
    
    # Required Core Identity Fields
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    
    # Profile & Contact Meta Fields
    phone = models.CharField(max_length=20, blank=True, null=True)
    date_of_birth = models.DateTimeField(blank=True, null=True)
    permanent_address = models.TextField(blank=True, null=True)
    profession = models.CharField(max_length=100, blank=True, null=True)
    institution = models.CharField(max_length=255, blank=True, null=True)
    
    # System Administration Status Flags
    is_admin = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)  
    is_active = models.BooleanField(default=False)
    
    # Automatic Metadata Trackers
    created_at = models.DateTimeField(auto_now_add=True)
    profile_picture_url = models.URLField(blank=True, null=True)  
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)

    objects = CustomUserManager()

    # Enforce Email as the primary authentication field identifier instead of username
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        
    def __str__(self):
        return self.email
    

class OTPModel(models.Model):
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"OTP for {self.user.email} - {self.otp}"

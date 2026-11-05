from django.db import models
from User_Authentication.models import UserModel
from datetime import timedelta
from django.utils import timezone
# Create your models here.
def get_expiry():
    return timezone.now() + timedelta(hours=72)

class Mess(models.Model):
    name = models.CharField(max_length=100)
    mess_address = models.CharField(max_length=200)
    instruction= models.TextField(default="No instructions provided.")
    capacity = models.IntegerField()
    contact_number = models.CharField(max_length=15)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Mess_Members(models.Model):
    member = models.ForeignKey(UserModel, on_delete=models.CASCADE)
    mess = models.ForeignKey(Mess, on_delete=models.CASCADE)
    is_manager = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)


class MessInvitation(models.Model):
    mess = models.ForeignKey(Mess, on_delete=models.CASCADE, related_name='invitations')
    invited_email = models.EmailField()
    invited_by = models.ForeignKey(UserModel, on_delete=models.CASCADE, related_name='sent_invitations')
    token = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField(default=get_expiry)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('mess', 'invited_email')
        indexes = [
            models.Index(fields=['invited_email']),
            models.Index(fields=['expires_at']),
        ]

    @property
    def last_sent_at(self):
        return self.expires_at - INVITE_TTL

    def __str__(self):
        return f"{self.invited_email} - {self.mess}"


class Notification(models.Model):
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=30)
    payload = models.JSONField(default=dict)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'is_read'])]
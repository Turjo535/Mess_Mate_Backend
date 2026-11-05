from rest_framework import serializers
from .models import Mess, Mess_Members, MessInvitation, Notification


class CreateMessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mess
        fields = ['id', 'name', 'mess_address', 'instruction', 'capacity', 'contact_number']


class AddMessMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mess_Members
        fields = ['member', 'mess', 'is_manager']


# ---- request ----
class BulkInviteSerializer(serializers.Serializer):
    emails = serializers.ListField(child=serializers.EmailField(), min_length=1, max_length=20)

    def validate_emails(self, value):
        return list({e.strip().lower() for e in value})


class InvitationRespondSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['accepted', 'declined'])


class NotificationReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['is_read']


# ---- model output ----
class InvitationSerializer(serializers.ModelSerializer):
    mess_name = serializers.CharField(source='mess.name')
    mess_address = serializers.CharField(source='mess.mess_address')
    invited_by_name = serializers.SerializerMethodField()

    class Meta:
        model = MessInvitation
        fields = ['id', 'mess_name', 'mess_address', 'invited_by_name', 'created_at', 'expires_at']

    def get_invited_by_name(self, obj) -> str:
        return getattr(obj.invited_by, 'name', None) or obj.invited_by.email


class SentInvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessInvitation
        fields = ['id', 'invited_email', 'created_at', 'expires_at']


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'type', 'payload', 'is_read', 'created_at']


# ---- Swagger response shapes ----
class SkippedEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()
    reason = serializers.ChoiceField(choices=['already_member', 'already_invited'])


class BulkInviteResponseSerializer(serializers.Serializer):
    sent = serializers.IntegerField()
    skipped = SkippedEmailSerializer(many=True)


class InvitationRespondResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=['accepted', 'declined'])


class InvitationLookupSerializer(serializers.Serializer):
    valid = serializers.BooleanField()
    mess_name = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    has_account = serializers.BooleanField(required=False)
    expires_at = serializers.DateTimeField(required=False)


class NotificationListSerializer(serializers.Serializer):
    unread_count = serializers.IntegerField()
    results = NotificationSerializer(many=True)


class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()
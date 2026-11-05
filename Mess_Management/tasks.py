from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone


@shared_task(bind=True, max_retries=3)
def send_invitation_email(self, email, mess_name, token):
    link = f"{settings.FRONTEND_URL}/register?invite={token}"
    try:
        send_mail(
            subject=f'"{mess_name}"-এ যোগ দেওয়ার আমন্ত্রণ',
            message=f'আপনাকে {mess_name}-এ আমন্ত্রণ জানানো হয়েছে।\n\nAccount তৈরি করতে: {link}',
            from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[email])
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task
def cleanup_invitations():
    from .models import MessInvitation
    from .services import expire_invitations
    return expire_invitations(MessInvitation.objects.filter(expires_at__lte=timezone.now()))
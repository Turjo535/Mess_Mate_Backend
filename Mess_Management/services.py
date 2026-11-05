import secrets
from datetime import timedelta
from django.db import transaction
from django.db.models.functions import Lower
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from User_Authentication.models import UserModel
from .models import Mess_Members, MessInvitation, Notification, get_expiry
from .tasks import send_invitation_email

VERIFIED_FIELD = 'is_verified'   # আপনার UserModel-এর আসল নাম না হলে শুধু এখানে বদলান
DAILY_INVITE_LIMIT = 20
RESEND_COOLDOWN = timedelta(minutes=10)
VERIFIED_FIELD = 'is_active'


def _invite_payload(inv):
    return {'invitation_id': inv.id, 'mess_id': inv.mess_id, 'mess_name': inv.mess.name}


def _result_payload(mess, email, user_id=None):
    return {'mess_id': mess.id, 'mess_name': mess.name, 'email': email, 'user_id': user_id}


def _managers(mess_ids):
    out = {}
    rows = Mess_Members.objects.filter(
        mess_id__in=mess_ids, is_manager=True).values_list('mess_id', 'member_id')
    for mess_id, user_id in rows:
        out.setdefault(mess_id, []).append(user_id)
    return out


def notify_managers(mess, type_, email, user_id=None):
    Notification.objects.bulk_create([
        Notification(user_id=uid, type=type_, payload=_result_payload(mess, email, user_id))
        for uid in _managers([mess.id]).get(mess.id, [])])


@transaction.atomic
def expire_invitations(qs):
    invs = list(qs.select_related('mess'))
    if not invs:
        return 0
    managers = _managers({i.mess_id for i in invs})
    users = {u.email.lower(): u.id for u in
             UserModel.objects.filter(email__in=[i.invited_email for i in invs])}
    Notification.objects.bulk_create([
        Notification(user_id=uid, type='invitation_expired',
                     payload=_result_payload(i.mess, i.invited_email, users.get(i.invited_email)))
        for i in invs for uid in managers.get(i.mess_id, [])])
    ids = [i.id for i in invs]
    Notification.objects.filter(type='mess_invitation', payload__invitation_id__in=ids).delete()
    MessInvitation.objects.filter(id__in=ids).delete()
    return len(invs)


def create_invitations(mess, inviter, emails):
    now = timezone.now()
    expire_invitations(MessInvitation.objects.filter(
        mess=mess, invited_email__in=emails, expires_at__lte=now))

    members = set(Mess_Members.objects.annotate(e=Lower('member__email'))
                  .filter(mess=mess, e__in=emails).values_list('e', flat=True))
    users = {u.e: u for u in UserModel.objects.annotate(e=Lower('email'))
             .filter(e__in=emails, **{VERIFIED_FIELD: True})}
    pending = {i.invited_email: i for i in
               MessInvitation.objects.filter(mess=mess, invited_email__in=emails)}

    skipped, new, resend = [], [], []
    for e in emails:
        inv = pending.get(e)
        if e in members:
            skipped.append({'email': e, 'reason': 'already_member'})
        elif not inv:
            new.append(e)
        elif e in users or now - inv.last_sent_at < RESEND_COOLDOWN:
            skipped.append({'email': e, 'reason': 'already_invited'})
        else:
            resend.append(inv)

    recent = MessInvitation.objects.filter(mess=mess, created_at__gte=now - timedelta(days=1)).count()
    if recent + len(new) > DAILY_INVITE_LIMIT:
        raise ValidationError('Daily invitation limit reached.')

    joined = Mess_Members.objects.filter(mess=mess).count()
    open_invites = MessInvitation.objects.filter(mess=mess, expires_at__gt=now).count()
    if joined + open_invites + len(new) > mess.capacity:
        raise ValidationError(f'Mess capacity ({mess.capacity}) exceeded.')

    created = [MessInvitation(mess=mess, invited_by=inviter, invited_email=e,
                              token=secrets.token_urlsafe(32)) for e in new]
    with transaction.atomic():
        MessInvitation.objects.bulk_create(created)
        for inv in resend:
            inv.expires_at = get_expiry()
        MessInvitation.objects.bulk_update(resend, ['expires_at'])
        Notification.objects.bulk_create([
            Notification(user=users[i.invited_email], type='mess_invitation', payload=_invite_payload(i))
            for i in created if i.invited_email in users])

    for i in created + resend:
        if i.invited_email not in users:
            send_invitation_email.delay(i.invited_email, mess.name, i.token)

    return len(created) + len(resend), skipped


def notify_pending_invitations(user):
    invs = MessInvitation.objects.filter(
        invited_email__iexact=user.email, expires_at__gt=timezone.now()).select_related('mess')
    already = set(Notification.objects.filter(user=user, type='mess_invitation')
                  .values_list('payload__invitation_id', flat=True))
    Notification.objects.bulk_create([
        Notification(user=user, type='mess_invitation', payload=_invite_payload(i))
        for i in invs if i.id not in already])


@transaction.atomic
def respond_to_invitation(invitation_id, user, new_status):
    inv = (MessInvitation.objects.select_for_update(of=('self',)).select_related('mess')
           .filter(pk=invitation_id, invited_email__iexact=user.email,
                   expires_at__gt=timezone.now()).first())
    if not inv:
        raise NotFound('Invitation not found or expired.')

    if new_status == 'accepted':
        if Mess_Members.objects.filter(mess=inv.mess).count() >= inv.mess.capacity:
            raise ValidationError('Mess is full.')
        if not Mess_Members.objects.filter(member=user, mess=inv.mess).exists():
            Mess_Members.objects.create(member=user, mess=inv.mess)

    notify_managers(inv.mess, f'invitation_{new_status}', user.email, user.id)
    Notification.objects.filter(user=user, type='mess_invitation',
                                payload__invitation_id=inv.id).delete()
    inv.delete()
    return new_status
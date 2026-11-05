from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (OpenApiExample, OpenApiParameter, OpenApiResponse,
                                   extend_schema, inline_serializer)
from rest_framework import generics, serializers, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

# Local imports
from User_Authentication.models import UserModel
from .models import Mess, MessInvitation, Notification
from .permissions import IsMessManager, IsVerifiedUser
from .serializers import (
    AddMessMemberSerializer, BulkInviteResponseSerializer, BulkInviteSerializer,
    CreateMessSerializer, DetailSerializer, InvitationLookupSerializer,
    InvitationRespondResponseSerializer, InvitationRespondSerializer, InvitationSerializer,
    NotificationListSerializer, NotificationReadSerializer, NotificationSerializer,
    SentInvitationSerializer)
from .services import create_invitations, respond_to_invitation

TAG = 'Mess Management'


# ---------------------------------------------------------------- Mess
class CreateMessView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @extend_schema(
        tags=[TAG],
        request=CreateMessSerializer,
        responses={
            201: OpenApiResponse(
                response=inline_serializer(
                    name='MessCreatedResponse',
                    fields={
                        'message': serializers.CharField(),
                        'mess_id': serializers.IntegerField(),
                    }
                ),
                description='Mess created successfully'
            ),
            400: OpenApiResponse(
                response=inline_serializer(
                    name='CreateMessBadRequest',
                    fields={'error': serializers.CharField()}
                ),
                description='Bad request'
            ),
        },
        examples=[
            OpenApiExample(
                'Successful Response',
                summary='Mess created successfully',
                value={'message': 'Mess created successfully', 'mess_id': 1},
                response_only=True,
            ),
        ]
    )
    def post(self, request):
        serializer = CreateMessSerializer(data=request.data)
        if serializer.is_valid():
            mess = serializer.save()

            if Mess.objects.filter(id=mess.id).exists():
                mess_member = AddMessMemberSerializer(
                    data={'member': request.user.id, 'mess': mess.id, 'is_manager': True})
                if mess_member.is_valid():
                    mess_member.save()
                    return Response({'message': 'Mess created successfully', 'mess_id': mess.id},
                                    status=status.HTTP_201_CREATED)
        return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------- Manager side
@extend_schema(tags=[TAG])
class MessInvitationListCreateView(generics.ListCreateAPIView):
    """GET: pending list, POST: invite (and resend)."""
    permission_classes = [IsAuthenticated, IsMessManager]
    parser_classes = [JSONParser]

    def get_serializer_class(self):
        return BulkInviteSerializer if self.request.method == 'POST' else SentInvitationSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return MessInvitation.objects.none()
        return (MessInvitation.objects
                .filter(mess_id=self.kwargs['mess_id'], expires_at__gt=timezone.now())
                .order_by('-created_at'))

    @extend_schema(
        request=BulkInviteSerializer,
        responses={201: BulkInviteResponseSerializer,
                   400: OpenApiResponse(description='Limit or capacity exceeded')})
    def create(self, request, *args, **kwargs):
        mess = get_object_or_404(Mess, pk=kwargs['mess_id'])
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sent, skipped = create_invitations(mess, request.user, serializer.validated_data['emails'])
        return Response({'sent': sent, 'skipped': skipped}, status=status.HTTP_201_CREATED)


@extend_schema(tags=[TAG])
class MessInvitationCancelView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated, IsMessManager]
    serializer_class = SentInvitationSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return MessInvitation.objects.none()
        return MessInvitation.objects.filter(mess_id=self.kwargs['mess_id'])

    def perform_destroy(self, invitation):
        Notification.objects.filter(
            type='mess_invitation', payload__invitation_id=invitation.id).delete()
        invitation.delete()


# ---------------------------------------------------------------- Invitee side
@extend_schema(tags=[TAG])
class MyInvitationListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsVerifiedUser]
    serializer_class = InvitationSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return MessInvitation.objects.none()
        return (MessInvitation.objects
                .filter(invited_email__iexact=self.request.user.email,
                        expires_at__gt=timezone.now())
                .select_related('mess', 'invited_by')
                .order_by('-created_at'))


@extend_schema(tags=[TAG])
class InvitationRespondView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsVerifiedUser]
    serializer_class = InvitationRespondSerializer
    parser_classes = [JSONParser]

    @extend_schema(
        request=InvitationRespondSerializer,
        responses={200: InvitationRespondResponseSerializer,
                   400: OpenApiResponse(description='Mess is full'),
                   404: DetailSerializer})
    def patch(self, request, pk):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = respond_to_invitation(pk, request.user, serializer.validated_data['status'])
        return Response({'id': pk, 'status': result})


@extend_schema(tags=[TAG])
class InvitationLookupView(APIView):
    """Public: registration page opens this with the token from the email link."""
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        parameters=[OpenApiParameter('token', OpenApiTypes.STR, required=True)],
        responses={200: InvitationLookupSerializer, 404: InvitationLookupSerializer})
    def get(self, request):
        invitation = (MessInvitation.objects.select_related('mess')
                      .filter(token=request.query_params.get('token', ''),
                              expires_at__gt=timezone.now()).first())
        if not invitation:
            return Response({'valid': False}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'valid': True,
            'mess_name': invitation.mess.name,
            'email': invitation.invited_email,
            'has_account': UserModel.objects.filter(email__iexact=invitation.invited_email).exists(),
            'expires_at': invitation.expires_at,
        })


# ---------------------------------------------------------------- Notifications
@extend_schema(tags=[TAG])
class NotificationListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Notification.objects.none()
        return Notification.objects.filter(user=self.request.user)

    @extend_schema(responses={200: NotificationListSerializer})
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        return Response({
            'unread_count': queryset.filter(is_read=False).count(),
            'results': NotificationSerializer(queryset[:50], many=True).data,
        })


@extend_schema(tags=[TAG])
class NotificationReadView(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationReadSerializer
    parser_classes = [JSONParser]
    http_method_names = ['patch']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Notification.objects.none()
        return Notification.objects.filter(user=self.request.user)
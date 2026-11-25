from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

# local imports
from Mess_Management.models import Mess, Mess_Members
from Mess_Management.permissions import IsMessManager, IsMessMember
from .permission import IsMessCycleActive
from .services import cycle_meal_summary, cycle_financial_summary, notify_mess
from .models import MemberDeposit, MessBazar, MessUtilities, MessCycle
from .serializers import (
    MemberDepositCreateGetSerializer,
    CreateMessCycleSerializer,
    MessBazarSerializer,
    MessUtilitiesSerializer,
)

# Create your views here.
TAG = 'Financial Management'


# =====================================================================
# 1. Mess Cycle Views
# =====================================================================

class CreateMessCycleView(APIView):
    permission_classes = [IsAuthenticated, IsMessManager]

    @extend_schema(
        tags=[TAG],
        responses={200: CreateMessCycleSerializer(many=True)},
    )
    def get(self, request, mess_id=None):
        mess_id = mess_id or request.query_params.get('mess_id')
        if not mess_id:
            return Response({'error': 'mess_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        mess = get_object_or_404(Mess, pk=mess_id)

        cycle_id = request.query_params.get('cycle_id')
        if cycle_id:
            cycle = get_object_or_404(MessCycle, pk=cycle_id, mess=mess)
            return Response(CreateMessCycleSerializer(cycle).data, status=status.HTTP_200_OK)

        cycles = MessCycle.objects.filter(mess=mess).order_by('-start_date')
        if request.query_params.get('latest') == 'true':
            cycle = cycles.first()
            if not cycle:
                return Response({'error': 'No cycle found for this mess.'}, status=status.HTTP_404_NOT_FOUND)
            return Response(CreateMessCycleSerializer(cycle).data, status=status.HTTP_200_OK)
        serializer = CreateMessCycleSerializer(cycles, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=[TAG],
        request=CreateMessCycleSerializer,
        responses={
            201: CreateMessCycleSerializer,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
    )
    def post(self, request, mess_id=None):
        mess_id = mess_id or request.query_params.get('mess_id')
        if not mess_id:
            return Response({'error': 'mess_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        mess = get_object_or_404(Mess, pk=mess_id)
        serializer = CreateMessCycleSerializer(data=request.data, context={'mess': mess})
        if serializer.is_valid():
            cycle = serializer.save(mess=mess)
            notify_mess(mess, request.user, 'cycle_created', {
                'cycle_id': cycle.id,
                'cycle_name': cycle.name,
                'start_date': str(cycle.start_date),
                'end_date': str(cycle.end_date),
                'by': request.user.email,
            })
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UpdateMessCycleView(APIView):
    """Dedicated view for PATCH request only - updates an existing MessCycle."""
    permission_classes = [IsAuthenticated, IsMessManager]

    @extend_schema(
        tags=[TAG],
        summary="Partially update a mess cycle",
        request=CreateMessCycleSerializer,
        responses={
            200: CreateMessCycleSerializer,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
    )
    def patch(self, request, mess_id=None, pk=None):
        mess_id = mess_id or request.query_params.get('mess_id')
        if not mess_id:
            return Response({'error': 'mess_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        mess = get_object_or_404(Mess, pk=mess_id)
        pk = pk or request.query_params.get('id') or (
            request.data.get('id') if hasattr(request, 'data') and isinstance(request.data, dict) else None
        )
        if not pk:
            return Response({'error': 'Cycle ID (pk) is required.'}, status=status.HTTP_400_BAD_REQUEST)

        cycle = get_object_or_404(MessCycle, pk=pk, mess=mess)
        serializer = CreateMessCycleSerializer(cycle, data=request.data, partial=True, context={'mess': mess})
        if serializer.is_valid():
            serializer.save()
            notify_mess(mess, request.user, 'cycle_updated', {
                'cycle_id': cycle.id,
                'cycle_name': cycle.name,
                'changed_fields': list(request.data.keys()),
                'by': request.user.email,
            })
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# =====================================================================
# 2. Member Deposit Views
# =====================================================================

class MemberDepositViewSet(APIView):
    permission_classes = [IsAuthenticated, IsMessManager]

    @extend_schema(
        tags=[TAG],
        responses={200: MemberDepositCreateGetSerializer(many=True)},
    )
    def get(self, request, mess_id=None):
        mess_id = mess_id or request.query_params.get('mess_id')
        if not mess_id:
            return Response({'error': 'mess_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        deposits = MemberDeposit.objects.filter(member__mess_id=mess_id).order_by('-deposit_date')
        serializer = MemberDepositCreateGetSerializer(deposits, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=[TAG],
        request=MemberDepositCreateGetSerializer,
        responses={
            201: MemberDepositCreateGetSerializer,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
    )
    def post(self, request, mess_id=None):
        mess_id = mess_id or request.query_params.get('mess_id')
        serializer = MemberDepositCreateGetSerializer(data=request.data)
        if serializer.is_valid():
            member = serializer.validated_data['member']
            target_mess_id = int(mess_id) if mess_id else member.mess_id

            if mess_id and member.mess_id != int(mess_id):
                return Response({'error': 'Selected member does not belong to this mess.'}, status=status.HTTP_400_BAD_REQUEST)

            mess_manager = Mess_Members.objects.filter(
                member=request.user,
                mess_id=target_mess_id,
                is_manager=True,
            ).first()
            if not mess_manager:
                return Response({'error': 'You are not a manager of this mess.'}, status=status.HTTP_403_FORBIDDEN)

            deposit = serializer.save(add_by=mess_manager)
            mess = mess_manager.mess
            notify_mess(mess, request.user, 'deposit_added', {
                'deposit_id': deposit.id,
                'amount': str(deposit.amount),
                'section': deposit.section,
                'member_id': member.id,
                'by': request.user.email,
            })
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UpdateMemberDepositView(APIView):
    """Dedicated view for PATCH request only - updates an existing MemberDeposit."""
    permission_classes = [IsAuthenticated, IsMessManager]

    @extend_schema(
        tags=[TAG],
        summary="Partially update a member deposit",
        request=MemberDepositCreateGetSerializer,
        responses={
            200: MemberDepositCreateGetSerializer,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
    )
    def patch(self, request, mess_id=None, pk=None):
        mess_id = mess_id or request.query_params.get('mess_id')
        if not mess_id:
            return Response({'error': 'mess_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        mess = get_object_or_404(Mess, pk=mess_id)
        pk = pk or request.query_params.get('id') or (
            request.data.get('id') if hasattr(request, 'data') and isinstance(request.data, dict) else None
        )
        if not pk:
            return Response({'error': 'Deposit ID (pk) is required.'}, status=status.HTTP_400_BAD_REQUEST)

        deposit = get_object_or_404(MemberDeposit, pk=pk, member__mess=mess)
        serializer = MemberDepositCreateGetSerializer(deposit, data=request.data, partial=True)
        if serializer.is_valid():
            if 'member' in serializer.validated_data:
                new_member = serializer.validated_data['member']
                if new_member.mess_id != mess.id:
                    return Response({'error': 'Selected member does not belong to this mess.'}, status=status.HTTP_400_BAD_REQUEST)

            serializer.save()
            notify_mess(mess, request.user, 'deposit_updated', {
                'deposit_id': deposit.id,
                'changed_fields': list(request.data.keys()),
                'by': request.user.email,
            })
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        tags=[TAG],
        summary="Delete a member deposit",
        responses={
            204: None,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
    )
    def delete(self, request, mess_id=None, pk=None):
        mess_id = mess_id or request.query_params.get('mess_id')
        if not mess_id:
            return Response({'error': 'mess_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        mess = get_object_or_404(Mess, pk=mess_id)
        pk = pk or request.query_params.get('id')
        if not pk:
            return Response({'error': 'Deposit ID (pk) is required.'}, status=status.HTTP_400_BAD_REQUEST)

        deposit = get_object_or_404(MemberDeposit, pk=pk, member__mess=mess)
        notify_mess(mess, request.user, 'deposit_deleted', {
            'deposit_id': deposit.id,
            'amount': str(deposit.amount),
            'section': deposit.section,
            'by': request.user.email,
        })
        deposit.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# =====================================================================
# 3. Mess Bazar Views
# =====================================================================

class MessBazarViewSet(APIView):
    permission_classes = [IsAuthenticated, IsMessMember]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        tags=[TAG],
        responses={
            200: MessBazarSerializer(many=True),
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
    )
    def get(self, request, mess_id=None):
        mess_id = mess_id or request.query_params.get('mess_id')
        if not mess_id:
            return Response({'error': 'mess_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        bazar_items = MessBazar.objects.filter(mess_id=mess_id).order_by('-created_at')
        serializer = MessBazarSerializer(bazar_items, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=[TAG],
        request={"multipart/form-data": MessBazarSerializer},
        responses={
            201: MessBazarSerializer,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
    )
    def post(self, request, mess_id=None):
        mess_id = mess_id or request.query_params.get('mess_id')
        if not mess_id:
            return Response({'error': 'mess_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        mess = get_object_or_404(Mess, pk=mess_id)
        serializer = MessBazarSerializer(data=request.data)
        if serializer.is_valid():
            member = serializer.validated_data.get('member')
            if member and member.mess_id != mess.id:
                return Response({'error': 'Selected member does not belong to this mess.'}, status=status.HTTP_400_BAD_REQUEST)
            bazar = serializer.save(mess=mess)
            notify_mess(mess, request.user, 'bazar_added', {
                'bazar_id': bazar.id,
                'product_name': bazar.product_name,
                'product_price': str(bazar.product_price),
                'by': request.user.email,
            })
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UpdateMessBazarView(APIView):
    """Dedicated view for PATCH/DELETE - updates or deletes an existing MessBazar item."""
    permission_classes = [IsAuthenticated, IsMessMember]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _get_bazar(self, request, mess_id, pk):
        """Shared lookup + ownership check. Returns (mess, bazar) or raises."""
        mess_id = mess_id or request.query_params.get('mess_id')
        if not mess_id:
            return None, None, Response({'error': 'mess_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        mess = get_object_or_404(Mess, pk=mess_id)
        pk = pk or request.query_params.get('id') or (
            request.data.get('id') if hasattr(request, 'data') and isinstance(request.data, dict) else None
        )
        if not pk:
            return None, None, Response({'error': 'Bazar ID (pk) is required.'}, status=status.HTTP_400_BAD_REQUEST)

        bazar = get_object_or_404(MessBazar, pk=pk, mess=mess)
        is_manager = Mess_Members.objects.filter(member=request.user, mess=mess, is_manager=True).exists()
        if not is_manager and bazar.member.member != request.user:
            return None, None, Response({'error': 'You do not have permission to edit this bazar item.'}, status=status.HTTP_403_FORBIDDEN)

        return mess, bazar, None

    @extend_schema(
        tags=[TAG],
        summary="Partially update a mess bazar item",
        request={"multipart/form-data": MessBazarSerializer},
        responses={
            200: MessBazarSerializer,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
    )
    def patch(self, request, mess_id=None, pk=None):
        mess, bazar, err = self._get_bazar(request, mess_id, pk)
        if err:
            return err

        serializer = MessBazarSerializer(bazar, data=request.data, partial=True)
        if serializer.is_valid():
            if 'member' in serializer.validated_data:
                if serializer.validated_data['member'].mess_id != mess.id:
                    return Response({'error': 'Selected member does not belong to this mess.'}, status=status.HTTP_400_BAD_REQUEST)
            serializer.save()
            notify_mess(mess, request.user, 'bazar_updated', {
                'bazar_id': bazar.id,
                'product_name': bazar.product_name,
                'changed_fields': list(request.data.keys()),
                'by': request.user.email,
            })
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        tags=[TAG],
        summary="Delete a mess bazar item",
        responses={
            204: None,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
    )
    def delete(self, request, mess_id=None, pk=None):
        mess, bazar, err = self._get_bazar(request, mess_id, pk)
        if err:
            return err

        notify_mess(mess, request.user, 'bazar_deleted', {
            'bazar_id': bazar.id,
            'product_name': bazar.product_name,
            'product_price': str(bazar.product_price),
            'by': request.user.email,
        })
        bazar.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# =====================================================================
# 4. Mess Utilities Views
# =====================================================================

class MessUtilitiesViewSet(APIView):
    permission_classes = [IsAuthenticated, IsMessMember]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        tags=[TAG],
        responses={
            200: MessUtilitiesSerializer(many=True),
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
    )
    def get(self, request, mess_id=None):
        mess_id = mess_id or request.query_params.get('mess_id')
        if not mess_id:
            return Response({'error': 'mess_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        utilities = MessUtilities.objects.filter(mess_id=mess_id).order_by('-utility_date')
        serializer = MessUtilitiesSerializer(utilities, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=[TAG],
        request=MessUtilitiesSerializer,
        responses={
            201: MessUtilitiesSerializer,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
    )
    def post(self, request, mess_id=None):
        mess_id = mess_id or request.query_params.get('mess_id')
        if not mess_id:
            return Response({'error': 'mess_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        mess = get_object_or_404(Mess, pk=mess_id)
        serializer = MessUtilitiesSerializer(data=request.data)
        if serializer.is_valid():
            utility = serializer.save(mess=mess)
            notify_mess(mess, request.user, 'utility_added', {
                'utility_id': utility.id,
                'utility_name': utility.utility_name,
                'utility_cost': str(utility.utility_cost),
                'by': request.user.email,
            })
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UpdateMessUtilitiesView(APIView):
    permission_classes = [IsAuthenticated, IsMessMember]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _get_utility(self, request, mess_id, pk):
        mess_id = mess_id or request.query_params.get('mess_id')
        if not mess_id:
            return None, None, Response({'error': 'mess_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        mess = get_object_or_404(Mess, pk=mess_id)
        pk = pk or request.query_params.get('id') or (
            request.data.get('id') if hasattr(request, 'data') and isinstance(request.data, dict) else None
        )
        if not pk:
            return None, None, Response({'error': 'Utilities ID (pk) is required.'}, status=status.HTTP_400_BAD_REQUEST)

        utility = get_object_or_404(MessUtilities, pk=pk, mess=mess)
        is_manager = Mess_Members.objects.filter(member=request.user, mess=mess, is_manager=True).exists()
        if not is_manager:
            return None, None, Response({'error': 'You do not have permission to edit this utility item.'}, status=status.HTTP_403_FORBIDDEN)

        return mess, utility, None

    @extend_schema(
        tags=[TAG],
        summary="Partially update a mess utilities item",
        request=MessUtilitiesSerializer,
        responses={
            200: MessUtilitiesSerializer,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
    )
    def patch(self, request, mess_id=None, pk=None):
        mess, utility, err = self._get_utility(request, mess_id, pk)
        if err:
            return err

        serializer = MessUtilitiesSerializer(utility, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            notify_mess(mess, request.user, 'utility_updated', {
                'utility_id': utility.id,
                'utility_name': utility.utility_name,
                'changed_fields': list(request.data.keys()),
                'by': request.user.email,
            })
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        tags=[TAG],
        summary="Delete a mess utilities item",
        responses={
            204: None,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
    )
    def delete(self, request, mess_id=None, pk=None):
        mess, utility, err = self._get_utility(request, mess_id, pk)
        if err:
            return err

        notify_mess(mess, request.user, 'utility_deleted', {
            'utility_id': utility.id,
            'utility_name': utility.utility_name,
            'utility_cost': str(utility.utility_cost),
            'by': request.user.email,
        })
        utility.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# =====================================================================
# 5. Cycle Financial Summary
# =====================================================================

class MessCycleFinancialSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsMessMember]

    @extend_schema(
        tags=[TAG],
        parameters=[
            OpenApiParameter(name='mess_id', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, description='ID of the mess'),
            OpenApiParameter(name='cycle_id', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, description='ID of the mess cycle'),
        ],
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
    )
    def get(self, request, mess_id=None, cycle_id=None):
        mess_id = mess_id or request.query_params.get('mess_id')
        cycle_id = cycle_id or request.query_params.get('cycle_id')

        if not mess_id or not cycle_id:
            return Response({'error': 'Both mess_id and cycle_id are required.'}, status=status.HTTP_400_BAD_REQUEST)

        mess = get_object_or_404(Mess, pk=mess_id)
        cycle = get_object_or_404(MessCycle, pk=cycle_id, mess=mess)

        meals = cycle_meal_summary(mess, cycle)
        fin   = cycle_financial_summary(mess, cycle, total_meals_eaten=meals['overall_eaten'])

        return Response({**fin, 'meal_summary': meals}, status=status.HTTP_200_OK)

from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView
from Mess_Management.models import Mess, Mess_Members
from User_Authentication.models import UserModel
from .models import MessCycle, MemberDeposit, MessBazar
from .permission import IsMessCycleActive
from .services import get_conflicting_cycles, validate_cycle_conflict, create_mess_cycle
from .views import (
    UpdateMessCycleView,
    UpdateMemberDepositView,
    UpdateMessBazarView,
)


class DummyView(APIView):
    permission_classes = [IsMessCycleActive]

    def get(self, request, *args, **kwargs):
        return None


class MessCycleServiceAndPermissionTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.permission = IsMessCycleActive()
        self.user = UserModel.objects.create_user(
            email='user@example.com',
            name='Test User',
            password='password123',
            is_active=True
        )
        self.mess = Mess.objects.create(
            name='Test Mess',
            mess_address='123 Test St',
            capacity=10,
            contact_number='01700000000'
        )
        self.member = Mess_Members.objects.create(
            member=self.user,
            mess=self.mess,
            is_manager=True
        )

    def test_active_cycle_returns_true(self):
        now = timezone.now()
        cycle = MessCycle.objects.create(
            mess=self.mess,
            name='Current Active Cycle',
            start_date=now - timedelta(days=5),
            end_date=now + timedelta(days=25)
        )
        self.assertTrue(cycle.is_active)
        self.assertFalse(cycle.is_over)

        request = self.factory.get('/')
        request.user = self.user
        view = DummyView()
        view.kwargs = {'mess_id': self.mess.id}

        self.assertTrue(self.permission.has_permission(request, view))

    def test_cycle_conflict_detection(self):
        now = timezone.now()
        # Existing cycle: Day 1 to Day 30
        existing = MessCycle.objects.create(
            mess=self.mess,
            name='November Cycle',
            start_date=now,
            end_date=now + timedelta(days=30)
        )

        # 1. Exact overlapping dates -> should conflict
        conflicts = get_conflicting_cycles(self.mess, now, now + timedelta(days=30))
        self.assertTrue(conflicts.exists())

        # 2. Overlapping at the start (Day -5 to Day 10) -> should conflict
        with self.assertRaises(ValidationError):
            validate_cycle_conflict(self.mess, now - timedelta(days=5), now + timedelta(days=10))

        # 3. Overlapping inside (Day 5 to Day 15) -> should conflict
        with self.assertRaises(ValidationError):
            create_mess_cycle(self.mess, 'Conflicting Sub-cycle', now + timedelta(days=5), now + timedelta(days=15))

        # 4. Overlapping at the end (Day 25 to Day 40) -> should conflict
        with self.assertRaises(ValidationError):
            validate_cycle_conflict(self.mess, now + timedelta(days=25), now + timedelta(days=40))

        # 5. Non-overlapping future cycle (Day 35 to Day 65) -> should succeed
        future_cycle = create_mess_cycle(
            self.mess,
            'December Cycle',
            now + timedelta(days=35),
            now + timedelta(days=65)
        )
        self.assertIsNotNone(future_cycle.id)

        # 6. End date before start date -> should raise ValidationError
        with self.assertRaises(ValidationError):
            validate_cycle_conflict(self.mess, now + timedelta(days=10), now + timedelta(days=5))

    def test_patch_cycle_view(self):
        now = timezone.now()
        cycle = MessCycle.objects.create(
            mess=self.mess,
            name='Original Cycle',
            start_date=now,
            end_date=now + timedelta(days=30)
        )

        view = UpdateMessCycleView.as_view()
        request = self.factory.patch(
            f'/{self.mess.id}/mess-cycle/{cycle.id}/',
            data={'name': 'Updated Cycle Name'},
            format='json'
        )
        request.user = self.user
        response = view(request, mess_id=self.mess.id, pk=cycle.id)

        self.assertEqual(response.status_code, 200)
        cycle.refresh_from_db()
        self.assertEqual(cycle.name, 'Updated Cycle Name')

    def test_patch_deposit_view(self):
        deposit = MemberDeposit.objects.create(
            member=self.member,
            add_by=self.member,
            amount=Decimal('500.00'),
            section='Bazar'
        )

        view = UpdateMemberDepositView.as_view()
        request = self.factory.patch(
            f'/{self.mess.id}/member-deposit/{deposit.id}/',
            data={'amount': '750.00', 'section': 'Utilities'},
            format='json'
        )
        request.user = self.user
        response = view(request, mess_id=self.mess.id, pk=deposit.id)

        self.assertEqual(response.status_code, 200)
        deposit.refresh_from_db()
        self.assertEqual(deposit.amount, Decimal('750.00'))
        self.assertEqual(deposit.section, 'Utilities')

    def test_patch_bazar_view(self):
        bazar = MessBazar.objects.create(
            mess=self.mess,
            member=self.member,
            product_name='Rice',
            product_quantity='5kg',
            product_price=Decimal('350.00')
        )

        view = UpdateMessBazarView.as_view()
        request = self.factory.patch(
            f'/{self.mess.id}/mess-bazar/{bazar.id}/',
            data={'product_name': 'Basmati Rice', 'product_price': '400.00'},
            format='json'
        )
        request.user = self.user
        response = view(request, mess_id=self.mess.id, pk=bazar.id)

        self.assertEqual(response.status_code, 200)
        bazar.refresh_from_db()
        self.assertEqual(bazar.product_name, 'Basmati Rice')
        self.assertEqual(bazar.product_price, Decimal('400.00'))

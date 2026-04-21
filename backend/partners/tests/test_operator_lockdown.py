"""
Tests for the Operator role lockdown on Partners / Contacts / Tasks APIs.

Operators are restricted to a narrow set of mutations:
  - assign card only to themselves
  - toggle whatsapp_added freely
  - fill empty Profile Info fields once
  - change status / control_date / notes only after they added at least one
    Activity record on the card
  - add new Activity records and Tasks
  - edit/delete only their own Activity records and Tasks
"""
from datetime import date, timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from contacts.models import Contact
from partners.models import Partner
from tasks.models import Task


class OperatorPartnerLockdownTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username='admin1', password='pw', role='admin', is_staff=True
        )
        cls.operator = User.objects.create_user(
            username='op1', password='pw', role='operator'
        )
        cls.other_op = User.objects.create_user(
            username='op2', password='pw', role='operator'
        )

    def setUp(self):
        self.client.force_authenticate(self.operator)
        self.partner = Partner.objects.create(
            name='Acme', stage=Partner.STAGE_NEW,
            assigned_to=self.other_op,
        )

    def _patch(self, data):
        return self.client.patch(f'/api/partners/{self.partner.pk}/', data, format='json')

    # ── creation / deletion ────────────────────────────────────────────
    def test_operator_cannot_create_partner(self):
        res = self.client.post('/api/partners/', {'name': 'New'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_operator_cannot_change_stage(self):
        res = self.client.patch(
            f'/api/partners/{self.partner.pk}/stage/',
            {'stage': Partner.STAGE_TRAINED}, format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_operator_cannot_patch_arbitrary_field(self):
        res = self._patch({'name': 'Renamed'})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # ── assignment ────────────────────────────────────────────────────
    def test_operator_can_assign_to_self(self):
        res = self._patch({'assigned_to': self.operator.id})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.partner.refresh_from_db()
        self.assertEqual(self.partner.assigned_to_id, self.operator.id)

    def test_operator_cannot_assign_to_someone_else(self):
        res = self._patch({'assigned_to': self.other_op.id})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # ── whatsapp ──────────────────────────────────────────────────────
    def test_operator_can_toggle_whatsapp_anytime(self):
        res = self._patch({'whatsapp_added': True})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.partner.refresh_from_db()
        self.assertTrue(self.partner.whatsapp_added)

    # ── profile-once ──────────────────────────────────────────────────
    def test_operator_can_fill_empty_profile_field(self):
        res = self._patch({'gender': 'male'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.partner.refresh_from_db()
        self.assertEqual(self.partner.gender, 'male')

    def test_operator_cannot_overwrite_filled_profile_field(self):
        self.partner.gender = 'male'
        self.partner.save()
        res = self._patch({'gender': 'female'})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_operator_can_fill_zero_experience_once_then_locked(self):
        # 0 is a real filled value; subsequent change should be denied
        res = self._patch({'experience_years': 0})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        res = self._patch({'experience_years': 5})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # ── activity-gated fields ─────────────────────────────────────────
    def test_status_change_blocked_without_own_activity(self):
        res = self._patch({'status': Partner.STATUS_IN_SUPPORT})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_control_date_change_blocked_without_own_activity(self):
        res = self._patch({'control_date': str(date.today() + timedelta(days=3))})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_notes_change_blocked_without_own_activity(self):
        res = self._patch({'notes': 'hi'})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_others_activity_does_not_unlock_operator(self):
        # Activity by another operator should NOT unlock current operator's gates
        Contact.objects.create(
            partner=self.partner, date=timezone.now(), created_by=self.other_op,
        )
        res = self._patch({'notes': 'hi'})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_status_change_allowed_after_own_activity(self):
        Contact.objects.create(
            partner=self.partner, date=timezone.now(), created_by=self.operator,
        )
        res = self._patch({'status': Partner.STATUS_IN_SUPPORT})
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_notes_and_control_date_allowed_after_own_activity(self):
        Contact.objects.create(
            partner=self.partner, date=timezone.now(), created_by=self.operator,
        )
        res = self._patch({
            'notes': 'follow-up',
            'control_date': str(date.today() + timedelta(days=2)),
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)


class OperatorContactLockdownTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.operator = User.objects.create_user(
            username='op1', password='pw', role='operator'
        )
        cls.other_op = User.objects.create_user(
            username='op2', password='pw', role='operator'
        )

    def setUp(self):
        self.client.force_authenticate(self.operator)
        self.partner = Partner.objects.create(name='Acme')
        self.own = Contact.objects.create(
            partner=self.partner, date=timezone.now(), created_by=self.operator,
            notes='mine',
        )
        self.other = Contact.objects.create(
            partner=self.partner, date=timezone.now(), created_by=self.other_op,
            notes='theirs',
        )

    def test_operator_can_create_contact(self):
        res = self.client.post('/api/contacts/', {
            'partner': self.partner.id,
            'date': timezone.now().isoformat(),
            'notes': 'new',
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_operator_can_edit_own_contact(self):
        res = self.client.patch(f'/api/contacts/{self.own.id}/',
                                {'notes': 'updated'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_operator_cannot_edit_others_contact(self):
        res = self.client.patch(f'/api/contacts/{self.other.id}/',
                                {'notes': 'hijack'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_operator_cannot_delete_others_contact(self):
        res = self.client.delete(f'/api/contacts/{self.other.id}/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


class OperatorTaskLockdownTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.operator = User.objects.create_user(
            username='op1', password='pw', role='operator'
        )
        cls.other_op = User.objects.create_user(
            username='op2', password='pw', role='operator'
        )

    def setUp(self):
        self.client.force_authenticate(self.operator)
        self.partner = Partner.objects.create(name='Acme')
        self.own = Task.objects.create(
            partner=self.partner, title='mine',
            created_by=self.operator, assigned_to=self.operator,
        )
        self.assigned_to_me = Task.objects.create(
            partner=self.partner, title='assigned-to-me',
            created_by=self.other_op, assigned_to=self.operator,
        )
        self.foreign = Task.objects.create(
            partner=self.partner, title='foreign',
            created_by=self.other_op, assigned_to=self.other_op,
        )

    def test_operator_can_create_task(self):
        res = self.client.post('/api/tasks/', {
            'partner': self.partner.id,
            'title': 'new task',
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_operator_can_edit_own_task(self):
        res = self.client.patch(f'/api/tasks/{self.own.id}/',
                                {'title': 'renamed'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_operator_cannot_edit_foreign_task(self):
        res = self.client.patch(f'/api/tasks/{self.foreign.id}/',
                                {'title': 'hijack'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_operator_can_toggle_status_on_assigned_task(self):
        res = self.client.patch(f'/api/tasks/{self.assigned_to_me.id}/',
                                {'status': Task.STATUS_DONE}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_operator_cannot_change_other_fields_on_assigned_task(self):
        res = self.client.patch(f'/api/tasks/{self.assigned_to_me.id}/',
                                {'title': 'rename'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_operator_cannot_delete_foreign_task(self):
        res = self.client.delete(f'/api/tasks/{self.foreign.id}/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

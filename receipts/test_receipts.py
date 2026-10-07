from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .admin import ReceiptAdminForm
from .models import Receipt


@override_settings(PROMO_START_DATE=date(2026, 10, 1), PROMO_END_DATE=date(2026, 10, 31))
class ReceiptTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="buyer", password="test-password-123")
        cls.other = User.objects.create_user(username="other", password="test-password-123")

    def setUp(self):
        self.client.force_login(self.user)

    def data(self, **changes):
        values = {
            "fn": "123456",
            "fd": "321",
            "fp": "987",
            "purchase_at": "2026-10-15T12:00",
            "amount": "1000.00",
        }
        values.update(changes)
        return values

    def create(self, **changes):
        return self.client.post(reverse("receipts:create"), self.data(**changes))

    def test_amount_limit(self):
        response = self.create(amount="999.99")
        self.assertEqual(response.status_code, 400)
        self.assertIn("amount", response.json()["errors"])

        response = self.create(amount="1000")
        self.assertEqual(response.status_code, 201)
        receipt = Receipt.objects.get()
        self.assertEqual(receipt.amount, Decimal("1000"))
        self.assertEqual(receipt.status, Receipt.Status.PENDING)
        self.assertEqual(receipt.user, self.user)

    def test_promo_dates(self):
        for value in ("2026-09-30T23:59", "2026-11-01T00:00"):
            with self.subTest(value=value):
                response = self.create(purchase_at=value)
                self.assertEqual(response.status_code, 400)
                self.assertIn("purchase_at", response.json()["errors"])

        for index, value in enumerate(("2026-10-01T00:00", "2026-10-31T23:59")):
            with self.subTest(value=value):
                response = self.create(fn=f"12345{index}", purchase_at=value)
                self.assertEqual(response.status_code, 201)

    def test_receipt_numbers_are_digits(self):
        for field in ("fn", "fd", "fp"):
            with self.subTest(field=field):
                response = self.create(**{field: "12a"})
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json()["errors"])

    def test_duplicate_receipt_is_rejected(self):
        self.assertEqual(self.create().status_code, 201)
        response = self.create()
        self.assertEqual(response.status_code, 400)
        self.assertIn("__all__", response.json()["errors"])
        self.assertEqual(Receipt.objects.count(), 1)

    def test_user_cannot_set_moderation_fields(self):
        response = self.create(status="accepted", rejection_reason="changed", user=self.other.pk)
        self.assertEqual(response.status_code, 201)
        receipt = Receipt.objects.get()
        self.assertEqual(receipt.status, Receipt.Status.PENDING)
        self.assertEqual(receipt.rejection_reason, "")
        self.assertEqual(receipt.user, self.user)

    def test_list_shows_only_own_receipts_and_paginates(self):
        for index in range(11):
            Receipt.objects.create(user=self.user, **self.receipt_values(fn=str(index)))
        Receipt.objects.create(user=self.other, **self.receipt_values(fn="999"))

        response = self.client.get(reverse("receipts:list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["page"]), 10)
        self.assertEqual(response.context["page"].paginator.count, 11)
        self.assertTrue(all(receipt.user == self.user for receipt in response.context["page"]))

        second_page = self.client.get(reverse("receipts:list"), {"page": 2})
        self.assertEqual(len(second_page.context["page"]), 1)

    def test_api_shows_only_own_receipts(self):
        own = Receipt.objects.create(user=self.user, **self.receipt_values(fn="888"))
        Receipt.objects.create(user=self.other, **self.receipt_values(fn="999"))

        response = self.client.get(reverse("receipts:api"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()], [own.pk])
        self.assertIn("На проверке", response.content.decode())

        response = self.client.get(reverse("receipts:api"), {"user": self.other.pk})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Неизвестные параметры запроса", response.content.decode())

    def test_api_is_read_only(self):
        strict_client = Client(enforce_csrf_checks=True)
        strict_client.force_login(self.user)
        for method in (self.client.post, self.client.put, self.client.patch, self.client.delete):
            with self.subTest(method=method.__name__):
                self.assertEqual(
                    getattr(strict_client, method.__name__)(reverse("receipts:api")).status_code,
                    405,
                )

    def test_login_is_required(self):
        self.client.logout()
        for name in ("receipts:list", "receipts:create", "receipts:api"):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 302)

    def test_rejected_receipt_needs_reason_in_admin(self):
        receipt = Receipt.objects.create(user=self.user, **self.receipt_values(fn="888"))
        data = {
            **self.data(fn="888"),
            "status": Receipt.Status.REJECTED,
            "rejection_reason": "",
            "user": self.user.pk,
        }
        form = ReceiptAdminForm(data=data, instance=receipt)
        self.assertFalse(form.is_valid())
        self.assertIn("rejection_reason", form.errors)

        data["rejection_reason"] = "Чек не подходит под условия акции."
        self.assertTrue(ReceiptAdminForm(data=data, instance=receipt).is_valid())

    @staticmethod
    def receipt_values(fn):
        return {
            "fn": fn,
            "fd": "321",
            "fp": "987",
            "purchase_at": timezone.now(),
            "amount": Decimal("1000.00"),
        }

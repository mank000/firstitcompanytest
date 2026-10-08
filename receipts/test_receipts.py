import csv
import io
import tempfile
from datetime import date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .admin import ReceiptAdminForm
from .models import Receipt
from .qr import receipt_qr_text


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
            "purchase_date": "2026-10-15",
            "purchase_time": "12:00",
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
        for value in ("2026-09-30", "2026-11-01"):
            with self.subTest(value=value):
                response = self.create(purchase_date=value)
                self.assertEqual(response.status_code, 400)
                self.assertIn("purchase_date", response.json()["errors"])

        for index, (day, hour) in enumerate((("2026-10-01", "00:00"), ("2026-10-31", "23:59"))):
            with self.subTest(day=day, hour=hour):
                response = self.create(fn=f"12345{index}", purchase_date=day, purchase_time=hour)
                self.assertEqual(response.status_code, 201)

    def test_receipt_numbers_are_digits(self):
        for field in ("fn", "fd", "fp"):
            with self.subTest(field=field):
                response = self.create(**{field: "12a"})
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json()["errors"])

    def test_purchase_date_and_time_stay_as_printed(self):
        response = self.create(purchase_date="2026-10-01", purchase_time="00:00")
        self.assertEqual(response.status_code, 201)
        receipt = Receipt.objects.get()
        self.assertEqual(receipt.purchase_date, date(2026, 10, 1))
        self.assertEqual(receipt.purchase_time, time(0, 0))

        page = self.client.get(reverse("receipts:list"))
        self.assertContains(page, "00:00 01.10.2026")
        api = self.client.get(reverse("receipts:api")).json()
        self.assertEqual(api[0]["purchase_date"], "2026-10-01")
        self.assertEqual(api[0]["purchase_time"], "00:00")

        response = self.create(fn="123457", purchase_date="2026-09-30", purchase_time="23:59")
        self.assertEqual(response.status_code, 400)
        self.assertIn("purchase_date", response.json()["errors"])

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
        self.assertContains(response, 'aria-current="page">1</span>')
        self.assertContains(response, 'aria-label="Страница 2"')

        second_page = self.client.get(reverse("receipts:list"), {"page": 2})
        self.assertEqual(len(second_page.context["page"]), 1)
        self.assertContains(second_page, 'aria-current="page">2</span>')

    def test_list_sorting_and_pagination(self):
        for index in range(12):
            receipt = Receipt.objects.create(
                user=self.user,
                status=Receipt.Status.ACCEPTED if index < 11 else Receipt.Status.REJECTED,
                **self.receipt_values(fn=str(index)),
            )
            receipt.purchase_date = date(2026, 10, 1 if index < 11 else 2)
            receipt.save(update_fields=["purchase_date"])
            registered_at = datetime(
                2026, 10, 8 if index < 11 else 9, tzinfo=ZoneInfo("Europe/Moscow")
            )
            Receipt.objects.filter(pk=receipt.pk).update(created_at=registered_at)
        Receipt.objects.create(user=self.other, **self.receipt_values(fn="999"))

        response = self.client.get(reverse("receipts:list"), {"sort": "amount_asc"})
        self.assertEqual(response.context["page"].paginator.count, 12)
        self.assertEqual(len(response.context["page"]), 10)
        self.assertContains(response, "page=2")
        self.assertContains(response, "sort=amount_asc")
        amounts = [receipt.amount for receipt in response.context["page"]]
        self.assertEqual(amounts, sorted(amounts))

        response = self.client.get(reverse("receipts:list"), {"sort": "amount_asc", "page": 2})
        self.assertEqual(len(response.context["page"]), 2)

        for sort, key, reverse_order in (
            ("purchase_desc", lambda receipt: (receipt.purchase_date, receipt.purchase_time), True),
            ("status_desc", lambda receipt: receipt.status == Receipt.Status.REJECTED, True),
            ("registered_asc", lambda receipt: receipt.created_at, False),
        ):
            with self.subTest(sort=sort):
                response = self.client.get(reverse("receipts:list"), {"sort": sort})
                receipts = list(response.context["page"].paginator.object_list)
                values = [key(receipt) for receipt in receipts]
                self.assertEqual(values, sorted(values, reverse=reverse_order))
                self.assertTrue(all(receipt.user == self.user for receipt in receipts))

    def test_qr_contains_receipt_data_and_is_private(self):
        receipt = Receipt.objects.create(user=self.user, **self.receipt_values(fn="888"))
        self.assertEqual(
            receipt_qr_text(receipt),
            "t=20261015T1200&s=1000.00&fn=888&i=321&fp=987",
        )
        url = reverse("receipts:qr", args=[receipt.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/svg+xml")
        self.assertIn(b"<svg", response.content)

        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)

        moderator = User.objects.create_user(username="staff", is_staff=True)
        moderator.user_permissions.add(Permission.objects.get(codename="change_receipt"))
        self.client.force_login(moderator)
        self.assertEqual(self.client.get(url).status_code, 200)

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

    def test_csv_contains_only_own_accepted_receipts(self):
        own = Receipt.objects.create(
            user=self.user, status=Receipt.Status.ACCEPTED, **self.receipt_values(fn="111")
        )
        Receipt.objects.create(user=self.user, **self.receipt_values(fn="222"))
        Receipt.objects.create(
            user=self.other, status=Receipt.Status.ACCEPTED, **self.receipt_values(fn="333")
        )
        response = self.client.get(reverse("receipts:export_csv"))
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], str(own.pk))

        moderator = User.objects.create_superuser(username="moderator", password="test-pass")
        self.client.force_login(moderator)
        response = self.client.get(reverse("admin:receipts_receipt_export_csv"))
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 3)
        self.assertIn("Пользователь", rows[0])

        user_page = self.client.get(reverse("admin:auth_user_change", args=[self.user.pk]))
        self.assertContains(user_page, "Скачать CSV")
        self.assertContains(user_page, "Доступ")
        self.assertNotContains(user_page, 'id="id_groups"')
        self.assertNotContains(user_page, 'id="id_user_permissions"')
        response = self.client.get(
            reverse("admin:receipts_receipt_export_user_csv", args=[self.user.pk])
        )
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], str(own.pk))

    def test_optional_photo_validation_and_private_access(self):
        def image_file(format_name, name):
            image = Image.new("RGB", (2, 2), "white")
            buffer = io.BytesIO()
            image.save(buffer, format=format_name)
            return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")

        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            response = self.create(photo=image_file("GIF", "check.gif"))
            self.assertEqual(response.status_code, 400)
            self.assertIn("photo", response.json()["errors"])

            photo = image_file("PNG", "check.png")
            oversized = SimpleUploadedFile(
                "large.png", photo.read() + b"\0" * (5 * 1024 * 1024), content_type="image/png"
            )
            response = self.create(photo=oversized)
            self.assertEqual(response.status_code, 400)
            self.assertIn("photo", response.json()["errors"])

            response = self.create(photo=image_file("PNG", "check.png"))
            self.assertEqual(response.status_code, 201)
            receipt = Receipt.objects.get()
            photo_url = reverse("receipts:photo", args=[receipt.pk])
            self.assertEqual(self.client.get(photo_url).status_code, 200)
            self.client.force_login(self.other)
            self.assertEqual(self.client.get(photo_url).status_code, 404)

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

    def test_admin_review_buttons(self):
        receipt = Receipt.objects.create(user=self.user, **self.receipt_values(fn="888"))
        reject_url = reverse("admin:receipts_receipt_review", args=[receipt.pk, "reject"])
        accept_url = reverse("admin:receipts_receipt_review", args=[receipt.pk, "accept"])

        self.assertEqual(self.client.get(reject_url).status_code, 302)
        moderator = User.objects.create_superuser(
            username="moderator", password="test-password-123"
        )
        self.client.force_login(moderator)

        changelist = self.client.get(reverse("admin:receipts_receipt_changelist"))
        self.assertContains(changelist, "QR-код")
        self.assertContains(changelist, "Принять")
        self.assertContains(changelist, "Отклонить")

        self.assertEqual(self.client.get(reject_url).status_code, 200)
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, Receipt.Status.PENDING)

        response = self.client.post(reject_url, {"reason": "  "})
        self.assertEqual(response.status_code, 200)
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, Receipt.Status.PENDING)

        response = self.client.post(reject_url, {"reason": "Неверные данные."})
        self.assertEqual(response.status_code, 302)
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, Receipt.Status.REJECTED)
        self.assertEqual(receipt.rejection_reason, "Неверные данные.")

        self.assertEqual(self.client.post(accept_url).status_code, 302)
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, Receipt.Status.ACCEPTED)
        self.assertEqual(receipt.rejection_reason, "")

    @staticmethod
    def receipt_values(fn):
        return {
            "fn": fn,
            "fd": "321",
            "fp": "987",
            "purchase_date": date(2026, 10, 15),
            "purchase_time": time(12, 0),
            "amount": Decimal("1000.00"),
        }

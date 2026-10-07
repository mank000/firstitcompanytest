import re
from decimal import Decimal

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Receipt


class ReceiptForm(forms.ModelForm):
    class Meta:
        model = Receipt
        fields = (
            "fn",
            "fd",
            "fp",
            "purchase_at",
            "amount",
        )
        widgets = {
            "purchase_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            )
        }

    def _clean_digits(self, field):
        value = self.cleaned_data[field]
        if not re.fullmatch(r"[0-9]+", value):
            raise ValidationError(f"{self.fields[field].label} должен содержать только цифры.")
        return value

    def clean_fn(self):
        return self._clean_digits("fn")

    def clean_fd(self):
        return self._clean_digits("fd")

    def clean_fp(self):
        return self._clean_digits("fp")

    def clean_amount(self):
        amount = self.cleaned_data["amount"]

        if amount < Decimal("1000.00"):
            raise ValidationError("Сумма чека должна быть не меньше 1000 руб.")

        return amount

    def clean_purchase_at(self):
        purchase_at = self.cleaned_data["purchase_at"]
        purchase_date = timezone.localtime(purchase_at).date()

        if not (
            settings.PROMO_START_DATE
            <= purchase_date
            <= settings.PROMO_END_DATE
        ):
            raise ValidationError("Дата покупки не входит в период акции.")

        return purchase_at

    def clean(self):
        cleaned_data = super().clean()

        fn = cleaned_data.get("fn")
        fd = cleaned_data.get("fd")
        fp = cleaned_data.get("fp")

        if fn and fd and fp:
            if Receipt.objects.filter(
                fn=fn,
                fd=fd,
                fp=fp,
            ).exists():
                raise ValidationError("Этот чек уже зарегистрирован.")

        return cleaned_data

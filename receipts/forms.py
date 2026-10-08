import re
from decimal import Decimal
from pathlib import Path

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from .models import Receipt


class ReceiptForm(forms.ModelForm):
    class Meta:
        model = Receipt
        fields = (
            "fn",
            "fd",
            "fp",
            "purchase_date",
            "purchase_time",
            "amount",
            "photo",
        )
        widgets = {
            "fn": forms.TextInput(attrs={"placeholder": "Введите ФН", "inputmode": "numeric"}),
            "fd": forms.TextInput(
                attrs={
                    "placeholder": "Введите номер чека (ФД)",
                    "inputmode": "numeric",
                }
            ),
            "fp": forms.TextInput(attrs={"placeholder": "Введите ФП", "inputmode": "numeric"}),
            "purchase_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "purchase_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "amount": forms.NumberInput(
                attrs={"placeholder": "0.00 руб", "min": "0", "step": "0.01"}
            ),
            "photo": forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png"}),
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

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if not photo:
            return photo
        if photo.size > 5 * 1024 * 1024:
            raise ValidationError("Размер фото не должен превышать 5 МБ.")
        if photo.image.format not in ("JPEG", "PNG"):
            raise ValidationError("Загрузите фото в формате JPG или PNG.")
        suffix = Path(photo.name).suffix.lower()
        allowed_suffixes = {"JPEG": (".jpg", ".jpeg"), "PNG": (".png",)}
        if suffix not in allowed_suffixes[photo.image.format]:
            raise ValidationError("Расширение файла не соответствует формату фото.")
        return photo

    def clean_purchase_date(self):
        purchase_date = self.cleaned_data["purchase_date"]
        if not (settings.PROMO_START_DATE <= purchase_date <= settings.PROMO_END_DATE):
            raise ValidationError("Дата покупки не входит в период акции.")

        return purchase_date

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

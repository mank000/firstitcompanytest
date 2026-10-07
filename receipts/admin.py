from django import forms
from django.contrib import admin

from .models import Receipt


class ReceiptAdminForm(forms.ModelForm):
    class Meta:
        model = Receipt
        fields = "__all__"

    def clean(self):
        data = super().clean()
        if data.get("status") == Receipt.Status.REJECTED:
            if not data.get("rejection_reason", "").strip():
                self.add_error("rejection_reason", "Укажите причину отказа.")
        else:
            data["rejection_reason"] = ""
        return data


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    form = ReceiptAdminForm
    list_display = (
        "fn",
        "fd",
        "fp",
        "amount",
        "purchase_at",
        "status",
        "user",
        "created_at",
    )

    list_filter = ("status",)
    search_fields = ("fn", "fd", "fp", "user__username")

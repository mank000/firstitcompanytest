from django.contrib import admin

from .models import Receipt


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = (
        "fn",
        "fd",
        "fp",
        "amount",
        "status",
        "user",
        "created_at",
    )

    list_filter = ("status",)
    search_fields = ("fn", "fd", "fp", "user__username")

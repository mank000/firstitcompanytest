from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from .models import Receipt
from .views import accepted_csv_response


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


class RejectionForm(forms.Form):
    reason = forms.CharField(
        label="Причина отказа",
        widget=forms.Textarea(attrs={"rows": 3}),
    )


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    change_list_template = "admin/receipts/receipt/change_list.html"

    class Media:
        css = {"all": ("receipts/admin.css",)}

    form = ReceiptAdminForm
    exclude = ("photo",)
    readonly_fields = ("photo_preview",)
    list_display = (
        "qr_preview",
        "receipt_details",
        "purchase_at",
        "amount",
        "status",
        "user",
        "review_actions",
    )
    list_display_links = ("receipt_details",)
    list_filter = ("status",)
    search_fields = ("fn", "fd", "fp", "user__username")
    list_select_related = ("user",)
    ordering = ("-created_at",)

    @admin.display(description="Фото чека")
    def photo_preview(self, obj):
        if not obj or not obj.photo:
            return "Фото не загружено"
        url = reverse("receipts:photo", args=[obj.pk])
        return format_html('<a href="{}" target="_blank" rel="noopener">Открыть фото</a>', url)

    @admin.display(description="QR-код")
    def qr_preview(self, obj):
        url = reverse("receipts:qr", args=[obj.pk])
        return format_html(
            '<a href="{}" target="_blank" rel="noopener" title="Открыть QR-код из данных чека">'
            '<img class="admin-receipt-qr" src="{}" alt="QR-код чека {}" loading="lazy"></a>',
            url,
            url,
            obj.pk,
        )

    @admin.display(description="Чек")
    def receipt_details(self, obj):
        return format_html("{}<br><small>ФД {} · ФП {}</small>", obj.fn, obj.fd, obj.fp)

    @admin.display(description="Покупка", ordering="purchase_date")
    def purchase_at(self, obj):
        return format_html(
            "{}<br>{}",
            obj.purchase_date.strftime("%d.%m.%Y"),
            obj.purchase_time.strftime("%H:%M"),
        )

    @admin.display(description="Решение")
    def review_actions(self, obj):
        accept_url = reverse("admin:receipts_receipt_review", args=[obj.pk, "accept"])
        reject_url = reverse("admin:receipts_receipt_review", args=[obj.pk, "reject"])
        return format_html(
            '<a class="button" href="{}">Принять</a> <a class="button" href="{}">Отклонить</a>',
            accept_url,
            reject_url,
        )

    def get_urls(self):
        urls = super().get_urls()
        export_url = path(
            "export/",
            self.admin_site.admin_view(self.export_csv),
            name="receipts_receipt_export_csv",
        )
        user_export_url = path(
            "export/user/<int:user_id>/",
            self.admin_site.admin_view(self.export_user_csv),
            name="receipts_receipt_export_user_csv",
        )
        review_url = path(
            "<int:receipt_id>/review/<str:decision>/",
            self.admin_site.admin_view(self.review_view),
            name="receipts_receipt_review",
        )
        return [export_url, user_export_url, review_url, *urls]

    def export_csv(self, request):
        if not self.has_view_permission(request):
            raise Http404
        receipts = (
            Receipt.objects.filter(status=Receipt.Status.ACCEPTED)
            .select_related("user")
            .order_by("-created_at", "-pk")
        )
        return accepted_csv_response(receipts, include_user=True)

    def export_user_csv(self, request, user_id):
        if not self.has_view_permission(request):
            raise Http404
        user = get_object_or_404(User, pk=user_id)
        receipts = Receipt.objects.filter(user=user, status=Receipt.Status.ACCEPTED).order_by(
            "-created_at", "-pk"
        )
        return accepted_csv_response(receipts)

    def review_view(self, request, receipt_id, decision):
        if request.method not in ("GET", "POST"):
            return HttpResponseNotAllowed(["GET", "POST"])
        if decision not in ("accept", "reject"):
            raise Http404

        receipt = self.get_object(request, str(receipt_id))
        if receipt is None or not self.has_change_permission(request, receipt):
            raise Http404

        form = (
            RejectionForm(request.POST if request.method == "POST" else None)
            if decision == "reject"
            else None
        )
        if request.method == "POST" and (form is None or form.is_valid()):
            receipt.status = (
                Receipt.Status.ACCEPTED if decision == "accept" else Receipt.Status.REJECTED
            )
            receipt.rejection_reason = form.cleaned_data["reason"].strip() if form else ""
            receipt.save(update_fields=["status", "rejection_reason"])
            self.message_user(request, "Статус чека обновлён.")
            return redirect("admin:receipts_receipt_changelist")

        title = "Принять чек" if decision == "accept" else "Отклонить чек"
        context = {
            **self.admin_site.each_context(request),
            "title": title,
            "opts": self.model._meta,
            "original": receipt,
            "form": form,
            "action_label": title,
            "changelist_url": reverse("admin:receipts_receipt_changelist"),
        }
        return render(request, "admin/receipts/receipt/review.html", context)


admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    readonly_fields = (*BaseUserAdmin.readonly_fields, "accepted_receipts_csv")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Личные данные", {"fields": ("first_name", "last_name", "email")}),
        ("Доступ", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Чеки", {"fields": ("accepted_receipts_csv",)}),
    )

    @admin.display(description="Принятые чеки")
    def accepted_receipts_csv(self, obj):
        if not obj or not obj.pk:
            return "Сохраните пользователя, чтобы скачать чеки"
        url = reverse("admin:receipts_receipt_export_user_csv", args=[obj.pk])
        return format_html('<a href="{}">Скачать CSV</a>', url)

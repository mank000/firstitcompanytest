import csv

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Case, IntegerField, When
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from .forms import ReceiptForm
from .models import Receipt
from .qr import receipt_qr_svg


@login_required
@require_http_methods(["GET", "POST"])
def create_receipt(request):
    if request.method == "POST":
        form = ReceiptForm(request.POST, request.FILES)

        if form.is_valid():
            receipt = form.save(commit=False)
            receipt.user = request.user
            receipt.status = Receipt.Status.PENDING
            try:
                with transaction.atomic():
                    receipt.save()
            except IntegrityError:
                form.add_error(None, "Этот чек уже зарегистрирован.")
            else:
                return JsonResponse(
                    {"success": True, "message": "Чек успешно зарегистрирован."},
                    status=201,
                    json_dumps_params={"ensure_ascii": False},
                )

        return JsonResponse(
            {
                "success": False,
                "errors": form.errors.get_json_data(),
            },
            status=400,
            json_dumps_params={"ensure_ascii": False},
        )

    form = ReceiptForm()

    return render(
        request,
        "receipts/create.html",
        {
            "form": form,
            "promo_start": settings.PROMO_START_DATE,
            "promo_end": settings.PROMO_END_DATE,
        },
    )


@login_required
@require_GET
def receipt_list(request):
    sort_fields = {
        "purchase_asc": ("purchase_date", "purchase_time", "pk"),
        "purchase_desc": ("-purchase_date", "-purchase_time", "-pk"),
        "status_asc": ("status_order", "-created_at", "-pk"),
        "status_desc": ("-status_order", "-created_at", "-pk"),
        "amount_asc": ("amount", "-created_at", "-pk"),
        "amount_desc": ("-amount", "-created_at", "-pk"),
        "registered_asc": ("created_at", "pk"),
        "registered_desc": ("-created_at", "-pk"),
    }
    sort = request.GET.get("sort", "registered_desc")
    if sort not in sort_fields:
        sort = "registered_desc"

    receipts = Receipt.objects.filter(user=request.user)
    if sort.startswith("status_"):
        receipts = receipts.annotate(
            status_order=Case(
                When(status=Receipt.Status.PENDING, then=0),
                When(status=Receipt.Status.ACCEPTED, then=1),
                When(status=Receipt.Status.REJECTED, then=2),
                output_field=IntegerField(),
            )
        )
    receipts = receipts.order_by(*sort_fields[sort])
    sort_headers = {}
    for name in ("purchase", "status", "amount", "registered"):
        ascending = f"{name}_asc"
        descending = f"{name}_desc"
        sort_headers[name] = {
            "url": f"?sort={descending if sort == ascending else ascending}",
            "active": sort in (ascending, descending),
            "arrow": "↑" if sort == ascending else "↓" if sort == descending else "↕",
        }

    paginator = Paginator(receipts, 10)

    page_number = request.GET.get("page")
    page = paginator.get_page(page_number)
    page_numbers = paginator.get_elided_page_range(page.number, on_each_side=3, on_ends=1)
    page_prefix = f"?sort={sort}&" if sort != "registered_desc" else "?"

    return render(
        request,
        "receipts/list.html",
        {
            "page": page,
            "page_numbers": page_numbers,
            "ellipsis": paginator.ELLIPSIS,
            "sort_headers": sort_headers,
            "page_prefix": page_prefix,
        },
    )


@login_required
@require_GET
def rules(request):
    return render(
        request,
        "receipts/rules.html",
        {
            "promo_start": settings.PROMO_START_DATE,
            "promo_end": settings.PROMO_END_DATE,
        },
    )


@login_required
@require_GET
def profile(request):
    return render(request, "receipts/profile.html")


@login_required
@require_GET
def receipt_qr(request, receipt_id):
    if request.user.has_perm("receipts.view_receipt") or request.user.has_perm(
        "receipts.change_receipt"
    ):
        receipt = get_object_or_404(Receipt, pk=receipt_id)
    else:
        receipt = get_object_or_404(Receipt, pk=receipt_id, user=request.user)
    response = HttpResponse(receipt_qr_svg(receipt), content_type="image/svg+xml")
    response["Cache-Control"] = "private, max-age=3600"
    return response


@login_required
@require_GET
def receipt_photo(request, receipt_id):
    if request.user.has_perm("receipts.view_receipt") or request.user.has_perm(
        "receipts.change_receipt"
    ):
        receipt = get_object_or_404(Receipt, pk=receipt_id)
    else:
        receipt = get_object_or_404(Receipt, pk=receipt_id, user=request.user)
    if not receipt.photo:
        raise Http404
    content_type = "image/png" if receipt.photo.name.lower().endswith(".png") else "image/jpeg"
    response = FileResponse(receipt.photo.open("rb"), content_type=content_type)
    response["Cache-Control"] = "private, no-store"
    return response


def accepted_csv_response(receipts, include_user=False):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="accepted_receipts.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    columns = ["ID", "ФН", "ФД", "ФП", "Дата покупки", "Время покупки", "Сумма", "Дата регистрации"]
    if include_user:
        columns.append("Пользователь")
    writer.writerow(columns)
    for receipt in receipts:
        row = [
            receipt.pk,
            receipt.fn,
            receipt.fd,
            receipt.fp,
            receipt.purchase_date.strftime("%d.%m.%Y"),
            receipt.purchase_time.strftime("%H:%M"),
            str(receipt.amount),
            timezone.localtime(receipt.created_at).strftime("%d.%m.%Y %H:%M"),
        ]
        if include_user:
            username = receipt.user.username
            row.append(
                f"'{username}" if username.lstrip().startswith(("=", "+", "-", "@")) else username
            )
        writer.writerow(row)
    return response


@login_required
@require_GET
def export_csv(request):
    receipts = Receipt.objects.filter(user=request.user, status=Receipt.Status.ACCEPTED).order_by(
        "-created_at", "-pk"
    )
    return accepted_csv_response(receipts)


def register(request):
    if request.user.is_authenticated:
        return redirect("receipts:list")

    if request.method == "POST":
        form = UserCreationForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)

            return redirect("receipts:list")

    else:
        form = UserCreationForm()

    return render(
        request,
        "registration/register.html",
        {"form": form},
    )


@csrf_exempt
@require_GET
@login_required
def receipt_api(request):
    if request.GET:
        return JsonResponse(
            {"error": "Неизвестные параметры запроса."},
            status=400,
            json_dumps_params={"ensure_ascii": False},
        )

    receipts = Receipt.objects.filter(user=request.user).order_by("-created_at", "-pk")

    data = [
        {
            "id": receipt.pk,
            "fn": receipt.fn,
            "fd": receipt.fd,
            "fp": receipt.fp,
            "purchase_date": receipt.purchase_date.isoformat(),
            "purchase_time": receipt.purchase_time.isoformat(timespec="minutes"),
            "amount": str(receipt.amount),
            "status": receipt.status,
            "status_display": Receipt.Status(receipt.status).label,
            "rejection_reason": receipt.rejection_reason,
            "created_at": receipt.created_at.isoformat(),
        }
        for receipt in receipts
    ]

    return JsonResponse(data, safe=False, json_dumps_params={"ensure_ascii": False})

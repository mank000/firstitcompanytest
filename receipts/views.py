from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from .forms import ReceiptForm
from .models import Receipt


@login_required
@require_http_methods(["GET", "POST"])
def create_receipt(request):
    if request.method == "POST":
        form = ReceiptForm(request.POST)

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
    receipts = Receipt.objects.filter(user=request.user).order_by(
        "-created_at", "-pk"
    )

    paginator = Paginator(receipts, 10)

    page_number = request.GET.get("page")
    page = paginator.get_page(page_number)

    return render(
        request,
        "receipts/list.html",
        {"page": page},
    )


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

    receipts = Receipt.objects.filter(user=request.user).order_by(
        "-created_at", "-pk"
    )

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

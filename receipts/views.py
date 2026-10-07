from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from .forms import ReceiptForm
from .models import Receipt


@login_required
def create_receipt(request):
    if request.method == "POST":
        form = ReceiptForm(request.POST)

        if form.is_valid():
            receipt = form.save(commit=False)

            receipt.user = request.user
            receipt.status = Receipt.Status.PENDING

            receipt.save()

            return redirect("receipts:list")

    else:
        form = ReceiptForm()

    return render(
        request,
        "receipts/create.html",
        {"form": form},
    )


@login_required
@require_GET
def receipt_list(request):
    user_id = request.GET.get("user")

    if user_id is not None and str(request.user.pk) != user_id:
        return JsonResponse(
            {"error": "Нельзя просматривать чеки другого пользователя."},
            status=403,
        )
    receipts = Receipt.objects.filter(user=request.user).order_by(
        "-created_at"
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


@login_required
def receipt_api(request):
    receipts = Receipt.objects.filter(user=request.user).order_by(
        "-created_at"
    )

    data = [
        {
            "id": receipt.pk,
            "fn": receipt.fn,
            "fd": receipt.fd,
            "fp": receipt.fp,
            "purchase_at": receipt.purchase_at.isoformat(),
            "amount": str(receipt.amount),
            "status": receipt.status,
            "status_display": Receipt.Status(receipt.status).label,
            "rejection_reason": receipt.rejection_reason,
            "created_at": receipt.created_at.isoformat(),
        }
        for receipt in receipts
    ]

    return JsonResponse(data, safe=False)

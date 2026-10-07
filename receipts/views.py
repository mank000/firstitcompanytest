from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.paginator import Paginator
from django.shortcuts import redirect, render

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
def receipt_list(request):
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

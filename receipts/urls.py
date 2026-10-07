from django.urls import path

from . import views

app_name = "receipts"

urlpatterns = [
    path("", views.receipt_list, name="list"),
    path("new/", views.create_receipt, name="create"),
    path("register/", views.register, name="register"),
]

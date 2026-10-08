from django.urls import path

from . import views

app_name = "receipts"

urlpatterns = [
    path("", views.receipt_list, name="list"),
    path("new/", views.create_receipt, name="create"),
    path("receipts/<int:receipt_id>/qr/", views.receipt_qr, name="qr"),
    path("register/", views.register, name="register"),
    path("api/receipts/", views.receipt_api, name="api"),
]

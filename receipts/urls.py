from django.urls import path

from . import views

app_name = "receipts"

urlpatterns = [
    path("", views.receipt_list, name="list"),
    path("new/", views.create_receipt, name="create"),
    path("rules/", views.rules, name="rules"),
    path("profile/", views.profile, name="profile"),
    path("receipts/<int:receipt_id>/qr/", views.receipt_qr, name="qr"),
    path("receipts/<int:receipt_id>/photo/", views.receipt_photo, name="photo"),
    path("export/", views.export_csv, name="export_csv"),
    path("register/", views.register, name="register"),
    path("api/receipts/", views.receipt_api, name="api"),
]

from django.conf import settings
from django.db import models


class Receipt(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "На проверке"
        ACCEPTED = "accepted", "Принят"
        REJECTED = "rejected", "Отклонен"

    fn = models.CharField("ФН", max_length=32)
    fd = models.CharField("ФД", max_length=32)
    fp = models.CharField("ФП", max_length=32)

    purchase_date = models.DateField("Дата покупки")
    purchase_time = models.TimeField("Время покупки")
    amount = models.DecimalField("Сумма", max_digits=10, decimal_places=2)

    status = models.CharField(
        "Статус",
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )

    rejection_reason = models.TextField("Причина отказа", blank=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Пользователь",
        on_delete=models.CASCADE,
        related_name="receipts",
    )

    created_at = models.DateTimeField("Дата регистрации", auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["fn", "fd", "fp"],
                name="unique_receipt",
            )
        ]
        verbose_name = "Чек"
        verbose_name_plural = "Чеки"

    def __str__(self):
        return f"{self.fn}/{self.fd}/{self.fp}"

from zoneinfo import ZoneInfo

from django.db import migrations, models
from django.utils import timezone


def copy_purchase_time(apps, schema_editor):
    Receipt = apps.get_model("receipts", "Receipt")
    moscow = ZoneInfo("Europe/Moscow")
    for receipt in Receipt.objects.all().iterator():
        local_time = timezone.localtime(receipt.purchase_at, moscow)
        receipt.purchase_date = local_time.date()
        receipt.purchase_time = local_time.time().replace(tzinfo=None)
        receipt.save(update_fields=["purchase_date", "purchase_time"])


class Migration(migrations.Migration):
    dependencies = [("receipts", "0002_alter_receipt_options_alter_receipt_amount_and_more")]

    operations = [
        migrations.AddField(
            model_name="receipt",
            name="purchase_date",
            field=models.DateField(null=True, verbose_name="Дата покупки"),
        ),
        migrations.AddField(
            model_name="receipt",
            name="purchase_time",
            field=models.TimeField(null=True, verbose_name="Время покупки"),
        ),
        migrations.RunPython(copy_purchase_time, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="receipt",
            name="purchase_date",
            field=models.DateField(verbose_name="Дата покупки"),
        ),
        migrations.AlterField(
            model_name="receipt",
            name="purchase_time",
            field=models.TimeField(verbose_name="Время покупки"),
        ),
        migrations.RemoveField(model_name="receipt", name="purchase_at"),
    ]

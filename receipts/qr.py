from io import BytesIO

import segno


def receipt_qr_text(receipt):
    purchase_time = receipt.purchase_time
    time_format = "%H%M%S" if purchase_time.second else "%H%M"
    return (
        f"t={receipt.purchase_date:%Y%m%d}T{purchase_time.strftime(time_format)}"
        f"&s={receipt.amount:.2f}&fn={receipt.fn}&i={receipt.fd}&fp={receipt.fp}"
    )


def receipt_qr_svg(receipt):
    image = BytesIO()
    segno.make_qr(receipt_qr_text(receipt)).save(image, kind="svg", scale=4, border=2)
    return image.getvalue()

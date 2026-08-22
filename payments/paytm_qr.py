"""
Paytm & UPI QR Code Generator
Generates UPI QR codes with embedded Transaction Reference for automatic verification
Supports direct UPI intent links (Paytm, PhonePe, GPay, BHIM, etc.)
"""

import qrcode
import secrets
import string
from io import BytesIO
from typing import Tuple, Optional
from urllib.parse import quote


def generate_unique_transaction_ref(prefix: str = "TRXN") -> str:
    """
    Generate a unique transaction reference for auto-verification.
    Format: TRXN + 12 random alphanumeric chars (e.g. TRXN0579FDFHPKTA)
    """
    chars = string.ascii_uppercase + string.digits
    random_part = "".join(secrets.choice(chars) for _ in range(12))
    return f"{prefix}{random_part}"


def generate_upi_url(
    upi_id: str,
    payee_name: str,
    amount: float,
    transaction_note: str = "Digital Store Purchase",
    transaction_ref: Optional[str] = None,
    merchant_code: Optional[str] = None,
) -> str:
    """
    Generate standard UPI payment URL
    """
    payee_name_encoded = quote(payee_name)
    note_encoded = quote(transaction_note)

    upi_url = f"upi://pay?pa={upi_id}&pn={payee_name_encoded}&am={amount:.2f}&cu=INR&tn={note_encoded}"

    if transaction_ref:
        upi_url += f"&tr={transaction_ref}"

    if merchant_code:
        upi_url += f"&mc={merchant_code}"

    return upi_url


def generate_upi_qr(
    upi_id: str,
    payee_name: str,
    amount: float,
    transaction_note: str = "Digital Store Purchase",
    transaction_ref: Optional[str] = None,
    merchant_code: Optional[str] = None,
) -> BytesIO:
    """
    Generate a high-quality QR code image buffer for Telegram photo sending
    """
    upi_url = generate_upi_url(
        upi_id=upi_id,
        payee_name=payee_name,
        amount=amount,
        transaction_note=transaction_note,
        transaction_ref=transaction_ref,
        merchant_code=merchant_code,
    )

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=3,
    )
    qr.add_data(upi_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer


def generate_payment_qr(
    upi_id: str,
    merchant_name: str,
    order_id: str,
    amount: float,
    transaction_ref: Optional[str] = None,
) -> Tuple[BytesIO, str, str]:
    """
    Generate payment QR and UPI deep link for an order or deposit
    """
    if not transaction_ref:
        transaction_ref = generate_unique_transaction_ref()

    clean_order_id = "".join(c for c in str(order_id) if c.isalnum())
    transaction_note = f"Order{clean_order_id}"

    qr_image = generate_upi_qr(
        upi_id=upi_id,
        payee_name=merchant_name,
        amount=amount,
        transaction_note=transaction_note,
        transaction_ref=transaction_ref,
    )

    upi_link = generate_upi_url(
        upi_id=upi_id,
        payee_name=merchant_name,
        amount=amount,
        transaction_note=transaction_note,
        transaction_ref=transaction_ref,
    )

    return qr_image, upi_link, transaction_ref


class PaytmQR:
    """Class helper for managing QR generation"""

    def __init__(self, upi_id: str, merchant_name: str):
        self.upi_id = upi_id
        self.merchant_name = merchant_name

    def create_payment_qr(
        self, order_id: str, amount: float, transaction_ref: Optional[str] = None
    ) -> Tuple[BytesIO, str, str]:
        return generate_payment_qr(
            upi_id=self.upi_id,
            merchant_name=self.merchant_name,
            order_id=order_id,
            amount=amount,
            transaction_ref=transaction_ref,
        )

    def get_upi_link(self, order_id: str, amount: float, transaction_ref: Optional[str] = None) -> str:
        if not transaction_ref:
            transaction_ref = generate_unique_transaction_ref()
        clean_order_id = "".join(c for c in str(order_id) if c.isalnum())
        return generate_upi_url(
            upi_id=self.upi_id,
            payee_name=self.merchant_name,
            amount=amount,
            transaction_note=f"Order{clean_order_id}",
            transaction_ref=transaction_ref,
        )

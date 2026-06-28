import base64
from datetime import datetime
from decimal import Decimal

import requests
from django.conf import settings
from requests.auth import HTTPBasicAuth


class MpesaConfigurationError(Exception):
    pass


class MpesaRequestError(Exception):
    pass


def normalize_phone_number(phone_number):
    cleaned = "".join(char for char in str(phone_number) if char.isdigit())
    if cleaned.startswith("0") and len(cleaned) == 10:
        return f"254{cleaned[1:]}"
    if cleaned.startswith("7") and len(cleaned) == 9:
        return f"254{cleaned}"
    return cleaned


def mpesa_base_url():
    if settings.MPESA_ENVIRONMENT.lower() == "production":
        return "https://api.safaricom.co.ke"
    return "https://sandbox.safaricom.co.ke"


def mpesa_is_configured():
    return all(
        [
            settings.MPESA_CONSUMER_KEY,
            settings.MPESA_CONSUMER_SECRET,
            settings.MPESA_PASSKEY,
            settings.MPESA_BUSINESS_SHORT_CODE,
        ]
    )


def require_mpesa_configured():
    if not mpesa_is_configured():
        raise MpesaConfigurationError("M-Pesa is not configured. Add Daraja credentials to environment variables.")


def get_access_token():
    require_mpesa_configured()
    response = requests.get(
        f"{mpesa_base_url()}{settings.MPESA_OAUTH_PATH}",
        auth=HTTPBasicAuth(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET),
        timeout=20,
    )
    if not response.ok:
        raise MpesaRequestError(f"Failed to get M-Pesa access token: {response.text}")
    return response.json()["access_token"]


def lipa_na_mpesa_password():
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    shortcode = settings.MPESA_BUSINESS_SHORT_CODE
    password = base64.b64encode(f"{shortcode}{settings.MPESA_PASSKEY}{timestamp}".encode()).decode()
    return password, timestamp


def initiate_stk_push(*, phone_number, amount, account_reference, callback_url, description):
    access_token = get_access_token()
    password, timestamp = lipa_na_mpesa_password()
    phone_number = normalize_phone_number(phone_number)
    amount = int(Decimal(str(amount)))
    payload = {
        "BusinessShortCode": settings.MPESA_BUSINESS_SHORT_CODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": settings.MPESA_STK_TRANSACTION_TYPE,
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": settings.MPESA_BUSINESS_SHORT_CODE,
        "PhoneNumber": phone_number,
        "CallBackURL": callback_url,
        "AccountReference": account_reference,
        "TransactionDesc": description[:100],
    }
    response = requests.post(
        f"{mpesa_base_url()}{settings.MPESA_STK_PUSH_PATH}",
        json=payload,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        timeout=30,
    )
    if not response.ok:
        raise MpesaRequestError(f"STK Push failed: {response.text}")
    return response.json(), payload


def register_c2b_urls(*, validation_url, confirmation_url):
    access_token = get_access_token()
    payload = {
        "ShortCode": settings.MPESA_BUSINESS_SHORT_CODE,
        "ResponseType": "Cancelled",
        "ConfirmationURL": confirmation_url,
        "ValidationURL": validation_url,
    }
    response = requests.post(
        f"{mpesa_base_url()}{settings.MPESA_C2B_REGISTER_URL_PATH}",
        json=payload,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        timeout=30,
    )
    if not response.ok:
        raise MpesaRequestError(f"C2B URL registration failed: {response.text}")
    return response.json(), payload

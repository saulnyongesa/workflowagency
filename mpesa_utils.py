import json
import requests
from requests.auth import HTTPBasicAuth
from remian_backend import settings
from .mpesa_config import MpesaAccessToken, MpesaC2bCredential, LipanaMpesaPassword


def trigger_stk_push(phone_number, amount, registration):
    """
    This function adapts your 'initiate_payment' logic to trigger an STK push.
    """
    # Clean phone number
    if phone_number.startswith('+'):
        phone_number = phone_number[1:]
    if phone_number.startswith('0'):
        phone_number = '254' + phone_number[1:]

    access_token = MpesaAccessToken.get_access_token()
    api_url = MpesaC2bCredential.request_api_url
    call_back_url = MpesaC2bCredential.call_back_url
    headers = {"Authorization": f"Bearer {access_token}"}

    password, timestamp, shortcode, _, _ = LipanaMpesaPassword.get_password()

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(float(amount)),  # Ensure amount is an integer
        "PartyA": phone_number,
        "PartyB": shortcode,
        "PhoneNumber": phone_number,
        "CallBackURL": call_back_url,
        "AccountReference": str(registration.mpesa_account_number),
        "TransactionDesc": f"Payment for webinar {registration.mpesa_account_number}"
    }

    response = requests.post(api_url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()  # Raise an error for bad responses

    resp_json = response.json()
    checkout_id = resp_json.get('CheckoutRequestID')
    merchant_id = resp_json.get('MerchantRequestID')

    return checkout_id, merchant_id

# --- C2B UTILS ---

def get_access_token():
    """
    Generates an OAuth access token for C2B URL Registration.
    FIXED: Now includes grant_type=client_credentials and uses correct settings names.
    """
   
    # URL for Live/Production (Switch to sandbox URL if needed)
    # Based on your prompt "I am live", we use the live URL.
    api_url = "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    
    try:
        r = requests.get(MpesaC2bCredential.api_URL,
                           auth=HTTPBasicAuth(MpesaC2bCredential.consumer_key, MpesaC2bCredential.consumer_secret),
                           timeout=10)
        r.raise_for_status()
        result = json.loads(r.text)
        return result['access_token']
    except Exception as e:
        print(f"Error generating access token: {e}")
        return None

def register_c2b_urls():
    """
    Registers the Validation and Confirmation URLs with Safaricom.
    """
    access_token = get_access_token()
    if not access_token:
        return {"error": "Failed to get access token"}

    # Production URL for C2B RegisterURL
    url = "https://api.safaricom.co.ke/mpesa/c2b/v2/registerurl"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # Your domain
    domain = "https://www.remiandiagnostics.com"
    
    # Payload
    payload = {
        "ShortCode": settings.BUSINESS_SHORT_CODE, # Using your settings variable
        "ResponseType": "Cancelled", 
        "ConfirmationURL": f"{domain}/webinar/c2b/confirmation/",
        "ValidationURL": f"{domain}/webinar/c2b/validation/"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        return response.json()
    except Exception as e:
        return {"error": str(e)}
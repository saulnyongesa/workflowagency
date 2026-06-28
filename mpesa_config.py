from decimal import Decimal
import requests
import json
from requests.auth import HTTPBasicAuth
from datetime import datetime
import base64

from remian_backend import settings


class MpesaC2bCredential:
    consumer_key = settings.CONSUMER_KEY
    consumer_secret = settings.CONSUMER_SECRET
    api_URL = 'https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
    call_back_url = 'https://www.remiandiagnostics.com/webinar/mpesa-callback/'
    request_api_url = "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"

class MpesaAccessToken:
    @staticmethod
    def get_access_token():
        try:
            r = requests.get(MpesaC2bCredential.api_URL,
                           auth=HTTPBasicAuth(MpesaC2bCredential.consumer_key, MpesaC2bCredential.consumer_secret),
                           timeout=10)
            r.raise_for_status()
            mpesa_access_token = json.loads(r.text)
            return mpesa_access_token["access_token"]
        except requests.exceptions.RequestException as e:
            print(f"Error fetching M-Pesa access token: {e}")
            raise

class LipanaMpesaPassword:
    @staticmethod
    def get_password():
        lipa_time = datetime.now().strftime('%Y%m%d%H%M%S')
        Business_short_code = "4043381"
        OffSetValue = '0'
        passkey = settings.PASSKEY
        data_to_encode = Business_short_code + passkey + lipa_time
        online_password = base64.b64encode(data_to_encode.encode())
        return online_password.decode('utf-8'), lipa_time, Business_short_code, OffSetValue, passkey
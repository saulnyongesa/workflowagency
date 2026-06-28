import base64
from decimal import Decimal
import io
import json
from datetime import datetime
import logging
import logging
import qrcode
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseForbidden
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import View, DetailView, ListView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.utils.timezone import make_aware
from django.contrib import messages
from django.db.models import Q

from conferences.models import ConferencePaymentTransaction, ConferenceRegistration
from remian_backend import settings
from .forms import WebinarCommentForm
from .models import PaymentMethod, Registration, PaymentTransaction, RegistrationStatus, Webinar
from .mpesa_utils import register_c2b_urls, trigger_stk_push
import os
from .tasks import task_award_points, task_send_payment_confirmation_email
from django.contrib.admin.views.decorators import staff_member_required
from google_auth_oauthlib.flow import Flow

logger = logging.getLogger(__name__)
class WebinarDetailView(DetailView):
    """
    Shows a single webinar's details and the registration/discussion sections.
    """
    model = Webinar
    template_name = 'webinars/webinar_detail.html'
    context_object_name = 'webinar'

    def user_can_discuss(self, user, webinar):
        if not user.is_authenticated:
            return False
        if user.is_staff:
            return True
        return Registration.objects.filter(
            participant=user,
            webinar=webinar,
            status=RegistrationStatus.CONFIRMED
        ).exists()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        webinar = self.get_object()
        user = self.request.user

        # Get registration status
        if user.is_authenticated:
            try:
                registration = Registration.objects.get(participant=user, webinar=webinar)
                context['registration'] = registration
            except Registration.DoesNotExist:
                context['registration'] = None

            # Get user's display name
            full_name = f"{user.first_name} {user.last_name}".strip()
            context['user_display_name'] = full_name if full_name else "Anonymous"

        else:
            context['registration'] = None
            context['user_display_name'] = "Guest"

        recent_comments = list(
            webinar.webinar_comments.all().select_related('user').order_by('-created_at')[:50]
        )
        recent_comments.reverse()
        context['can_discuss'] = self.user_can_discuss(user, webinar)
        context['comment_form'] = WebinarCommentForm()
        context['comments'] = recent_comments
        context['discussion_comment_count'] = webinar.webinar_comments.count()

        # --- NEW: Get suggested webinars ---
        context['suggested_webinars'] = Webinar.objects.public().exclude(pk=webinar.pk).order_by('-date')[:3]
        # --- END NEW ---

        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        webinar = self.object

        if not self.user_can_discuss(request.user, webinar):
            messages.error(request, "You must have a confirmed registration to join the discussion.")
            return redirect(f"{reverse('webinar_detail', kwargs={'pk': webinar.pk})}#webinarDiscussion")

        form = WebinarCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.webinar = webinar
            comment.user = request.user
            comment.save()
            messages.success(request, "Your discussion comment has been posted.")
        else:
            messages.error(request, "Please enter a valid discussion comment.")

        return redirect(f"{reverse('webinar_detail', kwargs={'pk': webinar.pk})}#webinarDiscussion")


@login_required
@require_POST
def participant_delete_pending_registration(request, registration_id):
    registration = get_object_or_404(
        Registration,
        pk=registration_id,
        participant=request.user,
        status=RegistrationStatus.PENDING,
    )
    webinar_title = registration.webinar.title
    registration.delete()
    messages.success(request, f'Pending registration for "{webinar_title}" has been deleted.')
    return redirect('participant_dashboard')


class PaymentPageView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        registration_id = self.kwargs.get('registration_id')
        registration = get_object_or_404(Registration, pk=registration_id)

        if registration.participant != request.user:
            messages.error(request, "You are not authorized to view this page.")
            return redirect('home')
        
        if registration.status == RegistrationStatus.CONFIRMED:
            messages.warning(request, "This registration has already been paid for.")
            return redirect('participant_dashboard')

        # --- NEW LOGIC: Fetch Active Payment Methods ---
        stk_method = PaymentMethod.objects.filter(method=PaymentMethod.PaymentOptions.MPESA_STK_PUSH).first()
        pochi_method = PaymentMethod.objects.filter(method=PaymentMethod.PaymentOptions.POCHI_LA_BIASHARA).first()
        
        # Default to True if record doesn't exist yet (fallback), otherwise use DB value
        stk_active = stk_method.is_active if stk_method else True
        pochi_active = pochi_method.is_active if pochi_method else True

        context = {
            'registration': registration,
            'stk_active': stk_active,
            'pochi_active': pochi_active,
        }
        return render(request, 'webinars/payment_page.html', context)

class PaymentPageView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        registration_id = self.kwargs.get('registration_id')
        registration = get_object_or_404(Registration, pk=registration_id)

        if registration.participant != request.user:
            messages.error(request, "You are not authorized to view this page.")
            return redirect('home')
        
        if registration.status == RegistrationStatus.CONFIRMED:
            messages.warning(request, "This registration has already been paid for.")
            return redirect('participant_dashboard')

        # --- Payment Methods Status ---
        stk_method = PaymentMethod.objects.filter(method=PaymentMethod.PaymentOptions.MPESA_STK_PUSH).first()
        pochi_method = PaymentMethod.objects.filter(method=PaymentMethod.PaymentOptions.POCHI_LA_BIASHARA).first()
        c2b_method = PaymentMethod.objects.filter(method=PaymentMethod.PaymentOptions.MPESA_C2B).first()
        
        stk_active = stk_method.is_active if stk_method else True
        pochi_active = pochi_method.is_active if pochi_method else True
        c2b_active = c2b_method.is_active if c2b_method else False # Default false if not configured

        context = {
            'registration': registration,
            'stk_active': stk_active,
            'pochi_active': pochi_active,
            'c2b_active': c2b_active,
            'paybill_number': settings.BUSINESS_SHORT_CODE,
            'account_number': registration.mpesa_account_number or f"WB{registration.id}",
        }
        return render(request, 'webinars/payment_page.html', context)


@login_required
def initiate_mpesa_payment(request, registration_id):
    """
    Initiates the STK push via AJAX.
    """
    registration = get_object_or_404(Registration, pk=registration_id)

    if registration.participant != request.user:
        return JsonResponse({'success': False, 'message': "Authorization failed."}, status=403)

    if registration.status == RegistrationStatus.CONFIRMED:
        return JsonResponse({'success': False, 'message': "Already paid."}, status=400)

    if request.method == 'POST':
        # Handle both JSON and Form data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            phone_number = data.get('phone_number')
        else:
            phone_number = request.POST.get('phone_number')
            
        amount = registration.webinar.price

        if not phone_number:
            return JsonResponse({'success': False, 'message': "Please enter a valid phone number."}, status=400)

        try:
            checkout_id, merchant_id = trigger_stk_push(phone_number, amount, registration)

            PaymentTransaction.objects.create(
                registration=registration,
                amount=amount,
                phone_number=phone_number,
                checkout_request_id=checkout_id,
                merchant_request_id=merchant_id,
                is_complete=False
            )

            return JsonResponse({
                'success': True, 
                'message': "STK push sent! Please check your phone.",
                'checkout_request_id': checkout_id
            })

        except Exception as e:
            return JsonResponse({'success': False, 'message': f"An error occurred: {str(e)}"}, status=500)

    return JsonResponse({'success': False, 'message': "Invalid request method."}, status=405)

@login_required
def check_payment_status(request, checkout_request_id):
    """
    Checks if a specific M-Pesa transaction is complete.
    Used for polling from the frontend.
    """
    try:
        transaction = PaymentTransaction.objects.get(checkout_request_id=checkout_request_id)
        
        # Security check: Ensure user owns this transaction
        if transaction.registration.participant != request.user and not request.user.is_staff:
            return JsonResponse({'status': 'UNKNOWN'}, status=403)

        if transaction.is_complete:
            return JsonResponse({'status': 'COMPLETED'})
        else:
            return JsonResponse({'status': 'PENDING'})
            
    except PaymentTransaction.DoesNotExist:
        return JsonResponse({'status': 'NOT_FOUND'}, status=404)
    

@csrf_exempt
def mpesa_callback(request):
    """
    Handles the callback from Safaricom.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Bad data.'}, status=400)

    callback = data.get('Body', {}).get('stkCallback', {})
    result_code = callback.get('ResultCode', 1)
    checkout_id = callback.get('CheckoutRequestID', '')

    try:
        tx = PaymentTransaction.objects.get(checkout_request_id=checkout_id)
    except PaymentTransaction.DoesNotExist:
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Transaction not found.'}, status=404)

    if result_code != 0:
        tx.is_complete = False
        tx.result_description = callback.get('ResultDesc', 'Failed')
        tx.save()
        return JsonResponse({'ResultCode': result_code, 'ResultDesc': callback.get('ResultDesc', 'Failed')})

    metadata = callback.get('CallbackMetadata', {})
    items = metadata.get('Item', [])

    mpesa_receipt = ''
    amount = None
    phone = ''
    txn_date_str = ''

    for item in items:
        name = item.get('Name')
        value = item.get('Value')
        if name == 'MpesaReceiptNumber':
            mpesa_receipt = value
        elif name == 'Amount':
            amount = value
        elif name == 'PhoneNumber':
            phone = str(value)
        elif name == 'TransactionDate':
            txn_date_str = str(value)

    tx.mpesa_receipt_number = mpesa_receipt
    tx.is_complete = True
    if txn_date_str:
        try:
            tx.transaction_date = make_aware(datetime.strptime(txn_date_str, '%Y%m%d%H%M%S'))
        except ValueError:
            pass
    tx.save()

    registration = tx.registration
    registration.status = RegistrationStatus.CONFIRMED
    registration.save()

    if registration.participant.is_active:
         task_send_payment_confirmation_email(registration.id)

    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})

# --- NEW: C2B Views ---

@login_required
def register_urls_view(request):
    """
    Helper view for Admin/Staff to register URLs manually.
    Only accessible by staff.
    """
    if not request.user.is_staff:
        return HttpResponseForbidden()
    
    response = register_c2b_urls()
    return JsonResponse(response)

@csrf_exempt
def c2b_validation(request):
    """
    Safaricom calls this to validate a transaction before completion.
    """
    try:
        data = json.loads(request.body)
        bill_ref_number = data.get('BillRefNumber', '').strip().upper()
        trans_amount = data.get('TransAmount')
        if bill_ref_number == "REMIAN":
            return JsonResponse({
                "ResultCode": "0", 
                "ResultDesc": "Accepted"
            })
        
        if bill_ref_number.startswith("CF"):
            conference_registration = ConferenceRegistration.objects.filter(mpesa_account_number=bill_ref_number).first()
            paid_amount = Decimal(str(trans_amount))
            if conference_registration and paid_amount == conference_registration.conference.fee:
                return JsonResponse({
                    "ResultCode": "0", 
                    "ResultDesc": "Accepted"
                })
        
        # 1. Find Registration
        registration = Registration.objects.get(mpesa_account_number=bill_ref_number)
        
        # 2. Check Amount
        paid_amount = Decimal(str(trans_amount))
        required_amount = registration.webinar.price
        
        if paid_amount != required_amount:
            return JsonResponse({
                "ResultCode": "C2B00013", 
                "ResultDesc": "Rejected: Amount does not match webinar price."
            })
            
        # 3. Check if already paid
        if registration.status == RegistrationStatus.CONFIRMED:
             return JsonResponse({
                "ResultCode": "C2B00016", 
                "ResultDesc": "Rejected: Registration already paid."
            })

        return JsonResponse({
            "ResultCode": "0", 
            "ResultDesc": "Accepted"
        })
        
    except Registration.DoesNotExist:
        return JsonResponse({
            "ResultCode": "C2B00012", 
            "ResultDesc": "Rejected: Invalid Account Number."
        })
    except Exception as e:
        logger.error(f"C2B Validation Error: {e}")
        return JsonResponse({
            "ResultCode": "C2B00016",
            "ResultDesc": "Rejected: Validation Error."
        })

@csrf_exempt
def c2b_confirmation(request):
    """
    Safaricom calls this when a C2B transaction is COMPLETED.
    """
    try:
        # 1. Parse JSON safely
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"ResultCode": "1", "ResultDesc": "Invalid JSON"}, status=400)

        # 2. Extract Data with defaults
        # Safely get fields and truncate them to avoid DB "value too long" errors
        trans_id = str(data.get('TransID', '')).strip()[:20] # Truncate to 20 chars max
        trans_amount = data.get('TransAmount')
        bill_ref_number = data.get('BillRefNumber', '').strip().upper()
        
        raw_msisdn = str(data.get('MSISDN', '')).strip()
        msisdn = raw_msisdn[:15] # Truncate Phone Number to 15 chars max (Safe for DB varchar(20))
        
        trans_time = data.get('TransTime')
        if bill_ref_number == "REMIAN":
            return JsonResponse({"ResultCode": "0", "ResultDesc": "Processed Successfully"})
        
        if bill_ref_number.startswith("CF"):
            try:
                conference_registration = ConferenceRegistration.objects.filter(mpesa_account_number=bill_ref_number).first()
                try:
                        paid_amount = Decimal(str(trans_amount)) if trans_amount else Decimal('0.00')
                except:
                    paid_amount = Decimal('0.00')
            
                is_valid_amount = paid_amount >= conference_registration.conference.fee

                aware_trans_time = timezone.now()
                if trans_time:
                    try:
                        aware_trans_time = make_aware(datetime.strptime(str(trans_time), '%Y%m%d%H%M%S'))
                    except ValueError:
                        pass # Use current time if parsing fails
                if conference_registration and is_valid_amount:
                    conference_registration.payment_status = ConferenceRegistration.PaymentStatus.COMPLETED
                    conference_registration.amount_paid = paid_amount
                    conference_registration.mpesa_reference = trans_id
                    conference_registration.save()
                    ConferencePaymentTransaction.objects.create(
                        conference_registration=conference_registration,
                        phone_number=msisdn,
                        amount=paid_amount,
                        mpesa_receipt_number=trans_id,
                        is_complete=True,
                        transaction_date=aware_trans_time 
                    )
                    return JsonResponse({"ResultCode": "0", "ResultDesc": "Processed Successfully"})
            except ConferenceRegistration.DoesNotExist:
                return JsonResponse({"ResultCode": "0", "ResultDesc": "Conference registration not found"})


         # Validate required fields

        if not trans_id:
            return JsonResponse({"ResultCode": "0", "ResultDesc": "Missing TransID"})

        # 3. Check for Duplicate Transaction (Prevent 500s on retries)
        if PaymentTransaction.objects.filter(mpesa_receipt_number=trans_id).exists():
            return JsonResponse({"ResultCode": "0", "ResultDesc": "Transaction already processed"})

        # 4. Find Registration
        try:
            registration = Registration.objects.get(mpesa_account_number=bill_ref_number)
        except Registration.DoesNotExist:
            logger.warning(f"C2B: Registration not found for BillRef {bill_ref_number}")
            return JsonResponse({"ResultCode": "0", "ResultDesc": "Registration not found"})
        except Registration.MultipleObjectsReturned:
            logger.error(f"C2B: Multiple registrations for {bill_ref_number}")
            registration = Registration.objects.filter(mpesa_account_number=bill_ref_number).last()

        # 5. Verify Amount & Parse Time
        try:
            paid_amount = Decimal(str(trans_amount)) if trans_amount else Decimal('0.00')
        except:
            paid_amount = Decimal('0.00')
            
        is_valid_amount = paid_amount >= registration.webinar.price

        aware_trans_time = timezone.now()
        if trans_time:
            try:
                aware_trans_time = make_aware(datetime.strptime(str(trans_time), '%Y%m%d%H%M%S'))
            except ValueError:
                pass # Use current time if parsing fails

        # 6. Create Transaction Record
        transaction = PaymentTransaction.objects.create(
            registration=registration,
            amount=paid_amount,
            phone_number=msisdn,
            mpesa_receipt_number=trans_id,
            checkout_request_id=trans_id,
            is_complete=True,
            transaction_date=aware_trans_time
        )

        # 7. Mark Registration Confirmed
        if is_valid_amount:
            if registration.status != RegistrationStatus.CONFIRMED:
                registration.status = RegistrationStatus.CONFIRMED
                registration.save()
                
                # Send Email
                if registration.participant.is_active:
                    task_send_payment_confirmation_email(registration.id)
        else:
            logger.warning(f"C2B: Amount mismatch. Paid {paid_amount}, expected {registration.webinar.price}")

        return JsonResponse({"ResultCode": "0", "ResultDesc": "Processed Successfully"})

    except Exception as e:
        # Catch ALL errors to prevent 500 response to Safaricom
        logger.exception("C2B Confirmation Critical Error")
        return JsonResponse({"ResultCode": "0", "ResultDesc": "Error Handled"})
    
    
class WebinarListView(ListView):

    """
    "View More" page for all public, upcoming webinars.
    """
    model = Webinar
    template_name = 'webinars/webinar_list.html'
    context_object_name = 'webinars'
    paginate_by = 6

    def get_queryset(self):
        return Webinar.objects.public().order_by('date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get ended webinars, ordered by most recent first
        context['past_webinars'] = Webinar.objects.filter(
            is_ended=True,
            published=True
        ).order_by('-date')[:5]  # Limit to 10 recent past events
        return context

class PastWebinarListView(ListView):
    """
    View for all past webinars.
    """
    model = Webinar
    template_name = 'webinars/webinar_past_list.html'
    context_object_name = 'past_webinars'
    paginate_by = 6

    def get_queryset(self):
        queryset = Webinar.objects.filter(
            is_ended=True,
            published=True
        ).order_by('-date')
        self.search_query = self.request.GET.get('q', '').strip()
        self.year_filter = self.request.GET.get('year', '').strip()

        if self.search_query:
            queryset = queryset.filter(
                Q(title__icontains=self.search_query) |
                Q(description__icontains=self.search_query) |
                Q(facilitator__icontains=self.search_query) |
                Q(speaker__icontains=self.search_query)
            )
        if self.year_filter.isdigit():
            queryset = queryset.filter(date__year=int(self.year_filter))

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_past = Webinar.objects.filter(is_ended=True, published=True)
        years = (
            all_past
            .dates('date', 'year', order='DESC')
        )
        context['new_webinars'] = Webinar.objects.public().filter(published=True).order_by('date')[:5]
        context['total_past_webinars'] = all_past.count()
        context['total_cpd_points'] = sum(float(item.cpd_points or 0) for item in all_past)
        context['available_years'] = [item.year for item in years]
        context['search_query'] = self.search_query
        context['selected_year'] = self.year_filter
        return context

# --- NEW: CERTIFICATE VIEW ---
def get_verification_url(request, registration_id):
    """Generates the full, unique verification URL."""
    domain = request.get_host()
    protocol = 'https' if request.is_secure() else 'http'
    return f"{protocol}://{domain}{reverse('public_verified_certificate', kwargs={'reg_id': registration_id})}"


class CertificateView(LoginRequiredMixin, View):
    """
    Renders the printable certificate for a user/webinar registration.
    """

    def get(self, request, *args, **kwargs):
        registration_id = self.kwargs.get('registration_id')
        registration = get_object_or_404(Registration, pk=registration_id)

        # Security check
        if registration.participant != request.user and not request.user.is_staff:
            return HttpResponseForbidden("You are not authorized to view this certificate.")

        webinar = registration.webinar

        # Eligibility check
        if registration.status != RegistrationStatus.CONFIRMED:
            messages.error(request, "Certificate cannot be generated: Registration is not confirmed.")
            return redirect('participant_dashboard')
        if registration.cpd_points_awarded == 0:
            messages.error(request, "Certificate cannot be generated: CPD Points Not Awarded, Please wait for a few minutes.")
            return redirect('participant_dashboard')

        # Check if webinar is ended
        if webinar.end_datetime > timezone.now() and not request.user.is_staff:
            messages.warning(request, "Certificate cannot be generated: Webinar has not yet ended.")
            return redirect('participant_dashboard')

        # Get user's full name
        user_full_name = f"{registration.participant.first_name} {registration.participant.last_name}".strip()
        user_full_name = user_full_name.upper() if user_full_name else "RECIPIENT NAME"

        certificate_id = str(registration.pk)
        verification_url = get_verification_url(request, registration_id)

        # --- NEW: QR CODE GENERATION ---

        # 1. Create the QR code image object
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=2,
        )
        qr.add_data(verification_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#1a4b8c", back_color="white")  # Use brand colors

        # 2. Save the image to a memory buffer
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()

        # --- END QR CODE GENERATION ---

        context = {
            'registration': registration,
            'webinar': webinar,
            'user': registration.participant,
            'user_full_name': user_full_name,
            'certificate_id': certificate_id,
            'verification_url': verification_url,
            'qr_base64': qr_base64,  # Pass the Base64 image string

            # --- FIX: Removed signature_url, template uses static ---
            'directors': [
                {'name': 'Ians Kasola', 'title': 'Director of Training Programs and Curriculum Development'},
                {'name': 'Jemimah Mwende', 'title': 'Director of Accounts and Clients Operations'},
                {'name': 'Reagan Oluoch', 'title': 'Director of Marketing and Partnership Strategies'},
            ]
        }
        return render(request, 'webinars/certificate.html', context)


# --- PUBLIC VERIFICATION VIEW (RESTRICTED AND FORM-BASED) ---
class PublicVerifiedCertificateView(TemplateView):
    # ... (unchanged)
    template_name = 'webinars/public_verification.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reg_id = self.kwargs.get('reg_id')  # Get ID from URL path

        if not reg_id or not str(reg_id).isdigit():
            context['error'] = "Invalid certificate ID."
            return context

        try:
            registration = Registration.objects.get(pk=reg_id)
            webinar = registration.webinar

            if registration.status != RegistrationStatus.CONFIRMED or not webinar.is_ended:
                context['error'] = "Verification failed: Certificate is not valid or the webinar has not ended."
                return context

            context['registration'] = registration
            context['webinar'] = webinar
            context['user'] = registration.participant
            context['page_title'] = "Certificate Verified"

        except Registration.DoesNotExist:
            context['error'] = f"Certificate ID {reg_id} not found."

        return context


# --- Existing: Public Verification Form View (for manual entry) ---
class PublicVerificationFormView(TemplateView):
    # ... (unchanged)
    template_name = 'webinars/public_verification_form.html'

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        context['page_title'] = "Verify Certificate (Manual)"
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        certificate_id = request.POST.get('certificate_id')

        context = self.get_context_data()
        context['search_id'] = certificate_id
        context['page_title'] = "Verify Certificate (Manual)"

        if not certificate_id or not certificate_id.isdigit():
            context['error'] = "Please enter a valid certificate ID (numbers only)."
            return self.render_to_response(context)

        return redirect('public_verified_certificate', reg_id=certificate_id)


# Google meet configs ==============================================================
CLIENT_CONFIG = json.loads(os.getenv('GOOGLE_CREDENTIALS', '{}'))

@staff_member_required
def google_auth_start(request):
    if not CLIENT_CONFIG:
        messages.error(request, "GOOGLE_CREDENTIALS not configured")
        return redirect('/admin/')

    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=['https://www.googleapis.com/auth/calendar.events'],
        redirect_uri=request.build_absolute_uri(reverse('webinar_google_callback'))
    )

    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )

    request.session['oauth_state'] = state
    return redirect(auth_url)


def google_auth_callback(request):
    state = request.session.get('oauth_state')
    if not state:
        messages.error(request, "Invalid state")
        return redirect('/admin/')

    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=['https://www.googleapis.com/auth/calendar.events'],
        redirect_uri=request.build_absolute_uri(reverse('webinar_google_callback')),
        state=state
    )

    flow.fetch_token(authorization_response=request.build_absolute_uri())

    creds = flow.credentials
    token_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }

    print("\n" + "="*80)
    print("COPY & RUN THIS COMMAND ONCE:")
    print("="*80)
    print(f"heroku config:set GOOGLE_TOKEN='{json.dumps(token_data)}' -a your-app-name")
    print("="*80 + "\n")

    messages.success(request, "Google Calendar Connected! Token command printed in logs.")
    return redirect('/admin/')


@login_required
def award_points(request, webinar_id):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # AJAX call from button
        webinar = get_object_or_404(Webinar, pk=webinar_id)
        task_award_points(webinar.id)
        return JsonResponse({"message": "CPD points are being awarded in the background..."})

    # Normal HTTP request
    webinar = get_object_or_404(Webinar, pk=webinar_id)
    task_award_points(webinar.id)
    messages.success(request, "CPD points awarding started in background!")
    return redirect('webinar_report', pk=webinar.id)

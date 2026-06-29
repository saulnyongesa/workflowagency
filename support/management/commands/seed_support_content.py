from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from support.models import FAQ, PolicyPage


POLICIES = [
    {
        "title": "Terms of Service",
        "slug": "terms-of-service",
        "policy_type": PolicyPage.PolicyType.TERMS,
        "summary": "Rules for using Workflow Agency accounts, jobs, products, referrals, wallets, and support.",
        "body": """Welcome to Workflow Agency. By creating an account or using the platform, you agree to use the service honestly, provide accurate account information, and follow all task, payment, referral, and support rules.

Accounts are personal and should not be sold, shared, or used to submit work for another person. The platform may review suspicious activity, duplicate accounts, false proof, abusive behavior, or attempts to manipulate rewards.

Jobs, surveys, products, and promotions may have limits, deadlines, proof requirements, and review periods. A task is payable only when it is completed according to the instructions and approved after review.

Wallet balances, commissions, activation credits, and payout requests are handled through the platform ledger. Balances may be held, reversed, or corrected when there is an error, refund, duplicate transaction, failed payment, fraud concern, or policy violation.

These terms may be updated as the service grows. Continued use of the platform after updates means you accept the latest published terms.""",
    },
    {
        "title": "Privacy Policy",
        "slug": "privacy-policy",
        "policy_type": PolicyPage.PolicyType.PRIVACY,
        "summary": "How account, payment, job, referral, support, and activity data is handled.",
        "body": """Workflow Agency collects the information needed to operate user accounts, process payments, review work, prevent abuse, and provide support. This can include name, username, email, phone number, country, referral relationships, wallet records, job submissions, product purchases, support messages, and technical activity data.

Payment-related details are used to process M-Pesa deposits, activation payments, withdrawal requests, reversals, and reconciliation. Sensitive payment credentials are not published to users and should only be stored in secure platform configuration.

User data is used for account access, fraud prevention, customer support, payout review, product delivery, referral tracking, and service improvement. The platform may keep audit logs for finance and security accountability.

Users should protect their passwords and avoid sharing account access. Support staff will never ask for a password.

Data may be retained where required for financial records, dispute handling, security review, or legal compliance. Users can contact support for account and privacy questions.""",
    },
    {
        "title": "Withdrawal and Payout Policy",
        "slug": "withdrawal-and-payout-policy",
        "policy_type": PolicyPage.PolicyType.WITHDRAWAL,
        "summary": "Minimum withdrawal rules, review status, M-Pesa payout handling, and reserve checks.",
        "body": """Withdrawals are available only to eligible active accounts with enough available balance. The requested amount must meet the current minimum withdrawal amount shown in the wallet page.

A withdrawal request may move funds from available balance into locked balance while the request is reviewed. This prevents the same funds from being spent or withdrawn twice.

Payouts may be reviewed for account status, proof quality, duplicate activity, daily withdrawal limits, platform reserve safety, and M-Pesa readiness. A request can be approved, paid, rejected, failed, or cancelled depending on the review result.

If a withdrawal is rejected or fails before payment, locked funds may be returned to the available wallet balance. If a payout is marked paid, the locked balance is reduced and the payout reference is recorded.

Payout timelines can vary because of review queues, M-Pesa processing, network delays, compliance checks, or maintenance windows.""",
    },
    {
        "title": "Jobs and Rewards Policy",
        "slug": "jobs-and-rewards-policy",
        "policy_type": PolicyPage.PolicyType.JOB_REWARD,
        "summary": "How claiming, worker limits, proof submission, review, approval, and rewards work.",
        "body": """Jobs are published with a reward amount, task instructions, proof requirements, and a limited number of available worker slots. Once all available positions are claimed or approved, a job may become full or unavailable.

Users should claim only jobs they can complete before the claim expires. Submitting fake proof, duplicate proof, copied responses, low-quality work, or proof from another person may lead to rejection and account review.

Rewards are posted only after the submitted proof is approved. Some jobs may be reviewed manually, while small approved tasks may be processed faster where platform settings allow.

The platform may pause all job claiming during client approval, maintenance, fraud review, or campaign changes. Active accounts will see an availability message if jobs are temporarily disabled.

Rejected tasks do not earn rewards. Users can contact support if they believe a rejection was caused by a mistake.""",
    },
    {
        "title": "Referral Policy",
        "slug": "referral-policy",
        "policy_type": PolicyPage.PolicyType.REFERRAL,
        "summary": "Referral code requirements, referral links, bonus eligibility, release timing, and abuse controls.",
        "body": """New users must join using a valid referral code or referral link. Existing accounts without a referrer may be asked to add a referral code before continuing.

Referral bonuses are based on the current platform settings. A bonus may be fixed or percentage-based, and it may be held as pending before becoming available.

A referral bonus is earned only when the referred user completes the required activation or qualifying action successfully. Reversed payments, duplicate users, fake accounts, self-referrals, or suspicious activity may cancel or reverse a referral bonus.

Users can share their referral link through approved channels. Misleading promises, spam, impersonation, or claims that are not supported by the platform rules are not allowed.

Referral settings can change over time. The applicable rules are the rules shown in the platform at the time of the qualifying action.""",
    },
    {
        "title": "Payments and Activation Policy",
        "slug": "payments-and-activation-policy",
        "policy_type": PolicyPage.PolicyType.OTHER,
        "summary": "Activation fees, wallet crediting, deposits, transaction references, and M-Pesa reconciliation.",
        "body": """Some accounts must pay an activation fee before accessing earning features. The required activation amount and credit rules are controlled by current platform settings.

After successful activation, the account status and wallet entries are updated through the platform ledger. If the user was referred, the referrer may receive a bonus according to the referral settings.

M-Pesa deposits and activation payments should be made only through the approved payment flow or official payment instructions shown on the platform. Users should keep transaction references for support.

Failed, pending, duplicate, or mismatched payments may require manual review. The platform may reconcile payment callbacks, account references, checkout request IDs, receipts, and ledger entries before crediting an account.

Do not send money to personal numbers claiming to represent the platform unless that payment route is shown inside the official system.""",
    },
    {
        "title": "Products and Digital Content Policy",
        "slug": "products-and-digital-content-policy",
        "policy_type": PolicyPage.PolicyType.OTHER,
        "summary": "Rules for guides, stories, videos, articles, templates, external links, and product commissions.",
        "body": """Products may include guides, stories, videos, articles, templates, files, links, and service resources. Product details should be reviewed before purchase.

Purchased products are delivered through the platform library, file delivery, or external link depending on the product type. Access may depend on successful wallet payment and product availability.

Digital product purchases are normally final once delivered, unless the platform confirms a delivery issue, duplicate charge, incorrect listing, or other valid support case.

Products can include affiliate commissions when enabled. Product commissions may be pending before release and may be reversed if the purchase is refunded, cancelled, or flagged.

Users must not resell, leak, or redistribute paid digital content unless the product page clearly allows it.""",
    },
    {
        "title": "Support and Dispute Policy",
        "slug": "support-and-dispute-policy",
        "policy_type": PolicyPage.PolicyType.SUPPORT,
        "summary": "How support tickets, evidence, response status, and disputes are handled.",
        "body": """Users should open a support ticket when they need help with account access, activation, deposits, withdrawals, jobs, products, referrals, or technical issues.

A good support request includes the account username, phone number, transaction reference if available, job or product name, screenshots or proof notes where relevant, and a clear description of the problem.

Support tickets may move through open, waiting for user, waiting for staff, resolved, or closed states. If more information is needed, the user should reply inside the ticket.

Disputes are reviewed using platform records such as payment callbacks, wallet ledger entries, job proof, product purchase logs, referral records, and support messages.

Abusive messages, fake evidence, repeated duplicate tickets, or attempts to pressure staff into bypassing finance rules may lead to ticket closure or account review.""",
    },
]


FAQS = [
    (
        "Accounts",
        "Can I create an account without a referral code?",
        "No. New users must provide a valid referral code or join through a referral link before an account can be registered.",
    ),
    (
        "Accounts",
        "Can I log in with my phone number?",
        "Yes. You can log in with your username, email address, or phone number together with your password.",
    ),
    (
        "Accounts",
        "Why is my account locked after registration?",
        "New accounts start locked until the required activation step is completed or an authorized staff action activates the account.",
    ),
    (
        "Activation",
        "What does the activation fee do?",
        "The activation fee unlocks earning features according to current settings. A wallet credit and referral bonus may also be recorded based on the active finance rules.",
    ),
    (
        "Activation",
        "What happens if my activation payment is pending?",
        "Keep the M-Pesa reference and wait for confirmation. If the wallet does not update after a reasonable time, open a support ticket with the receipt details.",
    ),
    (
        "Referrals",
        "Where do I find my referral link?",
        "Open the referral dashboard after logging in. The page shows your referral code and a shareable link that new users can use to join.",
    ),
    (
        "Referrals",
        "When do referral bonuses become available?",
        "Referral bonuses follow the current release delay and review rules. Some bonuses may remain pending before they move to available balance.",
    ),
    (
        "Referrals",
        "Can I refer myself?",
        "No. Self-referrals, duplicate accounts, and fake referrals may be cancelled or reversed.",
    ),
    (
        "Jobs",
        "Why can I not claim a job?",
        "The job may be full, expired, paused, limited to active accounts, already claimed by you, or temporarily unavailable while campaign approval is pending.",
    ),
    (
        "Jobs",
        "What happens when all job positions are taken?",
        "The job stops accepting new claims once the worker limit is reached unless the campaign is extended or republished with new slots.",
    ),
    (
        "Jobs",
        "How do I submit proof for a job?",
        "Open the claimed job, follow the proof instructions, then submit the required text, link, or file before the claim expires.",
    ),
    (
        "Jobs",
        "When is a job reward paid?",
        "A reward is added after the submitted proof is reviewed and approved. Rejected or expired claims do not earn rewards.",
    ),
    (
        "Jobs",
        "Why are all jobs temporarily unavailable?",
        "Job claiming may be paused during client approval, campaign review, maintenance, or safety checks. Published jobs can return once claiming is enabled again.",
    ),
    (
        "Wallet",
        "What is available balance?",
        "Available balance is money currently usable for eligible purchases or withdrawal requests, subject to minimum withdrawal and platform rules.",
    ),
    (
        "Wallet",
        "What is locked balance?",
        "Locked balance is money reserved for a pending withdrawal or review action. It cannot be spent until the request is completed or released.",
    ),
    (
        "M-Pesa",
        "How do deposits work?",
        "Deposits are processed through M-Pesa and recorded in the wallet ledger after successful confirmation.",
    ),
    (
        "M-Pesa",
        "What should I do if my M-Pesa payment is not reflected?",
        "Open a support ticket with your phone number, amount, payment time, and M-Pesa receipt code so the transaction can be checked.",
    ),
    (
        "Withdrawals",
        "Why is the withdrawal button disabled?",
        "The account may not be active, withdrawals may be disabled, or your available balance may be below the current minimum withdrawal amount.",
    ),
    (
        "Withdrawals",
        "Can a withdrawal be rejected?",
        "Yes. A request can be rejected if it fails account, balance, proof, daily limit, reserve, or payment review checks.",
    ),
    (
        "Withdrawals",
        "Where can I see my withdrawal status?",
        "Open the wallet or withdrawal history page to see requested, approved, paid, failed, rejected, or cancelled withdrawal records.",
    ),
    (
        "Products",
        "How do I buy a product?",
        "Open the product store, choose a published product, and pay from available wallet balance if the product is still available.",
    ),
    (
        "Products",
        "Where do purchased products appear?",
        "Purchased digital products appear in your product library with delivery notes, files, or external links where available.",
    ),
    (
        "Products",
        "Can products have referral commissions?",
        "Yes. A product can have no commission, a fixed commission, or a percentage commission depending on how it was configured.",
    ),
    (
        "Support",
        "How do I contact support?",
        "Open the support center, create a ticket, choose the right category, and include clear details plus any transaction or job reference.",
    ),
    (
        "Support",
        "How long does support take to reply?",
        "Response time depends on ticket volume and the type of issue. Payment and withdrawal disputes may take longer because they require reconciliation.",
    ),
]


class Command(BaseCommand):
    help = "Seed public support policies and FAQs for the prototype."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete seeded policies and FAQs before recreating.")
        parser.add_argument(
            "--updated-by",
            default="demo_admin",
            help="Username to store as the policy updater when available.",
        )

    def handle(self, *args, **options):
        updater = self._updater(options["updated_by"])
        if options["reset"]:
            FAQ.objects.filter(question__in=[question for _, question, _ in FAQS]).delete()
            PolicyPage.objects.filter(slug__in=[policy["slug"] for policy in POLICIES]).delete()

        policy_count = 0
        for policy in POLICIES:
            _, created = PolicyPage.objects.update_or_create(
                slug=policy["slug"],
                defaults={
                    "title": policy["title"],
                    "policy_type": policy["policy_type"],
                    "summary": policy["summary"],
                    "body": policy["body"],
                    "version": "1.0",
                    "is_published": True,
                    "updated_by": updater,
                },
            )
            policy_count += int(created)

        faq_count = 0
        for index, (category, question, answer) in enumerate(FAQS, start=1):
            _, created = FAQ.objects.update_or_create(
                question=question,
                defaults={
                    "category": category,
                    "answer": answer,
                    "is_published": True,
                    "sort_order": index * 10,
                },
            )
            faq_count += int(created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Support content ready: {len(POLICIES)} policies ({policy_count} new), "
                f"{len(FAQS)} FAQs ({faq_count} new)."
            )
        )

    def _updater(self, username):
        User = get_user_model()
        return User.objects.filter(username=username).first() or User.objects.filter(is_staff=True).first()

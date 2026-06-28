# Workflow Agency

Workflow Agency is a planned Django web system for mobile-first online jobs, referrals, wallet balances, M-Pesa deposits and withdrawals, surveys, ad watching, product commissions, game/app testing, paid chat sessions, and other admin-managed earning tasks.

The project will use Django function-based views, HTML templates, Bootstrap, vanilla JavaScript, PostgreSQL, Cloudinary, and Safaricom Daraja M-Pesa APIs.

## Current Status

This repository currently contains:

- Sample UI screenshots in `sample_UI/`
- A previous M-Pesa STK/C2B setup in `mpesa_config.py`, `mpesa_utils.py`, and `views.py`
- Initial product and architecture documentation in `docs/ARCHITECTURE_AND_DESIGN.txt`

The existing M-Pesa files are useful as a reference, but the final system should be built as a fresh Django project with separated apps for accounts, wallet, jobs, referrals, payments, products, and admin reporting.

## Important Hosting Note

Heroku is still a valid hosting option, but it is not truly free for Django apps with Postgres. Heroku removed free dynos and free Postgres plans starting November 28, 2022. The low-cost Heroku path is usually an Eco or Basic dyno plus a paid Heroku Postgres Essential plan. Cloudinary still has a free plan, with usage measured by monthly credits.

References:

- Heroku free plan removal: https://help.heroku.com/RSBRUH58/removal-of-heroku-free-product-plans-faq
- Heroku pricing: https://www.heroku.com/pricing/
- Heroku Postgres plans: https://devcenter.heroku.com/articles/heroku-postgres-plans
- Cloudinary billing and free plan: https://cloudinary.com/documentation/billing_and_plans
- Safaricom Daraja portal: https://developer.safaricom.co.ke/

## Product Vision

The system gives users one dashboard where they can:

- Register using username, phone number or email, plus password
- Stay locked until they pay the admin-defined activation fee
- Deposit or recharge through M-Pesa
- Claim available jobs while slots are still open
- Submit job proof for admin or automatic review
- Earn approved job rewards
- Earn referral bonuses from activated referrals
- Buy or access digital products and earn product commissions
- Request withdrawals only after meeting admin-defined rules
- View wallet history, referral tree, job history, product library, and profile data

The admin dashboard gives the business owner control over:

- Activation fee and referral bonus amounts
- Minimum withdrawal amount
- Job categories, job rewards, proof rules, expiry time, and worker limits
- User activation, suspension, KYC status, and fraud flags
- Deposits, withdrawal requests, M-Pesa reconciliation, and failed payments
- Platform revenue, wallet liabilities, pending rewards, and safe withdrawal capacity
- Digital products, commissions, announcements, and support links

## Financial Safety Principle

This system must not treat user wallet balances as company profit.

If the activation fee is shown back to the user as wallet balance, that amount is a user liability until the rules make it non-withdrawable or it is spent on platform products/services. Referral bonuses and job rewards must be funded from real platform revenue, client-funded tasks, product margins, ad income, or a clearly defined marketing budget.

The admin dashboard should always show:

- Confirmed M-Pesa cash received
- Total user wallet liability
- Pending job rewards
- Pending referral bonuses
- Pending withdrawal requests
- Platform revenue actually earned
- Available float after reserves
- Maximum withdrawals that can safely be paid today

Withdrawals should be blocked when the user is below the minimum withdrawal amount, the account is unverified or flagged, M-Pesa payout details are invalid, or the after-payout solvency check would fail. The solvency check should compare cash after the payout against wallet liabilities after the payout, plus the admin's required buffer and estimated M-Pesa fees.

## Recommended Tech Stack

- Backend: Django with function-based views
- Database: PostgreSQL
- Frontend: Django templates, HTML, Bootstrap 5, vanilla JavaScript
- Media storage: Cloudinary
- Static files: WhiteNoise on Heroku
- Payments: Safaricom Daraja STK Push, C2B confirmation, and B2C withdrawal payouts
- Server: Gunicorn on Heroku
- Background jobs: Prefer Celery/RQ or a database-backed queue with a Heroku worker. Python threading may be used only for short, non-critical, idempotent tasks. It should not be used for wallet posting, M-Pesa reconciliation, or withdrawals.

## Main Django Apps

Suggested app structure:

- `accounts`: custom user model, login by username/email/phone, profile, activation state, KYC, referral code
- `core`: site settings, finance settings, feature toggles, announcements, audit logs
- `wallets`: wallets, ledger transactions, balances, bonuses, adjustments
- `payments`: M-Pesa deposits, C2B callbacks, B2C withdrawals, reconciliation
- `jobs`: job categories, jobs, job claims, submissions, proof files, reviews
- `referrals`: referral tree, bonus rules, referral payouts
- `products`: digital products, purchases, downloads, product commissions
- `support`: tickets, FAQs, WhatsApp group links, support messages
- `reports`: admin analytics, revenue reports, solvency dashboard

## Core User Flow

1. User registers with username, phone number or email, password, and optional referral code.
2. Account is created as locked.
3. User pays the activation fee through M-Pesa STK Push or PayBill/C2B.
4. M-Pesa callback confirms the payment.
5. The system activates the account and posts ledger entries.
6. If the user had a valid referrer, the referral bonus is posted according to admin rules.
7. User can now claim jobs, buy products, invite referrals, and request withdrawals when eligible.
8. Admin can monitor revenue, liabilities, pending payouts, fraud flags, and payout safety before approving withdrawals.

## Job Claiming Flow

Each job has an admin-defined worker limit. A user can only claim a job while slots are available.

Example:

- Admin creates a survey job for 30 workers at KES 50 each.
- Each successful claim reserves one slot.
- When 30 users have claimed or completed the job, the job closes automatically.
- Admin can increase the worker limit, reopen the job, or clone/reactivate it as a new job.

The claim operation must be protected with a database transaction and row locking so two users cannot take the final slot at the same time.

## Suggested Job Catalog

All amounts are admin-configurable. These ranges are suggested starting values, not fixed promises.

| Job type | Suggested reward | Completion rule |
| --- | ---: | --- |
| Survey | KES 10-150 per approved survey | User answers all required questions; duplicate device/IP patterns can be flagged |
| Watch ad/video | KES 0.50-5 per verified view | Timer completes, video remains in focus, daily cap applies |
| Trivia/quiz | KES 2-20 per passed quiz | User scores above admin-defined pass mark |
| Blogging/social share | KES 5-40 per approved post/share | User submits URL or screenshot; admin verifies content still exists |
| App/game testing | KES 50-300 per report | User submits device info, screenshots, and useful feedback |
| Website feedback | KES 50-250 per review | User answers task checklist and submits screenshots |
| Data entry/tagging | KES 2-25 per batch | Admin or automatic validation confirms required accuracy |
| Transcription | KES 20-100 per short clip | Admin reviews text accuracy before approval |
| Translation | KES 20-200 per task | Admin reviews translation quality |
| Product review | KES 20-100 per approved review | User must have purchased or tested the product |
| Paid chat session | KES 20-150 per approved session | Only consenting verified clients; session duration and conduct rules apply |
| Product affiliate | Fixed amount or percent | Paid after product purchase is confirmed and reversal window passes |
| Referral activation | Fixed amount or percent | Paid only after referred user activation is confirmed and fraud checks pass |

## Wallet and Ledger Design

Use a ledger instead of directly editing balances. Every money movement should create an immutable ledger record.

Recommended wallet buckets:

- `available_balance`: money the user can withdraw, subject to rules
- `pending_balance`: rewards waiting for approval or reversal window
- `locked_balance`: activation credits, disputed rewards, or admin-held funds
- `withdrawn_total`: lifetime paid withdrawals
- `earned_total`: lifetime approved earnings

Recommended transaction types:

- Deposit initiated
- Deposit confirmed
- Activation credit
- Referral bonus pending
- Referral bonus available
- Job reward pending
- Job reward approved
- Product commission
- Withdrawal requested
- Withdrawal paid
- Withdrawal failed/reversed
- Admin adjustment
- Fraud hold

## M-Pesa Design

Deposits:

- STK Push for guided user payments
- C2B PayBill/Till as fallback
- Store `CheckoutRequestID`, `MerchantRequestID`, receipt number, amount, phone, account reference, raw callback, and status
- Make callbacks idempotent using unique receipt/request IDs
- Never credit wallet from a client-side response alone; credit only after trusted callback or reconciliation

Withdrawals:

- Use Daraja B2C where the business has approval and credentials
- If B2C is not ready, keep manual withdrawals with admin audit trail
- Lock the withdrawal amount when the request is created
- Pay only after admin approval, fraud checks, and platform solvency checks
- Mark success only from B2C result callback or verified manual receipt

## Admin Dashboard Reports

The admin dashboard should include:

- Today's deposits, withdrawals, job rewards, referral bonuses, product revenue, and net movement
- Total confirmed cash received
- Total user wallet liability
- Total pending withdrawals
- Total pending job rewards
- Total pending referral bonuses
- Safe withdrawal pool
- Reserve ratio
- Revenue by source
- Payouts by source
- Active users, locked users, suspended users, and flagged users
- Job fill rates and pending reviews
- M-Pesa failures and duplicate callback warnings

## Security Checklist

- Store all secrets in environment variables
- Do not commit M-Pesa consumer secrets, passkeys, security credentials, or Cloudinary secrets
- Use HTTPS in production
- Set `DEBUG=False` in production
- Use secure cookies and CSRF protection
- Keep M-Pesa callbacks public but idempotent, logged, and validated
- Rate-limit login, activation, job claim, and withdrawal endpoints
- Add admin audit logs for every finance setting and wallet adjustment
- Require strong passwords and consider OTP for withdrawals
- Use decimal money fields, never floats
- Add fraud detection for duplicate phone numbers, repeated devices, suspicious IPs, and impossible job completion times
- Export finance reports for external reconciliation

## Deployment Plan

Heroku deployment should include:

- `Procfile` with Gunicorn web process
- `requirements.txt`
- `runtime.txt` or `.python-version`
- `DATABASE_URL` from Heroku Postgres
- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, M-Pesa credentials, and Cloudinary credentials in Heroku config vars
- WhiteNoise for static files
- Cloudinary for uploaded proof files and product images
- Heroku worker dyno or scheduled management command for background processing

Because Heroku is not fully free, the client should budget for at least a small dyno plus a Postgres plan before production launch.

## Implementation Roadmap

Phase 1: Foundation

- Create Django project and apps
- Add custom user model with phone/email/username login
- Add Bootstrap app shell based on sample UI
- Add admin settings models

Phase 2: Wallet and activation

- Build wallet ledger
- Add activation payment flow through M-Pesa STK Push
- Add locked/unlocked account behavior
- Add referral code capture and first-level bonus rules

Phase 3: Jobs

- Add job categories, job creation, slot claiming, proof submission, review, approval, and reward posting
- Add worker limits and job reactivation/cloning

Phase 4: Withdrawals and reports

- Add withdrawal requests, minimum withdrawal rules, admin approval, B2C/manual payout workflow
- Add solvency dashboard and finance reports

Phase 5: Products, ads, chat sessions, and polish

- Add product store and product commissions
- Add ad watch timer rules
- Add paid chat session booking/session records
- Add anti-fraud checks, mobile UX improvements, and production monitoring

## Compliance Note

The product should pay users for real work, real purchases, real ad revenue, real client-funded tasks, or clearly funded promotions. Referral bonuses should be limited and transparent. A platform where old users are paid mainly from new users' activation fees can create serious legal, financial, and trust risk. The architecture therefore separates user liabilities, real revenue, expenses, and reserves so the business can remain sustainable.

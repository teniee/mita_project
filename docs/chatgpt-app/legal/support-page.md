# MITA Support — page draft for `https://{DOMAIN}/support`

Publishable once `{SUPPORT_EMAIL}` works (Step 2), the response time is
filled in, and a password-reset e-mail has been seen to arrive from
production: `mita-production` sets `SMTP_HOST/PORT/USERNAME/FROM` but not
`SMTP_PASSWORD`, which `app/core/config.py` reads (default empty) **[CONFIRM]**.
Every statement is backed by the code cited in the HTML comments; remove the
comments when publishing.

---

## MITA Support

**Contact:** {SUPPORT_EMAIL} — we reply within {RESPONSE_TIME} **[CONFIRM]**.
YAKOVLEV LTD (company no. 207808591), {POSTAL_ADDRESS}.

### Signing in

* Forgot your password? Tap **Forgot Password?** on the MITA sign-in screen.
  <!-- mobile_app: /forgot-password route, l10n "Forgot Password?"; API POST /forgot-password, /reset-password -->
  Changing your password signs you out of ChatGPT too.
* After 5 wrong passwords, sign-in pauses for 30 minutes. This applies to the
  app and to the ChatGPT connection page alike.
  <!-- app/services/credential_verification.py, app/api/auth/login.py: 5 failures → 30 min -->

### Deleting your account

In the MITA app: **Settings → Delete Account**. This deletes your account and
its data, including any ChatGPT connection. You can also e-mail
{SUPPORT_EMAIL} from the address you registered with.
<!-- user_settings_screen.dart "Delete Account" → DELETE /api/auth/delete-account; mcp_oauth_* rows cascade with the user (migration 0037) -->

### MITA in ChatGPT

**What it does.** ChatGPT works with your own MITA account: it can record and
correct expenses (also from a receipt photo you attach — ChatGPT reads it,
MITA never receives the image), save your income, currency, household size
and savings target, preview a monthly budget and save it after you review it,
add recurring expenses and savings goals, show your budget status, forecast
and spending history, and send feedback to the MITA team. Everything stays in
your MITA account for future conversations and the app.
<!-- app/mcp/tools: 22 tools; writes need the finance:write / feedback:write / profile:write scopes -->

**What it cannot do.** MITA cannot initiate, execute or facilitate payments,
money transfers or trades. MITA is not connected to your bank and does not
hold money. <!-- no bank/payment integration in app/ -->

**Connecting.** In ChatGPT, add **MITA Finance**, then sign in on the MITA page
— or choose **Create an account** — and approve. Accounts created with **Sign
in with Google** have no MITA password and cannot connect yet.
<!-- consent page: sign-in or sign-up; OWNER_ACTIONS O-16 -->

**Usage statistics.** Optional: which MITA features you use, never your
conversations or amounts. Say "stop sharing my usage statistics" in ChatGPT
to turn it off and delete what was linked to you.

**Disconnecting.** In ChatGPT: **Settings → Apps** (or Connectors) → **MITA
Finance** → Disconnect. Changing your MITA password also ends ChatGPT's
access immediately. <!-- credential_fingerprint + token_version checked on every call/refresh -->

**If something looks wrong.** Ask ChatGPT to list the expenses behind a figure;
you can correct or delete any expense there. MITA says so when it has no data
instead of estimating.

### Privacy and terms

[Privacy Policy](https://{DOMAIN}/privacy) · [Terms of Service](https://{DOMAIN}/terms)
· Data requests (access, correction, deletion, export): {PRIVACY_EMAIL}.

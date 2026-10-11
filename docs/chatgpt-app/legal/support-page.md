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

**What it does.** ChatGPT can read your own MITA data to answer questions:
spending and transactions, spending by category, your budget plan and how
you are tracking against it, a month-end projection, savings goals, and
scheduled or recurring expenses you entered.

**What it cannot do.** The connection is read-only. It cannot add, edit or
delete transactions or change your budget, and MITA cannot initiate, execute
or facilitate payments or money transfers. MITA is not connected to your
bank. <!-- app/mcp/tools: 8 tools, readOnlyHint true; no bank/payment integration in app/ -->

**What ChatGPT sees.** Only what your question needs: transaction dates,
amounts, currencies, categories and merchant names; budget totals; goal
titles and amounts; scheduled expenses; your display name, a masked e-mail
address, currency and time zone. Never your password, full e-mail address,
notes, receipt images or locations. <!-- app/mcp/serializers.py whitelist -->

**Connecting.** In ChatGPT, add **MITA Finance** and sign in on the MITA page
with your MITA e-mail and password, then choose **Allow read-only access**.
Accounts created with **Sign in with Google** have no MITA password and
cannot connect yet. <!-- consent page accepts e-mail/password only; OWNER_ACTIONS O-16 -->

**Disconnecting.** In ChatGPT: **Settings → Apps** (or Connectors) → **MITA
Finance** → Disconnect. Changing your MITA password also ends ChatGPT's
access immediately. <!-- credential_fingerprint + token_version checked on every call/refresh -->

**If an answer looks wrong.** Check the figure in the MITA app — it is the
source of truth. If MITA has no budget plan for a month yet, open the app
once that month; ChatGPT will say there is no plan rather than estimate one.
<!-- plan_status "not_generated"; the MCP service never writes -->

### Privacy and terms

[Privacy Policy](https://{DOMAIN}/privacy) · [Terms of Service](https://{DOMAIN}/terms)
· Data requests (access, correction, deletion, export): {PRIVACY_EMAIL}.

# SSL Certificate Pinning Setup Guide

## ⚠️ Current Status
Certificate pinning is **temporarily disabled** in tests until production domain is live.
- 2 tests are currently **skipped** (not failed)
- Certificate pinning is already disabled in debug mode (see `certificate_pinning_service.dart:48`)

## 📋 When to Configure Certificates

Configure SSL certificates BEFORE production deployment when:
1. ✅ Domain `api.mita.finance` is live and responding
2. ✅ SSL certificate is installed on the server
3. ✅ You're ready to deploy to App Store/Google Play

## 🔐 How to Get SSL Certificate Fingerprints

### Method 1: From Live Server (Recommended)

Once your domain is live, run this command:

```bash
# Get SHA-256 fingerprint from api.mita.finance
echo | openssl s_client -servername api.mita.finance -connect api.mita.finance:443 2>/dev/null | \
  openssl x509 -fingerprint -sha256 -noout

# Expected output:
# SHA256 Fingerprint=AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99
```

### Method 2: From Railway Deployment

If using Railway, get certificate from your Railway domain:

```bash
# Replace with your actual Railway domain
echo | openssl s_client -servername your-app.up.railway.app -connect your-app.up.railway.app:443 2>/dev/null | \
  openssl x509 -fingerprint -sha256 -noout
```

## 📝 How to Add Certificates

1. **Open** `mobile_app/lib/services/certificate_pinning_service.dart`

2. **Replace** the empty array with your fingerprints:

```dart
static const List<String> _pinnedCertificates = [
  // Primary certificate (api.mita.finance)
  'SHA256_FINGERPRINT_HERE',  // ← Paste fingerprint from step above
  
  // Backup certificate (in case of renewal)
  'SHA256_FINGERPRINT_BACKUP_HERE',  // ← Optional: second cert
];
```

3. **Example** with real fingerprints:

```dart
static const List<String> _pinnedCertificates = [
  'AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99',
  '11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF',
];
```

4. **Update tests** in `mobile_app/test/security_comprehensive_test.dart`:

Remove the `skip:` parameters from these 2 tests:
- Line 42: `test('Certificate pinning must be configured...', () {...}, skip: '...')`
- Line 483: `test('M3: Insecure Communication...', () {...}, skip: '...')`

Change to:
```dart
test('Certificate pinning must be configured with production certificates', () {
  // Test will now pass because certificates are configured
  expect(CertificatePinningService._pinnedCertificates.isNotEmpty, isTrue);
});
```

## ✅ Verification

After adding certificates, verify they work:

```bash
cd mobile_app
flutter test test/security_comprehensive_test.dart
```

Expected output:
```
00:01 +66: All tests passed!  # Was +64 ~2 before
```

## 🚨 Important Notes

1. **Certificate Expiry**: SSL certificates expire (usually after 90 days with Let's Encrypt)
   - Add BOTH current and backup certificates
   - Update before expiry to avoid app breaking

2. **Testing**: Test on real devices before production:
   ```bash
   flutter run --release
   ```

3. **Monitoring**: Watch for certificate renewal notifications from your hosting provider

## 📚 References

- Current implementation: `mobile_app/lib/services/certificate_pinning_service.dart`
- Security tests: `mobile_app/test/security_comprehensive_test.dart`
- OWASP Mobile Security: https://owasp.org/www-project-mobile-security-testing-guide/

---

**Status**: 🟡 Pending (configure when domain is live)  
**Priority**: 🔴 Critical (required before App Store/Play Store submission)  
**Impact**: High - Prevents MITM attacks on production API calls

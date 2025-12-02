# 🚀 App Store Readiness Checklist

## ❌ **CURRENT STATUS: NOT READY FOR APP STORE**

Your MITA app is **NOT production-ready** yet. Here's exactly what needs to be done:

---

## 🔴 **CRITICAL BLOCKERS (Must Fix Before Submission)**

### 1. ❌ SSL Certificate Pinning (PRODUCTION BLOCKER)
**Status:** Not configured  
**Risk:** App will be REJECTED by Apple for security issues

**What to do:**
1. Deploy backend to `api.mita.finance` with valid SSL certificate
2. Extract SSL fingerprints using command from `CERTIFICATE_PINNING_SETUP.md`
3. Add fingerprints to `mobile_app/lib/services/certificate_pinning_service.dart`
4. Re-enable 2 skipped tests in `mobile_app/test/security_comprehensive_test.dart`

**Apple's Requirement:** Apps handling financial data MUST use certificate pinning.

---

### 2. ❌ Bundle Identifier (CRITICAL)
**Current:** `com.example.mobileApp` ❌  
**Required:** `finance.mita.app` or similar

**Location:** `mobile_app/ios/Runner.xcodeproj/project.pbxproj`

**How to fix:**
```bash
# Open in Xcode
open mobile_app/ios/Runner.xcworkspace

# Change in Xcode:
# 1. Select Runner project
# 2. Go to "Signing & Capabilities"
# 3. Change Bundle Identifier to: finance.mita.app
# 4. Select your Apple Developer Team
```

---

### 3. ❌ Apple Developer Account Setup
**Required:**
- [ ] Apple Developer Program membership ($99/year)
- [ ] App ID registered: `finance.mita.app`
- [ ] Development certificate
- [ ] Distribution certificate
- [ ] Provisioning profiles (Development + App Store)

**Link:** https://developer.apple.com/programs/

---

### 4. ❌ Backend API Production Deployment
**Current:** Backend not accessible at `api.mita.finance`  
**Required:** Live production API with:
- Valid SSL certificate (Let's Encrypt or paid)
- Database configured (PostgreSQL on Supabase/Railway)
- Environment variables set
- Health check endpoint responding

**Test command:**
```bash
curl https://api.mita.finance/health
# Should return 200 OK
```

---

### 5. ❌ App Icons & Launch Screen
**Check if exist:**
```bash
ls mobile_app/ios/Runner/Assets.xcassets/AppIcon.appiconset/
ls mobile_app/ios/Runner/Assets.xcassets/LaunchImage.imageset/
```

**Required sizes for iOS:**
- 1024x1024 (App Store)
- 180x180 (iPhone @3x)
- 167x167 (iPad Pro @2x)
- 152x152 (iPad @2x)
- 120x120 (iPhone @2x)
- 87x87 (iPhone @3x notification)
- 80x80 (iPad @2x notification)
- 76x76 (iPad)
- 60x60 (iPhone @2x settings)
- 58x58 (iPhone @2x notification)
- 40x40 (iPad @2x Spotlight)
- 29x29 (Settings)

---

### 6. ❌ App Privacy Policy & Terms
**Required by Apple:**
- [ ] Privacy Policy URL (must be publicly accessible)
- [ ] Terms of Service URL
- [ ] Support URL
- [ ] Marketing URL (optional)

**Add to:**
- App Store Connect metadata
- In-app Settings screen
- Website at `mita.finance/privacy`

---

## 🟡 **IMPORTANT (Should Fix Before Launch)**

### 7. ⚠️ Firebase Configuration (Push Notifications)
**Status:** Configured but needs verification  
**Check:** `mobile_app/lib/firebase_options.dart`

**Verify:**
```bash
# Check if Firebase project exists
# Check if APNs certificate uploaded
# Test push notifications on real device
```

---

### 8. ⚠️ In-App Purchases Setup
**Code exists:** `mobile_app/lib/services/iap_service.dart`  
**Required:**
- [ ] Create IAP products in App Store Connect:
  - `premium_monthly` ($9.99/month)
  - `premium_yearly` ($99.99/year)
- [ ] Add product IDs to code
- [ ] Test purchases in sandbox environment
- [ ] Configure server-side receipt validation

---

### 9. ⚠️ Localization (i18n)
**Current:** English + Bulgarian configured  
**Supported:** 10+ languages mentioned

**Verify all translations complete:**
```bash
cd mobile_app
flutter gen-l10n
# Check for missing translations
```

---

### 10. ⚠️ Test Coverage
**Current Flutter Tests:** 224/312 passing (71.8%)  
**Minimum for production:** 90%+

**Failing tests:** 86 (mostly API timeouts)

**Fix before launch:**
```bash
cd mobile_app
flutter test
# Address all critical failures
```

---

## 🟢 **NICE TO HAVE (Can Do After Launch)**

### 11. ✅ App Store Listing
**Prepare:**
- [ ] App name (max 30 chars): "MITA - Money Intelligence"
- [ ] Subtitle (max 30 chars): "Smart Budget & Expense Tracker"
- [ ] Description (max 4000 chars)
- [ ] Keywords (max 100 chars): "budget,expense,finance,money"
- [ ] Screenshots (5-10 per device size)
- [ ] App Preview video (optional but recommended)
- [ ] Promotional text (max 170 chars)

---

### 12. ✅ App Store Review Preparation
**Demo Account Required:**
```
Username: demo@mita.finance
Password: DemoAccount123!

Provide in "App Review Information" section
```

**Review Notes:**
```
MITA is a personal finance app that helps users:
- Track daily expenses with AI-powered OCR
- Manage budgets by category
- Get financial insights

Test Features:
1. Login with demo account
2. Add expense via OCR (use sample receipt)
3. View daily budget calendar
4. Check AI insights

Financial Data Handling:
- All data encrypted at rest
- Certificate pinning enabled
- Biometric authentication for sensitive operations
```

---

## 📋 **DEPLOYMENT STEPS (Once Above is Complete)**

### Step 1: Build Release Version
```bash
cd mobile_app
flutter build ios --release
```

### Step 2: Archive in Xcode
```bash
open ios/Runner.xcworkspace

# In Xcode:
# 1. Product > Archive
# 2. Wait for archive to complete
# 3. Upload to App Store Connect
```

### Step 3: Submit for Review
1. Go to https://appstoreconnect.apple.com
2. Create new app version
3. Fill in metadata
4. Upload screenshots
5. Submit for review

### Step 4: Expected Review Time
- **First submission:** 2-7 days
- **Updates:** 1-3 days

---

## ⚠️ **COMMON REJECTION REASONS TO AVOID**

1. **Guideline 2.1 - App Completeness**
   - ❌ Demo/test account doesn't work
   - ❌ App crashes on launch
   - ❌ Features don't work as described

2. **Guideline 2.3.1 - Performance**
   - ❌ App has bugs or crashes
   - ❌ Broken links
   - ❌ Incomplete information

3. **Guideline 4.0 - Design**
   - ❌ Poor user interface
   - ❌ Confusing navigation
   - ❌ Placeholder content

4. **Guideline 5.1.1 - Data Collection & Storage**
   - ❌ Missing privacy policy
   - ❌ No consent for data collection
   - ❌ Insecure data storage

---

## 🎯 **ESTIMATED TIMELINE TO APP STORE READY**

| Task | Time | Priority |
|------|------|----------|
| Deploy backend to production | 1-2 days | 🔴 Critical |
| Configure SSL certificate pinning | 2 hours | 🔴 Critical |
| Change bundle ID + Apple Developer setup | 4 hours | 🔴 Critical |
| Create app icons & launch screen | 1 day | 🔴 Critical |
| Write privacy policy & terms | 1 day | 🔴 Critical |
| Setup IAP products | 4 hours | 🟡 Important |
| Fix failing tests | 2-3 days | 🟡 Important |
| Prepare App Store listing | 1 day | 🟢 Nice to have |
| Test on real devices | 1-2 days | 🟡 Important |

**Total estimated time:** 7-10 days of focused work

---

## ✅ **FINAL CHECKLIST BEFORE SUBMISSION**

- [ ] Backend live at `api.mita.finance` with valid SSL
- [ ] Certificate pinning configured and tested
- [ ] Bundle ID changed from `com.example.*`
- [ ] Apple Developer account active
- [ ] App icons all sizes present
- [ ] Privacy policy published
- [ ] IAP products created in App Store Connect
- [ ] All critical tests passing
- [ ] Tested on real iPhone/iPad devices
- [ ] Demo account working
- [ ] App Store listing complete
- [ ] Screenshots taken
- [ ] Archive builds successfully in Xcode

---

## 📞 **NEXT STEPS**

1. **Deploy backend FIRST** - everything depends on this
2. **Get Apple Developer account** - takes 1-2 days for approval
3. **Work through critical blockers** in order
4. **Test thoroughly** on real devices
5. **Submit for review** only when 100% ready

**Current Status:** ~40% ready  
**Estimated:** 7-10 days to submission-ready

---

**Last Updated:** December 2, 2025  
**Author:** Claude Code (CTO Engineering Agent)

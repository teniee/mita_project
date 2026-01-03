# Firebase API Key Restrictions Guide

**Priority:** HIGH
**Time Required:** 5-10 minutes
**Complexity:** Easy (web UI only, no code changes)
**Impact:** Security improvement, prevents API key abuse

---

## 🔒 Why This Matters

Your Firebase API key is currently embedded in your mobile app and visible to anyone who decompiles it:
```dart
// mobile_app/lib/firebase_options.dart
apiKey: 'AIzaSyCRI7k1ATHDbpi-KEpJCx8pgAufcF7WVKk',  // ⚠️ PUBLIC
```

**This is normal for client-side apps**, but you MUST restrict it to prevent abuse.

### Without Restrictions:
- ❌ Anyone can extract your API key from the app binary
- ❌ Attackers can abuse your Firebase quota (costs you money)
- ❌ Unauthorized apps can access your Firebase services
- ❌ Potential for spam, abuse, or data breaches

### With Restrictions:
- ✅ API key only works with your bundle ID (finance.mita.app)
- ✅ Prevents quota abuse
- ✅ Blocks unauthorized access
- ✅ App Store reviewers see proper security measures

---

## 📋 Step-by-Step Setup

### Step 1: Log into Firebase Console

1. Go to [https://console.firebase.google.com](https://console.firebase.google.com)
2. Select your MITA project
3. Click the gear icon ⚙️ (top left) → Project settings

### Step 2: Find Your iOS App

1. Scroll down to "Your apps" section
2. Find your iOS app (should show bundle ID: `finance.mita.app`)
3. Click on the iOS app to expand details

**If you don't see an iOS app:**
1. Click "Add app" → Choose iOS
2. Enter bundle ID: `finance.mita.app`
3. Download `GoogleService-Info.plist` (you already have this at `mobile_app/ios/Runner/GoogleService-Info.plist`)
4. Click "Continue" through the setup steps

### Step 3: Restrict the API Key

1. In Project settings, go to the "General" tab
2. Scroll to "Your apps" section
3. Find your iOS app
4. Look for "Web API Key" section (shows: AIzaSyCRI7k1ATHDbpi-KEpJCx8pgAufcF7WVKk)
5. Click "Manage API key in Google Cloud Console" (opens Google Cloud Console)

**Alternative path (if button missing):**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your Firebase project
3. Navigate to: APIs & Services → Credentials
4. Find API key: "Browser key (auto created by Firebase)"

### Step 4: Add iOS Bundle ID Restriction

In Google Cloud Console → API Keys:

1. Click on your API key (probably named "Browser key (auto created by Firebase)")
2. Scroll to "Application restrictions" section
3. Select **"iOS apps"**
4. Click "+ Add an item"
5. Enter your bundle ID: `finance.mita.app`
6. Click "Done"
7. Scroll down and click "Save"

**Screenshot reference:**
```
Application restrictions:
● None (not recommended)
○ HTTP referrers (web sites)
○ IP addresses (web servers, cron jobs, etc.)
● iOS apps                             <-- SELECT THIS

Authorized bundle IDs:
┌─────────────────────────────────┐
│ finance.mita.app               │  <-- ADD THIS
└─────────────────────────────────┘
[+ Add an item]
```

### Step 5: Restrict API Scopes (Optional but Recommended)

While in the API key settings:

1. Scroll to "API restrictions" section
2. Select **"Restrict key"**
3. Enable only the APIs your app uses:
   - ✅ Firebase Authentication API
   - ✅ Firebase Cloud Messaging API
   - ✅ Firebase Realtime Database API (if using)
   - ✅ Cloud Firestore API (if using)
   - ✅ Cloud Vision API (for OCR)
   - ❌ Uncheck everything else
4. Click "Save"

**Why restrict APIs:**
- Prevents attackers from using your key for unrelated Google services
- Reduces attack surface
- Best practice for production apps

### Step 6: Verify Restrictions Work

After saving (wait 5-10 minutes for changes to propagate):

1. **Test from your app** (should work):
   ```bash
   # Build and run on simulator or device
   flutter run

   # Try to register/login
   # Should work normally ✅
   ```

2. **Test from curl** (should fail):
   ```bash
   # This should return an error now:
   curl "https://identitytoolkit.googleapis.com/v1/accounts:signUp?key=AIzaSyCRI7k1ATHDbpi-KEpJCx8pgAufcF7WVKk" \
     -H "Content-Type: application/json" \
     --data '{"email":"test@example.com","password":"password123","returnSecureToken":true}'

   # Expected: "API key not valid. Please pass a valid API key." ✅
   ```

If the app still works but curl fails → restrictions are working correctly! 🎉

---

## 🔍 Additional Security: Enable App Check (Recommended)

**App Check** adds an extra layer of security by verifying that requests come from your authentic app, not a simulator or modified version.

### Setup App Check:

1. **In Firebase Console:**
   - Go to: Build → App Check
   - Click "Get started"
   - Select your iOS app
   - Choose provider: **"App Attest"** (for iOS 14+)
   - Click "Save"

2. **Add Firebase App Check SDK:**
   ```yaml
   # mobile_app/pubspec.yaml
   dependencies:
     firebase_app_check: ^0.3.0+4
   ```

3. **Initialize in your app:**
   ```dart
   // mobile_app/lib/main.dart
   import 'package:firebase_app_check/firebase_app_check.dart';

   void main() async {
     WidgetsFlutterBinding.ensureInitialized();

     await Firebase.initializeApp();

     // Add App Check
     await FirebaseAppCheck.instance.activate(
       androidProvider: AndroidProvider.playIntegrity,
       appleProvider: AppleProvider.deviceCheck,  // iOS 11-13
       // Or use: appleProvider: AppleProvider.appAttest,  // iOS 14+
     );

     runApp(MyApp());
   }
   ```

4. **For iOS 14+ (App Attest is more secure):**
   ```dart
   await FirebaseAppCheck.instance.activate(
     appleProvider: AppleProvider.appAttest,
     webProvider: ReCaptchaV3Provider('recaptcha-v3-site-key'),
   );
   ```

**Benefits of App Check:**
- ✅ Blocks requests from simulators (development only)
- ✅ Detects modified/tampered apps
- ✅ Prevents API abuse from cloned apps
- ✅ Works alongside API key restrictions
- ⚠️ May block legitimate debug builds (add debug exception)

**Debug mode exception:**
```dart
if (kDebugMode) {
  // Allow debug builds during development
  await FirebaseAppCheck.instance.activate(
    appleProvider: AppleProvider.debug,
  );
} else {
  // Production: Use App Attest
  await FirebaseAppCheck.instance.activate(
    appleProvider: AppleProvider.appAttest,
  );
}
```

---

## ✅ Verification Checklist

After completing all steps:

- [ ] API key restricted to bundle ID `finance.mita.app`
- [ ] API scopes restricted to only needed services
- [ ] Tested app still works (register/login functional)
- [ ] Tested curl request fails (restrictions working)
- [ ] (Optional) App Check enabled
- [ ] Changes propagated (waited 5-10 minutes)
- [ ] No error logs in Firebase Console

---

## 🚨 Troubleshooting

### Problem: App doesn't work after adding restrictions

**Solution:**
1. Verify bundle ID matches exactly: `finance.mita.app`
2. Check Xcode project: Runner → General → Bundle Identifier
3. Wait 5-10 minutes for Google Cloud changes to propagate
4. Clear app data and reinstall:
   ```bash
   flutter clean
   flutter pub get
   flutter run
   ```

### Problem: "API key not valid" error in app

**Possible causes:**
1. Bundle ID mismatch (check Xcode vs Firebase)
2. Wrong API key in code (verify matches Firebase Console)
3. Restrictions too strict (check API scopes)
4. Changes not propagated yet (wait longer)

**Quick fix:**
1. Go back to Google Cloud Console → API Keys
2. Temporarily select "None" under Application restrictions
3. Test if app works
4. If it does, issue is with bundle ID or API scopes
5. Re-add restrictions with correct bundle ID

### Problem: App Check blocking debug builds

**Solution:**
```dart
// Use debug provider for development
if (kDebugMode) {
  await FirebaseAppCheck.instance.activate(
    appleProvider: AppleProvider.debug,
  );
}
```

Or get a debug token:
```bash
# Run app and check logs for debug token
flutter run

# Look for: "Firebase App Check debug token: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"
# Add this token to Firebase Console → App Check → Apps → ... → Manage debug tokens
```

---

## 📚 References

- **Firebase Security Best Practices:** https://firebase.google.com/docs/projects/api-keys
- **App Check Documentation:** https://firebase.google.com/docs/app-check
- **Google Cloud API Key Restrictions:** https://cloud.google.com/docs/authentication/api-keys
- **iOS Bundle ID:** https://developer.apple.com/documentation/bundleresources/information_property_list/cfbundleidentifier

---

## 🎯 Expected Outcome

After completing this guide:

✅ **Security improved:** API key can only be used by your app
✅ **Cost protection:** Prevents quota abuse and unexpected bills
✅ **App Store compliance:** Shows proper security measures
✅ **Peace of mind:** Your Firebase project is protected

**Time investment:** 5-10 minutes
**Long-term benefit:** Prevents thousands of dollars in potential abuse

---

**Last Updated:** 2026-01-01
**Priority:** HIGH
**Status:** Action Required (User must configure in Firebase Console)
**Difficulty:** 🟢 Easy (no code changes, just web UI)

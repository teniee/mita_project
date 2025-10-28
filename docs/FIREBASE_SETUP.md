# Firebase Cloud Messaging Setup Guide

## Current Configuration

Your Google credentials are configured at:
```
/app/config/google-vision-credentials.json
```

## Environment Variable Setup

Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to point to your Firebase service account JSON file:

### Option 1: Using .env file (Development)
```bash
GOOGLE_APPLICATION_CREDENTIALS=/app/config/google-vision-credentials.json
```

### Option 2: Using Render.com Environment Variables (Production)
1. Go to your Render dashboard
2. Navigate to your web service
3. Go to "Environment" tab
4. Add environment variable:
   - **Key:** `GOOGLE_APPLICATION_CREDENTIALS`
   - **Value:** `/app/config/google-vision-credentials.json`

## Firebase Service Account Requirements

Your service account JSON file **MUST** have the following permissions for FCM to work:

### Required Roles
- ✅ **Firebase Cloud Messaging Admin** (or equivalent)
- ✅ **Firebase Admin SDK Administrator Service Agent**

### JSON File Structure
The file should contain:
```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "firebase-adminsdk-xxxxx@your-project.iam.gserviceaccount.com",
  "client_id": "...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "..."
}
```

## Verify Your Credentials File

### Check if file exists:
```bash
ls -la /app/config/google-vision-credentials.json
```

### Check file permissions:
```bash
# File should be readable by the app user
chmod 600 /app/config/google-vision-credentials.json
```

### Verify JSON is valid:
```bash
cat /app/config/google-vision-credentials.json | python -m json.tool
```

## Create New Firebase Service Account (If Needed)

If your current credentials don't have FCM permissions, create a new service account:

1. **Go to Firebase Console:**
   - https://console.firebase.google.com/
   - Select your project

2. **Navigate to Project Settings:**
   - Click gear icon → Project settings
   - Go to "Service accounts" tab

3. **Generate New Private Key:**
   - Click "Generate new private key"
   - Download the JSON file
   - This file contains all necessary permissions for FCM

4. **Upload to Your Server:**
   ```bash
   # Via Render Shell or deployment
   mkdir -p /app/config
   # Upload your downloaded file as google-vision-credentials.json
   ```

5. **Set Permissions:**
   ```bash
   chmod 600 /app/config/google-vision-credentials.json
   chown mita:mita /app/config/google-vision-credentials.json  # If using mita user
   ```

## Testing FCM Connection

After configuring credentials, test the connection:

### Method 1: Using Test Endpoint
```bash
curl -X POST https://your-app.onrender.com/api/notifications/test \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Test notification from MITA"
  }'
```

### Method 2: Check Application Logs
Look for these log messages on startup:
```
✅ Good: "Firebase initialized successfully"
❌ Bad: "Failed to initialize Firebase with credentials"
```

### Method 3: Python Script Test
```python
from firebase_admin import credentials, initialize_app, messaging

# Initialize
cred = credentials.Certificate('/app/config/google-vision-credentials.json')
app = initialize_app(cred)

# Test send
message = messaging.Message(
    notification=messaging.Notification(
        title='Test',
        body='Firebase is working!'
    ),
    token='YOUR_DEVICE_TOKEN'
)

response = messaging.send(message)
print(f"Successfully sent message: {response}")
```

## Common Issues & Solutions

### Issue 1: "Application Default Credentials not found"
**Solution:** Set `GOOGLE_APPLICATION_CREDENTIALS` environment variable correctly.

### Issue 2: "Permission denied"
**Solution:** Check file permissions with `chmod 600`

### Issue 3: "Invalid service account"
**Solution:** Make sure the JSON file is from Firebase (not Google Cloud Vision API)

### Issue 4: "Project ID mismatch"
**Solution:** Verify `project_id` in JSON matches your Firebase project

### Issue 5: FCM sends but devices don't receive
**Solutions:**
- Check device token is valid and not expired
- Verify Firebase project has Cloud Messaging enabled
- Check device has notification permissions
- Verify app's package name matches Firebase configuration

## Firebase Console Settings

Enable Cloud Messaging API:
1. Go to https://console.cloud.google.com/
2. Select your Firebase project
3. Navigate to "APIs & Services" → "Library"
4. Search for "Firebase Cloud Messaging API"
5. Click "Enable"

## Security Best Practices

1. **Never commit credentials to Git:**
   ```bash
   # Add to .gitignore
   echo "config/google-vision-credentials.json" >> .gitignore
   ```

2. **Rotate keys regularly:**
   - Generate new service account key every 90 days
   - Delete old keys from Firebase Console

3. **Use separate service accounts:**
   - Development: Use sandbox Firebase project
   - Production: Use production Firebase project
   - Never share credentials between environments

4. **Limit permissions:**
   - Service account should only have FCM permissions
   - Don't use owner/editor roles

## Integration with MITA Notifications

Once Firebase is configured, notifications will work automatically:

1. **User registers device:**
   ```dart
   // Flutter automatically registers on login
   await SecurePushTokenManager.instance.initializePostAuthentication();
   ```

2. **Backend sends notification:**
   ```python
   from app.services.notification_service import send_budget_alert

   notification = send_budget_alert(
       db=db,
       user_id=user.id,
       budget_name="Groceries",
       spent_amount=450.00,
       budget_limit=500.00,
       percentage=90.0,
   )
   ```

3. **FCM delivers to device:**
   - Push notification appears on user's device
   - Notification stored in database
   - Delivery logged for analytics

## Troubleshooting Commands

### Check environment variable:
```bash
echo $GOOGLE_APPLICATION_CREDENTIALS
```

### Test Firebase initialization:
```python
import firebase_admin
from firebase_admin import credentials

print(f"Apps: {firebase_admin._apps}")
print(f"Default app: {firebase_admin.get_app()}")
```

### View Firebase logs:
```bash
# In Render logs, search for:
grep -i "firebase" /var/log/app.log
```

## Alternative: Use Environment Variable for JSON Content

Instead of file path, you can set the entire JSON as environment variable:

```bash
# Set as env var (single line, escaped)
FIREBASE_CREDENTIALS='{"type":"service_account","project_id":"...","private_key":"..."}'
```

Then update `push_service.py` to use:
```python
import json
import os

if os.getenv('FIREBASE_CREDENTIALS'):
    cred_dict = json.loads(os.getenv('FIREBASE_CREDENTIALS'))
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)
```

## Contact & Support

- Firebase Documentation: https://firebase.google.com/docs/cloud-messaging
- Firebase Status: https://status.firebase.google.com/
- Google Cloud Support: https://cloud.google.com/support

---

**Last Updated:** 2025-10-28
**Module:** 10 - Notifications
**Version:** 1.0

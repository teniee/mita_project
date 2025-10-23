# Google Vision API Setup Guide

This guide will help you configure Google Vision API for premium OCR functionality in MITA.

## Prerequisites

- Google Cloud Platform account
- Project created in Google Cloud Console
- Billing enabled on the project

## Step 1: Enable Cloud Vision API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project: `mita-finance-photo-recognition`
3. Navigate to **APIs & Services** → **Library**
4. Search for "Cloud Vision API"
5. Click **Enable**

## Step 2: Create Service Account

1. Navigate to **IAM & Admin** → **Service Accounts**
2. Click **Create Service Account**
3. Fill in details:
   - **Name**: `mita-ocr-service`
   - **Description**: `Service account for MITA OCR processing`
4. Click **Create and Continue**

## Step 3: Assign Permissions

1. In the "Grant this service account access to project" section:
   - Add role: **Cloud Vision API User**
   - (Optional) Add role: **Storage Object Viewer** if using Cloud Storage
2. Click **Continue**
3. Click **Done**

## Step 4: Generate JSON Key

1. Find your newly created service account in the list
2. Click on the service account name
3. Go to the **Keys** tab
4. Click **Add Key** → **Create new key**
5. Select **JSON** format
6. Click **Create**
7. The JSON key file will be downloaded automatically

**IMPORTANT**: The downloaded file should look like this:
```json
{
  "type": "service_account",
  "project_id": "mita-finance-photo-recognition",
  "private_key_id": "abc123...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "mita-ocr-service@mita-finance-photo-recognition.iam.gserviceaccount.com",
  "client_id": "123456789...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/..."
}
```

**NOTE**: This is NOT the same as OAuth client credentials. The key must have `"type": "service_account"`.

## Step 5: Configure in Render

### Option A: Using Secret Files (Recommended)

1. Go to your Render Dashboard
2. Select your service: `mita-docker-ready-project-manus`
3. Navigate to **Environment** tab
4. Scroll to **Secret Files** section
5. Click **Add Secret File**
6. Configure:
   - **Filename**: `/app/config/google-vision-credentials.json`
   - **Contents**: Paste the entire JSON key content
7. Click **Save**

### Option B: Using Environment Variable

1. In Render Dashboard → **Environment** tab
2. Add environment variable:
   - **Key**: `GOOGLE_APPLICATION_CREDENTIALS`
   - **Value**: `/app/config/google-vision-credentials.json`
3. Click **Save Changes**

**NOTE**: If you used Option A, this environment variable should be automatically set.

## Step 6: Verify Configuration

After deployment completes, verify the setup:

### Check Logs
Look for these indicators in Render logs:
- No errors about missing credentials
- Google Vision API client initializes successfully

### Test API Endpoint

```bash
# Upload a receipt for premium OCR
curl -X POST "https://mita-docker-ready-project-manus.onrender.com/api/v1/ocr/process" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@receipt.jpg"
```

Expected response should include:
```json
{
  "status": "success",
  "data": {
    "result": {
      "merchant": "Kaufland",
      "amount": 42.50,
      "confidence": 0.85,
      "confidence_scores": {
        "merchant": 0.9,
        "amount": 0.85,
        "date": 0.8,
        "category": 0.7,
        "items": 0.75,
        "overall": 0.85
      },
      "fields_needing_review": [],
      "image_url": "/receipts/user_1/ocr_abc123_20241023_143022.jpg"
    }
  }
}
```

## Troubleshooting

### Error: "Could not automatically determine credentials"

**Cause**: Credentials file not found or environment variable not set.

**Solution**:
1. Verify Secret File path is exactly: `/app/config/google-vision-credentials.json`
2. Verify environment variable `GOOGLE_APPLICATION_CREDENTIALS` points to correct path
3. Check Render logs for file creation errors

### Error: "Permission denied"

**Cause**: Service account doesn't have correct permissions.

**Solution**:
1. Go to IAM & Admin → Service Accounts
2. Find your service account
3. Edit permissions and add "Cloud Vision API User" role

### Error: "API has not been used in project before"

**Cause**: Cloud Vision API not enabled.

**Solution**:
1. Go to APIs & Services → Library
2. Search "Cloud Vision API"
3. Click Enable

### Error: "Quota exceeded"

**Cause**: Free tier limits reached (1000 requests/month).

**Solution**:
1. Enable billing in Google Cloud Console
2. Set up billing alerts to monitor usage
3. Consider implementing request caching

## Cost Management

### Free Tier (First 1,000 units/month)
- Text detection: Free
- Document text detection: Free

### Paid Tier (After 1,000 units)
- Text detection: $1.50 per 1,000 units
- Document text detection: $3.00 per 1,000 units

### Tips to Reduce Costs
1. Use Tesseract OCR for non-premium users (already implemented)
2. Implement caching for repeated images
3. Set up billing alerts in Google Cloud Console
4. Monitor usage in Cloud Console → Billing

## Testing Checklist

- [ ] Cloud Vision API enabled in Google Cloud Console
- [ ] Service account created with correct permissions
- [ ] JSON key downloaded (type: "service_account")
- [ ] Secret File added to Render with correct path
- [ ] Environment variable set (if needed)
- [ ] Render service redeployed
- [ ] No credential errors in logs
- [ ] Test OCR request successful
- [ ] Confidence scores present in response
- [ ] Image stored successfully

## Premium vs Free OCR

The system automatically routes OCR requests:

- **Premium Users** (is_premium_user=true): Google Vision API
  - Higher accuracy (95%+)
  - Better with complex receipts
  - Multi-language support
  - Costs per request after free tier

- **Free Users**: Tesseract OCR
  - Good accuracy (75-85%)
  - Free and unlimited
  - Works offline
  - Already configured and working ✅

## Support

If you encounter issues:
1. Check Render deployment logs
2. Verify credentials format matches example above
3. Test with a simple receipt image first
4. Review Google Cloud Console for API errors

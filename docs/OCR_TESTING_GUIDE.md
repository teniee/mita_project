# OCR Module Testing Guide

This guide provides comprehensive testing instructions for the MITA OCR receipt processing module.

## Quick Status Check

### ✅ Completed Components

1. **Tesseract OCR** - Installed and configured in Docker
2. **Confidence Scoring** - Real heuristic-based scoring algorithm
3. **Persistent Image Storage** - Local filesystem with TTL cleanup
4. **Enhanced Categorization** - Bulgarian merchant database
5. **Dual OCR Engine** - Tesseract (free) vs Google Vision (premium)
6. **API Endpoints** - Process, retrieve, and delete receipt images

### ⏳ Pending Setup

1. **Google Vision API Credentials** - See `GOOGLE_VISION_SETUP.md`

## Testing Tesseract OCR (Free Tier)

### 1. Prepare Test Receipt

Create a test receipt image with clear text:
```
Kaufland
Sofia, Bulgaria
Date: 23/10/2024

Milk           2.50
Bread          1.20
Cheese         4.30
---------------
TOTAL:         8.00

Thank you!
```

Save as `test_receipt.jpg` with clear, readable text.

### 2. Test via API

#### Get JWT Token First

```bash
# Login to get token
curl -X POST "https://mita-docker-ready-project-manus.onrender.com/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your_email@example.com",
    "password": "your_password"
  }'
```

Response includes `access_token` - use this for subsequent requests.

#### Upload Receipt for OCR Processing

```bash
curl -X POST "https://mita-docker-ready-project-manus.onrender.com/api/v1/ocr/process" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@test_receipt.jpg"
```

#### Expected Response

```json
{
  "status": "success",
  "data": {
    "job_id": "ocr_1_1729684822",
    "status": "completed",
    "result": {
      "merchant": "Kaufland",
      "amount": 8.0,
      "date": "2024-10-23",
      "category": "groceries",
      "items": [
        {"name": "Milk", "price": 2.5},
        {"name": "Bread", "price": 1.2},
        {"name": "Cheese", "price": 4.3}
      ],
      "confidence": 0.75,
      "confidence_scores": {
        "merchant": 0.8,
        "amount": 0.85,
        "date": 0.7,
        "category": 0.8,
        "items": 0.65,
        "overall": 0.75
      },
      "fields_needing_review": ["date"],
      "image_url": "/receipts/user_1/ocr_1_1729684822_20241023_143022.jpg"
    }
  }
}
```

### 3. Verify Image Storage

```bash
# List user's receipt images
curl -X GET "https://mita-docker-ready-project-manus.onrender.com/api/v1/ocr/images" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Expected response:
```json
{
  "status": "success",
  "data": {
    "images": [
      {
        "filename": "ocr_1_1729684822_20241023_143022.jpg",
        "path": "/app/data/receipts/user_1/ocr_1_1729684822_20241023_143022.jpg",
        "url": "/receipts/user_1/ocr_1_1729684822_20241023_143022.jpg",
        "size": 125670,
        "created_at": "2024-10-23T14:30:22",
        "modified_at": "2024-10-23T14:30:22"
      }
    ],
    "total": 1
  }
}
```

### 4. Retrieve Receipt Image

```bash
# Download the image
curl -X GET "https://mita-docker-ready-project-manus.onrender.com/api/v1/ocr/image/ocr_1_1729684822" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  --output downloaded_receipt.jpg
```

### 5. Check Transaction Created

```bash
# Get recent transactions
curl -X GET "https://mita-docker-ready-project-manus.onrender.com/api/v1/transactions?limit=10" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Verify that a transaction was created with:
- Amount: 8.0
- Category: "groceries"
- Description: "Receipt from Kaufland (confidence: 75%)"

## Testing Google Vision OCR (Premium)

**Prerequisites**: Complete Google Vision API setup (see `GOOGLE_VISION_SETUP.md`)

### 1. Verify Premium User Status

```bash
curl -X GET "https://mita-docker-ready-project-manus.onrender.com/api/v1/users/me" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Check `is_premium_user` field in response.

### 2. Upload Receipt (Same as Tesseract)

The API automatically routes premium users to Google Vision:

```bash
curl -X POST "https://mita-docker-ready-project-manus.onrender.com/api/v1/ocr/process" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@test_receipt.jpg"
```

### 3. Expected Differences

Google Vision should provide:
- **Higher confidence scores** (typically 0.85-0.95)
- **Better merchant recognition** (handles complex fonts)
- **More accurate item extraction** (handles receipts with logos, stamps)
- **Multi-language support** (Cyrillic, Latin, mixed)

## Testing with Real Bulgarian Receipts

### Common Bulgarian Merchants

Test receipts from these stores (included in categorization database):

- **Groceries**: Kaufland, Lidl, Billa, Fantastico, Metro, Carrefour
- **Pharmacies**: Sophарма (Sofarma), аптеки
- **Gas Stations**: Lukoil, OMV, EKO, Rompetrol
- **Transport**: Metro, bus tickets, Bolt

### Example Bulgarian Receipt

```
КАУФЛАНД
ул. Граф Игнатиев 2
София 1000

Дата: 23.10.2024
Час: 14:30

Хляб               1.20лв
Мляко              2.50лв
Сирене             4.30лв
-----------------------
ОБЩО:              8.00лв

Благодарим!
```

Expected categorization: "groceries"

## Testing Edge Cases

### 1. Low Quality Image

Test with:
- Blurry photo
- Poor lighting
- Crumpled receipt
- Faded text

Expected:
- Lower confidence scores (< 0.6)
- Fields in `fields_needing_review` array
- Partial extraction (some fields may be "Unknown Store" or 0.0)

### 2. Non-Receipt Image

Test with:
- Random photo (not a receipt)
- Text document
- Completely blank image

Expected:
- Low confidence scores (< 0.3)
- All fields in `fields_needing_review`
- Category: "other"
- Amount: 0.0

### 3. Handwritten Receipt

Test with handwritten receipt image.

Expected:
- Tesseract: Low accuracy (40-60%)
- Google Vision: Better accuracy (70-85%)

### 4. Multi-Language Receipt

Test with receipt containing both Cyrillic and Latin text.

Expected:
- Both engines should handle it
- Google Vision may perform better

## Checking Logs

### View Render Logs

```bash
# Access Render Dashboard
# Navigate to your service
# Click "Logs" tab
```

Look for these indicators:

#### Success Indicators
```
INFO: OCR processing completed for user 1: Amount: 8.0, Store: Kaufland, Confidence: 0.75
INFO: Saved receipt image: /app/data/receipts/user_1/ocr_1_1729684822_20241023_143022.jpg
INFO: Transaction created successfully
```

#### Error Indicators
```
ERROR: Tesseract is not installed
ERROR: Could not load image: [Errno 2] No such file or directory
ERROR: Could not automatically determine credentials
WARNING: Low confidence extraction: 0.25
```

## Performance Benchmarks

### Expected Processing Times

- **Tesseract OCR**: 1-3 seconds per receipt
- **Google Vision API**: 0.5-2 seconds per receipt
- **Image Upload**: 0.2-1 second (depends on size)
- **Total API Response**: 2-5 seconds

### Expected Accuracy Rates

#### Tesseract (Free)
- Clear receipts: 75-85% accuracy
- Bulgarian text: 70-80% accuracy
- Handwritten: 30-50% accuracy

#### Google Vision (Premium)
- Clear receipts: 90-98% accuracy
- Bulgarian text: 85-95% accuracy
- Handwritten: 65-85% accuracy

## Troubleshooting

### Issue: "Tesseract not found"

**Cause**: Docker image not rebuilt with Tesseract.

**Solution**:
1. Verify Dockerfile contains `tesseract-ocr`
2. Trigger Render rebuild
3. Check deployment logs for Tesseract installation

### Issue: Confidence scores are 0.0

**Cause**: OCR couldn't extract any meaningful data.

**Possible reasons**:
- Image too blurry
- Wrong image format
- Empty image
- Non-receipt image

**Solution**:
- Try with clearer image
- Ensure image is JPEG/PNG
- Verify image contains visible text

### Issue: Wrong category detected

**Cause**: Merchant not in category database or ambiguous.

**Solution**:
- Add merchant to `ReceiptCategorizationService.category_keywords`
- Improve item-based categorization rules
- Check if merchant name was extracted correctly

### Issue: Amount is 0.0

**Cause**: OCR couldn't find "total" keyword or amount pattern.

**Possible reasons**:
- Receipt in unexpected format
- Total in different language
- Handwritten amount

**Solution**:
- Use Google Vision API (better at complex formats)
- Update `parse_receipt_details()` regex patterns
- Check raw_text to see what was extracted

### Issue: Date is today instead of receipt date

**Cause**: Date pattern not recognized.

**Solution**:
- Check raw_text for date format
- Add new date pattern to `parse_receipt_details()`
- Common Bulgarian format: "DD.MM.YYYY"

## Testing Checklist

- [ ] Tesseract OCR processes simple receipt
- [ ] Confidence scores present and reasonable
- [ ] Image stored persistently
- [ ] Image retrievable via API
- [ ] Transaction created with correct data
- [ ] Category correctly detected
- [ ] Bulgarian merchant recognized
- [ ] Low quality image handling (graceful degradation)
- [ ] Error handling (non-receipt image)
- [ ] Google Vision API working (if configured)
- [ ] Premium users routed to Google Vision
- [ ] Free users routed to Tesseract
- [ ] Image deletion works
- [ ] Cleanup job runs successfully

## Performance Testing

### Load Test

Test with multiple concurrent requests:

```bash
# Using Apache Bench
ab -n 100 -c 10 -H "Authorization: Bearer YOUR_TOKEN" \
  -p receipt.jpg -T "multipart/form-data" \
  "https://mita-docker-ready-project-manus.onrender.com/api/v1/ocr/process"
```

Expected:
- No failures under normal load
- Response time < 5 seconds
- No memory leaks

### Storage Test

Test image cleanup:

```bash
# Upload 10+ receipts
for i in {1..10}; do
  curl -X POST "..." -F "file=@test_receipt.jpg"
done

# Check storage stats
curl -X GET ".../api/v1/ocr/storage/stats" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Expected:
- All images stored correctly
- Storage stats accurate
- Cleanup doesn't delete recent images

## Integration Testing

### Test with Flutter App

1. Open MITA Flutter app
2. Navigate to "Add Receipt" screen
3. Upload receipt photo
4. Verify preview shows
5. Verify OCR results displayed correctly
6. Verify confidence indicator shown
7. Verify fields with low confidence highlighted
8. Edit any incorrect fields
9. Save transaction
10. Verify transaction appears in history

## Monitoring

### Key Metrics to Monitor

1. **OCR Success Rate**: % of requests with confidence > 0.6
2. **Processing Time**: Average response time
3. **Storage Usage**: Total images and disk space
4. **Error Rate**: % of failed requests
5. **API Costs**: Google Vision API usage (if configured)

### Set Up Alerts

Recommended alerts:
- OCR error rate > 10%
- Average confidence < 0.5
- Processing time > 10 seconds
- Storage > 1GB
- Google Vision API cost > $10/day

## Next Steps

After successful testing:

1. [ ] Monitor production usage for 1 week
2. [ ] Collect user feedback on accuracy
3. [ ] Fine-tune confidence thresholds based on real data
4. [ ] Add more Bulgarian merchants to categorization database
5. [ ] Consider implementing caching for repeated receipts
6. [ ] Set up automated testing pipeline
7. [ ] Document common merchant name variations
8. [ ] Implement receipt template recognition for common stores

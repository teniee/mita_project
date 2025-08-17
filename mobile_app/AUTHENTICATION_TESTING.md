# MITA Authentication Testing Guide

## Overview

This guide explains how to test the authentication flow between the MITA Flutter mobile app and the backend server running at `https://mita-docker-ready-project-manus.onrender.com`.

## Current Status ✅

- **Backend**: Running at `https://mita-docker-ready-project-manus.onrender.com`
- **Mobile App**: Configured to use the correct backend URL
- **Auth Endpoints**: Login, registration, and emergency registration available
- **Timeout Handling**: 30-second timeout configuration implemented
- **Error Handling**: Comprehensive error handling for network issues

## Testing Tools

### 1. Authentication Test Screen

A comprehensive testing screen has been added to the mobile app at `/auth-test` route.

**Access Methods:**
- **Debug Mode Only**: Look for a small debug FAB (floating action button) with a bug icon on:
  - Welcome Screen (when app first loads)
  - Login Screen
- **Direct Navigation**: Navigate to `/auth-test` programmatically

### 2. Test Features

The auth test screen provides:

#### Automated Tests
- **Backend Connectivity**: Tests if the backend server is reachable
- **API Configuration**: Verifies the API base URL is configured correctly
- **Login Endpoint**: Tests login endpoint accessibility (expects 401 for invalid credentials)
- **Registration Endpoint**: Tests registration endpoint functionality
- **Emergency Registration**: Tests the fast emergency registration endpoint
- **Timeout Handling**: Verifies timeout scenarios work correctly
- **Error Handling**: Tests various error conditions

#### Manual Tests
- **Test Login**: Input custom credentials to test login flow
- **Test Registration**: Input custom credentials to test registration (adds timestamp for uniqueness)

## Testing Scenarios

### 1. Basic Connectivity Test

```
Expected Results:
✅ Backend Connectivity: Backend online (status: healthy/degraded, DB: connected/disconnected)
✅ API Configuration: API configured correctly: https://mita-docker-ready-project-manus.onrender.com/api
```

### 2. Authentication Endpoints Test

```
Expected Results:
✅ Login Endpoint: Endpoint accessible (401 as expected)
✅ Registration Endpoint: Endpoint accessible (conflict/validation working)
✅ Emergency Registration: Emergency endpoint accessible
```

### 3. Error Handling Test

```
Expected Results:
✅ Timeout Handling: Timeout handling working correctly
✅ Error Handling: Connection error handling working
```

## Backend Status

The backend health endpoint should return:
- **Status**: `healthy` or `degraded`
- **Database**: `connected` or `disconnected`

Note: The backend may show "degraded" status if the database is disconnected, but auth endpoints should still be functional.

## Test Credentials

### For Manual Testing:

**Test Account (if exists):**
- Email: `test@mita.app`
- Password: `TestPassword123!`

**For Registration Testing:**
- The test screen automatically adds timestamps to email addresses to ensure uniqueness
- Example: `test+1692385234567@mita.app`

## Expected Behavior

### Successful Authentication Flow:

1. **Login Screen**: 
   - Form validation works
   - API calls reach the backend
   - Proper error messages for invalid credentials (401)
   - Timeout handling for slow responses

2. **Registration Screen**:
   - Emergency registration tried first (faster)
   - Fallback to regular registration if emergency fails
   - Proper conflict handling for existing emails (409/422)
   - Navigation to onboarding after success

3. **Error Scenarios**:
   - Network errors show user-friendly messages
   - Timeout scenarios trigger retry dialogs
   - Connection errors are handled gracefully

## Troubleshooting

### Common Issues:

1. **Backend Not Responding**:
   - Check if `https://mita-docker-ready-project-manus.onrender.com/health` returns 200
   - Backend might be sleeping (Render free tier) - first request may take 30+ seconds

2. **Timeout Errors**:
   - Normal for first request to sleeping backend
   - Check if timeout handling dialog appears
   - Retry should work faster on subsequent attempts

3. **Network Configuration**:
   - Ensure device has internet connectivity
   - Check if the API base URL in `lib/config.dart` is correct

### Debug Information:

The app logs detailed information to the console during testing:
- API requests and responses
- Error details with status codes
- Timeout and retry information

Look for logs tagged with:
- `AUTH_TEST`: Test results
- `API`: API service requests/responses  
- `EMERGENCY_AUTH`: Emergency registration attempts

## Testing Checklist

### Pre-Testing:
- [ ] Backend is running and accessible
- [ ] Mobile app builds successfully
- [ ] Debug mode is enabled (to see debug FAB)

### Automated Tests:
- [ ] Backend connectivity test passes
- [ ] API configuration test passes
- [ ] Login endpoint test passes (401 expected)
- [ ] Registration endpoint test passes
- [ ] Emergency registration endpoint test passes
- [ ] Timeout handling test passes
- [ ] Error handling test passes

### Manual Tests:
- [ ] Login with invalid credentials shows proper error
- [ ] Registration with unique email works or shows proper conflict
- [ ] Network errors are handled gracefully
- [ ] Timeout scenarios show retry dialog

### Integration Tests:
- [ ] Login screen can access auth test screen
- [ ] Registration screen functionality works
- [ ] Error messages are user-friendly
- [ ] Loading states work correctly

## Success Criteria ✅

The authentication testing is considered successful when:

1. **All automated tests pass** with green checkmarks
2. **Backend connectivity** is established
3. **API endpoints respond** appropriately (even with errors like 401/409)
4. **Timeout handling** works correctly
5. **Error scenarios** are handled gracefully
6. **Manual testing** with real credentials works as expected

## Results

Based on the implementation:

- ✅ **Authentication Test Screen**: Fully implemented with comprehensive testing
- ✅ **Backend Integration**: Properly configured to use production backend
- ✅ **Error Handling**: Comprehensive error handling for all scenarios
- ✅ **Timeout Management**: 30-second timeouts with retry functionality
- ✅ **Emergency Registration**: Fast emergency endpoint with fallback
- ✅ **Debug Access**: Easy access to testing tools in debug mode

The authentication flow is ready for testing and should work correctly with the deployed backend.
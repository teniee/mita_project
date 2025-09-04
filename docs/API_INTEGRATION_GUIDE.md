# MITA Finance API - Complete Integration Guide

**Version:** 2.2.0  
**Last Updated:** September 4, 2025  
**Status:** Production Ready - Fully Updated  

---

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [Authentication Guide](#authentication-guide)
3. [API Endpoints Reference](#api-endpoints-reference)
   - [User Management](#user-management)
   - [Transaction Management](#transaction-management)
   - [Budget Management](#budget-management)
   - [Financial Analysis](#financial-analysis)
   - [OCR Processing](#ocr-processing)
   - [Task Management](#task-management)
   - [Advanced Authentication](#advanced-authentication)
4. [Error Handling](#error-handling)
5. [Rate Limiting](#rate-limiting)
6. [Mobile Integration](#mobile-integration)
7. [Code Examples](#code-examples)
8. [Production Considerations](#production-considerations)
9. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Base URLs
- **Production**: `https://api.mita.finance`
- **Staging**: `https://staging-api.mita.finance`
- **Development**: `http://localhost:8000`

### Authentication
All protected endpoints require a Bearer token in the Authorization header:
```
Authorization: Bearer <access_token>
```

### Response Format
All API responses follow a standardized format:

**Success Response:**
```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": { /* response data */ },
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_507f1f77bcf8"
}
```

**Error Response:**
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_INVALID_FORMAT",
    "message": "Invalid input data",
    "error_id": "mita_507f1f77bcf8", 
    "timestamp": "2024-01-15T10:30:00Z",
    "details": { /* additional error context */ }
  }
}
```

---

## Authentication Guide

### 1. User Registration

**Endpoint:** `POST /api/auth/register`

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "country": "US",
  "annual_income": 75000.0,
  "timezone": "America/New_York"
}
```

**Response (201 Created):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "user": {
    "id": "user_123abc456def",
    "email": "user@example.com",
    "country": "US",
    "is_premium": false
  }
}
```

**Security Features:**
- Rate limited: 3 attempts per hour per IP
- Password strength validation
- Email format validation
- Comprehensive input sanitization

### 2. User Login

**Endpoint:** `POST /api/auth/login`

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer"
}
```

**Security Features:**
- Rate limited: 5 attempts per 15 minutes per IP
- Secure password verification with bcrypt
- Comprehensive audit logging

### 3. Token Refresh

**Endpoint:** `POST /api/auth/refresh`  
**Authentication:** Required (use refresh token)

**Headers:**
```
Authorization: Bearer <refresh_token>
```

**Response (200 OK):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer"
}
```

**Security Features:**
- Refresh token rotation
- Rate limited: 20 attempts per 5 minutes per user
- Automatic token blacklisting

### 4. User Logout

**Endpoint:** `POST /api/auth/logout`  
**Authentication:** Required

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Successfully logged out",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### JWT Token Structure

**Access Token Claims:**
```json
{
  "sub": "user_123abc456def",
  "email": "user@example.com", 
  "exp": 1693612345,
  "iat": 1693610545,
  "jti": "unique-token-id",
  "iss": "mita-finance-api",
  "aud": "mita-finance-app",
  "token_type": "access_token",
  "user_id": "user_123abc456def",
  "is_premium": false,
  "country": "US"
}
```

**Token Lifetimes:**
- **Access Token**: 30 minutes
- **Refresh Token**: 90 days

---

## API Endpoints Reference

### User Management

#### Get Current User Profile
**Endpoint:** `GET /api/users/me`  
**Authentication:** Required

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "id": "user_123abc456def",
    "email": "user@example.com",
    "country": "US", 
    "timezone": "America/New_York",
    "created_at": "2024-01-15T10:00:00Z"
  }
}
```

#### Update User Profile
**Endpoint:** `PATCH /api/users/me`  
**Authentication:** Required

**Request:**
```json
{
  "country": "CA",
  "timezone": "America/Toronto"
}
```

### Transaction Management

#### Create Transaction
**Endpoint:** `POST /api/transactions`  
**Authentication:** Required

**Request:**
```json
{
  "amount": 67.89,
  "category": "groceries",
  "description": "Weekly grocery shopping at SuperMart",
  "date": "2024-01-15T14:30:00Z"
}
```

**Valid Categories:**
- `food`, `dining`, `groceries`
- `transportation`, `gas`, `public_transport`
- `entertainment`, `shopping`, `clothing`
- `healthcare`, `insurance`, `utilities`
- `rent`, `mortgage`, `education`
- `childcare`, `pets`, `travel`
- `subscriptions`, `gifts`, `charity`, `other`

**Response (201 Created):**
```json
{
  "success": true,
  "data": {
    "id": "txn_123abc456def",
    "amount": 67.89,
    "category": "groceries",
    "description": "Weekly grocery shopping at SuperMart",
    "date": "2024-01-15T14:30:00Z",
    "created_at": "2024-01-15T14:30:00Z"
  },
  "budget_impact": {
    "category": "groceries",
    "amount": 67.89,
    "remaining_budget": 432.11,
    "budget_exceeded": false
  }
}
```

#### List Transactions
**Endpoint:** `GET /api/transactions`  
**Authentication:** Required

**Query Parameters:**
- `page` (integer): Page number (default: 1)
- `limit` (integer): Items per page (default: 20, max: 100)
- `category` (string): Filter by category
- `date_from` (date): Filter from date
- `date_to` (date): Filter to date

**Example Request:**
```
GET /api/transactions?page=1&limit=20&category=food&date_from=2024-01-01
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": [
    {
      "id": "txn_123abc456def",
      "amount": 67.89,
      "category": "groceries",
      "description": "Weekly grocery shopping",
      "date": "2024-01-15T14:30:00Z",
      "created_at": "2024-01-15T14:30:00Z"
    }
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 5,
    "total_items": 87,
    "items_per_page": 20,
    "has_next_page": true,
    "has_previous_page": false
  }
}
```

### Budget Management

#### Get Spending by Category
**Endpoint:** `GET /api/budget/spent`  
**Authentication:** Required

**Query Parameters:**
- `year` (integer): Year for spending data (default: current year)
- `month` (integer): Month for spending data (default: current month)

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "food": 450.75,
    "transportation": 120.00,
    "entertainment": 89.50,
    "utilities": 180.25
  }
}
```

#### Get Remaining Budget
**Endpoint:** `GET /api/budget/remaining`  
**Authentication:** Required

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "remaining_budget": 1249.25,
    "total_budget": 2000.00,
    "spent_amount": 750.75,
    "budget_utilization": 0.375
  }
}
```

#### Get AI Budget Suggestions
**Endpoint:** `GET /api/budget/suggestions`  
**Authentication:** Required

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "suggestions": [
      {
        "id": 1,
        "text": "Consider reducing dining out expenses by 20% to meet your savings goal",
        "category": "dining",
        "potential_savings": 120.0,
        "difficulty": "easy"
      },
      {
        "id": 2,
        "text": "You could save $45/month by switching to generic brands for groceries",
        "category": "groceries",
        "potential_savings": 45.0,
        "difficulty": "easy"
      }
    ],
    "total_potential_savings": 165.0,
    "priority_areas": ["dining", "groceries", "entertainment"]
  }
}
```

### Financial Analysis

#### Evaluate Installment Plan
**Endpoint:** `POST /api/financial/installment-evaluate`  
**Authentication:** Required

**Request:**
```json
{
  "price": 2500.00,
  "months": 12
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "affordable": true,
    "monthly_payment": 208.33,
    "total_amount": 2500.00,
    "budget_impact": 15.2,
    "risk_score": "low",
    "confidence_score": 0.87,
    "recommendations": [
      "Monthly payment fits comfortably within your budget",
      "Consider setting aside an additional $20/month for unexpected expenses"
    ]
  }
}
```

#### Get Personalized Budget Method
**Endpoint:** `GET /api/financial/dynamic-budget-method`  
**Authentication:** Required

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "personalized_method": {
      "needs": 55.5,
      "wants": 27.8,
      "savings": 16.7
    },
    "user_tier": "calculated_dynamically",
    "economic_justification": "Budget allocation calculated using income elasticity theory, regional cost adjustments, and behavioral economics principles"
  }
}
```

### OCR Processing

#### Process Receipt with OCR
**Endpoint:** `POST /api/transactions/receipt`  
**Authentication:** Required  
**Rate Limited:** 5 requests per minute

**Request:**
```
Content-Type: multipart/form-data

file: [receipt_image.jpg]
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "task_id": "task_123abc456def",
    "status": "processing",
    "estimated_completion": "2024-01-15T14:35:00Z",
    "message": "Receipt processing started. Use /tasks/{task_id} to check status."
  }
}
```

### Task Management

#### Get Task Status
**Endpoint:** `GET /api/tasks/{task_id}`  
**Authentication:** Required

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "task_id": "task_123abc456def",
    "status": "completed",
    "result": {
      "transactions": [
        {
          "amount": 45.67,
          "merchant": "SuperMart",
          "date": "2024-01-15",
          "category": "groceries",
          "confidence": 0.95
        }
      ]
    },
    "created_at": "2024-01-15T14:30:00Z",
    "completed_at": "2024-01-15T14:32:15Z"
  }
}
```

#### Cancel Task
**Endpoint:** `DELETE /api/tasks/{task_id}`  
**Authentication:** Required

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Task cancelled successfully"
}
```

### Advanced Authentication

#### Emergency Registration
**Endpoint:** `POST /api/auth/emergency-register`  
**Authentication:** Not Required

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "country": "US",
  "annual_income": 50000.0,
  "timezone": "America/New_York"
}
```

**Response (201 Created):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "user_id": "user_123abc456def",
  "message": "Registration successful in 0.45s"
}
```

#### Change Password
**Endpoint:** `POST /api/auth/change-password`  
**Authentication:** Required

**Request:**
```json
{
  "current_password": "OldPassword123!",
  "new_password": "NewSecurePassword456!"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Password changed successfully",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

#### Delete Account
**Endpoint:** `DELETE /api/auth/delete-account`  
**Authentication:** Required

**Request:**
```json
{
  "confirmation": true
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Account deleted successfully",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

---

## Error Handling

### Error Codes

The API uses standardized error codes for programmatic handling:

#### Authentication Errors (1000-1999)
- `AUTH_INVALID_CREDENTIALS` - Invalid email or password
- `AUTH_TOKEN_EXPIRED` - Access token has expired
- `AUTH_TOKEN_INVALID` - Invalid or malformed token
- `AUTH_TOKEN_MISSING` - Authorization header is required
- `AUTH_INSUFFICIENT_PERMISSIONS` - Insufficient permissions

#### Validation Errors (2000-2999)
- `VALIDATION_REQUIRED_FIELD` - Required field is missing
- `VALIDATION_INVALID_FORMAT` - Invalid field format
- `VALIDATION_OUT_OF_RANGE` - Value outside acceptable range
- `VALIDATION_AMOUNT_INVALID` - Invalid transaction amount
- `VALIDATION_CATEGORY_INVALID` - Invalid category

#### Business Logic Errors (4000-4999)
- `BUSINESS_BUDGET_EXCEEDED` - Transaction exceeds budget
- `BUSINESS_INSUFFICIENT_FUNDS` - Insufficient funds for operation
- `BUSINESS_INVALID_OPERATION` - Operation not allowed

#### System Errors (8000-8999)
- `SYSTEM_INTERNAL_ERROR` - Internal server error
- `RATE_LIMIT_EXCEEDED` - Rate limit exceeded

### Error Response Examples

**Validation Error:**
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_INVALID_FORMAT",
    "message": "Invalid input data",
    "error_id": "mita_507f1f77bcf8",
    "timestamp": "2024-01-15T10:30:00Z",
    "details": {
      "validation_errors": [
        {
          "field": "email",
          "message": "Invalid email format",
          "value": "invalid-email"
        },
        {
          "field": "amount", 
          "message": "Amount must be positive",
          "value": -50.0
        }
      ]
    }
  }
}
```

**Rate Limit Error:**
```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Please try again in 15 minutes.",
    "error_id": "mita_507f1f77bcf8",
    "timestamp": "2024-01-15T10:30:00Z",
    "details": {
      "limit": 5,
      "window": "15 minutes", 
      "reset_at": "2024-01-15T10:45:00Z"
    }
  }
}
```

---

## Rate Limiting

### Rate Limits by Endpoint

| Endpoint | Limit | Window | Scope |
|----------|-------|--------|-------|
| Registration | 3 attempts | 1 hour | Per IP |
| Login | 5 attempts | 15 minutes | Per IP |
| Token Refresh | 20 attempts | 5 minutes | Per User |
| General API | 100 requests | 1 hour | Per User |
| Financial Operations | 50 requests | 1 hour | Per User |

### Rate Limit Headers

All responses include rate limiting headers:

```
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 3
X-RateLimit-Reset: 1693612345
Retry-After: 900
```

### Handling Rate Limits

When you receive a `429 Too Many Requests` response:

1. **Check Headers**: Use `Retry-After` header for exact wait time
2. **Implement Exponential Backoff**: Start with the suggested delay and increase exponentially
3. **Cache Responses**: Reduce API calls by caching non-sensitive data
4. **Batch Operations**: Group multiple operations when possible

---

## Mobile Integration

### Flutter Integration Example

#### 1. Dependencies

```yaml
# pubspec.yaml
dependencies:
  http: ^1.1.0
  shared_preferences: ^2.2.0
  flutter_secure_storage: ^9.0.0
  jwt_decoder: ^2.0.1
  image_picker: ^1.0.4  # For receipt image capture
  path: ^1.8.3         # For file path handling
```

#### 2. Authentication Service

```dart
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:jwt_decoder/jwt_decoder.dart';

class MitaApiService {
  static const String baseUrl = 'https://api.mita.finance';
  static const _storage = FlutterSecureStorage();
  
  // Register new user
  Future<ApiResult<AuthResponse>> register({
    required String email,
    required String password,
    required String country,
    required double annualIncome,
    required String timezone,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/auth/register'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'email': email,
          'password': password,
          'country': country,
          'annual_income': annualIncome,
          'timezone': timezone,
        }),
      );
      
      if (response.statusCode == 201) {
        final data = jsonDecode(response.body);
        await _storeTokens(data['access_token'], data['refresh_token']);
        return ApiResult.success(AuthResponse.fromJson(data));
      } else if (response.statusCode == 429) {
        return ApiResult.rateLimited();
      } else {
        final error = jsonDecode(response.body);
        return ApiResult.error(error['error']['message']);
      }
    } catch (e) {
      return ApiResult.error('Network error: $e');
    }
  }
  
  // Login existing user
  Future<ApiResult<AuthResponse>> login({
    required String email,
    required String password,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/auth/login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'email': email,
          'password': password,
        }),
      );
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        await _storeTokens(data['access_token'], data['refresh_token']);
        return ApiResult.success(AuthResponse.fromJson(data));
      } else {
        final error = jsonDecode(response.body);
        return ApiResult.error(error['error']['message']);
      }
    } catch (e) {
      return ApiResult.error('Network error: $e');
    }
  }
  
  // Get authenticated HTTP client with automatic token refresh
  Future<http.Client> getAuthenticatedClient() async {
    final accessToken = await _storage.read(key: 'access_token');
    
    if (accessToken == null) {
      throw AuthException('Not authenticated');
    }
    
    // Check if token is expired
    if (JwtDecoder.isExpired(accessToken)) {
      await _refreshToken();
      final newToken = await _storage.read(key: 'access_token');
      if (newToken == null) {
        throw AuthException('Unable to refresh token');
      }
      return AuthenticatedHttpClient(newToken);
    }
    
    return AuthenticatedHttpClient(accessToken);
  }
  
  // Create transaction
  Future<ApiResult<Transaction>> createTransaction({
    required double amount,
    required String category,
    required String description,
    DateTime? date,
  }) async {
    try {
      final client = await getAuthenticatedClient();
      final response = await client.post(
        Uri.parse('$baseUrl/api/transactions'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'amount': amount,
          'category': category,
          'description': description,
          'date': (date ?? DateTime.now()).toIso8601String(),
        }),
      );
      
      if (response.statusCode == 201) {
        final data = jsonDecode(response.body);
        return ApiResult.success(Transaction.fromJson(data['data']));
      } else {
        final error = jsonDecode(response.body);
        return ApiResult.error(error['error']['message']);
      }
    } catch (e) {
      return ApiResult.error('Failed to create transaction: $e');
    }
  }
  
  // Get user profile
  Future<ApiResult<UserProfile>> getUserProfile() async {
    try {
      final client = await getAuthenticatedClient();
      final response = await client.get(
        Uri.parse('$baseUrl/api/users/me'),
      );
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return ApiResult.success(UserProfile.fromJson(data['data']));
      } else {
        final error = jsonDecode(response.body);
        return ApiResult.error(error['error']['message']);
      }
    } catch (e) {
      return ApiResult.error('Failed to get profile: $e');
    }
  }
  
  // Process receipt with OCR
  Future<ApiResult<TaskResponse>> processReceipt(File imageFile) async {
    try {
      final client = await getAuthenticatedClient();
      final request = http.MultipartRequest('POST', Uri.parse('$baseUrl/api/transactions/receipt'));
      
      // Add authorization header to multipart request
      final accessToken = await _storage.read(key: 'access_token');
      request.headers['Authorization'] = 'Bearer $accessToken';
      
      // Add the image file
      request.files.add(await http.MultipartFile.fromPath('file', imageFile.path));
      
      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return ApiResult.success(TaskResponse.fromJson(data['data']));
      } else if (response.statusCode == 429) {
        return ApiResult.rateLimited();
      } else {
        final error = jsonDecode(response.body);
        return ApiResult.error(error['error']['message']);
      }
    } catch (e) {
      return ApiResult.error('Failed to process receipt: $e');
    }
  }
  
  // Get task status
  Future<ApiResult<TaskStatus>> getTaskStatus(String taskId) async {
    try {
      final client = await getAuthenticatedClient();
      final response = await client.get(
        Uri.parse('$baseUrl/api/tasks/$taskId'),
      );
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return ApiResult.success(TaskStatus.fromJson(data['data']));
      } else if (response.statusCode == 404) {
        return ApiResult.error('Task not found');
      } else {
        final error = jsonDecode(response.body);
        return ApiResult.error(error['error']['message']);
      }
    } catch (e) {
      return ApiResult.error('Failed to get task status: $e');
    }
  }
  
  // Emergency registration (fallback)
  Future<ApiResult<AuthResponse>> emergencyRegister({
    required String email,
    required String password,
    required String country,
    required double annualIncome,
    required String timezone,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/auth/emergency-register'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'email': email,
          'password': password,
          'country': country,
          'annual_income': annualIncome,
          'timezone': timezone,
        }),
      );
      
      if (response.statusCode == 201) {
        final data = jsonDecode(response.body);
        await _storeTokens(data['access_token'], data['refresh_token']);
        return ApiResult.success(AuthResponse.fromJson(data));
      } else {
        final error = jsonDecode(response.body);
        return ApiResult.error(error['error']['message']);
      }
    } catch (e) {
      return ApiResult.error('Emergency registration failed: $e');
    }
  }
  
  // Private helper methods
  Future<void> _refreshToken() async {
    final refreshToken = await _storage.read(key: 'refresh_token');
    
    if (refreshToken == null) {
      throw AuthException('No refresh token available');
    }
    
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/auth/refresh'),
        headers: {
          'Authorization': 'Bearer $refreshToken',
          'Content-Type': 'application/json',
        },
      );
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        await _storeTokens(data['access_token'], data['refresh_token']);
      } else {
        // Refresh failed, redirect to login
        await _clearTokens();
        throw AuthException('Session expired');
      }
    } catch (e) {
      await _clearTokens();
      throw AuthException('Unable to refresh session');
    }
  }
  
  Future<void> _storeTokens(String accessToken, String refreshToken) async {
    await _storage.write(key: 'access_token', value: accessToken);
    await _storage.write(key: 'refresh_token', value: refreshToken);
  }
  
  Future<void> _clearTokens() async {
    await _storage.delete(key: 'access_token');
    await _storage.delete(key: 'refresh_token');
  }
}

// Data models
class AuthResponse {
  final String accessToken;
  final String refreshToken;
  final String tokenType;
  final UserProfile? user;
  
  AuthResponse({
    required this.accessToken,
    required this.refreshToken,
    required this.tokenType,
    this.user,
  });
  
  factory AuthResponse.fromJson(Map<String, dynamic> json) {
    return AuthResponse(
      accessToken: json['access_token'],
      refreshToken: json['refresh_token'],
      tokenType: json['token_type'],
      user: json['user'] != null ? UserProfile.fromJson(json['user']) : null,
    );
  }
}

class UserProfile {
  final String id;
  final String email;
  final String country;
  final String timezone;
  final bool isPremium;
  final DateTime createdAt;
  
  UserProfile({
    required this.id,
    required this.email,
    required this.country,
    required this.timezone,
    required this.isPremium,
    required this.createdAt,
  });
  
  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      id: json['id'],
      email: json['email'],
      country: json['country'],
      timezone: json['timezone'],
      isPremium: json['is_premium'] ?? false,
      createdAt: DateTime.parse(json['created_at']),
    );
  }
}

class Transaction {
  final String id;
  final double amount;
  final String category;
  final String description;
  final DateTime date;
  final DateTime createdAt;
  
  Transaction({
    required this.id,
    required this.amount,
    required this.category,
    required this.description,
    required this.date,
    required this.createdAt,
  });
  
  factory Transaction.fromJson(Map<String, dynamic> json) {
    return Transaction(
      id: json['id'],
      amount: json['amount'].toDouble(),
      category: json['category'],
      description: json['description'],
      date: DateTime.parse(json['date']),
      createdAt: DateTime.parse(json['created_at']),
    );
  }
}

// Task response models
class TaskResponse {
  final String taskId;
  final String status;
  final DateTime? estimatedCompletion;
  final String message;
  
  TaskResponse({
    required this.taskId,
    required this.status,
    this.estimatedCompletion,
    required this.message,
  });
  
  factory TaskResponse.fromJson(Map<String, dynamic> json) {
    return TaskResponse(
      taskId: json['task_id'],
      status: json['status'],
      estimatedCompletion: json['estimated_completion'] != null 
          ? DateTime.parse(json['estimated_completion']) 
          : null,
      message: json['message'],
    );
  }
}

class TaskStatus {
  final String taskId;
  final String status;
  final Map<String, dynamic>? result;
  final DateTime createdAt;
  final DateTime? completedAt;
  
  TaskStatus({
    required this.taskId,
    required this.status,
    this.result,
    required this.createdAt,
    this.completedAt,
  });
  
  factory TaskStatus.fromJson(Map<String, dynamic> json) {
    return TaskStatus(
      taskId: json['task_id'],
      status: json['status'],
      result: json['result'],
      createdAt: DateTime.parse(json['created_at']),
      completedAt: json['completed_at'] != null 
          ? DateTime.parse(json['completed_at']) 
          : null,
    );
  }
}

// Result wrapper for API responses
class ApiResult<T> {
  final bool success;
  final T? data;
  final String? error;
  final bool rateLimited;
  
  ApiResult._({
    required this.success,
    this.data,
    this.error,
    this.rateLimited = false,
  });
  
  factory ApiResult.success(T data) => ApiResult._(success: true, data: data);
  factory ApiResult.error(String error) => ApiResult._(success: false, error: error);
  factory ApiResult.rateLimited() => ApiResult._(success: false, rateLimited: true);
}

// Authenticated HTTP client
class AuthenticatedHttpClient extends http.BaseClient {
  final String accessToken;
  final http.Client _inner = http.Client();
  
  AuthenticatedHttpClient(this.accessToken);
  
  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) {
    request.headers['Authorization'] = 'Bearer $accessToken';
    return _inner.send(request);
  }
  
  @override
  void close() {
    _inner.close();
  }
}

// Exceptions
class AuthException implements Exception {
  final String message;
  AuthException(this.message);
}
```

#### 3. Usage in Flutter App

```dart
class AuthBloc extends Cubit<AuthState> {
  final MitaApiService _apiService = MitaApiService();
  
  AuthBloc() : super(AuthState.initial());
  
  Future<void> login({
    required String email,
    required String password,
  }) async {
    emit(state.copyWith(isLoading: true));
    
    final result = await _apiService.login(
      email: email,
      password: password,
    );
    
    if (result.success && result.data != null) {
      emit(state.copyWith(
        isLoading: false,
        isAuthenticated: true,
        user: result.data!.user,
      ));
    } else if (result.rateLimited) {
      emit(state.copyWith(
        isLoading: false,
        error: 'Too many login attempts. Please try again later.',
      ));
    } else {
      emit(state.copyWith(
        isLoading: false,
        error: result.error,
      ));
    }
  }
  
  Future<void> createTransaction({
    required double amount,
    required String category,
    required String description,
  }) async {
    final result = await _apiService.createTransaction(
      amount: amount,
      category: category,
      description: description,
    );
    
    if (result.success) {
      // Handle successful transaction creation
      // Maybe refresh transaction list or update budget
    } else {
      // Handle error
    }
  }
}
```

### iOS/Android Native Integration

#### iOS (Swift) Example

```swift
import Foundation

class MitaAPIService {
    static let shared = MitaAPIService()
    private let baseURL = "https://api.mita.finance"
    private let session = URLSession.shared
    
    private init() {}
    
    func register(email: String, password: String, country: String, annualIncome: Double, timezone: String) async throws -> AuthResponse {
        let url = URL(string: "\(baseURL)/api/auth/register")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = [
            "email": email,
            "password": password,
            "country": country,
            "annual_income": annualIncome,
            "timezone": timezone
        ] as [String: Any]
        
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        if httpResponse.statusCode == 201 {
            return try JSONDecoder().decode(AuthResponse.self, from: data)
        } else if httpResponse.statusCode == 429 {
            throw APIError.rateLimited
        } else {
            let errorResponse = try JSONDecoder().decode(ErrorResponse.self, from: data)
            throw APIError.serverError(errorResponse.error.message)
        }
    }
    
    func login(email: String, password: String) async throws -> AuthResponse {
        let url = URL(string: "\(baseURL)/api/auth/login")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = ["email": email, "password": password]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        if httpResponse.statusCode == 200 {
            return try JSONDecoder().decode(AuthResponse.self, from: data)
        } else {
            let errorResponse = try JSONDecoder().decode(ErrorResponse.self, from: data)
            throw APIError.serverError(errorResponse.error.message)
        }
    }
}

// Data models
struct AuthResponse: Codable {
    let accessToken: String
    let refreshToken: String
    let tokenType: String
    let user: UserProfile?
    
    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case tokenType = "token_type"
        case user
    }
}

struct UserProfile: Codable {
    let id: String
    let email: String
    let country: String
    let timezone: String
    let isPremium: Bool
    let createdAt: Date
    
    enum CodingKeys: String, CodingKey {
        case id, email, country, timezone
        case isPremium = "is_premium"
        case createdAt = "created_at"
    }
}

struct ErrorResponse: Codable {
    let success: Bool
    let error: ErrorDetail
}

struct ErrorDetail: Codable {
    let code: String
    let message: String
    let errorId: String
    let timestamp: Date
    
    enum CodingKeys: String, CodingKey {
        case code, message, timestamp
        case errorId = "error_id"
    }
}

enum APIError: Error {
    case invalidResponse
    case rateLimited
    case serverError(String)
}
```

---

## Code Examples

### cURL Examples

#### Register User
```bash
curl -X POST "https://api.mita.finance/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123!",
    "country": "US",
    "annual_income": 75000.0,
    "timezone": "America/New_York"
  }'
```

#### Login User
```bash
curl -X POST "https://api.mita.finance/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123!"
  }'
```

#### Create Transaction
```bash
curl -X POST "https://api.mita.finance/api/transactions" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 67.89,
    "category": "groceries",
    "description": "Weekly grocery shopping"
  }'
```

#### Get User Profile
```bash
curl -X GET "https://api.mita.finance/api/users/me" \
  -H "Authorization: Bearer <access_token>"
```

### JavaScript/Node.js Example

```javascript
const axios = require('axios');

class MitaAPI {
  constructor(baseURL = 'https://api.mita.finance') {
    this.baseURL = baseURL;
    this.accessToken = null;
    this.refreshToken = null;
  }

  // Register user
  async register(userData) {
    try {
      const response = await axios.post(`${this.baseURL}/api/auth/register`, userData);
      this.accessToken = response.data.access_token;
      this.refreshToken = response.data.refresh_token;
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  // Login user
  async login(email, password) {
    try {
      const response = await axios.post(`${this.baseURL}/api/auth/login`, {
        email,
        password
      });
      this.accessToken = response.data.access_token;
      this.refreshToken = response.data.refresh_token;
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  // Create authenticated request
  async authenticatedRequest(method, endpoint, data = null) {
    if (!this.accessToken) {
      throw new Error('Not authenticated');
    }

    try {
      const config = {
        method,
        url: `${this.baseURL}${endpoint}`,
        headers: {
          'Authorization': `Bearer ${this.accessToken}`,
          'Content-Type': 'application/json'
        }
      };

      if (data) {
        config.data = data;
      }

      const response = await axios(config);
      return response.data;
    } catch (error) {
      if (error.response?.status === 401) {
        // Token expired, try to refresh
        await this.refreshAccessToken();
        // Retry the request
        return this.authenticatedRequest(method, endpoint, data);
      }
      throw this.handleError(error);
    }
  }

  // Refresh access token
  async refreshAccessToken() {
    if (!this.refreshToken) {
      throw new Error('No refresh token available');
    }

    try {
      const response = await axios.post(`${this.baseURL}/api/auth/refresh`, {}, {
        headers: {
          'Authorization': `Bearer ${this.refreshToken}`
        }
      });
      
      this.accessToken = response.data.access_token;
      this.refreshToken = response.data.refresh_token;
    } catch (error) {
      // Refresh failed, clear tokens
      this.accessToken = null;
      this.refreshToken = null;
      throw new Error('Session expired, please login again');
    }
  }

  // Create transaction
  async createTransaction(transactionData) {
    return this.authenticatedRequest('POST', '/api/transactions', transactionData);
  }

  // Get user profile
  async getUserProfile() {
    return this.authenticatedRequest('GET', '/api/users/me');
  }

  // Get transactions
  async getTransactions(params = {}) {
    const queryString = new URLSearchParams(params).toString();
    const endpoint = queryString ? `/api/transactions?${queryString}` : '/api/transactions';
    return this.authenticatedRequest('GET', endpoint);
  }

  // Error handling
  handleError(error) {
    if (error.response) {
      const { data, status } = error.response;
      if (data.error) {
        const apiError = new Error(data.error.message);
        apiError.code = data.error.code;
        apiError.status = status;
        apiError.details = data.error.details;
        return apiError;
      }
    }
    return error;
  }
}

// Usage example
async function example() {
  const api = new MitaAPI();
  
  try {
    // Register user
    await api.register({
      email: 'user@example.com',
      password: 'SecurePassword123!',
      country: 'US',
      annual_income: 75000,
      timezone: 'America/New_York'
    });
    
    // Create transaction
    const transaction = await api.createTransaction({
      amount: 67.89,
      category: 'groceries',
      description: 'Weekly grocery shopping'
    });
    
    console.log('Transaction created:', transaction);
    
    // Get user profile
    const profile = await api.getUserProfile();
    console.log('User profile:', profile);
    
  } catch (error) {
    console.error('API Error:', error.message);
    if (error.code) {
      console.error('Error Code:', error.code);
    }
  }
}
```

---

## Production Considerations

### Security Best Practices

1. **Token Storage**
   - Store tokens securely using platform-specific secure storage
   - Never log tokens in production
   - Implement automatic token rotation

2. **Request Security**
   - Always use HTTPS in production
   - Implement request signing for critical operations
   - Validate all SSL certificates

3. **Error Handling**
   - Don't expose sensitive information in error messages
   - Implement proper retry logic with exponential backoff
   - Log errors securely for debugging

### Performance Optimization

1. **Caching**
   - Cache non-sensitive user data locally
   - Implement proper cache invalidation strategies
   - Use ETags for conditional requests where available

2. **Network Efficiency**
   - Batch requests when possible
   - Implement request deduplication
   - Use compression for large requests

3. **Connection Management**
   - Reuse HTTP connections
   - Implement proper timeout handling
   - Use connection pooling for high-volume applications

### Monitoring and Analytics

1. **Request Tracking**
   - Log API response times and success rates
   - Monitor rate limit usage
   - Track authentication failures

2. **Error Monitoring**
   - Implement comprehensive error logging
   - Set up alerts for critical failures
   - Monitor API health endpoints

### Compliance Considerations

1. **Data Privacy**
   - Follow GDPR compliance requirements
   - Implement proper data retention policies
   - Ensure secure data transmission

2. **Financial Compliance**
   - Maintain PCI DSS compliance for payment data
   - Implement proper audit trails
   - Follow SOX requirements for financial data

---

## Troubleshooting

### Common Issues

#### Authentication Issues

**Problem**: Getting 401 Unauthorized errors
**Solutions**:
1. Check if access token is expired and refresh it
2. Verify the Authorization header format: `Bearer <token>`
3. Ensure the token hasn't been revoked/blacklisted

**Problem**: Token refresh fails
**Solutions**:
1. Check if refresh token is expired (90 days)
2. Verify refresh token hasn't been used already (rotation)
3. Re-authenticate the user

#### Rate Limiting Issues

**Problem**: Getting 429 Rate Limited errors
**Solutions**:
1. Implement exponential backoff based on `Retry-After` header
2. Cache responses to reduce API calls
3. Consider upgrading to higher rate limits if needed

#### Validation Errors

**Problem**: Getting validation errors for transaction creation
**Solutions**:
1. Check amount is positive and within limits (0.01 - 100,000)
2. Verify category is from the approved list
3. Ensure required fields (amount, category, description) are present

#### Network Issues

**Problem**: Request timeouts or connection failures
**Solutions**:
1. Implement proper timeout handling (30 seconds recommended)
2. Add retry logic with exponential backoff
3. Check network connectivity and DNS resolution

### Debug Mode

Enable debug logging to troubleshoot issues:

```javascript
// JavaScript example
const api = new MitaAPI();
api.debug = true; // Enable debug logging

// This will log all requests and responses
```

```dart
// Flutter example  
class MitaApiService {
  static const bool debugMode = true; // Set to false in production
  
  void _logRequest(String method, String url, Map<String, dynamic>? body) {
    if (debugMode) {
      print('API Request: $method $url');
      if (body != null) {
        print('Request Body: ${jsonEncode(body)}');
      }
    }
  }
}
```

### Support

For additional support:

- **Documentation**: [https://docs.mita.finance](https://docs.mita.finance)
- **API Support**: api-support@mita.finance
- **Status Page**: [https://status.mita.finance](https://status.mita.finance)
- **GitHub Issues**: Report bugs and feature requests

---

**Last Updated**: September 4, 2025  
**API Version**: 2.2.0  
**Documentation Version**: 2.0.0
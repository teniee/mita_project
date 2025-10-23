# Dashboard API - Usage Examples

This document provides practical examples for using the Dashboard API endpoints.

## Table of Contents
1. [Authentication](#authentication)
2. [Get Dashboard Data](#get-dashboard-data)
3. [Get Quick Stats](#get-quick-stats)
4. [Error Handling](#error-handling)
5. [Frontend Integration](#frontend-integration)
6. [Performance Tips](#performance-tips)

---

## Authentication

All Dashboard API endpoints require JWT authentication.

### Getting a Token

```bash
# Login to get access token
curl -X POST "https://api.mita.finance/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword"
  }'
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer"
  }
}
```

---

## Get Dashboard Data

Retrieve comprehensive dashboard data including balance, spending, budget targets, and recent transactions.

### Basic Request

```bash
curl -X GET "https://api.mita.finance/api/dashboard" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Response Example

```json
{
  "status": "success",
  "data": {
    "balance": 2500.00,
    "spent": 45.50,
    "daily_targets": [
      {
        "category": "Food & Dining",
        "limit": 100.00,
        "spent": 25.50,
        "icon": "restaurant",
        "color": "#4CAF50"
      },
      {
        "category": "Transportation",
        "limit": 80.00,
        "spent": 15.00,
        "icon": "directions_car",
        "color": "#2196F3"
      },
      {
        "category": "Entertainment",
        "limit": 50.00,
        "spent": 5.00,
        "icon": "movie",
        "color": "#9C27B0"
      }
    ],
    "week": [
      {
        "day": "Mon",
        "status": "good",
        "spent": 75.00,
        "budget": 100.00
      },
      {
        "day": "Tue",
        "status": "warning",
        "spent": 95.00,
        "budget": 100.00
      },
      {
        "day": "Wed",
        "status": "over",
        "spent": 120.00,
        "budget": 100.00
      }
    ],
    "transactions": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "amount": 25.50,
        "category": "food",
        "action": "Lunch at Cafe Roma",
        "date": "2025-01-22T12:30:00Z",
        "icon": "restaurant",
        "color": "#4CAF50"
      }
    ],
    "insights_preview": {
      "text": "Great job! Only 45% of budget used.",
      "title": "Excellent"
    },
    "user_income": 3000.00
  }
}
```

### Python Example

```python
import requests

def get_dashboard(access_token):
    """Fetch dashboard data from MITA API"""
    url = "https://api.mita.finance/api/dashboard"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return response.json()

# Usage
token = "your_access_token_here"
dashboard_data = get_dashboard(token)

print(f"Current Balance: ${dashboard_data['data']['balance']:.2f}")
print(f"Spent Today: ${dashboard_data['data']['spent']:.2f}")
```

### JavaScript/TypeScript Example

```typescript
interface DashboardData {
  balance: number;
  spent: number;
  daily_targets: DailyTarget[];
  week: WeekOverview[];
  transactions: Transaction[];
  insights_preview: Insight;
  user_income: number;
}

async function getDashboard(accessToken: string): Promise<DashboardData> {
  const response = await fetch('https://api.mita.finance/api/dashboard', {
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json'
    }
  });

  if (!response.ok) {
    throw new Error(`Dashboard fetch failed: ${response.statusText}`);
  }

  const result = await response.json();
  return result.data;
}

// Usage
const token = 'your_access_token_here';
const dashboard = await getDashboard(token);

console.log(`Balance: $${dashboard.balance.toFixed(2)}`);
console.log(`Spent: $${dashboard.spent.toFixed(2)}`);
```

### Flutter/Dart Example

```dart
import 'package:dio/dio.dart';

class DashboardService {
  final Dio _dio = Dio();

  Future<Map<String, dynamic>> getDashboard(String accessToken) async {
    try {
      final response = await _dio.get(
        'https://api.mita.finance/api/dashboard',
        options: Options(
          headers: {'Authorization': 'Bearer $accessToken'},
        ),
      );

      return response.data['data'] as Map<String, dynamic>;
    } catch (e) {
      print('Error fetching dashboard: $e');
      rethrow;
    }
  }
}

// Usage
final service = DashboardService();
final token = 'your_access_token_here';
final dashboard = await service.getDashboard(token);

print('Balance: \$${dashboard['balance']}');
print('Spent: \$${dashboard['spent']}');
```

---

## Get Quick Stats

Retrieve quick statistics for dashboard widgets.

### Request

```bash
curl -X GET "https://api.mita.finance/api/dashboard/quick-stats" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Response Example

```json
{
  "status": "success",
  "data": {
    "monthly_spending": 1500.00,
    "daily_average": 68.18,
    "top_category": {
      "name": "Food",
      "amount": 450.00
    },
    "savings_rate": 50.0,
    "savings_amount": 1500.00
  }
}
```

### Python Example

```python
def get_quick_stats(access_token):
    """Fetch quick statistics"""
    url = "https://api.mita.finance/api/dashboard/quick-stats"
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    stats = response.json()['data']

    print(f"Monthly Spending: ${stats['monthly_spending']:.2f}")
    print(f"Daily Average: ${stats['daily_average']:.2f}")
    print(f"Top Category: {stats['top_category']['name']} (${stats['top_category']['amount']:.2f})")
    print(f"Savings Rate: {stats['savings_rate']:.1f}%")

    return stats
```

---

## Error Handling

### Common Error Responses

#### 401 Unauthorized
```json
{
  "status": "error",
  "message": "Invalid or expired token",
  "code": "UNAUTHORIZED"
}
```

**Solution**: Refresh your access token using the refresh token endpoint.

#### 404 Not Found
```json
{
  "status": "error",
  "message": "User profile not found",
  "code": "PROFILE_NOT_FOUND"
}
```

**Solution**: Complete user onboarding first.

#### 500 Internal Server Error
```json
{
  "status": "error",
  "message": "Unable to load dashboard data. Please refresh.",
  "error": true
}
```

**Solution**: Retry the request. Check if onboarding is completed.

### Error Handling Example

```python
def get_dashboard_safe(access_token):
    """Fetch dashboard with comprehensive error handling"""
    try:
        response = requests.get(
            "https://api.mita.finance/api/dashboard",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        )

        if response.status_code == 401:
            # Token expired, need to refresh
            print("Token expired. Please refresh your token.")
            return None

        elif response.status_code == 404:
            # User profile not found
            print("Profile not found. Please complete onboarding.")
            return None

        elif response.status_code == 500:
            # Server error
            print("Server error. Using cached data.")
            return get_cached_dashboard()

        response.raise_for_status()
        return response.json()['data']

    except requests.exceptions.Timeout:
        print("Request timed out. Using cached data.")
        return get_cached_dashboard()

    except requests.exceptions.RequestException as e:
        print(f"Network error: {e}")
        return get_cached_dashboard()
```

---

## Frontend Integration

### React Example

```typescript
import { useEffect, useState } from 'react';
import axios from 'axios';

interface DashboardData {
  balance: number;
  spent: number;
  daily_targets: any[];
  // ... other fields
}

function DashboardComponent() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const token = localStorage.getItem('access_token');
        const response = await axios.get(
          'https://api.mita.finance/api/dashboard',
          {
            headers: { Authorization: `Bearer ${token}` }
          }
        );
        setDashboard(response.data.data);
      } catch (err) {
        setError('Failed to load dashboard');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchDashboard();
  }, []);

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!dashboard) return null;

  return (
    <div className="dashboard">
      <h1>Balance: ${dashboard.balance.toFixed(2)}</h1>
      <p>Spent Today: ${dashboard.spent.toFixed(2)}</p>
      {/* Render daily targets, transactions, etc. */}
    </div>
  );
}
```

### Vue.js Example

```vue
<template>
  <div v-if="loading">Loading...</div>
  <div v-else-if="error">{{ error }}</div>
  <div v-else class="dashboard">
    <h1>Balance: ${{ dashboard.balance.toFixed(2) }}</h1>
    <p>Spent Today: ${{ dashboard.spent.toFixed(2) }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import axios from 'axios';

const dashboard = ref(null);
const loading = ref(true);
const error = ref(null);

onMounted(async () => {
  try {
    const token = localStorage.getItem('access_token');
    const response = await axios.get(
      'https://api.mita.finance/api/dashboard',
      {
        headers: { Authorization: `Bearer ${token}` }
      }
    );
    dashboard.value = response.data.data;
  } catch (err) {
    error.value = 'Failed to load dashboard';
  } finally {
    loading.value = false;
  }
});
</script>
```

---

## Performance Tips

### 1. Use Caching

```python
from functools import lru_cache
from datetime import datetime, timedelta

class DashboardClient:
    def __init__(self):
        self._cache = {}
        self._cache_ttl = timedelta(minutes=2)

    def get_dashboard(self, access_token):
        cache_key = f"dashboard_{access_token[:10]}"

        # Check cache
        if cache_key in self._cache:
            cached_data, cached_time = self._cache[cache_key]
            if datetime.now() - cached_time < self._cache_ttl:
                return cached_data

        # Fetch fresh data
        data = self._fetch_dashboard(access_token)
        self._cache[cache_key] = (data, datetime.now())

        return data
```

### 2. Batch Requests

```python
async def get_all_dashboard_data(access_token):
    """Fetch dashboard and quick stats in parallel"""
    import asyncio

    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_dashboard(session, access_token),
            fetch_quick_stats(session, access_token)
        ]

        dashboard, stats = await asyncio.gather(*tasks)

        return {
            'dashboard': dashboard,
            'quick_stats': stats
        }
```

### 3. Implement Retry Logic

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def get_dashboard_with_retry(access_token):
    """Fetch dashboard with automatic retry on failure"""
    response = requests.get(
        "https://api.mita.finance/api/dashboard",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10
    )
    response.raise_for_status()
    return response.json()['data']
```

### 4. Use Compression

```bash
# Request with gzip compression
curl -X GET "https://api.mita.finance/api/dashboard" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Accept-Encoding: gzip, deflate"
```

---

## Testing Examples

### Unit Test (Python)

```python
import unittest
from unittest.mock import Mock, patch

class TestDashboardAPI(unittest.TestCase):

    @patch('requests.get')
    def test_get_dashboard_success(self, mock_get):
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'success',
            'data': {
                'balance': 2500.00,
                'spent': 45.50
            }
        }
        mock_get.return_value = mock_response

        # Test
        result = get_dashboard('fake_token')

        self.assertEqual(result['balance'], 2500.00)
        self.assertEqual(result['spent'], 45.50)
```

### Integration Test (JavaScript)

```javascript
describe('Dashboard API Integration', () => {
  let accessToken;

  beforeAll(async () => {
    // Login to get token
    const loginResponse = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: 'test@example.com',
        password: 'testpassword'
      })
    });
    const loginData = await loginResponse.json();
    accessToken = loginData.data.access_token;
  });

  test('should fetch dashboard data successfully', async () => {
    const response = await fetch('/api/dashboard', {
      headers: { 'Authorization': `Bearer ${accessToken}` }
    });

    expect(response.status).toBe(200);

    const data = await response.json();
    expect(data.status).toBe('success');
    expect(data.data).toHaveProperty('balance');
    expect(data.data).toHaveProperty('spent');
    expect(data.data).toHaveProperty('daily_targets');
  });
});
```

---

## Rate Limiting

The Dashboard API is rate-limited to ensure fair usage:

- **Limit**: 60 requests per minute per user
- **Response Header**: `X-RateLimit-Remaining`

### Handling Rate Limits

```python
def get_dashboard_with_rate_limit(access_token):
    response = requests.get(
        "https://api.mita.finance/api/dashboard",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    # Check rate limit
    remaining = int(response.headers.get('X-RateLimit-Remaining', 0))

    if remaining < 10:
        print(f"Warning: Only {remaining} requests remaining")

    return response.json()['data']
```

---

## Support

For issues or questions:
- **Documentation**: https://docs.mita.finance
- **GitHub Issues**: https://github.com/teniee/mita_project/issues
- **Email**: api-support@mita.finance

---

**Last Updated**: January 2025
**API Version**: 1.0

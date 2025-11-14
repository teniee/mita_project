# Installments Screen - Quick Reference Guide

## Implementation Summary

A fully-featured Flutter screen for managing user installment plans with comprehensive UI, error handling, localization, and accessibility support.

## Key Files

| File | Purpose | Location |
|------|---------|----------|
| installments_screen.dart | Main screen implementation | `/mobile_app/lib/screens/` |
| installments_screen_test.dart | Comprehensive test suite | `/mobile_app/test/screens/` |
| installment_models.dart | Data models | `/mobile_app/lib/models/` |
| installment_service.dart | API service layer | `/mobile_app/lib/services/` |
| app_en.arb | English localization | `/mobile_app/lib/l10n/` |

## Feature Checklist

- [x] Header section with summary statistics
- [x] Load indicator with 4 levels (Safe/Moderate/High/Critical)
- [x] Filter tabs (All, Active, Completed, Overdue)
- [x] Count badges on tabs
- [x] Installment cards with detailed info
- [x] Progress bars with percentage
- [x] Category icons and colors
- [x] Status badges with colors
- [x] Action menu (view, mark paid, cancel, delete)
- [x] Quick action buttons
- [x] Empty state with CTA
- [x] Loading state with shimmer animation
- [x] Error state with retry
- [x] Pull-to-refresh functionality
- [x] Details modal sheet
- [x] Currency formatting with localization
- [x] Date/time formatting with localization
- [x] Comprehensive error handling
- [x] Proper logging and debugging
- [x] Accessibility labels
- [x] Responsive design
- [x] FAB navigation to calculator

## Component Structure

```
InstallmentsScreen (StatefulWidget)
├── AppBar
├── RefreshIndicator
│   └── Content (SingleChildScrollView)
│       ├── SummaryCard
│       │   ├── Stats Row
│       │   │   ├── Active Count
│       │   │   ├── Monthly Payment
│       │   │   └── Load Indicator (Circular)
│       │   └── Next Payment Info
│       ├── FilterTabs
│       │   └── FilterChips (All, Active, Completed, Overdue)
│       └── InstallmentsList
│           └── InstallmentCard (repeating)
│               ├── Header (Icon, Name, Category, Status, Menu)
│               ├── Progress Section (Bar + Stats)
│               ├── Financial Info (Payment, Date, Total)
│               └── Quick Actions (Mark Paid, Cancel)
├── DetailsModal (showModalBottomSheet)
│   └── DetailSheet
│       ├── Header (Name + Status)
│       ├── Detail Rows (Key-Value pairs)
│       ├── Notes Section (if available)
│       └── Close Button
└── FAB (Extended)
    └── "Can I Afford?" button
```

## Color Palette

### Status Colors
```dart
Active:     #FFD25F (Yellow)
Completed:  #84FAA1 (Green)
Overdue:    #FF5C5C (Red)
Cancelled:  Gray
```

### Load Indicator Colors
```dart
Safe:       #4CAF50 (Green)      < 50%
Moderate:   #FFD25F (Yellow)    50-70%
High:       #FF922B (Orange)    70-90%
Critical:   #FF5C5C (Red)       > 90%
```

### Category Colors
```dart
Electronics:  #5B7CFA (Blue)
Clothing:     #FF922B (Orange)
Furniture:    #8B5CF6 (Purple)
Travel:       #00BCD4 (Cyan)
Education:    #3F51B5 (Indigo)
Health:       #F44336 (Red)
Groceries:    #4CAF50 (Green)
Utilities:    #607D8B (Steel)
Other:        #795548 (Brown)
```

## Key Methods

### Initialization & Loading
```dart
void _loadInstallments()           // Load data from service
Future<void> _refreshInstallments() // Pull-to-refresh handler
String _getErrorMessage()           // Convert errors to UI messages
```

### Filtering & Display
```dart
List<Installment> _getFilteredInstallments() // Get current filter results
int _getTabCount(InstallmentStatus?)        // Get count for tab badge
```

### User Actions
```dart
Future<void> _handleMarkPaymentMade()    // Record payment
Future<void> _handleCancelInstallment()  // Cancel plan
Future<void> _handleDeleteInstallment()  // Delete plan
void _showInstallmentDetails()           // Open details modal
```

### UI Helpers
```dart
Color _getCategoryColor()        // Get color for category
IconData _getCategoryIcon()      // Get icon for category
Color _getStatusColor()          // Get color for status
Color _getLoadIndicatorColor()   // Get load indicator color
String _getLoadIndicatorLabel()  // Get load level text
```

### Widget Builders
```dart
Widget _buildErrorState()     // Error UI
Widget _buildMainContent()    // Main list view
Widget _buildEmptyState()     // Empty state
Widget _buildSummaryCard()    // Summary card
Widget _buildFilterTabs()     // Filter tabs
Widget _buildInstallmentCard() // Card widget
Widget _buildDetailsSheet()   // Details modal
Widget _buildDetailRow()      // Key-value row
```

## Service Integration

### Methods Called

```dart
// Fetch installments
InstallmentService().getInstallments(status: _selectedFilter)

// Mark payment
InstallmentService().markPaymentMade(installmentId)

// Cancel plan
InstallmentService().cancelInstallment(installmentId)

// Delete plan
InstallmentService().deleteInstallment(installmentId)
```

### Error Handling

```dart
try {
  // API call
} on InstallmentServiceException catch (e) {
  if (e.isNetworkError) { /* Handle network */ }
  else if (e.isServerError) { /* Handle server */ }
  else { /* Handle other */ }
} catch (e) {
  logError('Error: $e', tag: 'INSTALLMENTS_SCREEN');
}
```

## Localization Integration

### Currency Formatting
```dart
_localizationService.formatCurrency(amount)
// Output: "$1,234.56" (US) or "1.234,56 €" (EU)
```

### Date Formatting
```dart
DateFormat.MMMMd().format(date)       // "January 15"
DateFormat.yMMMMd().format(date)      // "January 15, 2024"
DateFormat.MMMMd().format(date)       // Full month format
```

### Available Keys
```dart
'installments'
'myInstallments'
'canIAfford'
'activeInstallments'
'completedInstallments'
'overdueInstallments'
'monthlyPayment'
'nextPaymentDate'
'totalAmount'
'interestRate'
'markPaymentMade'
'cancelInstallment'
'deleteInstallment'
'paymentMarkedSuccessfully'
'installmentCancelledSuccessfully'
'noInstallmentsYet'
// ... and more
```

## State Variables

```dart
final InstallmentService _installmentService        // Service instance
final LocalizationService _localizationService      // i18n instance

late Future<InstallmentsSummary> _installmentsFuture // Data future
InstallmentsSummary? _currentSummary                // Cached data
bool _isLoading = false                             // Loading flag
String? _errorMessage                               // Error text
InstallmentStatus? _selectedFilter                  // Active filter
bool _showMonthlyView = true                        // View mode (unused)
```

## Test Coverage

**Total Tests**: 50+ test cases

**Areas Covered**:
- Initial load states (shimmer, error, empty)
- Summary card display and calculations
- Filter tabs functionality and counts
- Card rendering and information
- Category icons and colors
- Action buttons and menus
- Progress bar calculations
- Status badge displays
- FAB navigation
- Refresh indicator functionality
- Edge cases (notes, multiple items)

## Accessibility Features

- Semantic labels on all buttons
- High contrast status colors
- Color + text for status (not color-only)
- Proper touch target sizes (48x48 min)
- Modal dialogs with proper focus
- Keyboard navigation support

## Performance Notes

- Shimmer animation: 1500ms duration
- No unnecessary rebuilds
- Efficient list rendering with ListView.builder()
- Proper async/await handling
- Mount checks to prevent memory leaks
- Optimized color calculations

## Navigation

### Route Setup
```dart
'/installments': (context) => const InstallmentsScreen(),
'/installment-calculator': (context) => const CalculatorScreen(),
```

### Navigation Usage
```dart
// Push screen
Navigator.push(context, MaterialPageRoute(
  builder: (context) => const InstallmentsScreen()
));

// Named route
Navigator.pushNamed(context, '/installments');

// From FAB
Navigator.pushNamed(context, '/installment-calculator');
```

## Error Types Handled

| Error Type | Status Code | Message |
|-----------|------------|---------|
| Network | 0 | "Network error. Please check your connection." |
| Server | 500+ | "Server error. Please try again later." |
| Generic | other | "Failed to load installments. Please try again." |
| Not Found | 404 | Service-specific message |
| Validation | 400, 422 | Service-specific message |

## Data Flow

```
User Opens Screen
    ↓
initState() → _loadInstallments()
    ↓
InstallmentService.getInstallments()
    ↓
Response → InstallmentsSummary
    ↓
setState() updates _currentSummary
    ↓
_buildMainContent() renders UI
```

## User Interactions

```
Pull Down          → _refreshInstallments()
Tap Filter Tab     → setState() + _loadInstallments()
Tap Card           → _showInstallmentDetails()
Tap Menu Item      → Appropriate action handler
Tap FAB            → Navigate to calculator
Tap Mark Paid      → _handleMarkPaymentMade()
Tap Cancel         → _handleCancelInstallment()
Tap Delete         → _handleDeleteInstallment()
Tap Retry (Error)  → _refreshInstallments()
```

## Browser Compatibility

- **Android**: 5.0+ (API 21+)
- **iOS**: 11.0+
- **Web**: All modern browsers
- **Responsive**: All screen sizes

## Dependencies

```yaml
flutter:
  sdk: flutter

packages:
  intl: ^0.18.0            # Date/currency formatting
  http: ^1.1.0             # HTTP client

imports:
  - package:flutter/material.dart
  - package:intl/intl.dart
  - ../models/installment_models.dart
  - ../services/installment_service.dart
  - ../services/logging_service.dart
  - ../services/localization_service.dart
```

## Code Metrics

- **Lines of Code**: ~1,400
- **Methods**: 25+
- **State Variables**: 8
- **Widgets Used**: 40+
- **Custom Widgets**: 2 (_ShimmerLoader, _ShimmerBar)
- **Test Cases**: 50+

## Common Issues & Solutions

### Issue: Installments not loading
**Solution**: Check network connection, verify API service, check auth token

### Issue: Formatting errors
**Solution**: Ensure LocalizationService initialized, check i18n keys

### Issue: Progress bar mismatch
**Solution**: Verify paymentsMade/totalPayments calculations

### Issue: Memory leaks
**Solution**: Screen properly disposes animations, checks mounted before setState

### Issue: Missing localization
**Solution**: Regenerate i18n files, add keys to ARB files

---

**Last Updated**: 2024
**Status**: Production Ready
**Version**: 1.0.0

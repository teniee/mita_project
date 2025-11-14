# Installments Screen Feature Documentation

## Overview

The Installments Screen is a comprehensive Flutter feature that displays all user's active and completed installment plans with detailed summary statistics, filtering capabilities, and quick action buttons. It provides a clean, intuitive interface for managing installment payments while integrating seamlessly with the MITA financial app.

## File Locations

- **Main Screen**: `/home/user/mita_project/mobile_app/lib/screens/installments_screen.dart`
- **Unit Tests**: `/home/user/mita_project/mobile_app/test/screens/installments_screen_test.dart`
- **Models**: `/home/user/mita_project/mobile_app/lib/models/installment_models.dart`
- **Service**: `/home/user/mita_project/mobile_app/lib/services/installment_service.dart`
- **Localization**: `/home/user/mita_project/mobile_app/lib/l10n/app_en.arb`

## Architecture

### State Management
The screen uses `StatefulWidget` with local state management for:
- Installments list and summary data
- Loading states
- Filter selections
- Error handling

### Service Integration
The screen integrates with `InstallmentService` which provides:
- Fetching all installments with optional status filters
- Marking payments as made
- Cancelling installments
- Deleting installments
- Error handling with RFC7807 compliance

### Localization
All user-facing strings are localized using Flutter's built-in i18n system with support for:
- Multiple languages (English, Spanish)
- Currency formatting per locale
- Date/time formatting
- Contextual translations

## UI Components

### 1. Header Section
**Components:**
- AppBar with "My Installments" title
- Summary stats card showing:
  - Total active installments count
  - Total monthly payment amount
  - Load indicator (Safe/Moderate/High/Critical) with color coding
  - Next payment date and amount (if available)

**Color Coding:**
- Safe (< 50%): Green (#4CAF50)
- Moderate (50-70%): Yellow (#FFD25F)
- High (70-90%): Orange (#FF922B)
- Critical (> 90%): Red (#FF5C5C)

### 2. Filter Tabs
**Features:**
- Horizontally scrollable tab bar
- Four filter options:
  - All (shows all installments)
  - Active (shows only active installments)
  - Completed (shows only completed installments)
  - Overdue (shows overdue installments)
- Count badges on each tab
- Visual feedback for selected tab

### 3. Installment Cards
Each card displays:
- **Header Section:**
  - Category icon (48x48 with category-specific color)
  - Item name (bold, max 1 line)
  - Category label
  - Status badge (color-coded: active/completed/overdue/cancelled)
  - More options menu (three-dot popup)

- **Progress Section:**
  - Linear progress bar (color-coded by status)
  - Payments made / Total payments text
  - Progress percentage

- **Financial Info:**
  - Monthly payment amount
  - Next payment date
  - Total amount and amount paid

- **Quick Action Buttons (for active installments):**
  - "Mark Paid" button
  - "Cancel" button

### 4. Empty State
**When no installments exist:**
- Large illustrative icon
- "No installments yet" heading
- Descriptive subtitle
- CTA button to launch calculator

### 5. Loading State
**Shimmer Animation:**
- Custom `_ShimmerLoader` widget
- Animates loading skeleton for:
  - Summary card
  - Filter tabs
  - Installment cards
- Duration: 1500ms (repeating)

### 6. Error State
**Display when loading fails:**
- Error icon
- Error message (specific to error type)
- Retry button

### 7. Floating Action Button
**Extended FAB with:**
- Calculate icon
- "Can I Afford?" label
- Navigates to `/installment-calculator`
- Always visible for easy access to calculator

## Features

### 1. Pull-to-Refresh
- Implemented using `RefreshIndicator`
- Refreshes installments list on pull down
- Shows loading indicator during refresh
- Works on all three states (loading, error, content)

### 2. Status Colors
- **Active**: Yellow (#FFD25F)
- **Completed**: Green (#84FAA1)
- **Overdue**: Red (#FF5C5C)
- **Cancelled**: Grey

### 3. Category Icons & Colors
Each installment category has:
- Unique icon (Material Icons)
- Unique color palette

Mappings:
- Electronics → Device icon (#5B7CFA)
- Clothing → Shopping bag (#FF922B)
- Furniture → Chair (#8B5CF6)
- Travel → Flight takeoff (#00BCD4)
- Education → School (#3F51B5)
- Health → Heart (#F44336)
- Groceries → Shopping cart (#4CAF50)
- Utilities → Home (#607D8B)
- Other → Category (#795548)

### 4. Action Menu
Three-dot menu provides:
- View Details (opens modal sheet)
- Mark Payment Made (for active only)
- Cancel (for active only)
- Delete (always available)

### 5. Details Modal
Bottom sheet showing comprehensive installment information:
- Item name and status badge
- Category
- Total amount
- Monthly payment
- Interest rate
- Total/completed payments
- Next and final payment dates
- Total paid and remaining balance
- Notes (if available)

### 6. Error Handling
**Error Types:**
- Network errors (0 status code)
- Server errors (500+)
- Generic errors (other status codes)

**User-Friendly Messages:**
- "Network error. Please check your connection."
- "Server error. Please try again later."
- "Failed to load installments. Please try again."

## Data Models

### Installment
Core model with properties:
- `id`: Unique identifier
- `itemName`: Name of the purchased item
- `category`: InstallmentCategory enum
- `totalAmount`: Total purchase amount
- `paymentAmount`: Monthly payment
- `interestRate`: Interest rate percentage
- `totalPayments`: Total number of payments
- `paymentsMade`: Number of completed payments
- `paymentFrequency`: "monthly"
- `nextPaymentDate`: Date of next payment
- `finalPaymentDate`: Date of last payment
- `status`: InstallmentStatus enum
- `notes`: Optional notes

### InstallmentsSummary
Summary data returned by service:
- `totalActive`: Count of active installments
- `totalCompleted`: Count of completed installments
- `totalMonthlyPayment`: Sum of all monthly payments
- `nextPaymentDate`: Next upcoming payment date
- `nextPaymentAmount`: Next payment amount
- `currentInstallmentLoad`: Load percentage (0.0-1.0)
- `loadMessage`: Human-readable load message
- `installments`: List of all installments

## API Integration

### Service Methods Used

```dart
// Fetch installments (with optional status filter)
Future<InstallmentsSummary> getInstallments({InstallmentStatus? status})

// Mark payment as made
Future<Installment> markPaymentMade(String installmentId)

// Cancel an installment
Future<Installment> cancelInstallment(String installmentId)

// Delete an installment
Future<void> deleteInstallment(String installmentId)
```

### Error Handling
All service calls include:
- Try-catch error handling
- RFC7807 error parsing
- User-friendly error messages
- Proper logging with tags

## Localization Keys

### Screen Labels
- `installments`: "Installments"
- `myInstallments`: "My Installments"
- `canIAfford`: "Can I Afford?"

### Filter Tabs
- `activeInstallments`: "Active Installments"
- `completedInstallments`: "Completed"
- `overdueInstallments`: "Overdue"

### Financial Labels
- `monthlyPayment`: "Monthly Payment"
- `nextPaymentDate`: "Next Payment Date"
- `totalAmount`: "Total Amount"
- `interestRate`: "Interest Rate"
- `totalPayments`: "Total Payments"
- `remainingBalance`: "Remaining Balance"
- `totalPaid`: "Total Paid"

### Action Buttons
- `markPaymentMade`: "Mark Payment Made"
- `cancelInstallment`: "Cancel Installment"
- `deleteInstallment`: "Delete Installment"
- `viewDetails`: "View Details"
- `startCalculator`: "Start Calculator"

### Messages
- `paymentMarkedSuccessfully`: "Payment marked as made"
- `installmentCancelledSuccessfully`: "Installment cancelled"
- `installmentDeletedSuccessfully`: "Installment deleted"
- `noInstallmentsYet`: "No installments yet"

### Error Messages
- `networkError`: "Network error. Please check your connection."
- `serverError`: "Server error. Please try again later."
- `failedToUpdatePayment`: "Failed to update payment: {error}"
- `failedToCancelInstallment`: "Failed to cancel installment: {error}"
- `failedToDeleteInstallment`: "Failed to delete installment: {error}"

## Accessibility Features

### Semantic Labels
- AppBar title properly labeled
- Icon buttons have semantic meaning
- Status badges use color + text
- Progress indicators have labels

### Focus Management
- Interactive elements are keyboard accessible
- Modal dialogs support proper focus
- Buttons have adequate touch targets (48x48 minimum)

### Visual Considerations
- High contrast colors for readability
- Status indicators use color + text (not color alone)
- Proper spacing and sizing for legibility

## Testing

### Test Coverage

**Test File**: `/home/user/mita_project/mobile_app/test/screens/installments_screen_test.dart`

**Test Groups:**

1. **Initial Load Tests**
   - Shimmer loader display while loading
   - Error state handling
   - Empty state display

2. **Summary Card Tests**
   - Correct summary information display
   - Load indicator color levels

3. **Filter Tabs Tests**
   - Tab display with counts
   - Filtering functionality

4. **Installment Card Tests**
   - Card information display
   - Category icon and color
   - Quick action buttons
   - Popup menu

5. **Progress Bar Tests**
   - Correct progress percentage

6. **Status Badge Tests**
   - Correct status display

7. **FAB Navigation Tests**
   - Navigation to calculator

8. **Refresh Indicator Tests**
   - Pull-to-refresh functionality

9. **Edge Cases**
   - Installments with notes
   - Multiple installments

**Test Count**: 50+ test cases covering all major functionality

## Dependencies

### Flutter & Dart
- `flutter/material.dart`: Material UI
- `intl/intl.dart`: Date/time and currency formatting

### MITA Services
- `InstallmentService`: API integration
- `LoggingService`: Error logging
- `LocalizationService`: i18n support

## Design Patterns

### State Management
- Single `StatefulWidget` with `_state` pattern
- Reactive updates with `setState()`
- Proper mount checks for async operations

### Error Handling
- RFC7807 compliant error parsing
- Graceful degradation
- User-friendly error messages

### Widget Composition
- Reusable widget building methods
- Proper separation of concerns
- Clean widget hierarchy

## Performance Considerations

### Memory Optimization
- Efficient list rendering with `ListView.builder()`
- Proper disposal of animations
- Minimal rebuilds

### Loading Performance
- Shimmer loader provides visual feedback
- Proper async/await handling
- Mounted checks to prevent memory leaks

### Display Performance
- Reasonable animation duration (1500ms)
- Efficient color calculations
- Optimized widget composition

## Future Enhancements

Potential improvements:
1. Add date range filtering
2. Implement search functionality
3. Add export/print functionality
4. Calendar view of payments
5. Payment notifications/reminders
6. Ability to modify payment schedule
7. Add payment method selection
8. Biometric authentication for payment confirmation
9. Advanced analytics on installment patterns
10. Integration with banking systems

## Usage

### Navigation
```dart
// Push the screen
Navigator.push(
  context,
  MaterialPageRoute(builder: (context) => const InstallmentsScreen()),
);

// Or use named routes (if configured)
Navigator.pushNamed(context, '/installments');
```

### Integration with Main App
Add to navigation/routing:
```dart
'/installments': (context) => const InstallmentsScreen(),
```

## Code Quality

### Code Style
- Follows Dart style guide
- Clear variable names
- Well-documented methods
- Proper error handling

### Documentation
- Comprehensive inline comments
- Clear widget structure
- Well-documented state variables
- Error handling explanations

### Testing
- Unit test coverage
- Widget tests for UI
- Mock services for isolation
- Edge case coverage

## Browser/Platform Support

### Android
- Minimum SDK: 21 (5.0+)
- Target SDK: 34
- All features fully supported

### iOS
- Minimum: iOS 11.0
- Target: iOS 17.0
- All features fully supported

### Web
- Full responsive design
- Touch and mouse support
- All features supported

## Troubleshooting

### Common Issues

**Installments not loading:**
- Check network connectivity
- Verify API service is running
- Check authentication token

**Error messages not displaying:**
- Ensure localization files are generated
- Check for missing i18n keys
- Verify AppLocalizations integration

**Formatting issues:**
- Ensure LocalizationService is properly initialized
- Check locale configuration
- Verify currency data for locale

## Related Features

- **Installment Calculator**: `/installment-calculator` route
- **Transaction Screen**: For viewing payment history
- **Budget Screen**: For financial planning
- **Profile Screen**: For financial profile management

---

**Version**: 1.0.0
**Last Updated**: 2024
**Status**: Production Ready

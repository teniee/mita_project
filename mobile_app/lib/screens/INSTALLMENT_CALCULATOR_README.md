# Installment Calculator Screen

## Overview

The Installment Calculator Screen is a comprehensive, user-friendly Flutter interface that helps users make informed decisions about installment purchases using advanced risk assessment algorithms.

## File Location

```
mobile_app/lib/screens/installment_calculator_screen.dart
```

## Features Implemented

### 1. Header Section
- **Title**: "Can I Afford This?"
- **Subtitle**: Explains the smart financial analysis
- **Design**: Gradient background with MITA brand colors
- **Icon**: Calculator icon in secondary color (FFD25F)

### 2. Input Form Section

#### Required Fields:
- **Purchase Amount**: USD input with $ prefix, validation for positive numbers
- **Category Dropdown**: All InstallmentCategory enum options with icons
- **Number of Payments**: Choice chips for 4, 6, 12, 24 months
- **Interest Rate**:
  - Preset buttons for 0%, 10%, 15%, 20%
  - Custom input field for any rate

#### Optional Fields (for users without financial profile):
- **Monthly Income**: Auto-filled from profile or manual entry
- **Current Balance**: Auto-filled from profile or manual entry

### 3. Calculate Button
- Large, prominent CTA button
- Shows loading spinner during calculation
- Disabled when form is incomplete
- Haptic feedback on press

### 4. Results Section (Animated)

The results appear with smooth fade and slide animations after calculation.

#### Risk Level Card
Color-coded risk assessment:
- **GREEN** (0xFF388E3C): Safe to proceed - encouraging message
- **YELLOW** (0xFFFFA000): Proceed with caution - warning icon
- **ORANGE** (0xFFEF6C00): High risk - strong warning
- **RED** (0xFFD32F2F): Not recommended - stop icon

Displays:
- Risk icon (check, warning, error)
- Risk level message
- Verdict text
- Risk score percentage

#### Payment Details Card
Shows:
- **Monthly Payment**: Large, bold display
- **Total Interest**: Color-coded (red if > 0)
- **Total Cost**: Full amount with interest
- **First Payment**: Initial payment amount
- **Payment Schedule**: Expandable list showing each payment breakdown

#### Financial Impact Card
Displays (when available):
- **DTI Ratio**: Progress bar with color coding
- **Payment as % of Income**: Percentage bar
- **Remaining Monthly Funds**: Green/red based on positive/negative
- **Balance After First Payment**: Shows financial cushion

#### Risk Factors List
For each identified risk factor:
- Severity icon (error, warning, info)
- Factor name
- Descriptive message
- Statistical information (if available)
- Color-coded by severity (high/medium/low)

#### Personalized Message
- Yellow gradient card with lightbulb icon
- Displays the algorithm's customized advice
- Based on user's complete financial situation

#### Alternative Recommendation
Shown when algorithm suggests different approach:
- Recommendation type badge
- Title and description
- Potential savings amount (green highlight)
- Time needed (in days)

#### Warnings & Tips (Expandable)
- **Warnings**: Orange-coded expandable section with count badge
- **Tips**: Green-coded expandable section with count badge
- **Statistics**: Relevant data points

### 5. Action Buttons

Bottom action section includes:
- **Create Installment Plan** (if risk is GREEN or YELLOW)
  - Primary button with green background
  - Navigates to installment creation flow

- **Learn More**
  - Shows detailed explanation of risk algorithm
  - Outlined button style

- **Calculate Again**
  - Resets form and scrolls to top
  - Outlined button style

## Technical Implementation

### State Management
- Uses `StatefulWidget` with `SingleTickerProviderStateMixin` for animations
- Form validation with `GlobalKey<FormState>`
- Proper lifecycle management (dispose controllers)

### Services Used
- `InstallmentService`: All API interactions
- `LoggingService`: Error logging and debugging

### Error Handling
- RFC7807 compliant error parsing
- User-friendly error dialogs
- Loading states with spinners
- Form validation with error messages

### Accessibility Features
- Semantic labels on all inputs
- Tooltip help icons for complex fields
- Sufficient color contrast (WCAG AA compliant)
- Large touch targets (minimum 48x48 dp)
- Screen reader support through Material widgets

### Responsive Design
- Works on various screen sizes
- ScrollController for proper scrolling
- Auto-scroll to results after calculation
- Expandable sections for long content

### Animations
- Fade animation for results (600ms)
- Slide animation for smooth entry
- Haptic feedback on important interactions
- Loading spinners during API calls

## Integration Guide

### Navigation to Calculator

From any screen, navigate using:

```dart
Navigator.pushNamed(context, '/installment-calculator');
```

Example integration in InstallmentsScreen:

```dart
// Add FAB to InstallmentsScreen
floatingActionButton: FloatingActionButton.extended(
  onPressed: () {
    Navigator.pushNamed(context, '/installment-calculator');
  },
  icon: const Icon(Icons.calculate),
  label: const Text('Calculate'),
  backgroundColor: const Color(0xFF193C57),
),
```

### Navigation from Main Screen

Add a menu item or button:

```dart
ListTile(
  leading: const Icon(Icons.calculate),
  title: const Text('Installment Calculator'),
  subtitle: const Text('Check if you can afford it'),
  onTap: () {
    Navigator.pushNamed(context, '/installment-calculator');
  },
),
```

### Deep Linking (Optional)

The route is registered as `/installment-calculator` and can be accessed via deep links.

## Color Scheme

Following MITA Material Design 3 theme:

### Primary Colors
- **Primary**: #193C57 (Deep navy blue)
- **Secondary**: #FFD25F (Warm yellow)
- **Background**: #FFF9F0 (Warm cream)

### Risk Level Colors
- **Green** (Safe): #388E3C
- **Yellow** (Caution): #FFA000
- **Orange** (Warning): #EF6C00
- **Red** (Critical): #D32F2F

### Severity Colors
- **High/Critical**: #F44336
- **Medium/Moderate**: #FF9800
- **Low**: #FFD25F
- **Info**: #2196F3

## Usage Examples

### Basic Usage

```dart
// Navigate to calculator
Navigator.pushNamed(context, '/installment-calculator');
```

### With Profile Check

```dart
// Check if user has financial profile first
final hasProfile = await InstallmentService().hasFinancialProfile();

if (hasProfile) {
  // Navigate directly
  Navigator.pushNamed(context, '/installment-calculator');
} else {
  // Prompt to create profile first
  showDialog(
    context: context,
    builder: (context) => AlertDialog(
      title: const Text('Complete Your Profile'),
      content: const Text(
        'For better recommendations, please complete your financial profile first.',
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Later'),
        ),
        ElevatedButton(
          onPressed: () {
            Navigator.pop(context);
            // Navigate to profile creation
          },
          child: const Text('Complete Profile'),
        ),
      ],
    ),
  );
}
```

### With Callback

```dart
// Navigate and handle result
final result = await Navigator.pushNamed(
  context,
  '/installment-calculator',
);

if (result == 'created') {
  // Refresh installments list
  fetchInstallments();
}
```

## API Integration

The screen integrates with the following endpoints via `InstallmentService`:

1. **GET** `/api/installments/profile` - Fetch user's financial profile
2. **POST** `/api/installments/calculator` - Calculate installment risk
3. **GET** `/api/installments?status=active` - Get active installments for DTI calculation

## Form Validation Rules

### Purchase Amount
- Required field
- Must be a valid number
- Must be greater than 0
- Accepts up to 2 decimal places

### Interest Rate
- Optional (defaults to 0)
- Must be a valid number
- Accepts up to 2 decimal places
- Can be 0-100%

### Monthly Income (if no profile)
- Required when no financial profile exists
- Must be a valid number
- Accepts up to 2 decimal places

### Current Balance (if no profile)
- Required when no financial profile exists
- Must be a valid number
- Accepts up to 2 decimal places
- Can be negative (overdraft)

## Performance Considerations

- Debounced validation on text inputs
- Lazy loading of results section
- Efficient animation controllers
- Proper disposal of resources
- ScrollController optimization

## Testing Recommendations

### Unit Tests
```dart
testWidgets('Calculator form validation works', (WidgetTester tester) async {
  // Test form validation logic
});

testWidgets('Risk color matches risk level', (WidgetTester tester) async {
  // Test color coding logic
});
```

### Widget Tests
```dart
testWidgets('Shows loading spinner during calculation', (WidgetTester tester) async {
  // Test loading state UI
});

testWidgets('Results appear after successful calculation', (WidgetTester tester) async {
  // Test results rendering
});
```

### Integration Tests
```dart
testWidgets('Complete calculation flow', (WidgetTester tester) async {
  // Test full user journey
});
```

## Future Enhancements

Potential improvements:
1. Save calculations to history
2. Compare multiple scenarios
3. Share results with financial advisor
4. Export PDF report
5. Integration with financial goals
6. Machine learning-based predictions
7. A/B test different risk thresholds

## Troubleshooting

### Common Issues

**Issue**: Form doesn't submit
- **Solution**: Check all required fields are filled and valid

**Issue**: Results don't appear
- **Solution**: Check network connection and API availability

**Issue**: Profile not loading
- **Solution**: Ensure user is authenticated and has completed onboarding

**Issue**: Animation stutters
- **Solution**: Check device performance, reduce animation complexity

## Related Files

- `/mobile_app/lib/services/installment_service.dart` - API service
- `/mobile_app/lib/models/installment_models.dart` - Data models
- `/mobile_app/lib/screens/installments_screen.dart` - List view
- `/mobile_app/lib/theme/mita_theme.dart` - Theme configuration

## Support

For issues or questions, contact the MITA development team or create an issue in the project repository.

## License

Copyright © 2025 MITA. All rights reserved.

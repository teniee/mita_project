# Financial Error Message Style Guide for MITA

## Overview
This guide establishes standards for creating user-friendly, actionable error messages throughout the MITA financial application. All error messages should prioritize clarity, provide helpful guidance, and maintain the user's trust in our financial platform.

## Core Principles

### 1. User-Centric Language
- **Use plain English**: Avoid technical jargon and system errors
- **Be conversational**: Write as you would speak to a friend
- **Stay positive**: Focus on solutions rather than problems
- **Show empathy**: Acknowledge the user's frustration

**✅ Good**: "We couldn't save your transaction right now. Your data is safe, and you can try again."

**❌ Bad**: "TransactionException: Database connection timeout occurred during INSERT operation."

### 2. Financial Context Awareness
- **Acknowledge financial sensitivity**: Users are dealing with money and personal data
- **Provide reassurance**: Emphasize data security and accuracy
- **Offer alternatives**: When primary actions fail, suggest other paths
- **Respect budgets**: Understand that financial limits have real consequences

**✅ Good**: "This transaction would exceed your daily budget by $25.50. You can still proceed, or consider adjusting the amount."

**❌ Bad**: "Amount validation failed. Check input parameters."

### 3. Actionable Guidance
Every error message should tell users:
- **What happened**: Clear explanation without blame
- **Why it matters**: Context about the impact
- **What they can do**: Specific next steps
- **How to prevent it**: Tips for future success

## Error Message Structure

### Standard Format
```
[TITLE]: Brief, descriptive headline
[MESSAGE]: Clear explanation of what happened and why
[FINANCIAL CONTEXT]: Security/trust reassurance (when applicable)
[ACTIONS]: Specific steps the user can take
[TIPS]: Additional helpful information (when relevant)
```

### Example Structure
```
Title: Transaction Failed
Message: We couldn't save your expense right now. Your data is safe, and you can try again.
Financial Context: Your financial records remain accurate and secure.
Actions: [Try Again] [Save Draft] [Contact Support]
Tips:
• Check your internet connection
• Verify all required fields are filled
• Try again in a few moments
```

## Error Categories & Standards

### Authentication Errors
**Context**: Users accessing their financial data
**Tone**: Reassuring but security-conscious
**Key Elements**:
- Emphasize data protection
- Clear re-authentication steps
- Alternative access methods

**Example**:
```
Title: Session Expired
Message: Your secure session has expired for your protection. Please sign in again to continue managing your finances.
Context: Your financial data remains secure while your session is refreshed.
Actions: [Sign In Again] [Use Biometrics]
```

### Transaction Errors
**Context**: Users recording financial transactions
**Tone**: Helpful and accuracy-focused
**Key Elements**:
- Data integrity assurance
- Alternative recording methods
- Validation guidance

**Example**:
```
Title: Invalid Amount
Message: The amount entered is not valid. Please enter a positive number with up to 2 decimal places.
Context: Accurate amounts help maintain precise financial records.
Actions: [Fix Amount] [Use Calculator]
Tips:
• Use numbers only (e.g., 25.50)
• Don't include currency symbols
• Maximum 2 decimal places for cents
```

### Budget & Spending Errors
**Context**: Users managing their budget
**Tone**: Advisory but non-judgmental
**Key Elements**:
- Budget context and goals
- Spending alternatives
- Financial guidance

**Example**:
```
Title: Budget Alert
Message: This transaction would exceed your daily budget by $15.75. You can still proceed, or consider adjusting the amount.
Context: Staying within budget helps achieve your financial goals. Consider if this expense is necessary.
Actions: [Adjust Amount] [Proceed Anyway] [View Budget]
Tips:
• Review your spending categories to find areas to save
• Consider postponing non-essential purchases
• Check if you can use a different payment method
```

### Network & Connectivity Errors
**Context**: Users experiencing connectivity issues
**Tone**: Understanding and solution-focused
**Key Elements**:
- Offline capabilities
- Data synchronization
- Troubleshooting steps

**Example**:
```
Title: No Internet Connection
Message: You're currently offline. Your transactions will be saved locally and synced when you reconnect.
Context: Your financial data is safely stored locally until connection is restored.
Actions: [Continue Offline] [Check Connection] [Retry]
Tips:
• Check your WiFi or mobile data connection
• You can still record transactions offline
• Data will sync automatically when reconnected
```

## Severity Levels

### Critical (Red)
- **When**: Data loss risk, security breach, account compromise
- **UI**: Full-screen dialog, blocks all actions
- **Tone**: Urgent but reassuring
- **Focus**: Immediate action required

### High (Orange)
- **When**: Transaction failures, budget violations, sync issues
- **UI**: Modal bottom sheet, prominent display
- **Tone**: Important but manageable
- **Focus**: User decision needed

### Medium (Blue)
- **When**: Validation errors, permission requests, warnings
- **UI**: Inline errors, banners
- **Tone**: Helpful guidance
- **Focus**: Corrective action

### Low (Green)
- **When**: Minor validation, informational
- **UI**: Subtle inline messages
- **Tone**: Gentle nudge
- **Focus**: Improvement suggestion

## Visual Design Standards

### Typography
- **Title**: Headlines/Small (20sp), Weight 600, System color
- **Message**: Body/Large (16sp), Weight 400, On-surface variant
- **Context**: Body/Medium (14sp), Weight 500, Primary color
- **Tips**: Body/Small (12sp), Weight 400, On-surface variant

### Iconography
Use Material Design icons with financial context:
- `error_outline` - Generic errors
- `lock_clock_outlined` - Session/auth issues
- `savings_outlined` - Budget/spending issues
- `sync_problem_outlined` - Transaction failures
- `wifi_off_outlined` - Connectivity issues
- `camera_alt_outlined` - Permission requests

### Colors
Follow Material 3 color system:
- **Error**: Use theme's error color
- **Warning**: Use theme's tertiary color
- **Info**: Use theme's primary color
- **Success**: Use theme's primary color

### Spacing
- **Dialog padding**: 24dp all around
- **Bottom sheet padding**: 24dp horizontal, 24dp top, 32dp bottom
- **Inline error margin**: 8dp top
- **Icon spacing**: 12-16dp from text
- **Action spacing**: 8dp between buttons

## Action Button Standards

### Primary Actions
- **Style**: FilledButton with theme colors
- **Label**: Active verbs (Try Again, Fix Amount, Sign In)
- **Position**: Right-aligned, most important action

### Secondary Actions
- **Style**: OutlinedButton or TextButton
- **Label**: Alternative options (Cancel, View Details, Learn More)
- **Position**: Left-aligned, less prominent

### Action Labels
Use clear, specific labels:
- ✅ "Try Again" (not "Retry")
- ✅ "Fix Amount" (not "Correct")
- ✅ "Sign In Again" (not "Re-authenticate")
- ✅ "Continue Offline" (not "Proceed")

## Accessibility Requirements

### Screen Readers
- Announce error category and severity
- Provide full context in announcements
- Include actionable guidance in accessibility labels

### Focus Management
- Set focus to first actionable element
- Ensure all actions are keyboard accessible
- Use proper focus indicators

### Visual Accessibility
- Maintain 4.5:1 contrast ratios
- Don't rely solely on color for meaning
- Support dynamic type sizing

## Localization Considerations

### Text Expansion
- Allow 30-40% text expansion for other languages
- Use flexible layouts that accommodate longer text
- Test with pseudo-localization

### Cultural Sensitivity
- Avoid idioms and cultural references
- Consider different financial systems and currencies
- Respect local privacy and financial regulations

## Testing Guidelines

### User Testing
- Test with real financial scenarios
- Include users with different technical expertise
- Test during stressful financial situations

### Automated Testing
- Verify all error states render correctly
- Test error message accessibility
- Validate action button functionality

### Content Testing
- Ensure all error messages are localized
- Test with various error combinations
- Verify financial context accuracy

## Common Mistakes to Avoid

### Technical Language
❌ "HTTP 404 error occurred"
✅ "We couldn't find that page"

### Blame Language
❌ "You entered an invalid amount"
✅ "The amount format isn't recognized"

### Vague Messages
❌ "Something went wrong"
✅ "We couldn't save your transaction right now"

### No Actionable Steps
❌ "Error saving data"
✅ "We couldn't save your data. Please check your connection and try again."

### Missing Financial Context
❌ "Validation failed"
✅ "To keep your financial records accurate, we need a valid amount"

## Implementation Checklist

Before implementing any error message:

- [ ] Does it use plain, conversational language?
- [ ] Does it explain what happened without blame?
- [ ] Does it provide specific next steps?
- [ ] Does it include appropriate financial context?
- [ ] Does it follow the visual design standards?
- [ ] Is it accessible to screen readers?
- [ ] Has it been tested with real users?
- [ ] Is it localized and culturally appropriate?
- [ ] Does it maintain user trust in the financial platform?
- [ ] Are the action buttons clear and helpful?

## Examples by Context

### Login Screen
```
Session Expired
Your secure session has expired for your protection. Please sign in again to continue managing your finances.
🔒 Your financial data remains secure while your session is refreshed.
[Sign In Again] [Use Biometrics]
```

### Expense Entry
```
Invalid Amount
The amount entered is not valid. Please enter a positive number with up to 2 decimal places.
💡 Accurate amounts help maintain precise financial records.
[Fix Amount]
Tips: Use numbers only (e.g., 25.50) • Maximum 2 decimal places for cents
```

### Budget Management
```
Budget Alert
This transaction would exceed your daily budget by $15.75. You can still proceed, or consider adjusting the amount.
🎯 Staying within budget helps achieve your financial goals.
[Adjust Amount] [Proceed Anyway] [View Budget]
Tips: Review spending categories • Consider postponing non-essential purchases
```

### Receipt Capture
```
Camera Access Needed
To scan receipts and capture expenses, MITA needs access to your camera.
📷 Receipt scanning makes expense tracking faster and more accurate.
[Grant Access] [Enter Manually]
Tips: Go to Settings > Privacy > Camera • Find MITA and toggle access on
```

This style guide ensures consistent, user-friendly error messages that maintain trust and provide helpful guidance in financial contexts.
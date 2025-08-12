// Copyright (c) 2025 MITA - Money Intelligence Task Assistant
// Auto-generated localization file. Do not edit manually.

import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_es.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'generated/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('es'),
  ];

  /// The name of the MITA financial application
  ///
  /// In en, this message translates to:
  /// **'MITA'**
  String get appTitle;

  /// MITA's official tagline
  ///
  /// In en, this message translates to:
  /// **'Money Intelligence Task Assistant'**
  String get appTagline;

  /// Welcome screen main title
  ///
  /// In en, this message translates to:
  /// **'Welcome to MITA'**
  String get welcome;

  /// Welcome screen subtitle describing MITA's purpose
  ///
  /// In en, this message translates to:
  /// **'Your personal financial companion for smarter money management'**
  String get welcomeSubtitle;

  /// Call-to-action button text for starting onboarding
  ///
  /// In en, this message translates to:
  /// **'Get Started'**
  String get getStarted;

  /// Sign in button text
  ///
  /// In en, this message translates to:
  /// **'Sign In'**
  String get signIn;

  /// Sign up button text
  ///
  /// In en, this message translates to:
  /// **'Sign Up'**
  String get signUp;

  /// Email input field label
  ///
  /// In en, this message translates to:
  /// **'Email'**
  String get email;

  /// Password input field label
  ///
  /// In en, this message translates to:
  /// **'Password'**
  String get password;

  /// Placeholder text for email input field
  ///
  /// In en, this message translates to:
  /// **'Enter your email address'**
  String get emailHint;

  /// Placeholder text for password input field
  ///
  /// In en, this message translates to:
  /// **'Enter your password'**
  String get passwordHint;

  /// Link text for password recovery
  ///
  /// In en, this message translates to:
  /// **'Forgot Password?'**
  String get forgotPassword;

  /// Remember login checkbox label
  ///
  /// In en, this message translates to:
  /// **'Remember me'**
  String get rememberMe;

  /// Google sign-in button text
  ///
  /// In en, this message translates to:
  /// **'Continue with Google'**
  String get continueWithGoogle;

  /// Text prompting user to register
  ///
  /// In en, this message translates to:
  /// **'Don\'t have an account?'**
  String get dontHaveAccount;

  /// Link text to registration screen
  ///
  /// In en, this message translates to:
  /// **'Create Account'**
  String get createAccount;

  /// Text prompting user to sign in
  ///
  /// In en, this message translates to:
  /// **'Already have an account?'**
  String get alreadyHaveAccount;

  /// Generic loading indicator text
  ///
  /// In en, this message translates to:
  /// **'Loading...'**
  String get loading;

  /// Daily budget screen title and navigation label
  ///
  /// In en, this message translates to:
  /// **'Daily Budget'**
  String get dailyBudget;

  /// Daily spending allowance section title
  ///
  /// In en, this message translates to:
  /// **'Today\'s Allowance'**
  String get todaysAllowance;

  /// Remaining budget amount label
  ///
  /// In en, this message translates to:
  /// **'Remaining'**
  String get remaining;

  /// Amount spent label
  ///
  /// In en, this message translates to:
  /// **'Spent'**
  String get spent;

  /// Total budget amount label
  ///
  /// In en, this message translates to:
  /// **'Budget'**
  String get budget;

  /// Add new expense button and screen title
  ///
  /// In en, this message translates to:
  /// **'Add Expense'**
  String get addExpense;

  /// Expense amount input field label
  ///
  /// In en, this message translates to:
  /// **'Expense Amount'**
  String get expenseAmount;

  /// Expense description input field label
  ///
  /// In en, this message translates to:
  /// **'Description'**
  String get expenseDescription;

  /// Expense category selection label
  ///
  /// In en, this message translates to:
  /// **'Category'**
  String get category;

  /// Date field label
  ///
  /// In en, this message translates to:
  /// **'Date'**
  String get date;

  /// Save button text
  ///
  /// In en, this message translates to:
  /// **'Save'**
  String get save;

  /// Cancel button text
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get cancel;

  /// Delete button text
  ///
  /// In en, this message translates to:
  /// **'Delete'**
  String get delete;

  /// Edit button text
  ///
  /// In en, this message translates to:
  /// **'Edit'**
  String get edit;

  /// Transactions screen title and navigation label
  ///
  /// In en, this message translates to:
  /// **'Transactions'**
  String get transactions;

  /// Empty state message for transactions
  ///
  /// In en, this message translates to:
  /// **'No transactions yet'**
  String get noTransactionsYet;

  /// Empty state subtitle for transactions
  ///
  /// In en, this message translates to:
  /// **'Start tracking your expenses to see them here'**
  String get startTrackingExpenses;

  /// Insights screen title and navigation label
  ///
  /// In en, this message translates to:
  /// **'Insights'**
  String get insights;

  /// Profile screen title and navigation label
  ///
  /// In en, this message translates to:
  /// **'Profile'**
  String get profile;

  /// Settings screen title
  ///
  /// In en, this message translates to:
  /// **'Settings'**
  String get settings;

  /// Currency setting label
  ///
  /// In en, this message translates to:
  /// **'Currency'**
  String get currency;

  /// Template for currency formatting
  ///
  /// In en, this message translates to:
  /// **'\${amount}'**
  String currencyFormat(String amount);

  /// Default currency symbol for USD
  ///
  /// In en, this message translates to:
  /// **'\$'**
  String get currencySymbol;

  /// Monthly budget setting label
  ///
  /// In en, this message translates to:
  /// **'Monthly Budget'**
  String get monthlyBudget;

  /// Weekly spending display label
  ///
  /// In en, this message translates to:
  /// **'Weekly Spending'**
  String get weeklySpending;

  /// Monthly spending display label
  ///
  /// In en, this message translates to:
  /// **'Monthly Spending'**
  String get monthlySpending;

  /// Status indicator when spending exceeds budget
  ///
  /// In en, this message translates to:
  /// **'Over Budget'**
  String get overBudget;

  /// Status indicator when spending is within budget
  ///
  /// In en, this message translates to:
  /// **'Under Budget'**
  String get underBudget;

  /// Status indicator when spending is as planned
  ///
  /// In en, this message translates to:
  /// **'On Track'**
  String get onTrack;

  /// Message when daily budget is exceeded
  ///
  /// In en, this message translates to:
  /// **'Budget exceeded by {amount}'**
  String budgetExceeded(String amount);

  /// Days remaining until next payday
  ///
  /// In en, this message translates to:
  /// **'{days} days until next pay'**
  String daysUntilNextPay(int days);

  /// Spending categories section title
  ///
  /// In en, this message translates to:
  /// **'Spending Categories'**
  String get spendingCategories;

  /// Food expense category
  ///
  /// In en, this message translates to:
  /// **'Food'**
  String get food;

  /// Transportation expense category
  ///
  /// In en, this message translates to:
  /// **'Transportation'**
  String get transportation;

  /// Entertainment expense category
  ///
  /// In en, this message translates to:
  /// **'Entertainment'**
  String get entertainment;

  /// Shopping expense category
  ///
  /// In en, this message translates to:
  /// **'Shopping'**
  String get shopping;

  /// Utilities expense category
  ///
  /// In en, this message translates to:
  /// **'Utilities'**
  String get utilities;

  /// Health expense category
  ///
  /// In en, this message translates to:
  /// **'Health'**
  String get health;

  /// Other/miscellaneous expense category
  ///
  /// In en, this message translates to:
  /// **'Other'**
  String get other;

  /// Category selection prompt
  ///
  /// In en, this message translates to:
  /// **'Select Category'**
  String get selectCategory;

  /// Receipt capture feature title
  ///
  /// In en, this message translates to:
  /// **'Receipt Capture'**
  String get receiptCapture;

  /// Take photo button text
  ///
  /// In en, this message translates to:
  /// **'Take Photo'**
  String get takePhoto;

  /// Select image from gallery button text
  ///
  /// In en, this message translates to:
  /// **'Select from Gallery'**
  String get selectFromGallery;

  /// Loading message while processing receipt OCR
  ///
  /// In en, this message translates to:
  /// **'Processing receipt...'**
  String get processingReceipt;

  /// Success message after receipt processing
  ///
  /// In en, this message translates to:
  /// **'Receipt processed successfully'**
  String get receiptProcessed;

  /// Error message when receipt processing fails
  ///
  /// In en, this message translates to:
  /// **'Unable to process receipt. Please try again.'**
  String get receiptProcessingError;

  /// Notifications screen title
  ///
  /// In en, this message translates to:
  /// **'Notifications'**
  String get notifications;

  /// Goals screen title and navigation label
  ///
  /// In en, this message translates to:
  /// **'Goals'**
  String get goals;

  /// Savings goal section title
  ///
  /// In en, this message translates to:
  /// **'Savings Goal'**
  String get savingsGoal;

  /// Goal target amount field label
  ///
  /// In en, this message translates to:
  /// **'Target Amount'**
  String get targetAmount;

  /// Current savings amount label
  ///
  /// In en, this message translates to:
  /// **'Current Saved'**
  String get currentSaved;

  /// Goal progress section title
  ///
  /// In en, this message translates to:
  /// **'Progress to Goal'**
  String get progressToGoal;

  /// Logout button text
  ///
  /// In en, this message translates to:
  /// **'Logout'**
  String get logout;

  /// Logout confirmation dialog message
  ///
  /// In en, this message translates to:
  /// **'Are you sure you want to logout?'**
  String get confirmLogout;

  /// Confirmation dialog yes button
  ///
  /// In en, this message translates to:
  /// **'Yes'**
  String get yes;

  /// Confirmation dialog no button
  ///
  /// In en, this message translates to:
  /// **'No'**
  String get no;

  /// Generic error title
  ///
  /// In en, this message translates to:
  /// **'Error'**
  String get error;

  /// Network connectivity error message
  ///
  /// In en, this message translates to:
  /// **'Network connection error. Please check your internet connection.'**
  String get networkError;

  /// Server error message
  ///
  /// In en, this message translates to:
  /// **'Server error. Please try again later.'**
  String get serverError;

  /// Form validation error message
  ///
  /// In en, this message translates to:
  /// **'Please check your input and try again.'**
  String get validationError;

  /// Invalid email validation message
  ///
  /// In en, this message translates to:
  /// **'Please enter a valid email address.'**
  String get invalidEmail;

  /// Password length validation message
  ///
  /// In en, this message translates to:
  /// **'Password must be at least 8 characters long.'**
  String get passwordTooShort;

  /// Password confirmation validation message
  ///
  /// In en, this message translates to:
  /// **'Passwords do not match.'**
  String get passwordsDoNotMatch;

  /// Required field validation message
  ///
  /// In en, this message translates to:
  /// **'This field is required.'**
  String get fieldRequired;

  /// Invalid amount validation message
  ///
  /// In en, this message translates to:
  /// **'Please enter a valid amount.'**
  String get invalidAmount;

  /// Maximum amount validation message
  ///
  /// In en, this message translates to:
  /// **'Amount cannot exceed {max}.'**
  String amountTooLarge(String max);

  /// Retry button text
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get retry;

  /// Dismiss button text for dialogs and notifications
  ///
  /// In en, this message translates to:
  /// **'Dismiss'**
  String get dismiss;

  /// Generic success title
  ///
  /// In en, this message translates to:
  /// **'Success'**
  String get success;

  /// Success message when expense is added
  ///
  /// In en, this message translates to:
  /// **'Expense added successfully!'**
  String get expenseAdded;

  /// Success message when expense is updated
  ///
  /// In en, this message translates to:
  /// **'Expense updated successfully!'**
  String get expenseUpdated;

  /// Success message when expense is deleted
  ///
  /// In en, this message translates to:
  /// **'Expense deleted successfully!'**
  String get expenseDeleted;

  /// Success message when budget is updated
  ///
  /// In en, this message translates to:
  /// **'Budget updated successfully!'**
  String get budgetUpdated;

  /// Success message when profile is updated
  ///
  /// In en, this message translates to:
  /// **'Profile updated successfully!'**
  String get profileUpdated;

  /// Total spending summary label
  ///
  /// In en, this message translates to:
  /// **'Total Spent'**
  String get totalSpent;

  /// Average daily spending label
  ///
  /// In en, this message translates to:
  /// **'Average Daily'**
  String get averageDaily;

  /// Current month filter label
  ///
  /// In en, this message translates to:
  /// **'This Month'**
  String get thisMonth;

  /// Previous month filter label
  ///
  /// In en, this message translates to:
  /// **'Last Month'**
  String get lastMonth;

  /// Current week filter label
  ///
  /// In en, this message translates to:
  /// **'This Week'**
  String get thisWeek;

  /// Previous week filter label
  ///
  /// In en, this message translates to:
  /// **'Last Week'**
  String get lastWeek;

  /// Today filter label
  ///
  /// In en, this message translates to:
  /// **'Today'**
  String get today;

  /// Yesterday filter label
  ///
  /// In en, this message translates to:
  /// **'Yesterday'**
  String get yesterday;

  /// Calendar view screen title
  ///
  /// In en, this message translates to:
  /// **'Calendar'**
  String get calendar;

  /// Onboarding process title
  ///
  /// In en, this message translates to:
  /// **'Getting Started'**
  String get onboarding;

  /// Next button in onboarding and forms
  ///
  /// In en, this message translates to:
  /// **'Next'**
  String get next;

  /// Back button text
  ///
  /// In en, this message translates to:
  /// **'Back'**
  String get back;

  /// Skip button text
  ///
  /// In en, this message translates to:
  /// **'Skip'**
  String get skip;

  /// Finish button text
  ///
  /// In en, this message translates to:
  /// **'Finish'**
  String get finish;

  /// Income input and display label
  ///
  /// In en, this message translates to:
  /// **'Income'**
  String get income;

  /// Monthly income field label
  ///
  /// In en, this message translates to:
  /// **'Monthly Income'**
  String get monthlyIncome;

  /// Expenses section title
  ///
  /// In en, this message translates to:
  /// **'Expenses'**
  String get expenses;

  /// Monthly expenses total label
  ///
  /// In en, this message translates to:
  /// **'Monthly Expenses'**
  String get monthlyExpenses;

  /// Login screen welcome header
  ///
  /// In en, this message translates to:
  /// **'Welcome back'**
  String get welcomeBack;

  /// Login screen subtitle
  ///
  /// In en, this message translates to:
  /// **'Sign in to continue managing your finances'**
  String get signInToContinue;

  /// Email field label
  ///
  /// In en, this message translates to:
  /// **'Email address'**
  String get emailAddress;

  /// Email field hint text
  ///
  /// In en, this message translates to:
  /// **'Enter your email'**
  String get enterYourEmail;

  /// Password field hint text
  ///
  /// In en, this message translates to:
  /// **'Enter your password'**
  String get enterYourPassword;

  /// Email validation error message
  ///
  /// In en, this message translates to:
  /// **'Please enter your email'**
  String get pleaseEnterEmail;

  /// Email format validation error message
  ///
  /// In en, this message translates to:
  /// **'Please enter a valid email'**
  String get pleaseEnterValidEmail;

  /// Password validation error message
  ///
  /// In en, this message translates to:
  /// **'Please enter your password'**
  String get pleaseEnterPassword;

  /// Accessibility label for show password button
  ///
  /// In en, this message translates to:
  /// **'Show password'**
  String get showPassword;

  /// Accessibility label for hide password button
  ///
  /// In en, this message translates to:
  /// **'Hide password'**
  String get hidePassword;

  /// Accessibility announcement when password is hidden
  ///
  /// In en, this message translates to:
  /// **'Password hidden'**
  String get passwordHidden;

  /// Accessibility announcement when password is shown
  ///
  /// In en, this message translates to:
  /// **'Password shown'**
  String get passwordShown;

  /// Forgot password link text
  ///
  /// In en, this message translates to:
  /// **'Forgot?'**
  String get forgot;

  /// Loading message during sign in
  ///
  /// In en, this message translates to:
  /// **'Signing in...'**
  String get signingIn;

  /// Divider text between login options
  ///
  /// In en, this message translates to:
  /// **'or'**
  String get or;

  /// Error message when Google sign-in is cancelled
  ///
  /// In en, this message translates to:
  /// **'Sign-in cancelled'**
  String get signInCancelled;

  /// Error message when Google authentication fails
  ///
  /// In en, this message translates to:
  /// **'Missing Google ID token'**
  String get missingGoogleToken;

  /// Generic login error message
  ///
  /// In en, this message translates to:
  /// **'Login failed. Please check your credentials and try again.'**
  String get loginFailed;

  /// Text prompting user to register - first part
  ///
  /// In en, this message translates to:
  /// **'Don\'t have an account? '**
  String get dontHaveAccountQuestion;

  /// Accessibility announcement when remember me is enabled
  ///
  /// In en, this message translates to:
  /// **'Remember me enabled'**
  String get rememberMeEnabled;

  /// Accessibility announcement when remember me is disabled
  ///
  /// In en, this message translates to:
  /// **'Remember me disabled'**
  String get rememberMeDisabled;

  /// Loading message during app initialization
  ///
  /// In en, this message translates to:
  /// **'Initializing...'**
  String get initializing;

  /// Error message when app initialization fails
  ///
  /// In en, this message translates to:
  /// **'Initialization failed'**
  String get initializationFailed;

  /// Loading message during MITA app initialization
  ///
  /// In en, this message translates to:
  /// **'Initializing MITA...'**
  String get initializingMita;

  /// Loading message during authentication check
  ///
  /// In en, this message translates to:
  /// **'Checking authentication...'**
  String get checkingAuthentication;

  /// Welcome message for new users
  ///
  /// In en, this message translates to:
  /// **'Welcome to MITA'**
  String get welcomeToMita;

  /// Loading message during session verification
  ///
  /// In en, this message translates to:
  /// **'Verifying session...'**
  String get verifyingSession;

  /// Loading message when loading user dashboard
  ///
  /// In en, this message translates to:
  /// **'Loading your dashboard...'**
  String get loadingDashboard;

  /// Enthusiastic welcome message for returning users
  ///
  /// In en, this message translates to:
  /// **'Welcome back!'**
  String get welcomeBackExclamation;

  /// Loading message during onboarding continuation
  ///
  /// In en, this message translates to:
  /// **'Continuing setup...'**
  String get continuingSetup;

  /// Message prompting user to log in
  ///
  /// In en, this message translates to:
  /// **'Please log in to continue'**
  String get pleaseLoginToContinue;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'es'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'es':
      return AppLocalizationsEs();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}

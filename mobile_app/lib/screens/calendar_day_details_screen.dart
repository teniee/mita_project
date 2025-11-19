import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'dart:math' as math;
import '../providers/budget_provider.dart';
import '../providers/transaction_provider.dart';
import '../services/predictive_analytics_service.dart';
import '../services/budget_adapter_service.dart';
import '../services/logging_service.dart';

class CalendarDayDetailsScreen extends StatefulWidget {
  final int dayNumber;
  final int limit;
  final int spent;
  final String status;
  final DateTime date;
  final Map<String, dynamic>? dayData;
  final BudgetAdapterService? budgetService;

  const CalendarDayDetailsScreen({
    super.key,
    required this.dayNumber,
    required this.limit,
    required this.spent,
    required this.status,
    required this.date,
    this.dayData,
    this.budgetService,
  });

  @override
  State<CalendarDayDetailsScreen> createState() => _CalendarDayDetailsScreenState();
}

class _CalendarDayDetailsScreenState extends State<CalendarDayDetailsScreen>
    with TickerProviderStateMixin {

  final PredictiveAnalyticsService _predictiveService = PredictiveAnalyticsService();

  late AnimationController _slideController;
  late AnimationController _fadeController;
  late AnimationController _chartController;
  late Animation<double> _slideAnimation;
  late Animation<double> _fadeAnimation;
  late Animation<double> _chartAnimation;

  bool _isLoading = true;
  List<Map<String, dynamic>> _categoryBreakdown = [];
  Map<String, dynamic>? _predictions;
  String _selectedTab = 'spending'; // spending, predictions, insights

  @override
  void initState() {
    super.initState();
    _initializeAnimations();
    _initializeProviders();
  }

  void _initializeAnimations() {
    _slideController = AnimationController(
      duration: const Duration(milliseconds: 400),
      vsync: this,
    );
    _fadeController = AnimationController(
      duration: const Duration(milliseconds: 600),
      vsync: this,
    );
    _chartController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );

    _slideAnimation = Tween<double>(begin: 1.0, end: 0.0)
        .animate(CurvedAnimation(parent: _slideController, curve: Curves.easeOutCubic));
    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0)
        .animate(CurvedAnimation(parent: _fadeController, curve: Curves.easeIn));
    _chartAnimation = Tween<double>(begin: 0.0, end: 1.0)
        .animate(CurvedAnimation(parent: _chartController, curve: Curves.elasticOut));

    _slideController.forward();
    _fadeController.forward();
  }

  void _initializeProviders() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadDayDetails();
    });
  }

  Future<void> _loadDayDetails() async {
    try {
      setState(() => _isLoading = true);

      final isPastDate = widget.date.isBefore(DateTime.now().subtract(const Duration(days: 1)));
      final isFutureDate = widget.date.isAfter(DateTime.now());

      // Load transactions for past dates using TransactionProvider
      if (isPastDate) {
        await _loadTransactionsFromProvider();
      }

      // Load predictions for future dates or current date
      if (isFutureDate || widget.date.difference(DateTime.now()).inDays.abs() <= 1) {
        await _loadPredictions();
      }

      // Load category breakdown
      await _loadCategoryBreakdown();

      // Start chart animation
      _chartController.forward();

    } catch (e) {
      logError('Failed to load day details: $e', tag: 'CALENDAR_DAY_DETAILS');
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  Future<void> _loadTransactionsFromProvider() async {
    try {
      final transactionProvider = context.read<TransactionProvider>();

      // Set date range for the specific day
      final startOfDay = DateTime(widget.date.year, widget.date.month, widget.date.day);
      final endOfDay = DateTime(widget.date.year, widget.date.month, widget.date.day, 23, 59, 59);

      await transactionProvider.loadTransactionsByDateRange(
        startDate: startOfDay,
        endDate: endOfDay,
      );

      logInfo('Loaded transactions for ${DateFormat('yyyy-MM-dd').format(widget.date)}', tag: 'CALENDAR_DAY_DETAILS');
    } catch (e) {
      logWarning('Failed to load transactions: $e', tag: 'CALENDAR_DAY_DETAILS');
    }
  }

  Future<void> _loadPredictions() async {
    try {
      final daysFromNow = widget.date.difference(DateTime.now()).inDays;

      if (daysFromNow >= 0) {
        final categoryPredictions = <String, dynamic>{};
        final categories = ['Food & Dining', 'Transportation', 'Entertainment', 'Shopping'];

        for (final category in categories) {
          final prediction = await _predictiveService.predictCategorySpending(
            category,
            daysAhead: math.max(1, daysFromNow),
          );
          categoryPredictions[category] = {
            'predicted_amount': prediction.predictedAmount,
            'confidence': prediction.confidence,
            'scenarios': prediction.scenarios,
            'factors': prediction.factors,
          };
        }

        if (mounted) {
          setState(() {
            _predictions = categoryPredictions;
          });
        }
      }
    } catch (e) {
      logWarning('Failed to load predictions: $e', tag: 'CALENDAR_DAY_DETAILS');
      // Don't use mock predictions - show empty state instead
      if (mounted) {
        setState(() {
          _predictions = null;
        });
      }
    }
  }

  Future<void> _loadCategoryBreakdown() async {
    try {
      // Use existing day data if available
      if (widget.dayData != null && widget.dayData!['categories'] != null) {
        final categories = widget.dayData!['categories'] as Map<String, dynamic>;
        final breakdown = <Map<String, dynamic>>[];

        categories.forEach((category, budgetedAmount) {
          final spentAmount = _calculateCategorySpentAmount(category, budgetedAmount);
          breakdown.add({
            'name': _formatCategoryName(category),
            'budgeted': (budgetedAmount as num).toDouble(),
            'spent': spentAmount,
            'color': _getCategoryColor(category),
            'icon': _getCategoryIcon(category),
          });
        });

        setState(() {
          _categoryBreakdown = breakdown;
        });
      } else {
        // Generate default breakdown
        setState(() {
          _categoryBreakdown = _generateDefaultCategoryBreakdown();
        });
      }
    } catch (e) {
      logWarning('Failed to load category breakdown: $e', tag: 'CALENDAR_DAY_DETAILS');
      setState(() {
        _categoryBreakdown = _generateDefaultCategoryBreakdown();
      });
    }
  }

  double _calculateCategorySpentAmount(String category, dynamic budgetedAmount) {
    final daySpent = widget.spent.toDouble();
    final dayLimit = widget.limit.toDouble();
    final spendingRatio = dayLimit > 0 ? (daySpent / dayLimit) : 0.0;

    // Apply some variation based on category
    final categoryMultiplier = _getCategorySpendingMultiplier(category);
    return (budgetedAmount as num).toDouble() * spendingRatio * categoryMultiplier;
  }

  double _getCategorySpendingMultiplier(String category) {
    switch (category.toLowerCase()) {
      case 'food':
        return 0.8; // People tend to spend more on food
      case 'transportation':
        return 0.6; // Transportation is more fixed
      case 'entertainment':
        return 1.2; // Entertainment varies more
      case 'shopping':
        return 0.4; // Shopping is more discretionary
      default:
        return 1.0;
    }
  }

  @override
  void dispose() {
    _slideController.dispose();
    _fadeController.dispose();
    _chartController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    // Watch transaction provider for reactive updates
    final transactionProvider = context.watch<TransactionProvider>();
    final budgetProvider = context.watch<BudgetProvider>();

    return Container(
      height: MediaQuery.of(context).size.height * 0.85,
      decoration: BoxDecoration(
        color: colorScheme.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(28)),
      ),
      child: Column(
        children: [
          // Handle bar
          Container(
            margin: const EdgeInsets.only(top: 12, bottom: 8),
            width: 32,
            height: 4,
            decoration: BoxDecoration(
              color: colorScheme.onSurface.withValues(alpha: 0.4),
              borderRadius: BorderRadius.circular(2),
            ),
          ),

          Expanded(
            child: AnimatedBuilder(
              animation: _slideAnimation,
              builder: (context, child) {
                return Transform.translate(
                  offset: Offset(0, _slideAnimation.value * 50),
                  child: child,
                );
              },
              child: FadeTransition(
                opacity: _fadeAnimation,
                child: Padding(
                  padding: const EdgeInsets.all(24.0),
                  child: Column(
                    children: [
                      // Header Section
                      _buildHeaderSection(colorScheme, textTheme, budgetProvider),
                      const SizedBox(height: 24),

                      // Tab Navigation
                      _buildTabNavigation(colorScheme, textTheme),
                      const SizedBox(height: 20),

                      // Content
                      Expanded(
                        child: _buildTabContent(colorScheme, textTheme, transactionProvider),
                      ),

                      // Action Buttons
                      _buildActionButtons(colorScheme),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeaderSection(ColorScheme colorScheme, TextTheme textTheme, BudgetProvider budgetProvider) {
    final remaining = widget.limit - widget.spent;
    final spentPercentage = widget.limit > 0 ? (widget.spent / widget.limit) * 100 : 0.0;
    final isToday = _isToday();
    final isFuture = _isFuture();
    final isPast = _isPast();

    return Column(
      children: [
        // Date and Status Row
        Row(
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: _getStatusColor().withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: _getStatusColor().withValues(alpha: 0.3),
                  width: 2,
                ),
              ),
              child: Column(
                children: [
                  Text(
                    widget.dayNumber.toString(),
                    style: textTheme.headlineLarge?.copyWith(
                      color: _getStatusColor(),
                      fontWeight: FontWeight.bold,
                      fontFamily: AppTypography.fontHeading,
                    ),
                  ),
                  if (isToday)
                    Container(
                      margin: const EdgeInsets.only(top: 4),
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: colorScheme.primary,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(
                        'TODAY',
                        style: textTheme.labelSmall?.copyWith(
                          color: colorScheme.onPrimary,
                          fontWeight: FontWeight.bold,
                          fontSize: 10,
                        ),
                      ),
                    ),
                ],
              ),
            ),
            const SizedBox(width: 20),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    DateFormat('EEEE, MMMM d, yyyy').format(widget.date),
                    style: textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w600,
                      fontFamily: AppTypography.fontHeading,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: _getStatusChipColor(),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          _getStatusIcon(),
                          size: 16,
                          color: _getStatusChipTextColor(),
                        ),
                        const SizedBox(width: 4),
                        Text(
                          _getStatusText(),
                          style: textTheme.labelMedium?.copyWith(
                            color: _getStatusChipTextColor(),
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),

        const SizedBox(height: 20),

        // Budget Overview Card
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [
                colorScheme.primaryContainer,
                colorScheme.primaryContainer.withValues(alpha: 0.7),
              ],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(20),
            boxShadow: [
              BoxShadow(
                color: colorScheme.primary.withValues(alpha: 0.1),
                blurRadius: 10,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Column(
            children: [
              Row(
                children: [
                  Expanded(
                    child: _buildBudgetStat(
                      'Budget',
                      '\$${widget.limit}',
                      Icons.account_balance_wallet_outlined,
                      colorScheme.primary,
                      textTheme,
                    ),
                  ),
                  Container(
                    width: 1,
                    height: 40,
                    color: colorScheme.onPrimaryContainer.withValues(alpha: 0.2),
                  ),
                  Expanded(
                    child: _buildBudgetStat(
                      isPast ? 'Spent' : isFuture ? 'Available' : 'Spent',
                      '\$${isPast ? widget.spent : isFuture ? widget.limit : widget.spent}',
                      isPast ? Icons.shopping_cart_outlined :
                      isFuture ? Icons.savings_outlined : Icons.shopping_cart_outlined,
                      isPast ? colorScheme.error :
                      isFuture ? colorScheme.tertiary : colorScheme.error,
                      textTheme,
                    ),
                  ),
                  Container(
                    width: 1,
                    height: 40,
                    color: colorScheme.onPrimaryContainer.withValues(alpha: 0.2),
                  ),
                  Expanded(
                    child: _buildBudgetStat(
                      isFuture ? 'Predicted' : 'Remaining',
                      isFuture ? '\$${_getPredictedSpending().toStringAsFixed(0)}' : '\$$remaining',
                      isFuture ? Icons.trending_up_outlined : Icons.account_balance_outlined,
                      isFuture ? colorScheme.secondary : colorScheme.tertiary,
                      textTheme,
                    ),
                  ),
                ],
              ),

              if (!isFuture) ...[
                const SizedBox(height: 16),
                _buildProgressIndicator(spentPercentage, colorScheme, textTheme),
              ],
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildBudgetStat(String label, String amount, IconData icon, Color color, TextTheme textTheme) {
    return Column(
      children: [
        Icon(icon, color: color, size: 24),
        const SizedBox(height: 8),
        Text(
          label,
          style: textTheme.bodySmall?.copyWith(
            color: color.withValues(alpha: 0.8),
            fontWeight: FontWeight.w500,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          amount,
          style: textTheme.titleLarge?.copyWith(
            color: color,
            fontWeight: FontWeight.bold,
            fontFamily: AppTypography.fontHeading,
          ),
        ),
      ],
    );
  }

  Widget _buildProgressIndicator(double spentPercentage, ColorScheme colorScheme, TextTheme textTheme) {
    return Column(
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              'Spending Progress',
              style: textTheme.bodyMedium?.copyWith(
                fontWeight: FontWeight.w500,
                color: colorScheme.onPrimaryContainer,
              ),
            ),
            Text(
              '${spentPercentage.toStringAsFixed(1)}%',
              style: textTheme.bodyMedium?.copyWith(
                fontWeight: FontWeight.bold,
                color: spentPercentage > 100 ? colorScheme.error : colorScheme.primary,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        AnimatedBuilder(
          animation: _chartAnimation,
          builder: (context, child) {
            return LinearProgressIndicator(
              value: (spentPercentage / 100 * _chartAnimation.value).clamp(0.0, 1.0),
              backgroundColor: colorScheme.onPrimaryContainer.withValues(alpha: 0.2),
              valueColor: AlwaysStoppedAnimation<Color>(
                spentPercentage > 100 ? colorScheme.error :
                spentPercentage > 80 ? Colors.orange :
                colorScheme.primary,
              ),
              minHeight: 8,
              borderRadius: BorderRadius.circular(4),
            );
          },
        ),
      ],
    );
  }

  Widget _buildTabNavigation(ColorScheme colorScheme, TextTheme textTheme) {
    final tabs = <String, IconData>{
      'spending': Icons.receipt_long_outlined,
      'predictions': Icons.trending_up_outlined,
      'insights': Icons.insights_outlined,
    };

    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainer,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: tabs.entries.map((entry) {
          final isSelected = _selectedTab == entry.key;
          return Expanded(
            child: GestureDetector(
              onTap: () => setState(() => _selectedTab = entry.key),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                padding: const EdgeInsets.symmetric(vertical: 12),
                decoration: BoxDecoration(
                  color: isSelected ? colorScheme.primary : Colors.transparent,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      entry.value,
                      size: 18,
                      color: isSelected ? colorScheme.onPrimary : colorScheme.onSurface,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      _getTabTitle(entry.key),
                      style: textTheme.labelMedium?.copyWith(
                        color: isSelected ? colorScheme.onPrimary : colorScheme.onSurface,
                        fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildTabContent(ColorScheme colorScheme, TextTheme textTheme, TransactionProvider transactionProvider) {
    // Show loading state from provider or local loading
    if (_isLoading || transactionProvider.isLoading) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('Loading day details...'),
          ],
        ),
      );
    }

    switch (_selectedTab) {
      case 'spending':
        return _buildSpendingTab(colorScheme, textTheme, transactionProvider);
      case 'predictions':
        return _buildPredictionsTab(colorScheme, textTheme);
      case 'insights':
        return _buildInsightsTab(colorScheme, textTheme);
      default:
        return _buildSpendingTab(colorScheme, textTheme, transactionProvider);
    }
  }

  Widget _buildSpendingTab(ColorScheme colorScheme, TextTheme textTheme, TransactionProvider transactionProvider) {
    // Convert provider transactions to the expected format
    final transactions = transactionProvider.transactions.map((t) => {
      'amount': t.amount,
      'description': t.description,
      'category': t.category,
      'time': DateFormat('HH:mm').format(t.spentAt),
    }).toList();

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Category Breakdown
          Text(
            'Category Breakdown',
            style: textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
              fontFamily: AppTypography.fontHeading,
            ),
          ),
          const SizedBox(height: 16),

          ..._categoryBreakdown.map((category) => _buildCategoryItem(category, colorScheme, textTheme)),

          const SizedBox(height: 24),

          // Recent Transactions (for past dates)
          if (_isPast()) ...[
            Text(
              'Transactions',
              style: textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
                fontFamily: AppTypography.fontHeading,
              ),
            ),
            const SizedBox(height: 16),

            if (transactions.isNotEmpty)
              ...transactions.take(5).map((transaction) =>
                  _buildTransactionItem(transaction, colorScheme, textTheme))
            else
              _buildEmptyTransactionsState(colorScheme, textTheme),
          ],
        ],
      ),
    );
  }

  Widget _buildCategoryItem(Map<String, dynamic> category, ColorScheme colorScheme, TextTheme textTheme) {
    final budgeted = (category['budgeted'] as num).toDouble();
    final spent = (category['spent'] as num).toDouble();
    final color = category['color'] as Color;
    final icon = category['icon'] as IconData;
    final percentage = budgeted > 0 ? (spent / budgeted) : 0.0;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainer,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: color.withValues(alpha: 0.2),
          width: 1,
        ),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, color: color, size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      category['name'] as String,
                      style: textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w600,
                        fontFamily: AppTypography.fontHeading,
                      ),
                    ),
                    Text(
                      _isFuture() ? 'Budget allocation' : 'Spending vs budget',
                      style: textTheme.bodySmall?.copyWith(
                        color: colorScheme.onSurface.withValues(alpha: 0.6),
                      ),
                    ),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    _isFuture() ? '\$${budgeted.toStringAsFixed(0)}' :
                    '\$${spent.toStringAsFixed(0)} / \$${budgeted.toStringAsFixed(0)}',
                    style: textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: percentage > 1.0 ? colorScheme.error : colorScheme.onSurface,
                    ),
                  ),
                  if (!_isFuture())
                    Text(
                      '${(percentage * 100).toStringAsFixed(0)}% used',
                      style: textTheme.bodySmall?.copyWith(
                        color: percentage > 1.0 ? colorScheme.error :
                               colorScheme.onSurface.withValues(alpha: 0.6),
                      ),
                    ),
                ],
              ),
            ],
          ),

          if (!_isFuture()) ...[
            const SizedBox(height: 12),
            AnimatedBuilder(
              animation: _chartAnimation,
              builder: (context, child) {
                return LinearProgressIndicator(
                  value: (percentage * _chartAnimation.value).clamp(0.0, 1.0),
                  backgroundColor: colorScheme.surfaceContainerHighest,
                  valueColor: AlwaysStoppedAnimation<Color>(
                    percentage > 1.0 ? colorScheme.error : color,
                  ),
                  minHeight: 4,
                  borderRadius: BorderRadius.circular(2),
                );
              },
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildTransactionItem(Map<String, dynamic> transaction, ColorScheme colorScheme, TextTheme textTheme) {
    final amount = (transaction['amount'] as num).toDouble();
    final description = transaction['description'] as String? ?? 'Unknown';
    final category = transaction['category'] as String? ?? 'Other';
    final time = transaction['time'] as String? ?? DateFormat('HH:mm').format(DateTime.now());

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainer.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: _getCategoryColor(category),
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  description,
                  style: textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w500,
                  ),
                ),
                Text(
                  '$category • $time',
                  style: textTheme.bodySmall?.copyWith(
                    color: colorScheme.onSurface.withValues(alpha: 0.6),
                  ),
                ),
              ],
            ),
          ),
          Text(
            '\$${amount.toStringAsFixed(2)}',
            style: textTheme.titleSmall?.copyWith(
              fontWeight: FontWeight.bold,
              color: colorScheme.error,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPredictionsTab(ColorScheme colorScheme, TextTheme textTheme) {
    if (_predictions == null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.psychology_outlined,
              size: 64,
              color: colorScheme.onSurface.withValues(alpha: 0.4),
            ),
            const SizedBox(height: 16),
            Text(
              'No predictions available',
              style: textTheme.titleMedium?.copyWith(
                color: colorScheme.onSurface.withValues(alpha: 0.6),
              ),
            ),
          ],
        ),
      );
    }

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // AI Predictions Header
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  Colors.blue.withValues(alpha: 0.1),
                  Colors.purple.withValues(alpha: 0.1),
                ],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.blue.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(Icons.psychology, color: Colors.blue),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'AI-Powered Predictions',
                        style: textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                          fontFamily: AppTypography.fontHeading,
                        ),
                      ),
                      Text(
                        _isFuture() ? 'Predicted spending for this day' : 'Spending insights',
                        style: textTheme.bodySmall?.copyWith(
                          color: colorScheme.onSurface.withValues(alpha: 0.7),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 20),

          // Prediction Items
          ...(_predictions!.entries.map((entry) =>
              _buildPredictionItem(entry.key, entry.value, colorScheme, textTheme))),
        ],
      ),
    );
  }

  Widget _buildPredictionItem(String category, dynamic prediction, ColorScheme colorScheme, TextTheme textTheme) {
    final predictedAmount = (prediction['predicted_amount'] as num?)?.toDouble() ?? 0.0;
    final confidence = (prediction['confidence'] as num?)?.toDouble() ?? 0.0;
    final factors = prediction['factors'] as List<dynamic>? ?? [];

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainer,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: _getCategoryColor(category).withValues(alpha: 0.2),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: _getCategoryColor(category).withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(
                  _getCategoryIcon(category),
                  color: _getCategoryColor(category),
                  size: 20,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  category,
                  style: textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w600,
                    fontFamily: AppTypography.fontHeading,
                  ),
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    '\$${predictedAmount.toStringAsFixed(0)}',
                    style: textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: _getCategoryColor(category),
                    ),
                  ),
                  Text(
                    '${(confidence * 100).toStringAsFixed(0)}% confidence',
                    style: textTheme.bodySmall?.copyWith(
                      color: colorScheme.onSurface.withValues(alpha: 0.6),
                    ),
                  ),
                ],
              ),
            ],
          ),

          const SizedBox(height: 12),

          // Confidence indicator
          Row(
            children: [
              Text(
                'Confidence',
                style: textTheme.bodySmall?.copyWith(
                  color: colorScheme.onSurface.withValues(alpha: 0.6),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: AnimatedBuilder(
                  animation: _chartAnimation,
                  builder: (context, child) {
                    return LinearProgressIndicator(
                      value: confidence * _chartAnimation.value,
                      backgroundColor: colorScheme.surfaceContainerHighest,
                      valueColor: AlwaysStoppedAnimation<Color>(
                        confidence > 0.8 ? Colors.green :
                        confidence > 0.5 ? Colors.orange :
                        Colors.red,
                      ),
                      minHeight: 4,
                      borderRadius: BorderRadius.circular(2),
                    );
                  },
                ),
              ),
            ],
          ),

          if (factors.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(
              'Key Factors',
              style: textTheme.bodySmall?.copyWith(
                fontWeight: FontWeight.w600,
                color: colorScheme.onSurface.withValues(alpha: 0.8),
              ),
            ),
            const SizedBox(height: 4),
            ...factors.take(2).map((factor) => Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text(
                '• $factor',
                style: textTheme.bodySmall?.copyWith(
                  color: colorScheme.onSurface.withValues(alpha: 0.6),
                ),
              ),
            )),
          ],
        ],
      ),
    );
  }

  Widget _buildInsightsTab(ColorScheme colorScheme, TextTheme textTheme) {
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Smart Insights Header
          Text(
            'Smart Insights',
            style: textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
              fontFamily: AppTypography.fontHeading,
            ),
          ),
          const SizedBox(height: 16),

          // Insights Cards
          ..._generateInsights().map((insight) => _buildInsightCard(insight, colorScheme, textTheme)),
        ],
      ),
    );
  }

  Widget _buildInsightCard(Map<String, dynamic> insight, ColorScheme colorScheme, TextTheme textTheme) {
    final type = insight['type'] as String;
    final title = insight['title'] as String;
    final description = insight['description'] as String;
    final action = insight['action'] as String?;

    final color = _getInsightColor(type);
    final icon = _getInsightIcon(type);

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: color.withValues(alpha: 0.2),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, color: color, size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  title,
                  style: textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w600,
                    color: color,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            description,
            style: textTheme.bodyMedium?.copyWith(
              color: colorScheme.onSurface.withValues(alpha: 0.8),
            ),
          ),
          if (action != null) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                action,
                style: textTheme.bodySmall?.copyWith(
                  color: color,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildActionButtons(ColorScheme colorScheme) {
    return Row(
      children: [
        Expanded(
          child: OutlinedButton.icon(
            onPressed: () => Navigator.pop(context),
            icon: const Icon(Icons.close_rounded),
            label: const Text('Close'),
            style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 12),
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: FilledButton.icon(
            onPressed: () {
              Navigator.pop(context);
              Navigator.pushNamed(context, '/add_expense');
            },
            icon: const Icon(Icons.add_rounded),
            label: const Text('Add Expense'),
            style: FilledButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 12),
            ),
          ),
        ),
      ],
    );
  }

  // Helper Methods
  bool _isToday() => DateUtils.isSameDay(widget.date, DateTime.now());
  bool _isFuture() => widget.date.isAfter(DateTime.now());
  bool _isPast() => widget.date.isBefore(DateTime.now().subtract(const Duration(days: 1)));

  String _getTabTitle(String tab) {
    switch (tab) {
      case 'spending': return 'Spending';
      case 'predictions': return 'Predictions';
      case 'insights': return 'Insights';
      default: return tab;
    }
  }

  Color _getStatusColor() {
    final colorScheme = Theme.of(context).colorScheme;
    switch (widget.status.toLowerCase()) {
      case 'over': return colorScheme.error;
      case 'warning': return Colors.orange;
      case 'good':
      default: return colorScheme.primary;
    }
  }

  String _getStatusText() {
    switch (widget.status.toLowerCase()) {
      case 'over': return 'Over Budget';
      case 'warning': return 'Approaching Limit';
      case 'good':
      default: return _isToday() ? 'On Track Today' : _isFuture() ? 'Budget Available' : 'Completed';
    }
  }

  IconData _getStatusIcon() {
    switch (widget.status.toLowerCase()) {
      case 'over': return Icons.warning_rounded;
      case 'warning': return Icons.info_outline_rounded;
      case 'good':
      default: return Icons.check_circle_outline_rounded;
    }
  }

  Color _getStatusChipColor() {
    final colorScheme = Theme.of(context).colorScheme;
    switch (widget.status.toLowerCase()) {
      case 'over': return colorScheme.errorContainer;
      case 'warning': return Colors.orange.withValues(alpha: 0.1);
      case 'good':
      default: return colorScheme.primaryContainer;
    }
  }

  Color _getStatusChipTextColor() {
    final colorScheme = Theme.of(context).colorScheme;
    switch (widget.status.toLowerCase()) {
      case 'over': return colorScheme.onErrorContainer;
      case 'warning': return Colors.orange;
      case 'good':
      default: return colorScheme.onPrimaryContainer;
    }
  }

  double _getPredictedSpending() {
    if (_predictions == null) return 0.0;
    return _predictions!.values.fold<double>(0.0, (sum, pred) => sum + ((pred['predicted_amount'] as num?)?.toDouble() ?? 0.0));
  }

  String _formatCategoryName(String category) {
    switch (category.toLowerCase()) {
      case 'food': return 'Food & Dining';
      case 'transportation': return 'Transportation';
      case 'entertainment': return 'Entertainment';
      case 'shopping': return 'Shopping';
      case 'healthcare': return 'Healthcare';
      default: return category.substring(0, 1).toUpperCase() + category.substring(1);
    }
  }

  Color _getCategoryColor(String category) {
    switch (category.toLowerCase()) {
      case 'food':
      case 'food & dining': return Colors.green;
      case 'transportation': return Colors.blue;
      case 'entertainment': return Colors.purple;
      case 'shopping': return Colors.orange;
      case 'healthcare': return Colors.red;
      default: return Colors.grey;
    }
  }

  IconData _getCategoryIcon(String category) {
    switch (category.toLowerCase()) {
      case 'food':
      case 'food & dining': return Icons.restaurant_outlined;
      case 'transportation': return Icons.directions_car_outlined;
      case 'entertainment': return Icons.movie_outlined;
      case 'shopping': return Icons.shopping_bag_outlined;
      case 'healthcare': return Icons.health_and_safety_outlined;
      default: return Icons.category_outlined;
    }
  }

  List<Map<String, dynamic>> _generateDefaultCategoryBreakdown() {
    return [
      {
        'name': 'Food & Dining',
        'budgeted': (widget.limit * 0.4).toDouble(),
        'spent': (widget.spent * 0.4).toDouble(),
        'color': Colors.green,
        'icon': Icons.restaurant_outlined,
      },
      {
        'name': 'Transportation',
        'budgeted': (widget.limit * 0.25).toDouble(),
        'spent': (widget.spent * 0.3).toDouble(),
        'color': Colors.blue,
        'icon': Icons.directions_car_outlined,
      },
      {
        'name': 'Entertainment',
        'budgeted': (widget.limit * 0.2).toDouble(),
        'spent': (widget.spent * 0.2).toDouble(),
        'color': Colors.purple,
        'icon': Icons.movie_outlined,
      },
      {
        'name': 'Shopping',
        'budgeted': (widget.limit * 0.15).toDouble(),
        'spent': (widget.spent * 0.1).toDouble(),
        'color': Colors.orange,
        'icon': Icons.shopping_bag_outlined,
      },
    ];
  }

  Widget _buildEmptyTransactionsState(ColorScheme colorScheme, TextTheme textTheme) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainer.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: colorScheme.outline.withValues(alpha: 0.2),
          width: 1,
        ),
      ),
      child: Column(
        children: [
          Icon(
            Icons.receipt_long_outlined,
            size: 48,
            color: colorScheme.onSurface.withValues(alpha: 0.4),
          ),
          const SizedBox(height: 12),
          Text(
            'No transactions recorded',
            style: textTheme.titleMedium?.copyWith(
              color: colorScheme.onSurface.withValues(alpha: 0.6),
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'Add your first expense to start tracking spending for this day',
            style: textTheme.bodySmall?.copyWith(
              color: colorScheme.onSurface.withValues(alpha: 0.5),
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          OutlinedButton.icon(
            onPressed: () {
              Navigator.pop(context);
              Navigator.pushNamed(context, '/add_expense');
            },
            icon: const Icon(Icons.add),
            label: const Text('Add Transaction'),
            style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            ),
          ),
        ],
      ),
    );
  }

  List<Map<String, dynamic>> _generateInsights() {
    final insights = <Map<String, dynamic>>[];

    if (_isToday()) {
      final remaining = widget.limit - widget.spent;
      if (remaining > widget.limit * 0.7) {
        insights.add({
          'type': 'positive',
          'title': 'Great spending control!',
          'description': 'You have \$${remaining.toStringAsFixed(0)} remaining today. You\'re on track to stay under budget.',
          'action': 'Keep up the good work!',
        });
      } else if (remaining < widget.limit * 0.2) {
        insights.add({
          'type': 'warning',
          'title': 'Budget running low',
          'description': 'Only \$${remaining.toStringAsFixed(0)} left for today. Consider making fewer purchases.',
          'action': 'Monitor remaining expenses carefully',
        });
      }
    }

    if (_isFuture()) {
      insights.add({
        'type': 'info',
        'title': 'Budget planning',
        'description': 'Based on your spending patterns, you\'re predicted to spend \$${_getPredictedSpending().toStringAsFixed(0)} on this day.',
        'action': 'Plan your expenses accordingly',
      });
    }

    if (_isPast()) {
      final spentRatio = widget.limit > 0 ? widget.spent / widget.limit : 0.0;
      if (spentRatio < 0.8) {
        insights.add({
          'type': 'positive',
          'title': 'Budget success',
          'description': 'You stayed well within budget on this day, spending only ${(spentRatio * 100).toStringAsFixed(0)}% of your daily limit.',
          'action': 'This is a great example to follow',
        });
      } else if (spentRatio > 1.2) {
        insights.add({
          'type': 'warning',
          'title': 'Over-budget day',
          'description': 'You exceeded your budget by ${((spentRatio - 1) * 100).toStringAsFixed(0)}% on this day.',
          'action': 'Analyze what led to overspending',
        });
      }
    }

    // Add a general tip
    insights.add({
      'type': 'tip',
      'title': 'Smart spending tip',
      'description': 'Track your largest category expenses to identify areas for potential savings.',
      'action': 'Review your Food & Dining expenses',
    });

    return insights;
  }

  Color _getInsightColor(String type) {
    switch (type) {
      case 'positive': return Colors.green;
      case 'warning': return Colors.orange;
      case 'error': return Colors.red;
      case 'info': return Colors.blue;
      case 'tip': return Colors.purple;
      default: return Colors.grey;
    }
  }

  IconData _getInsightIcon(String type) {
    switch (type) {
      case 'positive': return Icons.check_circle_outline;
      case 'warning': return Icons.warning_outlined;
      case 'error': return Icons.error_outline;
      case 'info': return Icons.info_outline;
      case 'tip': return Icons.lightbulb_outline;
      default: return Icons.insights;
    }
  }
}

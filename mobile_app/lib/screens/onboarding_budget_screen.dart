import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../services/onboarding_state.dart';
import '../services/income_service.dart';
import '../providers/user_provider.dart';
import '../theme/income_theme.dart';

class OnboardingBudgetScreen extends StatefulWidget {
  const OnboardingBudgetScreen({super.key});

  @override
  State<OnboardingBudgetScreen> createState() => _OnboardingBudgetScreenState();
}

class _OnboardingBudgetScreenState extends State<OnboardingBudgetScreen>
    with TickerProviderStateMixin {
  final _incomeService = IncomeService();
  late IncomeTier _incomeTier;
  late double _monthlyIncome;
  late Map<String, dynamic> _budgetTemplate;
  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;

  Map<String, double> _customAllocations = {};
  bool _useCustomBudget = false;

  @override
  void initState() {
    super.initState();

    // Get income data from onboarding state
    if (OnboardingState.instance.income == null || OnboardingState.instance.income! <= 0) {
      throw Exception(
          'Income must be provided before budget screen. Please go back and complete income entry.');
    }
    _monthlyIncome = OnboardingState.instance.income!;
    _incomeTier =
        OnboardingState.instance.incomeTier ?? _incomeService.classifyIncome(_monthlyIncome);

    // Generate budget template
    _budgetTemplate = _incomeService.getBudgetTemplate(_incomeTier, _monthlyIncome);
    _customAllocations = Map<String, double>.from(_budgetTemplate['allocations']);

    _animationController = AnimationController(
      duration: const Duration(milliseconds: 600),
      vsync: this,
    );
    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeInOut),
    );

    _animationController.forward();
  }

  void _onAllocationChanged(String category, double value) {
    setState(() {
      _customAllocations[category] = value;
      _useCustomBudget = true;
    });
  }

  void _resetToRecommended() {
    setState(() {
      _customAllocations = Map<String, double>.from(_budgetTemplate['allocations']);
      _useCustomBudget = false;
    });
  }

  void _continueToBudgetSetup() {
    // Store budget preferences in onboarding state
    OnboardingState.instance.expenses = _customAllocations.entries
        .map((entry) => {
              'category': entry.key,
              'amount': entry.value,
              'type': 'budget_allocation',
            })
        .toList();

    Navigator.pushNamed(context, '/onboarding_goal');
  }

  double get _totalAllocated => _customAllocations.values.fold(0.0, (sum, amount) => sum + amount);
  double get _remainingBudget => _monthlyIncome - _totalAllocated;

  @override
  Widget build(BuildContext context) {
    final primaryColor = _incomeService.getIncomeTierPrimaryColor(_incomeTier);
    final tierName = _incomeService.getIncomeTierName(_incomeTier);
    final categoryColors = IncomeTheme.getBudgetCategoryColors(_incomeTier);

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: IncomeTheme.createTierAppBar(
        tier: _incomeTier,
        title: 'Budget Setup',
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: FadeTransition(
        opacity: _fadeAnimation,
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header with income tier info
              Card(
                elevation: 2,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(
                            _incomeService.getIncomeTierIcon(_incomeTier),
                            color: primaryColor,
                            size: 28,
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'Budget for $tierName',
                                  style: TextStyle(
                                    fontFamily: AppTypography.fontHeading,
                                    fontWeight: FontWeight.bold,
                                    fontSize: 20,
                                    color: primaryColor,
                                  ),
                                ),
                                Text(
                                  'Monthly Income: \$${_monthlyIncome.toStringAsFixed(0)}',
                                  style: const TextStyle(
                                    fontFamily: AppTypography.fontBody,
                                    fontSize: 16,
                                    color: Colors.black87,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: primaryColor.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Row(
                          children: [
                            Icon(
                              Icons.lightbulb_outline_rounded,
                              color: primaryColor,
                              size: 20,
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                'We\'ve created a personalized budget based on your income level. You can adjust these allocations to fit your needs.',
                                style: TextStyle(
                                  fontFamily: AppTypography.fontBody,
                                  fontSize: 14,
                                  color: primaryColor,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 24),

              // Budget allocation cards
              Text(
                'Budget Allocations',
                style: TextStyle(
                  fontFamily: AppTypography.fontHeading,
                  fontWeight: FontWeight.bold,
                  fontSize: 18,
                  color: primaryColor,
                ),
              ),
              const SizedBox(height: 16),

              ...(_customAllocations.entries.map((entry) {
                final category = entry.key;
                final amount = entry.value;
                final percentage = _incomeService.getIncomePercentage(amount, _monthlyIncome);
                final categoryColor = categoryColors[category] ?? Colors.grey.shade600;

                return Card(
                  elevation: 1,
                  margin: const EdgeInsets.only(bottom: 12),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      children: [
                        Row(
                          children: [
                            Container(
                              width: 12,
                              height: 12,
                              decoration: BoxDecoration(
                                color: categoryColor,
                                shape: BoxShape.circle,
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                category.toUpperCase(),
                                style: const TextStyle(
                                  fontFamily: AppTypography.fontHeading,
                                  fontWeight: FontWeight.w600,
                                  fontSize: 14,
                                ),
                              ),
                            ),
                            Text(
                              '${percentage.toStringAsFixed(1)}%',
                              style: TextStyle(
                                fontFamily: AppTypography.fontHeading,
                                fontWeight: FontWeight.bold,
                                fontSize: 14,
                                color: categoryColor,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            Expanded(
                              child: Slider(
                                value: amount,
                                min: 0,
                                max: _monthlyIncome * 0.5, // Max 50% of income
                                divisions: 50,
                                activeColor: categoryColor,
                                inactiveColor: categoryColor.withValues(alpha: 0.2),
                                onChanged: (value) => _onAllocationChanged(category, value),
                              ),
                            ),
                            const SizedBox(width: 12),
                            SizedBox(
                              width: 80,
                              child: Text(
                                '\$${amount.toStringAsFixed(0)}',
                                style: TextStyle(
                                  fontFamily: AppTypography.fontHeading,
                                  fontWeight: FontWeight.bold,
                                  fontSize: 16,
                                  color: categoryColor,
                                ),
                                textAlign: TextAlign.end,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                );
              }).toList()),

              const SizedBox(height: 20),

              // Budget summary
              Card(
                elevation: 3,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            'Total Allocated',
                            style: TextStyle(
                              fontFamily: AppTypography.fontHeading,
                              fontWeight: FontWeight.w600,
                              fontSize: 16,
                              color: Colors.grey.shade700,
                            ),
                          ),
                          Text(
                            '\$${_totalAllocated.toStringAsFixed(0)}',
                            style: const TextStyle(
                              fontFamily: AppTypography.fontHeading,
                              fontWeight: FontWeight.bold,
                              fontSize: 18,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            'Remaining',
                            style: TextStyle(
                              fontFamily: AppTypography.fontHeading,
                              fontWeight: FontWeight.w600,
                              fontSize: 16,
                              color: _remainingBudget < 0
                                  ? Colors.red.shade600
                                  : Colors.green.shade600,
                            ),
                          ),
                          Text(
                            '\$${_remainingBudget.toStringAsFixed(0)}',
                            style: TextStyle(
                              fontFamily: AppTypography.fontHeading,
                              fontWeight: FontWeight.bold,
                              fontSize: 18,
                              color: _remainingBudget < 0
                                  ? Colors.red.shade600
                                  : Colors.green.shade600,
                            ),
                          ),
                        ],
                      ),
                      if (_remainingBudget < 0) ...[
                        const SizedBox(height: 12),
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: Colors.red.shade50,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Row(
                            children: [
                              Icon(
                                Icons.warning_rounded,
                                color: Colors.red.shade600,
                                size: 20,
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  'Budget exceeds income by \$${(-_remainingBudget).toStringAsFixed(0)}',
                                  style: TextStyle(
                                    fontFamily: AppTypography.fontBody,
                                    fontSize: 12,
                                    color: Colors.red.shade600,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 20),

              // Action buttons
              Row(
                children: [
                  if (_useCustomBudget)
                    Expanded(
                      child: OutlinedButton(
                        onPressed: _resetToRecommended,
                        style: OutlinedButton.styleFrom(
                          side: BorderSide(color: primaryColor),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                          padding: const EdgeInsets.symmetric(vertical: 16),
                        ),
                        child: Text(
                          'Reset to Recommended',
                          style: TextStyle(
                            fontFamily: AppTypography.fontHeading,
                            fontWeight: FontWeight.w600,
                            color: primaryColor,
                          ),
                        ),
                      ),
                    ),
                  if (_useCustomBudget) const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: _remainingBudget >= 0 ? _continueToBudgetSetup : null,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: primaryColor,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                        padding: const EdgeInsets.symmetric(vertical: 16),
                      ),
                      child: const Text(
                        'Continue to Goals',
                        style: TextStyle(
                          fontFamily: AppTypography.fontHeading,
                          fontWeight: FontWeight.w600,
                          fontSize: 16,
                        ),
                      ),
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 40),
            ],
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }
}

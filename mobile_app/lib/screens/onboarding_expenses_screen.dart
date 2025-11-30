import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'package:flutter/services.dart';
import '../services/onboarding_state.dart';
import '../widgets/onboarding_progress_indicator.dart';

class PredefinedExpense {
  final String id;
  final String label;
  final IconData icon;
  bool isSelected;
  String amount;

  PredefinedExpense({
    required this.id,
    required this.label,
    required this.icon,
    this.isSelected = false,
    this.amount = '',
  });
}

class OnboardingExpensesScreen extends StatefulWidget {
  const OnboardingExpensesScreen({super.key});

  @override
  State<OnboardingExpensesScreen> createState() => _OnboardingExpensesScreenState();
}

class _OnboardingExpensesScreenState extends State<OnboardingExpensesScreen> {
  final _formKey = GlobalKey<FormState>();

  final List<PredefinedExpense> expenses = [
    PredefinedExpense(id: 'rent', label: 'Rent/Mortgage', icon: Icons.home),
    PredefinedExpense(id: 'utilities', label: 'Utilities (Electric, Water, Gas)', icon: Icons.bolt),
    PredefinedExpense(id: 'internet', label: 'Internet & Phone', icon: Icons.wifi),
    PredefinedExpense(id: 'insurance', label: 'Insurance', icon: Icons.shield),
    PredefinedExpense(id: 'car_payment', label: 'Car Payment', icon: Icons.directions_car),
    PredefinedExpense(
        id: 'subscriptions',
        label: 'Subscriptions (Netflix, Spotify, etc.)',
        icon: Icons.subscriptions),
    PredefinedExpense(id: 'loan_payment', label: 'Loan Payments', icon: Icons.payment),
    PredefinedExpense(id: 'childcare', label: 'Childcare', icon: Icons.child_care),
  ];

  Future<void> _submitExpenses() async {
    if (_formKey.currentState?.validate() ?? false) {
      final apiExpenses = expenses
          .where((e) =>
              e.isSelected &&
              e.amount.isNotEmpty &&
              double.tryParse(e.amount) != null &&
              double.parse(e.amount) > 0)
          .map((e) => {"category": e.id, "amount": double.parse(e.amount)})
          .toList();

      // Preserve expenses for the final onboarding request
      OnboardingState.instance.expenses = apiExpenses;
      await OnboardingState.instance.save();

      Navigator.pushNamed(context, '/onboarding_goal');
    }
  }

  Widget _buildExpenseCard(PredefinedExpense expense) {
    return Card(
      elevation: expense.isSelected ? 3 : 1,
      color: expense.isSelected ? AppColors.secondary.withOpacity(0.3) : Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(
          color: expense.isSelected ? AppColors.textPrimary : Colors.grey.shade300,
          width: expense.isSelected ? 2 : 1,
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Row(
              children: [
                // Icon
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppColors.textPrimary.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(
                    expense.icon,
                    color: AppColors.textPrimary,
                    size: 24,
                  ),
                ),
                const SizedBox(width: 12),
                // Label and checkbox
                Expanded(
                  child: Text(
                    expense.label,
                    style: const TextStyle(
                      fontFamily: AppTypography.fontBody,
                      fontWeight: FontWeight.w600,
                      fontSize: 15,
                      color: AppColors.textPrimary,
                    ),
                  ),
                ),
                Checkbox(
                  value: expense.isSelected,
                  activeColor: AppColors.textPrimary,
                  onChanged: (value) {
                    setState(() {
                      expense.isSelected = value ?? false;
                      if (!expense.isSelected) {
                        expense.amount = '';
                      }
                    });
                  },
                ),
              ],
            ),
            // Amount field (shown only when selected)
            if (expense.isSelected) ...[
              const SizedBox(height: 12),
              TextFormField(
                initialValue: expense.amount,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: [
                  FilteringTextInputFormatter.allow(RegExp(r'^\d+\.?\d{0,2}')),
                ],
                decoration: InputDecoration(
                  labelText: 'Monthly Amount',
                  prefixText: '\$ ',
                  filled: true,
                  fillColor: Colors.white,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  contentPadding: const EdgeInsets.symmetric(vertical: 14, horizontal: 12),
                ),
                onChanged: (value) {
                  expense.amount = value;
                },
                validator: (value) {
                  if (expense.isSelected) {
                    if (value == null || value.isEmpty) {
                      return 'Enter amount';
                    }
                    final amount = double.tryParse(value);
                    if (amount == null || amount <= 0) {
                      return 'Enter valid amount';
                    }
                  }
                  return null;
                },
              ),
            ],
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final selectedCount = expenses.where((e) => e.isSelected).length;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: AppColors.textPrimary),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: SafeArea(
        child: Column(
          children: [
            const SizedBox(height: 8),
            const OnboardingProgressIndicator(
              currentStep: 3,
              totalSteps: 7,
            ),
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(24),
                child: Form(
                  key: _formKey,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        "What are your fixed monthly expenses?",
                        style: TextStyle(
                          fontFamily: AppTypography.fontHeading,
                          fontWeight: FontWeight.w700,
                          fontSize: 22,
                          color: AppColors.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Text(
                        "Select your regular bills and enter the amounts. This helps create an accurate budget.",
                        style: TextStyle(
                          fontFamily: AppTypography.fontBody,
                          color: Colors.grey.shade700,
                          fontSize: 14,
                        ),
                      ),
                      if (selectedCount > 0) ...[
                        const SizedBox(height: 12),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                          decoration: BoxDecoration(
                            color: AppColors.textPrimary.withOpacity(0.1),
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: Text(
                            '$selectedCount expense${selectedCount == 1 ? '' : 's'} selected',
                            style: const TextStyle(
                              fontFamily: AppTypography.fontBody,
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
                              color: AppColors.textPrimary,
                            ),
                          ),
                        ),
                      ],
                      const SizedBox(height: 20),
                      // Expense cards
                      ...expenses.map((expense) => Padding(
                            padding: const EdgeInsets.only(bottom: 12),
                            child: _buildExpenseCard(expense),
                          )),
                      const SizedBox(height: 24),
                      // Buttons
                      SizedBox(
                        width: double.infinity,
                        child: ElevatedButton(
                          style: ElevatedButton.styleFrom(
                            backgroundColor: AppColors.textPrimary,
                            foregroundColor: Colors.white,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(18),
                            ),
                            padding: const EdgeInsets.symmetric(vertical: 16),
                            textStyle: const TextStyle(
                              fontFamily: AppTypography.fontHeading,
                              fontWeight: FontWeight.w600,
                              fontSize: 16,
                            ),
                          ),
                          onPressed: _submitExpenses,
                          child: const Text("Continue"),
                        ),
                      ),
                      const SizedBox(height: 12),
                      SizedBox(
                        width: double.infinity,
                        child: TextButton(
                          onPressed: () async {
                            // Skip expenses - set empty list
                            OnboardingState.instance.expenses = [];
                            await OnboardingState.instance.save();
                            Navigator.pushNamed(context, '/onboarding_goal');
                          },
                          child: const Text(
                            "Skip for now",
                            style: TextStyle(
                              fontFamily: AppTypography.fontHeading,
                              color: Colors.grey,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

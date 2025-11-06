import 'package:flutter/material.dart';
import '../services/onboarding_state.dart';
import '../widgets/onboarding_progress_indicator.dart';

class FixedExpense {
  String category;
  String amount;

  FixedExpense({this.category = '', this.amount = ''});
}

class OnboardingExpensesScreen extends StatefulWidget {
  const OnboardingExpensesScreen({super.key});

  @override
  State<OnboardingExpensesScreen> createState() => _OnboardingExpensesScreenState();
}

class _OnboardingExpensesScreenState extends State<OnboardingExpensesScreen> {
  final List<FixedExpense> expenses = [FixedExpense()];
  final _formKey = GlobalKey<FormState>();

  void _addExpense() {
    setState(() {
      expenses.add(FixedExpense());
    });
  }

  void _submitExpenses() async {
    if (_formKey.currentState?.validate() ?? false) {
      final apiExpenses = expenses
          .where((e) => e.category.isNotEmpty && double.tryParse(e.amount) != null && double.parse(e.amount) > 0)
          .map((e) => {"category": e.category, "amount": double.parse(e.amount)})
          .toList();

      // Preserve expenses for the final onboarding request
      OnboardingState.instance.expenses = apiExpenses;

      Navigator.pushNamed(context, '/onboarding_goal');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      body: SafeArea(
        child: Column(
          children: [
            const SizedBox(height: 8),
            const OnboardingProgressIndicator(
              currentStep: 3,
              totalSteps: 7,
            ),
            Expanded(
              child: Center(
                child: Card(
            elevation: 3,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(28),
            ),
            color: Colors.white,
            margin: const EdgeInsets.symmetric(horizontal: 24, vertical: 60),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 28),
              child: Form(
                key: _formKey,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text(
                      "What are your fixed monthly expenses?",
                      style: TextStyle(
                        fontFamily: 'Sora',
                        fontWeight: FontWeight.w700,
                        fontSize: 22,
                        color: Color(0xFF193C57),
                      ),
                    ),
                    const SizedBox(height: 16),
                    const Text(
                      "Add your regular bills (rent, subscriptions, loans, etc.). No discipline — no freedom. Track everything honestly.",
                      style: TextStyle(
                        fontFamily: 'Manrope',
                        color: Colors.black54,
                        fontSize: 13,
                      ),
                    ),
                    const SizedBox(height: 20),
                    ...expenses.asMap().entries.map(
                      (entry) {
                        int idx = entry.key;
                        FixedExpense exp = entry.value;
                        return Padding(
                          padding: const EdgeInsets.only(bottom: 12),
                          child: Row(
                            children: [
                              Expanded(
                                flex: 5,
                                child: TextFormField(
                                  initialValue: exp.category,
                                  decoration: InputDecoration(
                                    labelText: "Category",
                                    border: OutlineInputBorder(
                                      borderRadius: BorderRadius.circular(14),
                                    ),
                                  ),
                                  onChanged: (val) => exp.category = val,
                                  validator: (val) {
                                    if (val == null || val.trim().isEmpty) {
                                      return "Required";
                                    }
                                    return null;
                                  },
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                flex: 3,
                                child: TextFormField(
                                  initialValue: exp.amount,
                                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                                  decoration: InputDecoration(
                                    labelText: "\$",
                                    border: OutlineInputBorder(
                                      borderRadius: BorderRadius.circular(14),
                                    ),
                                  ),
                                  onChanged: (val) => exp.amount = val,
                                  validator: (val) {
                                    if (val == null || val.trim().isEmpty) {
                                      return "Required";
                                    }
                                    final n = double.tryParse(val);
                                    if (n == null || n <= 0) {
                                      return "Enter a positive number";
                                    }
                                    return null;
                                  },
                                ),
                              ),
                              if (idx > 0)
                                IconButton(
                                  icon: const Icon(Icons.close, color: Colors.red),
                                  onPressed: () {
                                    setState(() {
                                      expenses.removeAt(idx);
                                    });
                                  },
                                )
                            ],
                          ),
                        );
                      },
                    ),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: TextButton.icon(
                        onPressed: _addExpense,
                        icon: const Icon(Icons.add),
                        label: const Text("Add More"),
                        style: TextButton.styleFrom(
                          foregroundColor: const Color(0xFF193C57),
                          textStyle: const TextStyle(fontFamily: 'Sora'),
                        ),
                      ),
                    ),
                    const SizedBox(height: 22),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFFFFD25F),
                          foregroundColor: const Color(0xFF193C57),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(18),
                          ),
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          textStyle: const TextStyle(
                            fontFamily: 'Sora',
                            fontWeight: FontWeight.w600,
                            fontSize: 18,
                          ),
                        ),
                        onPressed: _submitExpenses,
                        child: const Text("Continue"),
                      ),
                    ),
                  ],
                ),
              ),
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

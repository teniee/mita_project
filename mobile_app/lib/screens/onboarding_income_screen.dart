import 'package:flutter/material.dart';
import '../services/onboarding_state.dart';

class OnboardingIncomeScreen extends StatefulWidget {
  const OnboardingIncomeScreen({Key? key}) : super(key: key);

  @override
  State<OnboardingIncomeScreen> createState() => _OnboardingIncomeScreenState();
}

class _OnboardingIncomeScreenState extends State<OnboardingIncomeScreen> {
  final _formKey = GlobalKey<FormState>();
  final _incomeController = TextEditingController();

  void _submitIncome() async {
    if (_formKey.currentState?.validate() ?? false) {
      double income = double.parse(_incomeController.text.replaceAll(',', ''));

      // Store income until all onboarding data is collected
      OnboardingState.instance.income = income;

      Navigator.pushNamed(context, '/onboarding_expenses');
    }
  }

  @override
  void dispose() {
    _incomeController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      body: SafeArea(
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
                    Text(
                      "What’s your average monthly income?",
                      style: const TextStyle(
                        fontFamily: 'Sora',
                        fontWeight: FontWeight.w700,
                        fontSize: 24,
                        color: Color(0xFF193C57),
                      ),
                    ),
                    const SizedBox(height: 18),
                    Text(
                      "If you want to be rich, start acting like one. No sugar-coating here.",
                      style: const TextStyle(
                        fontFamily: 'Manrope',
                        color: Colors.black54,
                        fontSize: 14,
                      ),
                    ),
                    const SizedBox(height: 30),
                    TextFormField(
                      controller: _incomeController,
                      keyboardType: TextInputType.numberWithOptions(decimal: true),
                      decoration: InputDecoration(
                        labelText: "Monthly Income (\$)",
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                        prefixIcon: const Icon(Icons.attach_money),
                      ),
                      validator: (value) {
                        if (value == null || value.isEmpty) {
                          return "Please enter your income.";
                        }
                        final income = double.tryParse(value.replaceAll(',', ''));
                        if (income == null || income <= 0) {
                          return "Enter a positive amount.";
                        }
                        return null;
                      },
                    ),
                    const SizedBox(height: 36),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFFFFD25F),
                          foregroundColor: const Color(0xFF193C57),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(18),
                          ),
                          padding: const EdgeInsets.symmetric(vertical: 18),
                          textStyle: const TextStyle(
                            fontFamily: 'Sora',
                            fontWeight: FontWeight.w600,
                            fontSize: 18,
                          ),
                        ),
                        onPressed: _submitIncome,
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
    );
  }
}

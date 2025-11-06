import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../services/onboarding_state.dart';
import '../widgets/onboarding_progress_indicator.dart';

class OnboardingSpendingFrequencyScreen extends StatefulWidget {
  const OnboardingSpendingFrequencyScreen({super.key});

  @override
  State<OnboardingSpendingFrequencyScreen> createState() => _OnboardingSpendingFrequencyScreenState();
}

class _OnboardingSpendingFrequencyScreenState extends State<OnboardingSpendingFrequencyScreen> {
  final _formKey = GlobalKey<FormState>();

  // Controllers for each frequency input
  final _diningOutController = TextEditingController();
  final _entertainmentController = TextEditingController();
  final _clothingController = TextEditingController();
  final _travelController = TextEditingController();
  final _coffeeController = TextEditingController();
  final _transportController = TextEditingController();

  @override
  void initState() {
    super.initState();
    // Set default values
    _diningOutController.text = '8';
    _entertainmentController.text = '4';
    _clothingController.text = '2';
    _travelController.text = '2';
    _coffeeController.text = '5';
    _transportController.text = '20';
  }

  @override
  void dispose() {
    _diningOutController.dispose();
    _entertainmentController.dispose();
    _clothingController.dispose();
    _travelController.dispose();
    _coffeeController.dispose();
    _transportController.dispose();
    super.dispose();
  }

  void _submitFrequencies() {
    if (_formKey.currentState?.validate() ?? false) {
      // Save real user input to onboarding state
      OnboardingState.instance.spendingFrequencies = {
        'dining_out_per_month': int.parse(_diningOutController.text),
        'entertainment_per_month': int.parse(_entertainmentController.text),
        'clothing_per_month': int.parse(_clothingController.text),
        'travel_per_year': int.parse(_travelController.text),
        'coffee_per_week': int.parse(_coffeeController.text),
        'transport_per_month': int.parse(_transportController.text),
      };

      Navigator.pushNamed(context, '/onboarding_habits');
    }
  }

  Widget _buildFrequencyInput({
    required String label,
    required String unit,
    required TextEditingController controller,
    required IconData icon,
  }) {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFFFD25F).withOpacity(0.3),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: const Color(0xFF193C57), size: 24),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: const TextStyle(
                      fontFamily: 'Manrope',
                      fontWeight: FontWeight.w600,
                      fontSize: 16,
                      color: Color(0xFF193C57),
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    unit,
                    style: const TextStyle(
                      fontFamily: 'Manrope',
                      fontSize: 12,
                      color: Colors.black54,
                    ),
                  ),
                ],
              ),
            ),
            SizedBox(
              width: 80,
              child: TextFormField(
                controller: controller,
                keyboardType: TextInputType.number,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontFamily: 'Sora',
                  fontWeight: FontWeight.w600,
                  fontSize: 20,
                  color: Color(0xFF193C57),
                ),
                decoration: InputDecoration(
                  filled: true,
                  fillColor: const Color(0xFFFFF9F0),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide.none,
                  ),
                  contentPadding: const EdgeInsets.symmetric(vertical: 12),
                ),
                validator: (value) {
                  if (value == null || value.isEmpty) {
                    return 'Required';
                  }
                  final num = int.tryParse(value);
                  if (num == null || num < 0) {
                    return 'Invalid';
                  }
                  return null;
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      appBar: AppBar(
        backgroundColor: const Color(0xFFFFF9F0),
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Color(0xFF193C57)),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 8),
                const OnboardingProgressIndicator(
                  currentStep: 5,
                  totalSteps: 7,
                ),
                const SizedBox(height: 24),
                const Text(
                  'How often do you spend on these?',
                  style: TextStyle(
                    fontFamily: 'Sora',
                    fontWeight: FontWeight.w700,
                    fontSize: 22,
                    color: Color(0xFF193C57),
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  'This helps us create a personalized budget just for you. Be honest!',
                  style: TextStyle(
                    fontFamily: 'Manrope',
                    fontSize: 14,
                    color: Colors.black54,
                  ),
                ),
                const SizedBox(height: 24),
                Expanded(
                  child: ListView(
                    children: [
                      _buildFrequencyInput(
                        label: 'Dining Out & Takeout',
                        unit: 'times per month',
                        controller: _diningOutController,
                        icon: Icons.restaurant,
                      ),
                      const SizedBox(height: 12),
                      _buildFrequencyInput(
                        label: 'Coffee & Drinks',
                        unit: 'times per week',
                        controller: _coffeeController,
                        icon: Icons.coffee,
                      ),
                      const SizedBox(height: 12),
                      _buildFrequencyInput(
                        label: 'Entertainment',
                        unit: 'times per month',
                        controller: _entertainmentController,
                        icon: Icons.movie,
                      ),
                      const SizedBox(height: 12),
                      _buildFrequencyInput(
                        label: 'Shopping & Clothing',
                        unit: 'times per month',
                        controller: _clothingController,
                        icon: Icons.shopping_bag,
                      ),
                      const SizedBox(height: 12),
                      _buildFrequencyInput(
                        label: 'Transportation',
                        unit: 'times per month',
                        controller: _transportController,
                        icon: Icons.directions_car,
                      ),
                      const SizedBox(height: 12),
                      _buildFrequencyInput(
                        label: 'Travel & Vacations',
                        unit: 'times per year',
                        controller: _travelController,
                        icon: Icons.flight,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: _submitFrequencies,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF193C57),
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(18),
                      ),
                      textStyle: const TextStyle(
                        fontFamily: 'Sora',
                        fontWeight: FontWeight.w600,
                        fontSize: 16,
                      ),
                    ),
                    child: const Text("Continue"),
                  ),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: TextButton(
                    onPressed: () {
                      // Skip spending frequencies - will use defaults
                      OnboardingState.instance.spendingFrequencies = null;
                      Navigator.pushNamed(context, '/onboarding_habits');
                    },
                    child: const Text(
                      "Skip for now",
                      style: TextStyle(fontFamily: 'Sora', color: Colors.grey),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

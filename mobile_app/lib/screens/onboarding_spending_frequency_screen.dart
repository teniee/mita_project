import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../services/onboarding_state.dart';
import '../providers/user_provider.dart';
import '../widgets/onboarding_progress_indicator.dart';

class OnboardingSpendingFrequencyScreen extends StatefulWidget {
  const OnboardingSpendingFrequencyScreen({super.key});

  @override
  State<OnboardingSpendingFrequencyScreen> createState() => _OnboardingSpendingFrequencyScreenState();
}

class _OnboardingSpendingFrequencyScreenState extends State<OnboardingSpendingFrequencyScreen> {
  // Simplified to 3 categories with sliders (1-5 scale)
  double _lifestyleFrequency = 3.0; // Dining, coffee, entertainment
  double _shoppingFrequency = 3.0; // Clothing, online shopping
  double _travelFrequency = 2.0; // Travel, vacations

  final Map<int, String> _frequencyLabels = {
    1: 'Rarely',
    2: 'Occasionally',
    3: 'Regularly',
    4: 'Frequently',
    5: 'Very Often',
  };

  Future<void> _submitFrequencies() async {
    // Convert simplified categories back to detailed format for backend
    final frequencies = {
      // Lifestyle (dining, coffee, entertainment)
      'dining_out_per_month': (_lifestyleFrequency * 3).round(), // 3-15 times/month
      'coffee_per_week': (_lifestyleFrequency * 1.5).round(), // 1.5-7.5 times/week
      'entertainment_per_month': (_lifestyleFrequency * 2).round(), // 2-10 times/month

      // Shopping (clothing, online)
      'clothing_per_month': (_shoppingFrequency).round(), // 1-5 times/month
      'transport_per_month': (_shoppingFrequency * 4).round(), // 4-20 times/month

      // Travel
      'travel_per_year': (_travelFrequency).round(), // 1-5 times/year
    };

    OnboardingState.instance.spendingFrequencies = frequencies;
    await OnboardingState.instance.save();

    if (!mounted) return;
    Navigator.pushNamed(context, '/onboarding_habits');
  }

  Widget _buildFrequencySlider({
    required String title,
    required String subtitle,
    required IconData icon,
    required double value,
    required ValueChanged<double> onChanged,
    required Color accentColor,
  }) {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
      ),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: accentColor.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(icon, color: accentColor, size: 28),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: const TextStyle(
                          fontFamily: AppTypography.fontHeading,
                          fontWeight: FontWeight.w700,
                          fontSize: 18,
                          color: AppColors.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        subtitle,
                        style: TextStyle(
                          fontFamily: AppTypography.fontBody,
                          fontSize: 13,
                          color: Colors.grey.shade600,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            // Frequency label
            Center(
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                decoration: BoxDecoration(
                  color: accentColor.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  _frequencyLabels[value.round()] ?? 'Regularly',
                  style: TextStyle(
                    fontFamily: AppTypography.fontHeading,
                    fontWeight: FontWeight.w600,
                    fontSize: 16,
                    color: accentColor,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 12),
            // Slider
            SliderTheme(
              data: SliderTheme.of(context).copyWith(
                activeTrackColor: accentColor,
                inactiveTrackColor: accentColor.withOpacity(0.3),
                thumbColor: accentColor,
                overlayColor: accentColor.withOpacity(0.2),
                trackHeight: 6,
              ),
              child: Slider(
                value: value,
                min: 1,
                max: 5,
                divisions: 4,
                onChanged: onChanged,
              ),
            ),
            // Scale labels
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Rarely',
                    style: TextStyle(
                      fontFamily: AppTypography.fontBody,
                      fontSize: 11,
                      color: Colors.grey.shade600,
                    ),
                  ),
                  Text(
                    'Very Often',
                    style: TextStyle(
                      fontFamily: AppTypography.fontBody,
                      fontSize: 11,
                      color: Colors.grey.shade600,
                    ),
                  ),
                ],
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
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24),
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
                  fontFamily: AppTypography.fontHeading,
                  fontWeight: FontWeight.w700,
                  fontSize: 22,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Move the sliders to match your spending habits. This helps create a personalized budget.',
                style: TextStyle(
                  fontFamily: AppTypography.fontBody,
                  fontSize: 14,
                  color: Colors.grey.shade700,
                ),
              ),
              const SizedBox(height: 24),

              // Lifestyle spending
              _buildFrequencySlider(
                title: 'Lifestyle',
                subtitle: 'Dining out, coffee, entertainment',
                icon: Icons.restaurant_menu,
                value: _lifestyleFrequency,
                onChanged: (value) => setState(() => _lifestyleFrequency = value),
                accentColor: AppColors.danger,
              ),
              const SizedBox(height: 16),

              // Shopping
              _buildFrequencySlider(
                title: 'Shopping',
                subtitle: 'Clothing, online shopping, personal items',
                icon: Icons.shopping_bag,
                value: _shoppingFrequency,
                onChanged: (value) => setState(() => _shoppingFrequency = value),
                accentColor: AppColors.chart7,
              ),
              const SizedBox(height: 16),

              // Travel
              _buildFrequencySlider(
                title: 'Travel',
                subtitle: 'Vacations, trips, weekend getaways',
                icon: Icons.flight_takeoff,
                value: _travelFrequency,
                onChanged: (value) => setState(() => _travelFrequency = value),
                accentColor: AppColors.secondary,
              ),
              const SizedBox(height: 32),

              // Continue button
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _submitFrequencies,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.textPrimary,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(18),
                    ),
                    textStyle: const TextStyle(
                      fontFamily: AppTypography.fontHeading,
                      fontWeight: FontWeight.w600,
                      fontSize: 16,
                    ),
                  ),
                  child: const Text("Continue"),
                ),
              ),
              const SizedBox(height: 12),

              // Skip button
              SizedBox(
                width: double.infinity,
                child: TextButton(
                  onPressed: () async {
                    // Skip spending frequencies - will use defaults
                    OnboardingState.instance.spendingFrequencies = null;
                    await OnboardingState.instance.save();
                    if (!mounted) return;
                    Navigator.pushNamed(context, '/onboarding_habits');
                  },
                  child: const Text(
                    "Skip for now",
                    style: TextStyle(fontFamily: AppTypography.fontHeading, color: Colors.grey),
                  ),
                ),
              ),
              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }
}

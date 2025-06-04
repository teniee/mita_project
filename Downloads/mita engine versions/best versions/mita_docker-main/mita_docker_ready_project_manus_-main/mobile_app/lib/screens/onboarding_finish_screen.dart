
import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../services/onboarding_state.dart';

class OnboardingFinishScreen extends StatefulWidget {
  const OnboardingFinishScreen({Key? key}) : super(key: key);

  @override
  State<OnboardingFinishScreen> createState() => _OnboardingFinishScreenState();
}

class _OnboardingFinishScreenState extends State<OnboardingFinishScreen> {
  final ApiService _api = ApiService();
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _submitOnboardingData();
  }

  Future<void> _submitOnboardingData() async {
    try {
      // Gather answers from the temporary onboarding state
      final state = OnboardingState.instance;
      final onboardingData = {
        "region": state.region,
        "income": state.income,
        "expenses": state.expenses,
        "goals": state.goals,
        "habits": state.habits,
        "motivation": state.motivation,
        if (state.habitsComment != null && state.habitsComment!.isNotEmpty)
          "habits_comment": state.habitsComment,
      };

      await _api.submitOnboarding(onboardingData);

      if (!mounted) return;
      setState(() {
        _loading = false;
      });

      Navigator.pushReplacementNamed(context, '/main');
    } catch (e) {
      setState(() {
        _loading = false;
        _error = "Ошибка при отправке данных: \$e";
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      body: Center(
        child: _loading
            ? const CircularProgressIndicator()
            : _error != null
                ? Padding(
                    padding: const EdgeInsets.all(24),
                    child: Text(
                      _error!,
                      style: const TextStyle(
                        color: Colors.red,
                        fontFamily: 'Manrope',
                        fontSize: 16,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  )
                : const Text(
                    'Добро пожаловать в MITA!',
                    style: TextStyle(
                      fontFamily: 'Sora',
                      fontWeight: FontWeight.bold,
                      fontSize: 24,
                      color: Color(0xFF193C57),
                    ),
                  ),
      ),
    );
  }
}

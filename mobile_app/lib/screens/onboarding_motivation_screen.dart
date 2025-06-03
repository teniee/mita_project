
import 'package:flutter/material.dart';
import '../services/onboarding_state.dart';

class OnboardingMotivationScreen extends StatefulWidget {
  const OnboardingMotivationScreen({Key? key}) : super(key: key);

  @override
  State<OnboardingMotivationScreen> createState() => _OnboardingMotivationScreenState();
}

class _OnboardingMotivationScreenState extends State<OnboardingMotivationScreen> {
  final TextEditingController _controller = TextEditingController();

  void _submitMotivation() {
    final text = _controller.text.trim();
    if (text.isEmpty) return;
    // Persist motivation text
    OnboardingState.instance.motivation = text;
    Navigator.pushNamed(context, '/onboarding_finish');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Что вас мотивирует изменить ваши финансы?',
                style: TextStyle(
                  fontFamily: 'Sora',
                  fontWeight: FontWeight.w700,
                  fontSize: 22,
                  color: Color(0xFF193C57),
                ),
              ),
              const SizedBox(height: 24),
              TextFormField(
                controller: _controller,
                decoration: InputDecoration(
                  hintText: 'Например: Хочу научиться контролировать расходы...',
                  filled: true,
                  fillColor: Colors.white,
                  contentPadding: const EdgeInsets.symmetric(vertical: 16, horizontal: 16),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(20),
                    borderSide: BorderSide.none,
                  ),
                ),
                maxLines: 6,
              ),
              const Spacer(),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _controller.text.trim().isNotEmpty ? _submitMotivation : null,
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
                  child: const Text("Завершить онбординг"),
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

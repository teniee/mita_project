import 'package:flutter/material.dart';

class OnboardingRegionScreen extends StatefulWidget {
  const OnboardingRegionScreen({Key? key}) : super(key: key);

  @override
  State<OnboardingRegionScreen> createState() => _OnboardingRegionScreenState();
}

class _OnboardingRegionScreenState extends State<OnboardingRegionScreen> {
  final List<String> regions = [
    'United States',
    'Canada',
    'Europe',
    'Other',
  ];
  String? selectedRegion;

  void _submitRegion() async {
    if (selectedRegion == null) return;

    // TODO: Подключи к своему API, если нужно сохранить регион сразу:
    // await ApiService.submitRegion(selectedRegion);

    Navigator.pushNamed(context, '/onboarding_income');
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
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    "Where do you live?",
                    style: const TextStyle(
                      fontFamily: 'Sora',
                      fontWeight: FontWeight.w700,
                      fontSize: 24,
                      color: Color(0xFF193C57),
                    ),
                  ),
                  const SizedBox(height: 24),
                  DropdownButtonFormField<String>(
                    decoration: InputDecoration(
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(16),
                      ),
                      labelText: "Region",
                    ),
                    value: selectedRegion,
                    items: regions
                        .map((region) => DropdownMenuItem(
                              value: region,
                              child: Text(
                                region,
                                style: const TextStyle(fontFamily: 'Manrope'),
                              ),
                            ))
                        .toList(),
                    onChanged: (value) {
                      setState(() {
                        selectedRegion = value;
                      });
                    },
                  ),
                  const SizedBox(height: 32),
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
                      onPressed: selectedRegion != null ? _submitRegion : null,
                      child: const Text("Continue"),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

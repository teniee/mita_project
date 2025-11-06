import 'package:flutter/material.dart';
import '../services/onboarding_state.dart';
import '../services/income_service.dart';
import '../widgets/income_tier_widgets.dart';
import '../widgets/onboarding_progress_indicator.dart';

class OnboardingIncomeScreen extends StatefulWidget {
  const OnboardingIncomeScreen({super.key});

  @override
  State<OnboardingIncomeScreen> createState() => _OnboardingIncomeScreenState();
}

class _OnboardingIncomeScreenState extends State<OnboardingIncomeScreen> with TickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final _incomeController = TextEditingController();
  final _incomeService = IncomeService();
  
  IncomeTier? _currentTier;
  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;
  late Animation<Offset> _slideAnimation;
  bool _showTierInfo = false;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );
    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeInOut),
    );
    _slideAnimation = Tween<Offset>(
      begin: const Offset(0, 0.3),
      end: Offset.zero,
    ).animate(CurvedAnimation(parent: _animationController, curve: Curves.easeOutCubic));
  }

  void _onIncomeChanged(String value) async {
    if (value.isNotEmpty) {
      final income = double.tryParse(value.replaceAll(',', ''));
      if (income != null && income > 0) {
        // Use location-aware classification if location is available
        IncomeTier newTier;
        if (OnboardingState.instance.countryCode != null) {
          newTier = _incomeService.classifyIncomeForLocation(
            income, 
            OnboardingState.instance.countryCode!, 
            stateCode: OnboardingState.instance.stateCode
          );
        } else {
          newTier = await _incomeService.classifyIncomeByLocation(income);
        }
        
        if (newTier != _currentTier) {
          setState(() {
            _currentTier = newTier;
            _showTierInfo = true;
          });
          _animationController.forward();
        }
      } else {
        setState(() {
          _currentTier = null;
          _showTierInfo = false;
        });
        _animationController.reverse();
      }
    }
  }

  void _submitIncome() async {
    if (_formKey.currentState?.validate() ?? false) {
      double income = double.parse(_incomeController.text.replaceAll(',', ''));
      
      // Use location-aware classification
      IncomeTier tier;
      if (OnboardingState.instance.countryCode != null) {
        tier = _incomeService.classifyIncomeForLocation(
          income, 
          OnboardingState.instance.countryCode!, 
          stateCode: OnboardingState.instance.stateCode
        );
      } else {
        tier = await _incomeService.classifyIncomeByLocation(income);
      }

      // Store income and tier information
      OnboardingState.instance.income = income;
      OnboardingState.instance.incomeTier = tier;

      // Show personalized message before continuing
      await _showIncomeConfirmationDialog(income, tier);
    }
  }

  Future<void> _showIncomeConfirmationDialog(double income, IncomeTier tier) async {
    final tierName = _incomeService.getIncomeTierName(tier);
    final message = _incomeService.getOnboardingMessage(tier);
    final primaryColor = _incomeService.getIncomeTierPrimaryColor(tier);
    
    await showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Row(
          children: [
            Icon(
              _incomeService.getIncomeTierIcon(tier),
              color: primaryColor,
              size: 28,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                'Welcome, $tierName!',
                style: TextStyle(
                  fontFamily: 'Sora',
                  fontWeight: FontWeight.bold,
                  color: primaryColor,
                ),
              ),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              message,
              style: const TextStyle(
                fontFamily: 'Manrope',
                fontSize: 16,
              ),
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
                      'We\'ll customize your budget and recommendations based on your income level.',
                      style: TextStyle(
                        fontFamily: 'Manrope',
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
        actions: [
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              Navigator.pushNamed(context, '/onboarding_expenses');
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: primaryColor,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
            child: const Text(
              'Continue Setup',
              style: TextStyle(
                fontFamily: 'Sora',
                fontWeight: FontWeight.w600,
                color: Colors.white,
              ),
            ),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _animationController.dispose();
    _incomeController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final primaryColor = _currentTier != null 
        ? _incomeService.getIncomeTierPrimaryColor(_currentTier!)
        : const Color(0xFF193C57);
    
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
        child: SingleChildScrollView(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Column(
              children: [
                const SizedBox(height: 8),
                OnboardingProgressIndicator(
                  currentStep: 2,
                  totalSteps: 7,
                  activeColor: primaryColor,
                ),
                const SizedBox(height: 24),

                // Main income input card
                Card(
                  elevation: 3,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(28),
                  ),
                  color: Colors.white,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 28),
                    child: Form(
                      key: _formKey,
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            "What's your average monthly income?",
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              fontFamily: 'Sora',
                              fontWeight: FontWeight.w700,
                              fontSize: 24,
                              color: primaryColor,
                            ),
                          ),
                          const SizedBox(height: 18),
                          const Text(
                            "We'll create a personalized budget plan based on your income level.",
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              fontFamily: 'Manrope',
                              color: Colors.black54,
                              fontSize: 14,
                            ),
                          ),
                          const SizedBox(height: 30),
                          TextFormField(
                            controller: _incomeController,
                            keyboardType: const TextInputType.numberWithOptions(decimal: true),
                            onChanged: _onIncomeChanged,
                            decoration: InputDecoration(
                              labelText: "Monthly Income (\$)",
                              border: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(16),
                              ),
                              focusedBorder: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(16),
                                borderSide: BorderSide(color: primaryColor, width: 2),
                              ),
                              prefixIcon: Icon(
                                Icons.attach_money,
                                color: primaryColor,
                              ),
                            ),
                            validator: (value) {
                              if (value == null || value.isEmpty) {
                                return "Please enter your income.";
                              }
                              final income = double.tryParse(value.replaceAll(',', ''));
                              if (income == null || income <= 0) {
                                return "Enter a positive amount.";
                              }

                              // Minimum income check
                              if (income < 100) {
                                return "Monthly income seems too low. Please verify.";
                              }

                              // Maximum income check
                              if (income > 1000000) {
                                return "Please verify this amount. It seems unusually high.";
                              }

                              // Check if user might have entered yearly income
                              if (income > 100000 && income < 1000000) {
                                // Might be yearly income (e.g., $120,000/year entered instead of $10,000/month)
                                // Show warning but allow it (user confirmation in dialog)
                                return "Are you sure? This is monthly income (not yearly).";
                              }

                              return null;
                            },
                          ),
                          const SizedBox(height: 36),
                          SizedBox(
                            width: double.infinity,
                            child: ElevatedButton(
                              style: ElevatedButton.styleFrom(
                                backgroundColor: primaryColor,
                                foregroundColor: Colors.white,
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
                
                // Income tier information card (animated)
                if (_showTierInfo && _currentTier != null)
                  AnimatedBuilder(
                    animation: _animationController,
                    builder: (context, child) {
                      return FadeTransition(
                        opacity: _fadeAnimation,
                        child: SlideTransition(
                          position: _slideAnimation,
                          child: Padding(
                            padding: const EdgeInsets.only(top: 20),
                            child: Column(
                              children: [
                                // Income tier display
                                IncomeTierCard(
                                  monthlyIncome: double.tryParse(_incomeController.text.replaceAll(',', '')) ?? 0.0,
                                  showDetails: true,
                                ),
                                
                                const SizedBox(height: 16),
                                
                                // Quick preview of benefits
                                Card(
                                  elevation: 2,
                                  margin: const EdgeInsets.symmetric(horizontal: 16),
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
                                              Icons.auto_awesome_rounded,
                                              color: primaryColor,
                                              size: 24,
                                            ),
                                            const SizedBox(width: 12),
                                            Text(
                                              'What You\'ll Get',
                                              style: TextStyle(
                                                fontFamily: 'Sora',
                                                fontWeight: FontWeight.bold,
                                                fontSize: 18,
                                                color: primaryColor,
                                              ),
                                            ),
                                          ],
                                        ),
                                        const SizedBox(height: 16),
                                        ..._getIncomeBasedBenefits(_currentTier!).map((benefit) => 
                                          Padding(
                                            padding: const EdgeInsets.only(bottom: 8),
                                            child: Row(
                                              children: [
                                                Icon(
                                                  Icons.check_circle_rounded,
                                                  color: primaryColor,
                                                  size: 16,
                                                ),
                                                const SizedBox(width: 12),
                                                Expanded(
                                                  child: Text(
                                                    benefit,
                                                    style: const TextStyle(
                                                      fontFamily: 'Manrope',
                                                      fontSize: 14,
                                                    ),
                                                  ),
                                                ),
                                              ],
                                            ),
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      );
                    },
                  ),
                
                const SizedBox(height: 40),
              ],
            ),
          ),
        ),
      ),
    );
  }
  
  List<String> _getIncomeBasedBenefits(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low:
        return [
          'Budget templates focused on essential spending',
          'Tips for maximizing every dollar',
          'Affordable goal suggestions',
          'Community resources and discounts',
        ];
      case IncomeTier.lowerMiddle:
        return [
          'Emergency fund building strategies',
          'Income growth planning tools',
          'Debt elimination frameworks',
          'Skills development budget allocation',
        ];
      case IncomeTier.middle:
        return [
          'Balanced budget with growth opportunities',
          'Investment and savings strategies',
          'Career advancement financial planning',
          'Medium-term goal recommendations',
        ];
      case IncomeTier.upperMiddle:
        return [
          'Advanced investment portfolio building',
          'Tax optimization strategies',
          'Property investment planning',
          'Retirement acceleration techniques',
        ];
      case IncomeTier.high:
        return [
          'Advanced wealth-building strategies',
          'Tax optimization recommendations',  
          'Premium investment opportunities',
          'High-value goal planning',
        ];
    }
  }
}

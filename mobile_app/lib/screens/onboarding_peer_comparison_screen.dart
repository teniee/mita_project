import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../services/onboarding_state.dart';
import '../services/income_service.dart';
import '../services/api_service.dart';
import '../widgets/income_tier_widgets.dart';
import '../theme/income_theme.dart';

class OnboardingPeerComparisonScreen extends StatefulWidget {
  const OnboardingPeerComparisonScreen({super.key});

  @override
  State<OnboardingPeerComparisonScreen> createState() => _OnboardingPeerComparisonScreenState();
}

class _OnboardingPeerComparisonScreenState extends State<OnboardingPeerComparisonScreen> 
    with TickerProviderStateMixin {
  final _incomeService = IncomeService();
  final _apiService = ApiService();
  
  late IncomeTier _incomeTier;
  late double _monthlyIncome;
  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;
  late Animation<Offset> _slideAnimation;
  
  Map<String, dynamic>? _peerData;
  Map<String, dynamic>? _cohortInsights;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    
    // Get income data from onboarding state
    if (OnboardingState.instance.income == null || OnboardingState.instance.income! <= 0) {
      throw Exception('Income must be provided before peer comparison. Please go back and complete income entry.');
    }
    _monthlyIncome = OnboardingState.instance.income!;
    _incomeTier = OnboardingState.instance.incomeTier ?? _incomeService.classifyIncome(_monthlyIncome);
    
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
    
    _loadPeerData();
  }

  Future<void> _loadPeerData() async {
    try {
      // Load peer comparison data and cohort insights
      final results = await Future.wait([
        _apiService.getPeerComparison(),
        _apiService.getCohortInsights(),
      ]);
      
      setState(() {
        _peerData = results[0];
        _cohortInsights = results[1];
        _isLoading = false;
      });
      
      _animationController.forward();
    } catch (e) {
      // Show empty state when peer comparison service is unavailable
      setState(() {
        _peerData = {
          'error': 'Peer comparison service is currently unavailable',
          'your_spending': null,
          'peer_average': null,
          'peer_median': null,
          'percentile': null,
          'categories': {},
          'insights': [],
        };
        _cohortInsights = {
          'error': 'Cohort insights service is currently unavailable',
          'cohort_size': null,
          'your_rank': null,
          'percentile': null,
          'top_insights': [],
        };
        _isLoading = false;
      });

      _animationController.forward();
    }
  }


  void _continueToFinish() {
    Navigator.pushNamed(context, '/onboarding_finish');
  }

  @override
  Widget build(BuildContext context) {
    final primaryColor = _incomeService.getIncomeTierPrimaryColor(_incomeTier);
    final tierName = _incomeService.getIncomeTierName(_incomeTier);

    if (_isLoading) {
      return Scaffold(
        backgroundColor: const AppColors.background,
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              CircularProgressIndicator(color: primaryColor),
              const SizedBox(height: 16),
              Text(
                'Finding your peer group...',
                style: TextStyle(
                  fontFamily: AppTypography.fontBody,
                  fontSize: 16,
                  color: primaryColor,
                ),
              ),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      backgroundColor: const AppColors.background,
      appBar: IncomeTheme.createTierAppBar(
        tier: _incomeTier,
        title: 'Your Peer Group',
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: FadeTransition(
        opacity: _fadeAnimation,
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: SlideTransition(
            position: _slideAnimation,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Welcome message
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
                              Icons.people_rounded,
                              color: primaryColor,
                              size: 28,
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'Welcome to Your Peer Group!',
                                    style: TextStyle(
                                      fontFamily: AppTypography.fontHeading,
                                      fontWeight: FontWeight.bold,
                                      fontSize: 20,
                                      color: primaryColor,
                                    ),
                                  ),
                                  Text(
                                    'Connect with ${_cohortInsights?['cohort_size'] ?? 0} other $tierName users',
                                    style: const TextStyle(
                                      fontFamily: AppTypography.fontBody,
                                      fontSize: 14,
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
                          child: Text(
                            'You\'re in the ${_cohortInsights?['percentile'] ?? 0}th percentile of your peer group! This means you\'re already doing better than most users with similar income levels.',
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
                ),

                const SizedBox(height: 24),

                // Peer comparison card
                if (_peerData != null)
                  PeerComparisonCard(
                    comparisonData: _peerData!,
                    monthlyIncome: _monthlyIncome,
                  ),

                const SizedBox(height: 24),

                // Cohort insights
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
                              Icons.insights_rounded,
                              color: primaryColor,
                              size: 24,
                            ),
                            const SizedBox(width: 12),
                            Text(
                              'Peer Insights',
                              style: TextStyle(
                                fontFamily: AppTypography.fontHeading,
                                fontWeight: FontWeight.bold,
                                fontSize: 18,
                                color: primaryColor,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        
                        // Top insights
                        ...(_cohortInsights?['top_insights'] as List<String>? ?? []).map((insight) =>
                          Padding(
                            padding: const EdgeInsets.only(bottom: 8),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Container(
                                  margin: const EdgeInsets.only(top: 6),
                                  width: 6,
                                  height: 6,
                                  decoration: BoxDecoration(
                                    color: primaryColor,
                                    shape: BoxShape.circle,
                                  ),
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Text(
                                    insight,
                                    style: const TextStyle(
                                      fontFamily: AppTypography.fontBody,
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

                const SizedBox(height: 24),

                // Recommendations
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
                              Icons.recommend_rounded,
                              color: primaryColor,
                              size: 24,
                            ),
                            const SizedBox(width: 12),
                            Text(
                              'Personalized Recommendations',
                              style: TextStyle(
                                fontFamily: AppTypography.fontHeading,
                                fontWeight: FontWeight.bold,
                                fontSize: 18,
                                color: primaryColor,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        
                        // Recommendations
                        ...(_cohortInsights?['recommendations'] as List<String>? ?? []).map((recommendation) =>
                          Container(
                            margin: const EdgeInsets.only(bottom: 12),
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: Colors.green.shade50,
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: Colors.green.shade200),
                            ),
                            child: Row(
                              children: [
                                Icon(
                                  Icons.check_circle_rounded,
                                  color: Colors.green.shade600,
                                  size: 16,
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Text(
                                    recommendation,
                                    style: TextStyle(
                                      fontFamily: AppTypography.fontBody,
                                      fontSize: 14,
                                      color: Colors.green.shade700,
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

                const SizedBox(height: 32),

                // Continue button
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: _continueToFinish,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: primaryColor,
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16),
                      ),
                      padding: const EdgeInsets.symmetric(vertical: 18),
                    ),
                    child: const Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          'Complete Setup',
                          style: TextStyle(
                            fontFamily: AppTypography.fontHeading,
                            fontWeight: FontWeight.w600,
                            fontSize: 18,
                          ),
                        ),
                        SizedBox(width: 8),
                        Icon(
                          Icons.arrow_forward_rounded,
                          size: 20,
                        ),
                      ],
                    ),
                  ),
                ),

                const SizedBox(height: 40),
              ],
            ),
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
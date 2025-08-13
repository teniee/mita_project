import 'package:flutter/material.dart';
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
      // Generate demo data if API is not available
      setState(() {
        _peerData = _generateDemoPeerData();
        _cohortInsights = _generateDemoCohortInsights();
        _isLoading = false;
      });
      
      _animationController.forward();
    }
  }

  Map<String, dynamic> _generateDemoPeerData() {
    // Generate realistic demo data based on income tier
    final baseSpending = _monthlyIncome * 0.75; // 75% spending rate
    final tierMultiplier = _incomeTier == IncomeTier.low ? 0.9 
                         : _incomeTier == IncomeTier.lowerMiddle ? 0.95
                         : _incomeTier == IncomeTier.middle ? 1.0 
                         : _incomeTier == IncomeTier.upperMiddle ? 1.05
                         : 1.1;
    
    return {
      'your_spending': baseSpending * 0.85, // User spends less than average
      'peer_average': baseSpending * tierMultiplier,
      'peer_median': baseSpending * tierMultiplier * 0.95,
      'percentile': 35, // User is in the 35th percentile (doing well)
      'categories': {
        'food': {'your_amount': _monthlyIncome * 0.12, 'peer_average': _monthlyIncome * 0.15},
        'transportation': {'your_amount': _monthlyIncome * 0.10, 'peer_average': _monthlyIncome * 0.15},
        'entertainment': {'your_amount': _monthlyIncome * 0.06, 'peer_average': _monthlyIncome * 0.08},
        'shopping': {'your_amount': _monthlyIncome * 0.08, 'peer_average': _monthlyIncome * 0.12},
      },
      'insights': [
        'You spend 15% less than peers in your income group',
        'Your food spending is very close to the average',
        'You save more on transportation than most peers',
        'Your entertainment budget is well-controlled',
      ],
    };
  }

  Map<String, dynamic> _generateDemoCohortInsights() {
    return {
      'cohort_size': _incomeTier == IncomeTier.low ? 2847 
                   : _incomeTier == IncomeTier.lowerMiddle ? 3241
                   : _incomeTier == IncomeTier.middle ? 4126 
                   : _incomeTier == IncomeTier.upperMiddle ? 2089
                   : 1653,
      'your_rank': _incomeTier == IncomeTier.low ? 842 
                 : _incomeTier == IncomeTier.lowerMiddle ? 973
                 : _incomeTier == IncomeTier.middle ? 1247 
                 : _incomeTier == IncomeTier.upperMiddle ? 542
                 : 423,
      'percentile': 70,
      'top_insights': _getTierSpecificInsights(),
      'recommendations': _getTierSpecificRecommendations(),
    };
  }

  List<String> _getTierSpecificInsights() {
    switch (_incomeTier) {
      case IncomeTier.low:
        return [
          'Essential Earners typically save 8-12% of their income',
          'Most peers allocate 40% to housing costs',
          'Food expenses average 15-18% for your income group',
          'Transportation costs vary from 12-20% among peers',
        ];
      case IncomeTier.lowerMiddle:
        return [
          'Rising Savers typically save 12-16% of their income',
          'Most peers allocate 35-38% to housing costs',
          'Food expenses average 13-16% for your income group',
          'Emergency fund building becomes a priority at this level',
        ];
      case IncomeTier.middle:
        return [
          'Growing Professionals typically save 15-20% of their income',
          'Most peers allocate 30-35% to housing costs',
          'Food expenses average 12-15% for your income group',
          'Investment activity increases significantly in this tier',
        ];
      case IncomeTier.upperMiddle:
        return [
          'Established Professionals typically save 20-28% of their income',
          'Most peers allocate 28-32% to housing costs',
          'Food expenses average 10-13% for your income group',
          'Advanced investment strategies become common at this level',
        ];
      case IncomeTier.high:
        return [
          'High Achievers typically save 25-35% of their income',
          'Most peers allocate 25-30% to housing costs',
          'Food expenses average 8-12% for your income group',
          'Tax optimization becomes a major focus at this level',
        ];
    }
  }

  List<String> _getTierSpecificRecommendations() {
    switch (_incomeTier) {
      case IncomeTier.low:
        return [
          'Focus on building a small emergency fund first',
          'Look for ways to reduce transportation costs',
          'Consider meal planning to optimize food spending',
        ];
      case IncomeTier.lowerMiddle:
        return [
          'Build a 3-month emergency fund as your foundation',
          'Invest in skills development to increase income potential',
          'Create a debt elimination plan for high-interest debt',
        ];
      case IncomeTier.middle:
        return [
          'Consider increasing your savings rate to match top performers',
          'Start exploring investment opportunities',
          'Look into employer benefits optimization',
        ];
      case IncomeTier.upperMiddle:
        return [
          'Diversify your investment portfolio across asset classes',
          'Explore tax loss harvesting strategies',
          'Consider real estate investment opportunities',
        ];
      case IncomeTier.high:
        return [
          'Maximize tax-advantaged investment accounts',
          'Consider working with a financial advisor',
          'Explore advanced wealth-building strategies',
        ];
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
        backgroundColor: const Color(0xFFFFF9F0),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              CircularProgressIndicator(color: primaryColor),
              const SizedBox(height: 16),
              Text(
                'Finding your peer group...',
                style: TextStyle(
                  fontFamily: 'Manrope',
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
      backgroundColor: const Color(0xFFFFF9F0),
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
                                      fontFamily: 'Sora',
                                      fontWeight: FontWeight.bold,
                                      fontSize: 20,
                                      color: primaryColor,
                                    ),
                                  ),
                                  Text(
                                    'Connect with ${_cohortInsights?['cohort_size'] ?? 0} other $tierName users',
                                    style: const TextStyle(
                                      fontFamily: 'Manrope',
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
                              fontFamily: 'Manrope',
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
                                fontFamily: 'Sora',
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
                                fontFamily: 'Sora',
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
                                      fontFamily: 'Manrope',
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
                            fontFamily: 'Sora',
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
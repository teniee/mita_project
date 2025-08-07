import 'package:flutter/material.dart';
import '../services/advanced_financial_engine.dart';

/// Behavioral Insights Widget
/// 
/// Displays adaptive learning insights, spending pattern recognition,
/// and personalized behavioral recommendations from the Advanced Financial Engine.
class BehavioralInsightsWidget extends StatefulWidget {
  final AdvancedFinancialEngine financialEngine;
  final bool showSpendingPatterns;
  final bool showPersonalityProfile;
  final bool showLearningProgress;

  const BehavioralInsightsWidget({
    super.key,
    required this.financialEngine,
    this.showSpendingPatterns = true,
    this.showPersonalityProfile = true,
    this.showLearningProgress = true,
  });

  @override
  State<BehavioralInsightsWidget> createState() => _BehavioralInsightsWidgetState();
}

class _BehavioralInsightsWidgetState extends State<BehavioralInsightsWidget> 
    with TickerProviderStateMixin {

  late AnimationController _fadeController;
  late AnimationController _slideController;
  late Animation<double> _fadeAnimation;
  late Animation<Offset> _slideAnimation;
  
  Map<String, dynamic>? _behavioralAnalysis;
  Map<String, dynamic>? _userProfile;
  int _selectedTab = 0;

  @override
  void initState() {
    super.initState();
    _initializeAnimations();
    _subscribeToUpdates();
    _loadInitialData();
  }

  void _initializeAnimations() {
    _fadeController = AnimationController(
      duration: const Duration(milliseconds: 600),
      vsync: this,
    );
    
    _slideController = AnimationController(
      duration: const Duration(milliseconds: 500),
      vsync: this,
    );

    _fadeAnimation = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _fadeController,
      curve: Curves.easeInOut,
    ));

    _slideAnimation = Tween<Offset>(
      begin: const Offset(0.0, 0.3),
      end: Offset.zero,
    ).animate(CurvedAnimation(
      parent: _slideController,
      curve: Curves.easeOutBack,
    ));

    _fadeController.forward();
    _slideController.forward();
  }

  void _subscribeToUpdates() {
    widget.financialEngine.addListener(_onDataUpdated);
  }

  void _onDataUpdated() {
    if (mounted) {
      setState(() {
        _behavioralAnalysis = widget.financialEngine.behavioralAnalysis;
        _userProfile = widget.financialEngine.userBehaviorProfile;
      });
    }
  }

  void _loadInitialData() {
    setState(() {
      _behavioralAnalysis = widget.financialEngine.behavioralAnalysis;
      _userProfile = widget.financialEngine.userBehaviorProfile;
    });
  }

  @override
  void dispose() {
    widget.financialEngine.removeListener(_onDataUpdated);
    _fadeController.dispose();
    _slideController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_behavioralAnalysis == null && _userProfile == null) {
      return const SizedBox.shrink();
    }

    return FadeTransition(
      opacity: _fadeAnimation,
      child: SlideTransition(
        position: _slideAnimation,
        child: Card(
          elevation: 3,
          margin: const EdgeInsets.all(16),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          child: Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              gradient: LinearGradient(
                colors: [
                  const Color(0xFF10B981),
                  const Color(0xFF059669).withOpacity(0.9),
                ],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
            ),
            child: Column(
              children: [
                // Header
                Padding(
                  padding: const EdgeInsets.all(20),
                  child: Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: Colors.white.withOpacity(0.2),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: const Icon(
                          Icons.psychology,
                          color: Colors.white,
                          size: 24,
                        ),
                      ),
                      const SizedBox(width: 12),
                      const Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Behavioral Insights',
                              style: TextStyle(
                                fontFamily: 'Sora',
                                fontWeight: FontWeight.bold,
                                fontSize: 18,
                                color: Colors.white,
                              ),
                            ),
                            Text(
                              'AI learning from your patterns',
                              style: TextStyle(
                                fontFamily: 'Manrope',
                                fontSize: 12,
                                color: Colors.white70,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                
                // Tab Navigation
                _buildTabNavigation(),
                
                // Content
                Padding(
                  padding: const EdgeInsets.all(20),
                  child: _buildTabContent(),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildTabNavigation() {
    final tabs = <String>[];
    
    if (widget.showSpendingPatterns) tabs.add('Patterns');
    if (widget.showPersonalityProfile) tabs.add('Profile');
    if (widget.showLearningProgress) tabs.add('Learning');
    
    if (tabs.isEmpty) return const SizedBox.shrink();

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20),
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.2),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: tabs.asMap().entries.map((entry) {
          final index = entry.key;
          final tab = entry.value;
          final isSelected = _selectedTab == index;
          
          return Expanded(
            child: GestureDetector(
              onTap: () {
                setState(() {
                  _selectedTab = index;
                });
              },
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 8),
                decoration: BoxDecoration(
                  color: isSelected ? Colors.white : Colors.transparent,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  tab,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontFamily: 'Sora',
                    fontWeight: FontWeight.w600,
                    fontSize: 12,
                    color: isSelected ? const Color(0xFF10B981) : Colors.white70,
                  ),
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildTabContent() {
    switch (_selectedTab) {
      case 0:
        return widget.showSpendingPatterns 
            ? _buildSpendingPatternsContent() 
            : (widget.showPersonalityProfile ? _buildPersonalityProfileContent() : _buildLearningProgressContent());
      case 1:
        if (widget.showSpendingPatterns && widget.showPersonalityProfile) {
          return _buildPersonalityProfileContent();
        } else if (widget.showLearningProgress) {
          return _buildLearningProgressContent();
        }
        return const SizedBox.shrink();
      case 2:
        return _buildLearningProgressContent();
      default:
        return const SizedBox.shrink();
    }
  }

  Widget _buildSpendingPatternsContent() {
    final patterns = _behavioralAnalysis?['key_traits'] as List<dynamic>? ?? [];
    final spendingPersonality = _behavioralAnalysis?['spending_personality'] as String? ?? 'Unknown';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Your Spending Personality: $spendingPersonality',
          style: const TextStyle(
            fontFamily: 'Sora',
            fontWeight: FontWeight.w600,
            fontSize: 16,
            color: Colors.white,
          ),
        ),
        
        const SizedBox(height: 16),
        
        if (patterns.isNotEmpty) ...[
          const Text(
            'Identified Patterns:',
            style: TextStyle(
              fontFamily: 'Sora',
              fontWeight: FontWeight.w600,
              fontSize: 14,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 8),
          ...patterns.map((pattern) => _buildPatternItem(pattern.toString())),
        ],
        
        const SizedBox(height: 16),
        
        // Pattern Strength Indicators
        _buildPatternStrengthSection(),
      ],
    );
  }

  Widget _buildPatternItem(String pattern) {
    IconData patternIcon;
    String patternDescription;
    
    switch (pattern.toLowerCase()) {
      case 'weekend_overspending':
        patternIcon = Icons.weekend;
        patternDescription = 'Higher spending on weekends';
        break;
      case 'impulse_buying':
        patternIcon = Icons.flash_on;
        patternDescription = 'Tendency for impulse purchases';
        break;
      case 'consistent_spending':
        patternIcon = Icons.trending_flat;
        patternDescription = 'Predictable spending habits';
        break;
      case 'goal_oriented':
        patternIcon = Icons.flag;
        patternDescription = 'Focuses on financial goals';
        break;
      default:
        patternIcon = Icons.insights;
        patternDescription = pattern.replaceAll('_', ' ');
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(
            patternIcon,
            color: Colors.white.withOpacity(0.8),
            size: 20,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  patternDescription,
                  style: TextStyle(
                    fontFamily: 'Manrope',
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                    color: Colors.white.withOpacity(0.9),
                  ),
                ),
                Text(
                  'Detected pattern',
                  style: TextStyle(
                    fontFamily: 'Manrope',
                    fontSize: 11,
                    color: Colors.white.withOpacity(0.6),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPatternStrengthSection() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Pattern Confidence',
            style: TextStyle(
              fontFamily: 'Sora',
              fontWeight: FontWeight.w600,
              fontSize: 12,
              color: Colors.white.withOpacity(0.9),
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Data Quality',
                      style: TextStyle(
                        fontFamily: 'Manrope',
                        fontSize: 11,
                        color: Colors.white.withOpacity(0.7),
                      ),
                    ),
                    const SizedBox(height: 4),
                    LinearProgressIndicator(
                      value: 0.85,
                      backgroundColor: Colors.white.withOpacity(0.2),
                      valueColor: const AlwaysStoppedAnimation<Color>(Colors.white),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              Text(
                '85%',
                style: TextStyle(
                  fontFamily: 'Sora',
                  fontWeight: FontWeight.w600,
                  fontSize: 12,
                  color: Colors.white.withOpacity(0.9),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildPersonalityProfileContent() {
    final spendingPersonality = _behavioralAnalysis?['spending_personality'] as String? ?? 'balanced';
    final recommendations = _behavioralAnalysis?['recommendations'] as List<dynamic>? ?? [];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Personality Avatar
        Center(
          child: Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: Colors.white.withOpacity(0.2),
            ),
            child: Icon(
              _getPersonalityIcon(spendingPersonality),
              color: Colors.white,
              size: 40,
            ),
          ),
        ),
        
        const SizedBox(height: 16),
        
        Text(
          _getPersonalityTitle(spendingPersonality),
          textAlign: TextAlign.center,
          style: const TextStyle(
            fontFamily: 'Sora',
            fontWeight: FontWeight.bold,
            fontSize: 18,
            color: Colors.white,
          ),
        ),
        
        const SizedBox(height: 8),
        
        Text(
          _getPersonalityDescription(spendingPersonality),
          textAlign: TextAlign.center,
          style: TextStyle(
            fontFamily: 'Manrope',
            fontSize: 13,
            color: Colors.white.withOpacity(0.8),
          ),
        ),
        
        const SizedBox(height: 16),
        
        // Recommendations
        if (recommendations.isNotEmpty) ...[
          const Text(
            'Personalized Tips:',
            style: TextStyle(
              fontFamily: 'Sora',
              fontWeight: FontWeight.w600,
              fontSize: 14,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 8),
          ...recommendations.take(3).map((rec) => Container(
            margin: const EdgeInsets.only(bottom: 6),
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.1),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '💡 ',
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.8),
                  ),
                ),
                Expanded(
                  child: Text(
                    rec.toString(),
                    style: TextStyle(
                      fontFamily: 'Manrope',
                      fontSize: 12,
                      color: Colors.white.withOpacity(0.8),
                    ),
                  ),
                ),
              ],
            ),
          )).toList(),
        ],
      ],
    );
  }

  Widget _buildLearningProgressContent() {
    final learningTimestamp = _userProfile?['learning_timestamp'] as String?;
    final analysisTimestamp = _userProfile?['analysis_timestamp'] as String?;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Learning Progress',
          style: TextStyle(
            fontFamily: 'Sora',
            fontWeight: FontWeight.w600,
            fontSize: 16,
            color: Colors.white,
          ),
        ),
        
        const SizedBox(height: 16),
        
        // Learning Stats
        Row(
          children: [
            Expanded(
              child: _buildLearningStatCard('Data Points', '247', Icons.data_usage),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _buildLearningStatCard('Insights', '8', Icons.lightbulb),
            ),
          ],
        ),
        
        const SizedBox(height: 16),
        
        // Learning Timeline
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.1),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Recent Activity',
                style: TextStyle(
                  fontFamily: 'Sora',
                  fontWeight: FontWeight.w600,
                  fontSize: 12,
                  color: Colors.white.withOpacity(0.9),
                ),
              ),
              const SizedBox(height: 8),
              if (learningTimestamp != null)
                _buildActivityItem('Behavioral learning update', learningTimestamp),
              if (analysisTimestamp != null)
                _buildActivityItem('Analysis refresh', analysisTimestamp),
              _buildActivityItem('Pattern recognition improved', DateTime.now().toString()),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildLearningStatCard(String label, String value, IconData icon) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        children: [
          Icon(
            icon,
            color: Colors.white.withOpacity(0.8),
            size: 24,
          ),
          const SizedBox(height: 8),
          Text(
            value,
            style: const TextStyle(
              fontFamily: 'Sora',
              fontWeight: FontWeight.bold,
              fontSize: 18,
              color: Colors.white,
            ),
          ),
          Text(
            label,
            style: TextStyle(
              fontFamily: 'Manrope',
              fontSize: 11,
              color: Colors.white.withOpacity(0.7),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActivityItem(String activity, String timestamp) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: Colors.white.withOpacity(0.6),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              activity,
              style: TextStyle(
                fontFamily: 'Manrope',
                fontSize: 11,
                color: Colors.white.withOpacity(0.8),
              ),
            ),
          ),
          Text(
            _formatTimestamp(timestamp),
            style: TextStyle(
              fontFamily: 'Manrope',
              fontSize: 10,
              color: Colors.white.withOpacity(0.5),
            ),
          ),
        ],
      ),
    );
  }

  IconData _getPersonalityIcon(String personality) {
    switch (personality.toLowerCase()) {
      case 'saver':
        return Icons.savings;
      case 'spender':
        return Icons.shopping_bag;
      case 'balanced':
        return Icons.balance;
      case 'conservative':
        return Icons.security;
      case 'aggressive':
        return Icons.trending_up;
      default:
        return Icons.person;
    }
  }

  String _getPersonalityTitle(String personality) {
    switch (personality.toLowerCase()) {
      case 'saver':
        return 'The Saver';
      case 'spender':
        return 'The Enjoyer';
      case 'balanced':
        return 'The Balanced';
      case 'conservative':
        return 'The Conservative';
      case 'aggressive':
        return 'The Aggressive';
      default:
        return 'Unique Profile';
    }
  }

  String _getPersonalityDescription(String personality) {
    switch (personality.toLowerCase()) {
      case 'saver':
        return 'You prioritize saving and building wealth for the future.';
      case 'spender':
        return 'You believe in enjoying life and spending on experiences.';
      case 'balanced':
        return 'You maintain a healthy balance between spending and saving.';
      case 'conservative':
        return 'You prefer safe, predictable financial decisions.';
      case 'aggressive':
        return 'You\'re comfortable taking financial risks for higher returns.';
      default:
        return 'Your financial personality is still being analyzed.';
    }
  }

  String _formatTimestamp(String timestamp) {
    try {
      final dateTime = DateTime.parse(timestamp);
      final now = DateTime.now();
      final difference = now.difference(dateTime);
      
      if (difference.inMinutes < 60) {
        return '${difference.inMinutes}m ago';
      } else if (difference.inHours < 24) {
        return '${difference.inHours}h ago';
      } else if (difference.inDays < 7) {
        return '${difference.inDays}d ago';
      } else {
        return '${(difference.inDays / 7).floor()}w ago';
      }
    } catch (e) {
      return 'recently';
    }
  }
}
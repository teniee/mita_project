import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';
import '../services/income_service.dart';
import '../widgets/income_tier_widgets.dart';
import '../theme/income_theme.dart';

class BudgetSettingsScreen extends StatefulWidget {
  const BudgetSettingsScreen({super.key});

  @override
  State<BudgetSettingsScreen> createState() => _BudgetSettingsScreenState();
}

class _BudgetSettingsScreenState extends State<BudgetSettingsScreen> {
  final ApiService _apiService = ApiService();
  final IncomeService _incomeService = IncomeService();
  
  bool _isLoading = true;
  String _currentBudgetMode = 'default';
  Map<String, dynamic> _automationSettings = {};
  bool _isUpdating = false;

  // Income-related data
  double _monthlyIncome = 0.0;
  IncomeTier? _incomeTier;
  Map<String, dynamic>? _budgetRecommendations;

  // Budget status data
  Map<String, dynamic>? _budgetRemaining;
  Map<String, dynamic>? _behavioralAllocation;

  final List<Map<String, dynamic>> _budgetModes = [
    {
      'id': 'default',
      'name': 'Standard Budget',
      'description': 'Traditional budget tracking with basic redistribution',
      'icon': Icons.account_balance_wallet,
      'color': Colors.grey,
      'features': ['Basic tracking', 'Manual redistribution', 'Standard alerts'],
    },
    {
      'id': 'flexible',
      'name': 'Flexible Budget',
      'description': 'Adaptive budget that adjusts to your spending patterns',
      'icon': Icons.auto_fix_high,
      'color': const AppColors.successLight,
      'features': ['Auto-adjustment', 'Smart redistribution', 'Flexible limits'],
    },
    {
      'id': 'strict',
      'name': 'Strict Budget',
      'description': 'Rigid budget control with firm spending limits',
      'icon': Icons.lock,
      'color': const AppColors.danger,
      'features': ['Hard limits', 'Strict alerts', 'No overspending'],
    },
    {
      'id': 'behavioral',
      'name': 'Behavioral Adaptive',
      'description': 'AI-powered budget that learns from your behavior',
      'icon': Icons.psychology,
      'color': const AppColors.accent,
      'features': ['AI learning', 'Behavioral insights', 'Predictive adjustments'],
    },
    {
      'id': 'goal',
      'name': 'Goal-Oriented',
      'description': 'Budget optimized for achieving your savings goals',
      'icon': Icons.flag,
      'color': const AppColors.secondary,
      'features': ['Goal tracking', 'Savings priority', 'Target optimization'],
    },
  ];

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    setState(() {
      _isLoading = true;
    });

    try {
      // Load user profile for income data
      final profileResponse = await _apiService.getUserProfile();
      final incomeValue = (profileResponse['data']?['income'] as num?)?.toDouble();
      
      if (incomeValue == null || incomeValue <= 0) {
        throw Exception('Income data required for budget settings. Please complete onboarding.');
      }
      
      _monthlyIncome = incomeValue;
      _incomeTier = _incomeService.classifyIncome(_monthlyIncome);
      
      final now = DateTime.now();
      final futures = await Future.wait([
        _apiService.getBudgetMode(),
        _apiService.getBudgetAutomationSettings(),
        _apiService.getIncomeBasedBudgetRecommendations(_monthlyIncome),
        _apiService.getBudgetRemaining(year: now.year, month: now.month),
        _apiService.getBehavioralBudgetAllocation(_monthlyIncome, profile: {'income_tier': _incomeTier.toString()}),
      ]);

      final budgetMode = futures[0] as String;
      final automationSettings = futures[1] as Map<String, dynamic>;
      final budgetRecommendations = futures[2] as Map<String, dynamic>;
      final budgetRemaining = futures[3] as Map<String, dynamic>;
      final behavioralAllocation = futures[4] as Map<String, dynamic>;

      if (mounted) {
        setState(() {
          _currentBudgetMode = budgetMode;
          _automationSettings = automationSettings;
          _budgetRecommendations = budgetRecommendations;
          _budgetRemaining = budgetRemaining;
          _behavioralAllocation = behavioralAllocation;
          _isLoading = false;
        });
      }
    } catch (e) {
      logError('Error loading budget settings: $e');
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _updateBudgetMode(String newMode) async {
    if (_isUpdating) return;
    
    setState(() {
      _isUpdating = true;
    });

    try {
      await _apiService.setBudgetMode(newMode);
      
      if (mounted) {
        setState(() {
          _currentBudgetMode = newMode;
        });
        
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Row(
              children: [
                const Icon(Icons.check_circle, color: Colors.white),
                const SizedBox(width: 8),
                Text('Budget mode updated to ${_getBudgetModeByIdName(newMode)}'),
              ],
            ),
            backgroundColor: Theme.of(context).colorScheme.primary,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } catch (e) {
      logError('Error updating budget mode: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Row(
              children: [
                Icon(Icons.error, color: Colors.white),
                SizedBox(width: 8),
                Text('Failed to update budget mode'),
              ],
            ),
            backgroundColor: Theme.of(context).colorScheme.error,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _isUpdating = false;
        });
      }
    }
  }

  Future<void> _updateAutomationSettings(Map<String, dynamic> newSettings) async {
    try {
      await _apiService.updateBudgetAutomationSettings(newSettings);
      
      if (mounted) {
        setState(() {
          _automationSettings = {..._automationSettings, ...newSettings};
        });
        
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Row(
              children: [
                Icon(Icons.check_circle, color: Colors.white),
                SizedBox(width: 8),
                Text('Automation settings updated'),
              ],
            ),
            backgroundColor: Theme.of(context).colorScheme.primary,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } catch (e) {
      logError('Error updating automation settings: $e');
    }
  }

  String _getBudgetModeByIdName(String id) {
    final mode = _budgetModes.firstWhere(
      (mode) => mode['id'] == id,
      orElse: () => _budgetModes[0],
    );
    return mode['name'];
  }

  Map<String, dynamic> _getBudgetModeById(String id) {
    return _budgetModes.firstWhere(
      (mode) => mode['id'] == id,
      orElse: () => _budgetModes[0],
    );
  }

  Widget _buildBudgetModeCard(Map<String, dynamic> mode) {
    final isSelected = mode['id'] == _currentBudgetMode;
    final colorScheme = Theme.of(context).colorScheme;
    
    return Card(
      elevation: isSelected ? 6 : 2,
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: isSelected 
          ? BorderSide(color: mode['color'], width: 2)
          : BorderSide.none,
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: _isUpdating ? null : () => _updateBudgetMode(mode['id']),
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
                      color: mode['color'].withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(
                      mode['icon'],
                      color: mode['color'],
                      size: 24,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Text(
                              mode['name'],
                              style: TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                                color: colorScheme.onSurface,
                                fontFamily: AppTypography.fontHeading,
                              ),
                            ),
                            if (isSelected) ...[
                              const SizedBox(width: 8),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                decoration: BoxDecoration(
                                  color: mode['color'],
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: const Text(
                                  'ACTIVE',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 10,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ),
                            ],
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text(
                          mode['description'],
                          style: TextStyle(
                            fontSize: 14,
                            color: colorScheme.onSurface.withValues(alpha: 0.7),
                          ),
                        ),
                      ],
                    ),
                  ),
                  if (_isUpdating && isSelected)
                    const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  else if (isSelected)
                    Icon(
                      Icons.check_circle,
                      color: mode['color'],
                      size: 24,
                    ),
                ],
              ),
              const SizedBox(height: 16),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: (mode['features'] as List<String>).map<Widget>((feature) =>
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: colorScheme.surface,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: mode['color'].withValues(alpha: 0.3)),
                    ),
                    child: Text(
                      feature,
                      style: TextStyle(
                        fontSize: 12,
                        color: mode['color'],
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ).toList(),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildBudgetRemainingCard() {
    if (_budgetRemaining == null) return const SizedBox.shrink();

    final colorScheme = Theme.of(context).colorScheme;
    final primaryColor = _incomeTier != null ? _incomeService.getIncomeTierPrimaryColor(_incomeTier!) : colorScheme.primary;

    final totalBudget = (_budgetRemaining!['total_budget'] as num?)?.toDouble() ?? 0.0;
    final totalSpent = (_budgetRemaining!['total_spent'] as num?)?.toDouble() ?? 0.0;
    final remaining = (_budgetRemaining!['remaining'] as num?)?.toDouble() ?? 0.0;
    final percentageUsed = totalBudget > 0 ? (totalSpent / totalBudget * 100) : 0.0;

    return Card(
      elevation: 2,
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.account_balance_wallet, color: primaryColor),
                const SizedBox(width: 12),
                Text(
                  'Budget Status This Month',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: colorScheme.onSurface,
                    fontFamily: AppTypography.fontHeading,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),

            // Progress bar
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: LinearProgressIndicator(
                value: percentageUsed / 100,
                minHeight: 12,
                backgroundColor: Colors.grey[200],
                valueColor: AlwaysStoppedAnimation<Color>(
                  percentageUsed > 90 ? Colors.red : percentageUsed > 70 ? Colors.orange : primaryColor,
                ),
              ),
            ),

            const SizedBox(height: 16),

            // Budget stats
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Total Budget',
                      style: TextStyle(
                        fontSize: 12,
                        color: colorScheme.onSurface.withValues(alpha: 0.6),
                      ),
                    ),
                    Text(
                      '\$${totalBudget.toStringAsFixed(0)}',
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        fontFamily: AppTypography.fontHeading,
                      ),
                    ),
                  ],
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    Text(
                      'Spent',
                      style: TextStyle(
                        fontSize: 12,
                        color: colorScheme.onSurface.withValues(alpha: 0.6),
                      ),
                    ),
                    Text(
                      '\$${totalSpent.toStringAsFixed(0)}',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        fontFamily: AppTypography.fontHeading,
                        color: percentageUsed > 90 ? Colors.red : null,
                      ),
                    ),
                  ],
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      'Remaining',
                      style: TextStyle(
                        fontSize: 12,
                        color: colorScheme.onSurface.withValues(alpha: 0.6),
                      ),
                    ),
                    Text(
                      '\$${remaining.toStringAsFixed(0)}',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        fontFamily: AppTypography.fontHeading,
                        color: remaining < 0 ? Colors.red : Colors.green,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAutomationSettings() {
    final colorScheme = Theme.of(context).colorScheme;

    return Card(
      elevation: 2,
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.settings_suggest, color: colorScheme.primary),
                const SizedBox(width: 12),
                Text(
                  'Automation Settings',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: colorScheme.onSurface,
                    fontFamily: AppTypography.fontHeading,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            
            // Auto Redistribution
            SwitchListTile(
              title: const Text(
                'Auto Redistribution',
                style: TextStyle(fontWeight: FontWeight.w500),
              ),
              subtitle: const Text(
                'Automatically redistribute budget when overspending occurs',
                style: TextStyle(fontSize: 12),
              ),
              value: _automationSettings['auto_redistribution'] ?? false,
              onChanged: (bool value) {
                _updateAutomationSettings({'auto_redistribution': value});
              },
              activeColor: colorScheme.primary,
            ),
            
            // Smart Suggestions
            SwitchListTile(
              title: const Text(
                'Smart Suggestions',
                style: TextStyle(fontWeight: FontWeight.w500),
              ),
              subtitle: const Text(
                'Receive AI-powered budget recommendations',
                style: TextStyle(fontSize: 12),
              ),
              value: _automationSettings['smart_suggestions'] ?? true,
              onChanged: (bool value) {
                _updateAutomationSettings({'smart_suggestions': value});
              },
              activeColor: colorScheme.primary,
            ),
            
            // Behavioral Learning
            SwitchListTile(
              title: const Text(
                'Behavioral Learning',
                style: TextStyle(fontWeight: FontWeight.w500),
              ),
              subtitle: const Text(
                'Allow AI to learn from your spending patterns',
                style: TextStyle(fontSize: 12),
              ),
              value: _automationSettings['behavioral_learning'] ?? true,
              onChanged: (bool value) {
                _updateAutomationSettings({'behavioral_learning': value});
              },
              activeColor: colorScheme.primary,
            ),
            
            // Real-time Alerts
            SwitchListTile(
              title: const Text(
                'Real-time Alerts',
                style: TextStyle(fontWeight: FontWeight.w500),
              ),
              subtitle: const Text(
                'Get instant notifications for budget changes',
                style: TextStyle(fontSize: 12),
              ),
              value: _automationSettings['realtime_alerts'] ?? true,
              onChanged: (bool value) {
                _updateAutomationSettings({'realtime_alerts': value});
              },
              activeColor: colorScheme.primary,
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final primaryColor = _incomeTier != null ? _incomeService.getIncomeTierPrimaryColor(_incomeTier!) : colorScheme.primary;
    
    return Scaffold(
      backgroundColor: colorScheme.surface,
      appBar: _incomeTier != null 
        ? IncomeTheme.createTierAppBar(
            tier: _incomeTier!,
            title: 'Budget Settings',
          )
        : AppBar(
            title: const Text(
              'Budget Settings',
              style: TextStyle(
                fontFamily: AppTypography.fontHeading,
                fontWeight: FontWeight.bold,
              ),
            ),
            backgroundColor: colorScheme.surface,
            elevation: 0,
            centerTitle: true,
            iconTheme: IconThemeData(color: colorScheme.onSurface),
          ),
      body: _isLoading
        ? const Center(child: CircularProgressIndicator())
        : RefreshIndicator(
            onRefresh: _loadSettings,
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              physics: const AlwaysScrollableScrollPhysics(),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Income Context Card
                  if (_incomeTier != null)
                    IncomeTierCard(
                      monthlyIncome: _monthlyIncome,
                      showDetails: false,
                    ),
                  
                  if (_incomeTier != null)
                    const SizedBox(height: 16),

                  // Budget Remaining Status
                  _buildBudgetRemainingCard(),

                  // Income-based Budget Recommendations
                  if (_budgetRecommendations != null)
                    Card(
                      elevation: 2,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
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
                                  'Income-Based Recommendations',
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
                            ...(_budgetRecommendations!['allocations'] as Map<String, dynamic>?)?.entries.map((entry) {
                              final category = entry.key;
                              final amount = entry.value as double;
                              final percentage = _incomeService.getIncomePercentage(amount, _monthlyIncome);
                              
                              return Padding(
                                padding: const EdgeInsets.only(bottom: 8),
                                child: Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Text(
                                      category.toUpperCase(),
                                      style: const TextStyle(
                                        fontFamily: AppTypography.fontHeading,
                                        fontWeight: FontWeight.w600,
                                        fontSize: 14,
                                      ),
                                    ),
                                    Column(
                                      crossAxisAlignment: CrossAxisAlignment.end,
                                      children: [
                                        Text(
                                          '\$${amount.toStringAsFixed(0)}',
                                          style: TextStyle(
                                            fontFamily: AppTypography.fontHeading,
                                            fontWeight: FontWeight.bold,
                                            color: primaryColor,
                                          ),
                                        ),
                                        Text(
                                          '${percentage.toStringAsFixed(1)}% of income',
                                          style: TextStyle(
                                            fontFamily: AppTypography.fontBody,
                                            fontSize: 11,
                                            color: Colors.grey[600],
                                          ),
                                        ),
                                      ],
                                    ),
                                  ],
                                ),
                              );
                            }).toList() ?? [],
                          ],
                        ),
                      ),
                    ),
                  
                  if (_budgetRecommendations != null)
                    const SizedBox(height: 16),

                  // Behavioral Budget Allocation (AI-powered)
                  if (_behavioralAllocation != null && _behavioralAllocation!['allocations'] != null)
                    Card(
                      elevation: 2,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                      child: Padding(
                        padding: const EdgeInsets.all(20),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Icon(
                                  Icons.psychology,
                                  color: const AppColors.accent,
                                  size: 24,
                                ),
                                const SizedBox(width: 12),
                                Text(
                                  'AI Behavioral Allocation',
                                  style: TextStyle(
                                    fontFamily: AppTypography.fontHeading,
                                    fontWeight: FontWeight.bold,
                                    fontSize: 18,
                                    color: colorScheme.onSurface,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            Text(
                              'Budget allocation based on your behavioral patterns',
                              style: TextStyle(
                                fontSize: 12,
                                color: colorScheme.onSurface.withValues(alpha: 0.6),
                              ),
                            ),
                            const SizedBox(height: 16),
                            ...(_behavioralAllocation!['allocations'] as Map<String, dynamic>?)?.entries.map((entry) {
                              final category = entry.key;
                              final data = entry.value as Map<String, dynamic>;
                              final amount = (data['amount'] as num?)?.toDouble() ?? 0.0;
                              final confidence = (data['confidence'] as num?)?.toDouble() ?? 0.0;

                              return Padding(
                                padding: const EdgeInsets.only(bottom: 12),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Row(
                                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                      children: [
                                        Text(
                                          category.toUpperCase(),
                                          style: const TextStyle(
                                            fontFamily: AppTypography.fontHeading,
                                            fontWeight: FontWeight.w600,
                                            fontSize: 13,
                                          ),
                                        ),
                                        Text(
                                          '\$${amount.toStringAsFixed(0)}',
                                          style: const TextStyle(
                                            fontFamily: AppTypography.fontHeading,
                                            fontWeight: FontWeight.bold,
                                            fontSize: 15,
                                          ),
                                        ),
                                      ],
                                    ),
                                    const SizedBox(height: 4),
                                    Row(
                                      children: [
                                        Expanded(
                                          child: ClipRRect(
                                            borderRadius: BorderRadius.circular(4),
                                            child: LinearProgressIndicator(
                                              value: confidence / 100,
                                              minHeight: 6,
                                              backgroundColor: Colors.grey[200],
                                              valueColor: AlwaysStoppedAnimation<Color>(
                                                const AppColors.accent,
                                              ),
                                            ),
                                          ),
                                        ),
                                        const SizedBox(width: 8),
                                        Text(
                                          '${confidence.toStringAsFixed(0)}% confidence',
                                          style: TextStyle(
                                            fontSize: 11,
                                            color: Colors.grey[600],
                                          ),
                                        ),
                                      ],
                                    ),
                                  ],
                                ),
                              );
                            }).toList() ?? [],
                          ],
                        ),
                      ),
                    ),

                  if (_behavioralAllocation != null)
                    const SizedBox(height: 24),

                  // Current Mode Display
                  Card(
                    elevation: 4,
                    margin: const EdgeInsets.only(bottom: 24),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                    child: Container(
                      padding: const EdgeInsets.all(20),
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(16),
                        gradient: LinearGradient(
                          colors: [
                            _getBudgetModeById(_currentBudgetMode)['color'],
                            _getBudgetModeById(_currentBudgetMode)['color'].withValues(alpha: 0.8),
                          ],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                      ),
                      child: Row(
                        children: [
                          Icon(
                            _getBudgetModeById(_currentBudgetMode)['icon'],
                            color: Colors.white,
                            size: 32,
                          ),
                          const SizedBox(width: 16),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text(
                                  'Current Budget Mode',
                                  style: TextStyle(
                                    color: Colors.white70,
                                    fontSize: 14,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  _getBudgetModeById(_currentBudgetMode)['name'],
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 20,
                                    fontWeight: FontWeight.bold,
                                    fontFamily: AppTypography.fontHeading,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  
                  // Budget Modes Section
                  Text(
                    'Choose Your Budget Mode',
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                      color: colorScheme.onSurface,
                      fontFamily: AppTypography.fontHeading,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Select the budget management approach that best fits your financial goals and spending habits.',
                    style: TextStyle(
                      fontSize: 14,
                      color: colorScheme.onSurface.withValues(alpha: 0.7),
                    ),
                  ),
                  const SizedBox(height: 20),
                  
                  // Budget mode cards
                  ..._budgetModes.map((mode) => _buildBudgetModeCard(mode)),
                  
                  const SizedBox(height: 24),
                  
                  // Automation Settings
                  Text(
                    'Automation Preferences',
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                      color: colorScheme.onSurface,
                      fontFamily: AppTypography.fontHeading,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Customize how MITA automatically manages your budget and provides intelligent recommendations.',
                    style: TextStyle(
                      fontSize: 14,
                      color: colorScheme.onSurface.withValues(alpha: 0.7),
                    ),
                  ),
                  const SizedBox(height: 20),
                  
                  _buildAutomationSettings(),
                  
                  const SizedBox(height: 24),
                  
                  // Additional Info
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: colorScheme.primary.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      children: [
                        Icon(Icons.info_outline, color: colorScheme.primary),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            'Changes to your budget mode will take effect immediately and may trigger automatic redistribution of your current budget.',
                            style: TextStyle(
                              fontSize: 13,
                              color: colorScheme.primary,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
    );
  }
}
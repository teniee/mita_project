/// Installment Calculator Screen
/// Smart financial analysis tool to help users make informed installment purchase decisions
/// Features risk assessment, payment breakdown, and personalized recommendations

import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../models/installment_models.dart';
import '../providers/installments_provider.dart';
import '../services/installment_service.dart';
import '../services/logging_service.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';

class InstallmentCalculatorScreen extends StatefulWidget {
  const InstallmentCalculatorScreen({super.key});

  @override
  State<InstallmentCalculatorScreen> createState() => _InstallmentCalculatorScreenState();
}

class _InstallmentCalculatorScreenState extends State<InstallmentCalculatorScreen>
    with SingleTickerProviderStateMixin {
  final InstallmentService _installmentService = InstallmentService();
  final _formKey = GlobalKey<FormState>();

  // Form controllers
  final _purchaseAmountController = TextEditingController();
  final _interestRateController = TextEditingController();
  final _monthlyIncomeController = TextEditingController();
  final _currentBalanceController = TextEditingController();

  // Form values
  InstallmentCategory _selectedCategory = InstallmentCategory.electronics;
  int _selectedPayments = 4;
  double _selectedInterestRate = 0.0;

  // Local UI state management
  bool _isLoading = false;
  bool _hasProfile = false;
  UserFinancialProfile? _userProfile;
  InstallmentCalculatorOutput? _calculationResult;
  bool _showResults = false;

  // Animation controller for results
  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;
  late Animation<Offset> _slideAnimation;

  // Scroll controller for auto-scroll to results
  final ScrollController _scrollController = ScrollController();

  // Payment options
  final List<int> _paymentOptions = [4, 6, 12, 24];
  final List<double> _interestPresets = [0, 10, 15, 20];

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 600),
      vsync: this,
    );
    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeIn),
    );
    _slideAnimation = Tween<Offset>(
      begin: const Offset(0, 0.1),
      end: Offset.zero,
    ).animate(CurvedAnimation(
      parent: _animationController,
      curve: Curves.easeOutCubic,
    ));

    // Initialize provider and load user profile
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final provider = context.read<InstallmentsProvider>();
      if (provider.state == InstallmentsState.initial) {
        provider.initialize();
      }
      _loadUserProfile();
    });
  }

  @override
  void dispose() {
    _animationController.dispose();
    _scrollController.dispose();
    _purchaseAmountController.dispose();
    _interestRateController.dispose();
    _monthlyIncomeController.dispose();
    _currentBalanceController.dispose();
    super.dispose();
  }

  Future<void> _loadUserProfile() async {
    try {
      final profile = await _installmentService.getFinancialProfile();
      if (mounted) {
        setState(() {
          _userProfile = profile;
          _hasProfile = profile != null;

          // Pre-fill form with profile data
          if (profile != null) {
            if (profile.monthlyIncome != null) {
              _monthlyIncomeController.text = profile.monthlyIncome!.toStringAsFixed(2);
            }
            if (profile.currentBalance != null) {
              _currentBalanceController.text = profile.currentBalance!.toStringAsFixed(2);
            }
          }
        });
      }
    } catch (e) {
      logError('Error loading financial profile', tag: 'CALCULATOR', error: e);
    }
  }

  Future<void> _calculateInstallment() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    // Validate required fields for users without profile
    if (!_hasProfile) {
      if (_monthlyIncomeController.text.isEmpty || _currentBalanceController.text.isEmpty) {
        _showErrorDialog(
          'Missing Information',
          'Please provide your monthly income and current balance to calculate risk assessment.',
        );
        return;
      }
    }

    setState(() {
      _isLoading = true;
      _showResults = false;
    });

    // Haptic feedback
    HapticFeedback.mediumImpact();

    try {
      final purchaseAmount = double.parse(_purchaseAmountController.text);
      final monthlyIncome = _hasProfile
          ? _userProfile!.monthlyIncome
          : double.tryParse(_monthlyIncomeController.text);
      final currentBalance = _hasProfile
          ? _userProfile!.currentBalance
          : double.tryParse(_currentBalanceController.text);

      // Use provider data for active installments
      final provider = context.read<InstallmentsProvider>();
      final activeInstallmentsCount = provider.totalActive;
      final activeInstallmentsMonthly = provider.totalMonthlyPayment;

      final input = InstallmentCalculatorInput(
        purchaseAmount: purchaseAmount,
        category: _selectedCategory,
        numPayments: _selectedPayments,
        interestRate: _selectedInterestRate,
        monthlyIncome: monthlyIncome,
        currentBalance: currentBalance,
        ageGroup: _userProfile?.ageGroup,
        activeInstallmentsCount: activeInstallmentsCount,
        activeInstallmentsMonthly: activeInstallmentsMonthly,
        creditCardDebt: _userProfile?.creditCardDebt ?? 0.0,
        otherMonthlyObligations: _userProfile?.totalMonthlyObligations ?? 0.0,
        planningMortgage: _userProfile?.planningMortgage ?? false,
      );

      final result = await _installmentService.calculateInstallmentRisk(input);

      if (mounted) {
        setState(() {
          _calculationResult = result;
          _showResults = true;
          _isLoading = false;
        });

        // Start animation
        _animationController.forward(from: 0.0);

        // Scroll to results section
        Future.delayed(const Duration(milliseconds: 300), () {
          if (_scrollController.hasClients) {
            _scrollController.animateTo(
              _scrollController.position.maxScrollExtent,
              duration: const Duration(milliseconds: 800),
              curve: Curves.easeOutCubic,
            );
          }
        });

        // Haptic feedback based on risk level
        if (result.riskLevel == RiskLevel.green) {
          HapticFeedback.lightImpact();
        } else if (result.riskLevel == RiskLevel.red) {
          HapticFeedback.heavyImpact();
        }
      }
    } on InstallmentServiceException catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        _showErrorDialog('Calculation Error', e.message);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        _showErrorDialog('Error', 'Failed to calculate installment: $e');
      }
      logError('Calculation error', tag: 'CALCULATOR', error: e);
    }
  }

  void _showErrorDialog(String title, String message) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Row(
          children: [
            const Icon(Icons.error_outline, color: AppColors.error),
            const SizedBox(width: 8),
            Text(title),
          ],
        ),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  Color _getRiskColor(RiskLevel risk) {
    switch (risk) {
      case RiskLevel.green:
        return AppColors.successDark; // Colors.green[700]
      case RiskLevel.yellow:
        return AppColors.warning; // Colors.amber[700]
      case RiskLevel.orange:
        return AppColors.warningDark; // Colors.orange[800]
      case RiskLevel.red:
        return AppColors.errorDark; // Colors.red[700]
    }
  }

  IconData _getRiskIcon(RiskLevel risk) {
    switch (risk) {
      case RiskLevel.green:
        return Icons.check_circle;
      case RiskLevel.yellow:
        return Icons.warning_amber;
      case RiskLevel.orange:
        return Icons.warning;
      case RiskLevel.red:
        return Icons.cancel;
    }
  }

  String _getRiskMessage(RiskLevel risk) {
    switch (risk) {
      case RiskLevel.green:
        return 'Safe to Proceed';
      case RiskLevel.yellow:
        return 'Proceed with Caution';
      case RiskLevel.orange:
        return 'High Risk';
      case RiskLevel.red:
        return 'Not Recommended';
    }
  }

  @override
  Widget build(BuildContext context) {
    // Watch provider for reactive updates
    final provider = context.watch<InstallmentsProvider>();

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text(
          'Can I Afford This?',
          style: TextStyle(
            fontFamily: AppTypography.fontHeading,
            fontWeight: FontWeight.bold,
            color: AppColors.textPrimary,
          ),
        ),
        backgroundColor: AppColors.background,
        elevation: 0,
        centerTitle: true,
        iconTheme: const IconThemeData(color: AppColors.textPrimary),
      ),
      body: SingleChildScrollView(
        controller: _scrollController,
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _buildHeaderSection(),
              const SizedBox(height: 24),
              _buildInputFormSection(),
              const SizedBox(height: 24),
              _buildCalculateButton(),
              if (_showResults && _calculationResult != null) ...[
                const SizedBox(height: 32),
                _buildResultsSection(),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeaderSection() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [AppColors.textPrimary, AppColors.primary],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.1),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          const Icon(
            Icons.calculate,
            size: 48,
            color: AppColors.secondary,
          ),
          const SizedBox(height: 12),
          const Text(
            'Smart Financial Analysis',
            style: TextStyle(
              fontFamily: AppTypography.fontHeading,
              fontSize: 20,
              fontWeight: FontWeight.bold,
              color: Colors.white,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 8),
          Text(
            'Get personalized risk assessment and recommendations\nbased on your financial situation',
            style: TextStyle(
              fontFamily: AppTypography.fontBody,
              fontSize: 14,
              color: Colors.white.withValues(alpha: 0.9),
              height: 1.4,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _buildInputFormSection() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Purchase Details',
            style: TextStyle(
              fontFamily: AppTypography.fontHeading,
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 20),

          // Purchase Amount
          TextFormField(
            controller: _purchaseAmountController,
            decoration: InputDecoration(
              labelText: 'Purchase Amount',
              hintText: '0.00',
              prefixText: '\$ ',
              prefixStyle: const TextStyle(
                fontFamily: AppTypography.fontBody,
                fontWeight: FontWeight.bold,
                color: AppColors.textPrimary,
              ),
              suffixIcon: Tooltip(
                message: 'Total cost of the item you want to purchase',
                child: Icon(Icons.info_outline, color: Colors.grey[600]),
              ),
              filled: true,
              fillColor: AppColors.background,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide.none,
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide(color: Colors.grey[300]!),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: const BorderSide(color: AppColors.textPrimary, width: 2),
              ),
            ),
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: [
              FilteringTextInputFormatter.allow(RegExp(r'^\d+\.?\d{0,2}')),
            ],
            validator: (value) {
              if (value == null || value.isEmpty) {
                return 'Please enter purchase amount';
              }
              final amount = double.tryParse(value);
              if (amount == null || amount <= 0) {
                return 'Please enter a valid amount';
              }
              return null;
            },
          ),
          const SizedBox(height: 16),

          // Category Dropdown
          DropdownButtonFormField<InstallmentCategory>(
            value: _selectedCategory,
            decoration: InputDecoration(
              labelText: 'Category',
              suffixIcon: Tooltip(
                message: 'What type of purchase is this?',
                child: Icon(Icons.info_outline, color: Colors.grey[600]),
              ),
              filled: true,
              fillColor: AppColors.background,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide.none,
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide(color: Colors.grey[300]!),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: const BorderSide(color: AppColors.textPrimary, width: 2),
              ),
            ),
            items: InstallmentCategory.values.map((category) {
              return DropdownMenuItem(
                value: category,
                child: Row(
                  children: [
                    Icon(_getCategoryIcon(category), size: 20, color: AppColors.textPrimary),
                    const SizedBox(width: 8),
                    Text(category.displayName,
                        style: const TextStyle(fontFamily: AppTypography.fontBody)),
                  ],
                ),
              );
            }).toList(),
            onChanged: (value) {
              setState(() {
                _selectedCategory = value!;
              });
            },
          ),
          const SizedBox(height: 16),

          // Number of Payments
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Text(
                    'Number of Payments',
                    style: TextStyle(
                      fontFamily: AppTypography.fontBody,
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(width: 4),
                  Tooltip(
                    message: 'How many monthly payments?',
                    child: Icon(Icons.info_outline, size: 16, color: Colors.grey[600]),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: _paymentOptions.map((payments) {
                  final isSelected = _selectedPayments == payments;
                  return ChoiceChip(
                    label: Text(
                      '$payments months',
                      style: TextStyle(
                        fontFamily: AppTypography.fontBody,
                        fontWeight: FontWeight.w600,
                        color: isSelected ? Colors.white : AppColors.textPrimary,
                      ),
                    ),
                    selected: isSelected,
                    onSelected: (selected) {
                      setState(() {
                        _selectedPayments = payments;
                      });
                    },
                    selectedColor: AppColors.textPrimary,
                    backgroundColor: AppColors.background,
                    side: BorderSide(
                      color: isSelected ? AppColors.textPrimary : Colors.grey[300]!,
                      width: isSelected ? 2 : 1,
                    ),
                    elevation: isSelected ? 2 : 0,
                  );
                }).toList(),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Interest Rate
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Text(
                    'Interest Rate',
                    style: TextStyle(
                      fontFamily: AppTypography.fontBody,
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(width: 4),
                  Tooltip(
                    message: 'Annual percentage rate (APR)',
                    child: Icon(Icons.info_outline, size: 16, color: Colors.grey[600]),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: _interestPresets.map((rate) {
                  final isSelected = _selectedInterestRate == rate;
                  return Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(
                      label: Text(
                        '${rate.toInt()}%',
                        style: TextStyle(
                          fontFamily: AppTypography.fontBody,
                          fontWeight: FontWeight.w600,
                          color: isSelected ? Colors.white : AppColors.textPrimary,
                        ),
                      ),
                      selected: isSelected,
                      onSelected: (selected) {
                        setState(() {
                          _selectedInterestRate = rate;
                          _interestRateController.text = rate.toStringAsFixed(1);
                        });
                      },
                      selectedColor: AppColors.secondary,
                      backgroundColor: AppColors.background,
                      side: BorderSide(
                        color: isSelected ? AppColors.secondary : Colors.grey[300]!,
                        width: isSelected ? 2 : 1,
                      ),
                    ),
                  );
                }).toList(),
              ),
              const SizedBox(height: 8),
              TextFormField(
                controller: _interestRateController,
                decoration: InputDecoration(
                  labelText: 'Custom Rate',
                  hintText: '0.0',
                  suffixText: '%',
                  suffixStyle: const TextStyle(
                    fontFamily: AppTypography.fontBody,
                    fontWeight: FontWeight.bold,
                    color: AppColors.textPrimary,
                  ),
                  filled: true,
                  fillColor: AppColors.background,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide.none,
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide(color: Colors.grey[300]!),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(color: AppColors.textPrimary, width: 2),
                  ),
                ),
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: [
                  FilteringTextInputFormatter.allow(RegExp(r'^\d+\.?\d{0,2}')),
                ],
                onChanged: (value) {
                  final rate = double.tryParse(value);
                  if (rate != null) {
                    setState(() {
                      _selectedInterestRate = rate;
                    });
                  }
                },
              ),
            ],
          ),

          // Optional fields for users without profile
          if (!_hasProfile) ...[
            const SizedBox(height: 24),
            const Divider(),
            const SizedBox(height: 16),
            const Text(
              'Your Financial Information',
              style: TextStyle(
                fontFamily: AppTypography.fontHeading,
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 16),

            // Monthly Income
            TextFormField(
              controller: _monthlyIncomeController,
              decoration: InputDecoration(
                labelText: 'Monthly Income',
                hintText: '0.00',
                prefixText: '\$ ',
                prefixStyle: const TextStyle(
                  fontFamily: AppTypography.fontBody,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
                suffixIcon: Tooltip(
                  message: 'Your total monthly income',
                  child: Icon(Icons.info_outline, color: Colors.grey[600]),
                ),
                filled: true,
                fillColor: AppColors.background,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide(color: Colors.grey[300]!),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppColors.textPrimary, width: 2),
                ),
              ),
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              inputFormatters: [
                FilteringTextInputFormatter.allow(RegExp(r'^\d+\.?\d{0,2}')),
              ],
            ),
            const SizedBox(height: 16),

            // Current Balance
            TextFormField(
              controller: _currentBalanceController,
              decoration: InputDecoration(
                labelText: 'Current Balance',
                hintText: '0.00',
                prefixText: '\$ ',
                prefixStyle: const TextStyle(
                  fontFamily: AppTypography.fontBody,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
                suffixIcon: Tooltip(
                  message: 'Your current account balance',
                  child: Icon(Icons.info_outline, color: Colors.grey[600]),
                ),
                filled: true,
                fillColor: AppColors.background,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide(color: Colors.grey[300]!),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppColors.textPrimary, width: 2),
                ),
              ),
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              inputFormatters: [
                FilteringTextInputFormatter.allow(RegExp(r'^\d+\.?\d{0,2}')),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildCalculateButton() {
    return Container(
      height: 56,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: AppColors.textPrimary.withValues(alpha: 0.3),
            blurRadius: 12,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: ElevatedButton(
        onPressed: _isLoading ? null : _calculateInstallment,
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.textPrimary,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          elevation: 0,
          disabledBackgroundColor: Colors.grey[400],
        ),
        child: _isLoading
            ? const SizedBox(
                height: 24,
                width: 24,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                ),
              )
            : const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.calculate, size: 24),
                  SizedBox(width: 12),
                  Text(
                    'Calculate Risk',
                    style: TextStyle(
                      fontFamily: AppTypography.fontHeading,
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
      ),
    );
  }

  Widget _buildResultsSection() {
    final result = _calculationResult!;

    return FadeTransition(
      opacity: _fadeAnimation,
      child: SlideTransition(
        position: _slideAnimation,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _buildRiskLevelCard(result),
            const SizedBox(height: 16),
            _buildPaymentDetailsCard(result),
            if (result.dtiRatio != null) ...[
              const SizedBox(height: 16),
              _buildFinancialImpactCard(result),
            ],
            if (result.riskFactors.isNotEmpty) ...[
              const SizedBox(height: 16),
              _buildRiskFactorsCard(result),
            ],
            const SizedBox(height: 16),
            _buildPersonalizedMessageCard(result),
            if (result.alternativeRecommendation != null) ...[
              const SizedBox(height: 16),
              _buildAlternativeRecommendationCard(result.alternativeRecommendation!),
            ],
            if (result.warnings.isNotEmpty || result.tips.isNotEmpty) ...[
              const SizedBox(height: 16),
              _buildWarningsAndTipsCard(result),
            ],
            const SizedBox(height: 24),
            _buildActionButtons(result),
            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }

  Widget _buildRiskLevelCard(InstallmentCalculatorOutput result) {
    final riskColor = _getRiskColor(result.riskLevel);
    final riskIcon = _getRiskIcon(result.riskLevel);
    final riskMessage = _getRiskMessage(result.riskLevel);

    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: riskColor.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: riskColor, width: 2),
        boxShadow: [
          BoxShadow(
            color: riskColor.withValues(alpha: 0.2),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          Icon(riskIcon, size: 64, color: riskColor),
          const SizedBox(height: 12),
          Text(
            riskMessage,
            style: TextStyle(
              fontFamily: AppTypography.fontHeading,
              fontSize: 24,
              fontWeight: FontWeight.bold,
              color: riskColor,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            result.verdict,
            style: TextStyle(
              fontFamily: AppTypography.fontBody,
              fontSize: 16,
              color: riskColor.withValues(alpha: 0.9),
              height: 1.4,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            decoration: BoxDecoration(
              color: riskColor.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(
              'Risk Score: ${result.riskScore.toStringAsFixed(1)}%',
              style: TextStyle(
                fontFamily: AppTypography.fontBody,
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: riskColor,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPaymentDetailsCard(InstallmentCalculatorOutput result) {
    return _buildCard(
      title: 'Payment Details',
      icon: Icons.payment,
      child: Column(
        children: [
          _buildDetailRow(
            'Monthly Payment',
            '\$${result.monthlyPayment.toStringAsFixed(2)}',
            isHighlight: true,
          ),
          const Divider(height: 24),
          _buildDetailRow(
            'Total Interest',
            '\$${result.totalInterest.toStringAsFixed(2)}',
            valueColor: result.totalInterest > 0 ? AppColors.error : null,
          ),
          const SizedBox(height: 8),
          _buildDetailRow(
            'Total Cost',
            '\$${result.totalCost.toStringAsFixed(2)}',
          ),
          const SizedBox(height: 8),
          _buildDetailRow(
            'First Payment',
            '\$${result.firstPaymentAmount.toStringAsFixed(2)}',
          ),
          const SizedBox(height: 16),
          _buildPaymentScheduleSection(result),
        ],
      ),
    );
  }

  Widget _buildPaymentScheduleSection(InstallmentCalculatorOutput result) {
    return Theme(
      data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
      child: ExpansionTile(
        title: const Text(
          'Payment Schedule',
          style: TextStyle(
            fontFamily: AppTypography.fontHeading,
            fontWeight: FontWeight.w600,
            fontSize: 16,
            color: AppColors.textPrimary,
          ),
        ),
        children: [
          Container(
            constraints: const BoxConstraints(maxHeight: 300),
            child: SingleChildScrollView(
              child: Column(
                children: result.paymentSchedule.asMap().entries.map((entry) {
                  final index = entry.key;
                  final payment = entry.value;
                  final paymentNumber = payment['payment_number'] ?? index + 1;
                  final amount = payment['amount'] ?? result.monthlyPayment;
                  final principal = payment['principal'] ?? 0.0;
                  final interest = payment['interest'] ?? 0.0;

                  return Container(
                    margin: const EdgeInsets.symmetric(vertical: 4, horizontal: 8),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppColors.background,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.grey[300]!),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'Payment $paymentNumber',
                          style: const TextStyle(
                            fontFamily: AppTypography.fontBody,
                            fontWeight: FontWeight.w600,
                            color: AppColors.textPrimary,
                          ),
                        ),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            Text(
                              '\$${amount.toStringAsFixed(2)}',
                              style: const TextStyle(
                                fontFamily: AppTypography.fontBody,
                                fontWeight: FontWeight.bold,
                                fontSize: 16,
                                color: AppColors.textPrimary,
                              ),
                            ),
                            if ((interest > 0) == true)
                              Text(
                                'Interest: \$${interest.toStringAsFixed(2)}',
                                style: TextStyle(
                                  fontFamily: AppTypography.fontBody,
                                  fontSize: 12,
                                  color: Colors.grey[600],
                                ),
                              ),
                          ],
                        ),
                      ],
                    ),
                  );
                }).toList(),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFinancialImpactCard(InstallmentCalculatorOutput result) {
    return _buildCard(
      title: 'Financial Impact',
      icon: Icons.account_balance_wallet,
      child: Column(
        children: [
          if (result.dtiRatio != null) ...[
            _buildProgressIndicator(
              'Debt-to-Income Ratio',
              result.dtiRatio! / 100,
              '${result.dtiRatio!.toStringAsFixed(1)}%',
            ),
            const SizedBox(height: 16),
          ],
          if (result.paymentToIncomeRatio != null) ...[
            _buildProgressIndicator(
              'Payment as % of Income',
              result.paymentToIncomeRatio! / 100,
              '${result.paymentToIncomeRatio!.toStringAsFixed(1)}%',
            ),
            const SizedBox(height: 16),
          ],
          if (result.remainingMonthlyFunds != null) ...[
            _buildDetailRow(
              'Remaining Monthly Funds',
              '\$${result.remainingMonthlyFunds!.toStringAsFixed(2)}',
              valueColor: result.remainingMonthlyFunds! < 0 ? AppColors.error : AppColors.success,
            ),
          ],
          if (result.balanceAfterFirstPayment != null) ...[
            const SizedBox(height: 8),
            _buildDetailRow(
              'Balance After First Payment',
              '\$${result.balanceAfterFirstPayment!.toStringAsFixed(2)}',
              valueColor: result.balanceAfterFirstPayment! < 0 ? AppColors.error : null,
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildRiskFactorsCard(InstallmentCalculatorOutput result) {
    return _buildCard(
      title: 'Risk Factors',
      icon: Icons.warning_amber,
      child: Column(
        children: result.riskFactors.map((factor) {
          return Container(
            margin: const EdgeInsets.only(bottom: 12),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: _getSeverityColor(factor.severity).withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: _getSeverityColor(factor.severity).withValues(alpha: 0.3),
              ),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  _getSeverityIcon(factor.severity),
                  color: _getSeverityColor(factor.severity),
                  size: 20,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        factor.factor,
                        style: TextStyle(
                          fontFamily: AppTypography.fontHeading,
                          fontWeight: FontWeight.w600,
                          fontSize: 14,
                          color: _getSeverityColor(factor.severity),
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        factor.message,
                        style: const TextStyle(
                          fontFamily: AppTypography.fontBody,
                          fontSize: 13,
                          color: AppColors.textPrimary,
                          height: 1.3,
                        ),
                      ),
                      if (factor.stat != null) ...[
                        const SizedBox(height: 4),
                        Text(
                          factor.stat!,
                          style: TextStyle(
                            fontFamily: AppTypography.fontBody,
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: _getSeverityColor(factor.severity),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildPersonalizedMessageCard(InstallmentCalculatorOutput result) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [AppColors.secondary, AppColors.secondary],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: AppColors.secondary.withValues(alpha: 0.3),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.lightbulb,
            color: AppColors.textPrimary,
            size: 32,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Our Recommendation',
                  style: TextStyle(
                    fontFamily: AppTypography.fontHeading,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: AppColors.textPrimary,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  result.personalizedMessage,
                  style: const TextStyle(
                    fontFamily: AppTypography.fontBody,
                    fontSize: 15,
                    color: AppColors.textPrimary,
                    height: 1.5,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAlternativeRecommendationCard(AlternativeRecommendation alternative) {
    return _buildCard(
      title: alternative.title,
      icon: Icons.auto_awesome,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: AppColors.info.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              alternative.recommendationType.toUpperCase(),
              style: const TextStyle(
                fontFamily: AppTypography.fontBody,
                fontSize: 11,
                fontWeight: FontWeight.bold,
                color: AppColors.info,
                letterSpacing: 0.5,
              ),
            ),
          ),
          const SizedBox(height: 12),
          Text(
            alternative.description,
            style: const TextStyle(
              fontFamily: AppTypography.fontBody,
              fontSize: 14,
              color: AppColors.textPrimary,
              height: 1.5,
            ),
          ),
          if (alternative.savingsAmount != null) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.success.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  const Icon(Icons.savings, color: AppColors.success, size: 20),
                  const SizedBox(width: 8),
                  Text(
                    'Potential Savings: \$${alternative.savingsAmount!.toStringAsFixed(2)}',
                    style: const TextStyle(
                      fontFamily: AppTypography.fontBody,
                      fontWeight: FontWeight.bold,
                      color: AppColors.success,
                    ),
                  ),
                ],
              ),
            ),
          ],
          if (alternative.timeNeededDays != null) ...[
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.info.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  const Icon(Icons.schedule, color: AppColors.info, size: 20),
                  const SizedBox(width: 8),
                  Text(
                    'Time Needed: ${alternative.timeNeededDays} days',
                    style: const TextStyle(
                      fontFamily: AppTypography.fontBody,
                      fontWeight: FontWeight.bold,
                      color: AppColors.info,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildWarningsAndTipsCard(InstallmentCalculatorOutput result) {
    return _buildCard(
      title: 'Important Information',
      icon: Icons.info,
      child: Column(
        children: [
          if (result.warnings.isNotEmpty) ...[
            Theme(
              data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
              child: ExpansionTile(
                title: Row(
                  children: [
                    const Icon(Icons.warning, color: AppColors.warning, size: 20),
                    const SizedBox(width: 8),
                    const Text(
                      'Warnings',
                      style: TextStyle(
                        fontFamily: AppTypography.fontHeading,
                        fontWeight: FontWeight.w600,
                        fontSize: 16,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppColors.warning.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        '${result.warnings.length}',
                        style: const TextStyle(
                          fontFamily: AppTypography.fontBody,
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          color: AppColors.warning,
                        ),
                      ),
                    ),
                  ],
                ),
                initiallyExpanded: true,
                children: result.warnings.map((warning) {
                  return Container(
                    margin: const EdgeInsets.symmetric(vertical: 4, horizontal: 8),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppColors.warning.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.warning_amber, color: AppColors.warning, size: 18),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            warning,
                            style: const TextStyle(
                              fontFamily: AppTypography.fontBody,
                              fontSize: 13,
                              color: AppColors.textPrimary,
                              height: 1.4,
                            ),
                          ),
                        ),
                      ],
                    ),
                  );
                }).toList(),
              ),
            ),
          ],
          if (result.tips.isNotEmpty) ...[
            if (result.warnings.isNotEmpty) const SizedBox(height: 8),
            Theme(
              data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
              child: ExpansionTile(
                title: Row(
                  children: [
                    const Icon(Icons.tips_and_updates, color: AppColors.success, size: 20),
                    const SizedBox(width: 8),
                    const Text(
                      'Tips',
                      style: TextStyle(
                        fontFamily: AppTypography.fontHeading,
                        fontWeight: FontWeight.w600,
                        fontSize: 16,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppColors.success.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        '${result.tips.length}',
                        style: const TextStyle(
                          fontFamily: AppTypography.fontBody,
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          color: AppColors.success,
                        ),
                      ),
                    ),
                  ],
                ),
                children: result.tips.map((tip) {
                  return Container(
                    margin: const EdgeInsets.symmetric(vertical: 4, horizontal: 8),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppColors.success.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.check_circle, color: AppColors.success, size: 18),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            tip,
                            style: const TextStyle(
                              fontFamily: AppTypography.fontBody,
                              fontSize: 13,
                              color: AppColors.textPrimary,
                              height: 1.4,
                            ),
                          ),
                        ),
                      ],
                    ),
                  );
                }).toList(),
              ),
            ),
          ],
          if (result.statistics.isNotEmpty) ...[
            const SizedBox(height: 12),
            ...result.statistics.map((stat) {
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  children: [
                    const Icon(Icons.show_chart, color: AppColors.info, size: 16),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        stat,
                        style: const TextStyle(
                          fontFamily: AppTypography.fontBody,
                          fontSize: 12,
                          color: AppColors.textPrimary,
                        ),
                      ),
                    ),
                  ],
                ),
              );
            }),
          ],
        ],
      ),
    );
  }

  Widget _buildActionButtons(InstallmentCalculatorOutput result) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (result.shouldProceed) ...[
          Container(
            height: 56,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(
                  color: AppColors.success.withValues(alpha: 0.3),
                  blurRadius: 12,
                  offset: const Offset(0, 6),
                ),
              ],
            ),
            child: ElevatedButton.icon(
              onPressed: () {
                // Navigate to installment creation screen
                // TODO: Implement navigation
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Installment creation coming soon!'),
                    behavior: SnackBarBehavior.floating,
                  ),
                );
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.success,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
                elevation: 0,
              ),
              icon: const Icon(Icons.add_card),
              label: const Text(
                'Create Installment Plan',
                style: TextStyle(
                  fontFamily: AppTypography.fontHeading,
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
          const SizedBox(height: 12),
        ],
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () {
                  // Show help dialog or navigate to documentation
                  showDialog(
                    context: context,
                    builder: (context) => AlertDialog(
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16),
                      ),
                      title: const Row(
                        children: [
                          Icon(Icons.help, color: AppColors.textPrimary),
                          SizedBox(width: 8),
                          Text('How It Works'),
                        ],
                      ),
                      content: const SingleChildScrollView(
                        child: Text(
                          'Our smart algorithm analyzes your financial situation considering:\n\n'
                          '• Your monthly income and expenses\n'
                          '• Current debt obligations\n'
                          '• Debt-to-income ratio\n'
                          '• Available cash balance\n'
                          '• Interest costs\n\n'
                          'We use industry standards and behavioral finance principles '
                          'to provide personalized recommendations.',
                          style: TextStyle(
                            fontFamily: AppTypography.fontBody,
                            height: 1.5,
                          ),
                        ),
                      ),
                      actions: [
                        TextButton(
                          onPressed: () => Navigator.pop(context),
                          child: const Text('Got it'),
                        ),
                      ],
                    ),
                  );
                },
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppColors.textPrimary,
                  side: const BorderSide(color: AppColors.textPrimary),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                  padding: const EdgeInsets.symmetric(vertical: 16),
                ),
                icon: const Icon(Icons.help_outline),
                label: const Text(
                  'Learn More',
                  style: TextStyle(
                    fontFamily: AppTypography.fontHeading,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () {
                  setState(() {
                    _showResults = false;
                    _calculationResult = null;
                  });
                  _animationController.reset();

                  // Scroll to top
                  if (_scrollController.hasClients) {
                    _scrollController.animateTo(
                      0,
                      duration: const Duration(milliseconds: 500),
                      curve: Curves.easeOut,
                    );
                  }
                },
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppColors.textPrimary,
                  side: const BorderSide(color: AppColors.textPrimary),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                  padding: const EdgeInsets.symmetric(vertical: 16),
                ),
                icon: const Icon(Icons.refresh),
                label: const Text(
                  'Calculate Again',
                  style: TextStyle(
                    fontFamily: AppTypography.fontHeading,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }

  // Helper widgets

  Widget _buildCard({
    required String title,
    required IconData icon,
    required Widget child,
  }) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: AppColors.textPrimary, size: 24),
              const SizedBox(width: 8),
              Text(
                title,
                style: const TextStyle(
                  fontFamily: AppTypography.fontHeading,
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          child,
        ],
      ),
    );
  }

  Widget _buildDetailRow(
    String label,
    String value, {
    bool isHighlight = false,
    Color? valueColor,
  }) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: TextStyle(
            fontFamily: AppTypography.fontBody,
            fontSize: isHighlight ? 16 : 14,
            fontWeight: isHighlight ? FontWeight.w600 : FontWeight.w500,
            color: AppColors.textPrimary,
          ),
        ),
        Text(
          value,
          style: TextStyle(
            fontFamily: AppTypography.fontBody,
            fontSize: isHighlight ? 20 : 16,
            fontWeight: FontWeight.bold,
            color: valueColor ?? AppColors.textPrimary,
          ),
        ),
      ],
    );
  }

  Widget _buildProgressIndicator(String label, double value, String displayValue) {
    final percentage = (value * 100).clamp(0.0, 100.0);
    Color progressColor;

    if (percentage <= 30) {
      progressColor = AppColors.success;
    } else if (percentage <= 50) {
      progressColor = AppColors.secondary;
    } else if (percentage <= 70) {
      progressColor = AppColors.warning;
    } else {
      progressColor = AppColors.error;
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              label,
              style: const TextStyle(
                fontFamily: AppTypography.fontBody,
                fontSize: 14,
                fontWeight: FontWeight.w500,
                color: AppColors.textPrimary,
              ),
            ),
            Text(
              displayValue,
              style: TextStyle(
                fontFamily: AppTypography.fontBody,
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: progressColor,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: LinearProgressIndicator(
            value: value.clamp(0.0, 1.0),
            minHeight: 12,
            backgroundColor: Colors.grey[200],
            valueColor: AlwaysStoppedAnimation<Color>(progressColor),
          ),
        ),
      ],
    );
  }

  IconData _getCategoryIcon(InstallmentCategory category) {
    switch (category) {
      case InstallmentCategory.electronics:
        return Icons.devices;
      case InstallmentCategory.clothing:
        return Icons.checkroom;
      case InstallmentCategory.furniture:
        return Icons.chair;
      case InstallmentCategory.travel:
        return Icons.flight;
      case InstallmentCategory.education:
        return Icons.school;
      case InstallmentCategory.health:
        return Icons.health_and_safety;
      case InstallmentCategory.groceries:
        return Icons.shopping_cart;
      case InstallmentCategory.utilities:
        return Icons.electrical_services;
      case InstallmentCategory.other:
        return Icons.category;
    }
  }

  Color _getSeverityColor(String severity) {
    switch (severity.toLowerCase()) {
      case 'high':
      case 'critical':
        return AppColors.error;
      case 'medium':
      case 'moderate':
        return AppColors.warning;
      case 'low':
        return AppColors.secondary;
      default:
        return AppColors.info;
    }
  }

  IconData _getSeverityIcon(String severity) {
    switch (severity.toLowerCase()) {
      case 'high':
      case 'critical':
        return Icons.error;
      case 'medium':
      case 'moderate':
        return Icons.warning;
      case 'low':
        return Icons.info;
      default:
        return Icons.help_outline;
    }
  }
}

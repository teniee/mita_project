import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../models/installment_models.dart';
import '../providers/installments_provider.dart';
import '../services/localization_service.dart';

class InstallmentsScreen extends StatefulWidget {
  const InstallmentsScreen({super.key});

  @override
  State<InstallmentsScreen> createState() => _InstallmentsScreenState();
}

class _InstallmentsScreenState extends State<InstallmentsScreen> {
  final LocalizationService _localizationService = LocalizationService.instance;
  bool _showMonthlyView = true;

  @override
  void initState() {
    super.initState();
    // Initialize provider and load installments
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<InstallmentsProvider>().loadInstallments();
    });
  }

  Future<void> _refreshInstallments() async {
    await context.read<InstallmentsProvider>().refresh();
  }

  Future<void> _handleMarkPaymentMade(Installment installment) async {
    final provider = context.read<InstallmentsProvider>();
    final success = await provider.markPaymentMade(installment.id);

    if (mounted) {
      if (success) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(provider.successMessage ?? 'Payment marked as made')),
        );
        provider.clearSuccess();
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(provider.errorMessage ?? 'Failed to update payment')),
        );
        provider.clearError();
      }
    }
  }

  Future<void> _handleCancelInstallment(Installment installment) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Cancel Installment'),
        content: Text('Are you sure you want to cancel "${installment.itemName}"?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Confirm'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      final provider = context.read<InstallmentsProvider>();
      final success = await provider.cancelInstallment(installment.id);

      if (mounted) {
        if (success) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(provider.successMessage ?? 'Installment cancelled')),
          );
          provider.clearSuccess();
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(provider.errorMessage ?? 'Failed to cancel installment')),
          );
          provider.clearError();
        }
      }
    }
  }

  Future<void> _handleDeleteInstallment(Installment installment) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Installment'),
        content: Text(
          'Are you sure you want to permanently delete "${installment.itemName}"? This action cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      final provider = context.read<InstallmentsProvider>();
      final success = await provider.deleteInstallment(installment.id);

      if (mounted) {
        if (success) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(provider.successMessage ?? 'Installment deleted')),
          );
          provider.clearSuccess();
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(provider.errorMessage ?? 'Failed to delete installment')),
          );
          provider.clearError();
        }
      }
    }
  }

  Color _getCategoryColor(InstallmentCategory category) {
    switch (category) {
      case InstallmentCategory.electronics:
        return AppColors.info;
      case InstallmentCategory.clothing:
        return AppColors.warning;
      case InstallmentCategory.furniture:
        return AppColors.categoryEntertainment;
      case InstallmentCategory.travel:
        return AppColors.chart7;
      case InstallmentCategory.education:
        return AppColors.categoryEducation;
      case InstallmentCategory.health:
        return AppColors.error;
      case InstallmentCategory.groceries:
        return AppColors.success;
      case InstallmentCategory.utilities:
        return AppColors.categoryUtilities;
      case InstallmentCategory.other:
        return AppColors.categoryOther;
    }
  }

  IconData _getCategoryIcon(InstallmentCategory category) {
    switch (category) {
      case InstallmentCategory.electronics:
        return Icons.devices;
      case InstallmentCategory.clothing:
        return Icons.shopping_bag;
      case InstallmentCategory.furniture:
        return Icons.chair;
      case InstallmentCategory.travel:
        return Icons.flight_takeoff;
      case InstallmentCategory.education:
        return Icons.school;
      case InstallmentCategory.health:
        return Icons.favorite;
      case InstallmentCategory.groceries:
        return Icons.shopping_cart;
      case InstallmentCategory.utilities:
        return Icons.home;
      case InstallmentCategory.other:
        return Icons.category;
    }
  }

  Color _getStatusColor(InstallmentStatus status) {
    switch (status) {
      case InstallmentStatus.active:
        return AppColors.secondary;
      case InstallmentStatus.completed:
        return AppColors.successLight;
      case InstallmentStatus.overdue:
        return AppColors.danger;
      case InstallmentStatus.cancelled:
        return Colors.grey;
    }
  }

  Color _getLoadIndicatorColor(double load) {
    if (load < 0.5) return AppColors.success; // Safe
    if (load < 0.7) return AppColors.secondary; // Moderate
    if (load < 0.9) return AppColors.warning; // High
    return AppColors.danger; // Critical
  }

  String _getLoadIndicatorLabel(double load) {
    if (load < 0.5) return 'Safe';
    if (load < 0.7) return 'Moderate';
    if (load < 0.9) return 'High';
    return 'Critical';
  }

  @override
  Widget build(BuildContext context) {
    // Use context.watch for reactive state - automatically rebuilds when provider changes
    final provider = context.watch<InstallmentsProvider>();
    final isLoading = provider.isLoading;
    final errorMessage = provider.errorMessage;
    final currentSummary = provider.summary;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text(
          'My Installments',
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
      body: RefreshIndicator(
        onRefresh: _refreshInstallments,
        color: AppColors.textPrimary,
        child: isLoading && currentSummary == null
            ? const Center(child: _ShimmerLoader())
            : errorMessage != null && currentSummary == null
                ? _buildErrorState(errorMessage)
                : _buildMainContent(provider),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () {
          Navigator.pushNamed(context, '/installment-calculator');
        },
        icon: const Icon(Icons.calculate),
        label: const Text(
          'Can I Afford?',
          style: TextStyle(
            fontFamily: AppTypography.fontHeading,
            fontWeight: FontWeight.bold,
          ),
        ),
        backgroundColor: AppColors.textPrimary,
        foregroundColor: Colors.white,
        elevation: 4,
      ),
    );
  }

  Widget _buildErrorState(String? errorMessage) {
    return SingleChildScrollView(
      physics: const AlwaysScrollableScrollPhysics(),
      child: SizedBox(
        height: MediaQuery.of(context).size.height - 200,
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(
                Icons.error_outline,
                size: 64,
                color: AppColors.textPrimary,
              ),
              const SizedBox(height: 16),
              Text(
                errorMessage ?? 'Something went wrong',
                style: const TextStyle(
                  fontSize: 16,
                  fontFamily: AppTypography.fontHeading,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: _refreshInstallments,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.textPrimary,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 32,
                    vertical: 12,
                  ),
                ),
                child: const Text(
                  'Retry',
                  style: TextStyle(
                    color: Colors.white,
                    fontFamily: AppTypography.fontHeading,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildMainContent(InstallmentsProvider provider) {
    final installments = provider.filteredInstallments;
    final currentSummary = provider.summary;
    final isEmpty = installments.isEmpty && (currentSummary?.totalInstallments ?? 0) == 0;

    if (isEmpty) {
      return _buildEmptyState();
    }

    return SingleChildScrollView(
      child: Column(
        children: [
          // Summary Stats Card
          if (currentSummary != null) _buildSummaryCard(currentSummary),

          // Filter Tabs
          _buildFilterTabs(provider),

          // Installments List
          if (installments.isEmpty)
            Padding(
              padding: const EdgeInsets.all(32),
              child: Column(
                children: [
                  Icon(
                    Icons.inbox_outlined,
                    size: 64,
                    color: Colors.grey[400],
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'No installments',
                    style: TextStyle(
                      fontSize: 16,
                      fontFamily: AppTypography.fontHeading,
                      fontWeight: FontWeight.w600,
                      color: Colors.grey[600],
                    ),
                  ),
                ],
              ),
            )
          else
            ListView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              padding: const EdgeInsets.all(16),
              itemCount: installments.length,
              itemBuilder: (context, index) {
                return _buildInstallmentCard(installments[index]);
              },
            ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return SingleChildScrollView(
      physics: const AlwaysScrollableScrollPhysics(),
      child: SizedBox(
        height: MediaQuery.of(context).size.height - 200,
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 120,
                height: 120,
                decoration: BoxDecoration(
                  color: AppColors.textPrimary.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(60),
                ),
                child: const Icon(
                  Icons.credit_card,
                  size: 60,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 24),
              const Text(
                'No installments yet',
                style: TextStyle(
                  fontSize: 20,
                  fontFamily: AppTypography.fontHeading,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 8),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: Text(
                  'Start by using our calculator to see if you can afford an installment plan',
                  style: TextStyle(
                    fontSize: 14,
                    fontFamily: AppTypography.fontBody,
                    color: Colors.grey[600],
                  ),
                  textAlign: TextAlign.center,
                ),
              ),
              const SizedBox(height: 32),
              ElevatedButton.icon(
                onPressed: () {
                  Navigator.pushNamed(context, '/installment-calculator');
                },
                icon: const Icon(Icons.calculate),
                label: const Text(
                  'Start Calculator',
                  style: TextStyle(
                    fontFamily: AppTypography.fontHeading,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.textPrimary,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 32,
                    vertical: 16,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSummaryCard(InstallmentsSummary summary) {
    final loadColor = _getLoadIndicatorColor(summary.currentInstallmentLoad);
    final loadLabel = _getLoadIndicatorLabel(summary.currentInstallmentLoad);

    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Main Stats Row
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${summary.totalActive} Active',
                    style: const TextStyle(
                      fontSize: 16,
                      fontFamily: AppTypography.fontHeading,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    _localizationService.formatCurrency(
                      summary.totalMonthlyPayment,
                    ),
                    style: const TextStyle(
                      fontSize: 18,
                      fontFamily: AppTypography.fontHeading,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 2),
                  const Text(
                    'Monthly Payment',
                    style: TextStyle(
                      fontSize: 12,
                      fontFamily: AppTypography.fontBody,
                      color: Colors.grey,
                    ),
                  ),
                ],
              ),
              // Load Indicator
              Column(
                children: [
                  Container(
                    width: 80,
                    height: 80,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: loadColor.withOpacity(0.1),
                    ),
                    child: Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text(
                            '${(summary.currentInstallmentLoad * 100).toStringAsFixed(0)}%',
                            style: TextStyle(
                              fontSize: 18,
                              fontFamily: AppTypography.fontHeading,
                              fontWeight: FontWeight.bold,
                              color: loadColor,
                            ),
                          ),
                          Text(
                            loadLabel,
                            style: TextStyle(
                              fontSize: 11,
                              fontFamily: AppTypography.fontBody,
                              color: loadColor,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Next Payment Info
          if (summary.nextPaymentDate != null && summary.nextPaymentAmount != null)
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.secondary.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: AppColors.secondary,
                  width: 1,
                ),
              ),
              child: Row(
                children: [
                  const Icon(
                    Icons.calendar_today,
                    size: 16,
                    color: AppColors.secondary,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Next Payment',
                          style: TextStyle(
                            fontSize: 12,
                            fontFamily: AppTypography.fontBody,
                            color: Colors.grey,
                          ),
                        ),
                        Text(
                          '${DateFormat.MMMMd().format(summary.nextPaymentDate!)} • ${_localizationService.formatCurrency(summary.nextPaymentAmount!)}',
                          style: const TextStyle(
                            fontSize: 14,
                            fontFamily: AppTypography.fontHeading,
                            fontWeight: FontWeight.w600,
                            color: AppColors.textPrimary,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildFilterTabs(InstallmentsProvider provider) {
    final tabs = [
      (null, 'All'),
      (InstallmentStatus.active, 'Active'),
      (InstallmentStatus.completed, 'Completed'),
      (InstallmentStatus.overdue, 'Overdue'),
    ];

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: tabs.map((tab) {
          final (status, label) = tab;
          final count = provider.getTabCount(status);
          final isSelected = provider.selectedFilter == status;

          return Padding(
            padding: const EdgeInsets.only(right: 8),
            child: FilterChip(
              label: Text(
                '$label ${count > 0 ? '($count)' : ''}',
                style: TextStyle(
                  fontFamily: AppTypography.fontHeading,
                  fontWeight: FontWeight.w600,
                  color: isSelected ? Colors.white : AppColors.textPrimary,
                  fontSize: 14,
                ),
              ),
              selected: isSelected,
              onSelected: (selected) {
                provider.setFilter(selected ? status : null);
              },
              backgroundColor: Colors.transparent,
              selectedColor: AppColors.textPrimary,
              side: BorderSide(
                color: isSelected
                    ? AppColors.textPrimary
                    : Colors.grey[300]!,
              ),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(20),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildInstallmentCard(Installment installment) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      child: GestureDetector(
        onTap: () {
          _showInstallmentDetails(installment);
        },
        child: Card(
          elevation: 2,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          child: Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              color: Colors.white,
            ),
            child: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Header
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Container(
                            width: 48,
                            height: 48,
                            decoration: BoxDecoration(
                              color: _getCategoryColor(installment.category),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Icon(
                              _getCategoryIcon(installment.category),
                              color: Colors.white,
                              size: 24,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  installment.itemName,
                                  style: const TextStyle(
                                    fontSize: 16,
                                    fontFamily: AppTypography.fontHeading,
                                    fontWeight: FontWeight.bold,
                                    color: AppColors.textPrimary,
                                  ),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                                const SizedBox(height: 4),
                                Row(
                                  children: [
                                    Text(
                                      installment.category.displayName,
                                      style: TextStyle(
                                        fontSize: 12,
                                        fontFamily: AppTypography.fontBody,
                                        color: Colors.grey[600],
                                      ),
                                    ),
                                    const SizedBox(width: 8),
                                    Container(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 8,
                                        vertical: 2,
                                      ),
                                      decoration: BoxDecoration(
                                        color:
                                            _getStatusColor(installment.status)
                                                .withOpacity(0.2),
                                        borderRadius:
                                            BorderRadius.circular(6),
                                      ),
                                      child: Text(
                                        installment.status.displayName,
                                        style: TextStyle(
                                          fontSize: 10,
                                          fontFamily: AppTypography.fontBody,
                                          fontWeight: FontWeight.w600,
                                          color: _getStatusColor(
                                            installment.status,
                                          ),
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                          // More menu
                          PopupMenuButton(
                            itemBuilder: (context) => [
                              PopupMenuItem(
                                child: const Row(
                                  children: [
                                    Icon(Icons.info_outline, size: 18),
                                    SizedBox(width: 8),
                                    Text('View Details'),
                                  ],
                                ),
                                onTap: () {
                                  _showInstallmentDetails(installment);
                                },
                              ),
                              if (installment.status.isActive)
                                PopupMenuItem(
                                  child: const Row(
                                    children: [
                                      Icon(Icons.check_circle_outline,
                                          size: 18),
                                      SizedBox(width: 8),
                                      Text('Mark Payment Made'),
                                    ],
                                  ),
                                  onTap: () {
                                    _handleMarkPaymentMade(installment);
                                  },
                                ),
                              if (installment.status.isActive)
                                PopupMenuItem(
                                  child: const Row(
                                    children: [
                                      Icon(Icons.cancel_outlined, size: 18),
                                      SizedBox(width: 8),
                                      Text('Cancel'),
                                    ],
                                  ),
                                  onTap: () {
                                    _handleCancelInstallment(installment);
                                  },
                                ),
                              PopupMenuItem(
                                child: const Row(
                                  children: [
                                    Icon(Icons.delete_outline, size: 18),
                                    SizedBox(width: 8),
                                    Text('Delete'),
                                  ],
                                ),
                                onTap: () {
                                  _handleDeleteInstallment(installment);
                                },
                              ),
                            ],
                            icon: const Icon(Icons.more_vert),
                            color: AppColors.textPrimary,
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),

                      // Progress Bar
                      ClipRRect(
                        borderRadius: BorderRadius.circular(8),
                        child: LinearProgressIndicator(
                          value: installment.progressPercentage / 100,
                          backgroundColor: Colors.grey[200],
                          valueColor: AlwaysStoppedAnimation(
                            _getStatusColor(installment.status),
                          ),
                          minHeight: 8,
                        ),
                      ),
                      const SizedBox(height: 8),

                      // Progress Info
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            '${installment.paymentsMade}/${installment.totalPayments} payments',
                            style: TextStyle(
                              fontSize: 12,
                              fontFamily: AppTypography.fontBody,
                              color: Colors.grey[600],
                            ),
                          ),
                          Text(
                            '${installment.progressPercentage.toStringAsFixed(0)}%',
                            style: const TextStyle(
                              fontSize: 12,
                              fontFamily: AppTypography.fontHeading,
                              fontWeight: FontWeight.w600,
                              color: AppColors.textPrimary,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),

                      // Amount Info
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Monthly Payment',
                                style: TextStyle(
                                  fontSize: 11,
                                  fontFamily: AppTypography.fontBody,
                                  color: Colors.grey[600],
                                ),
                              ),
                              Text(
                                _localizationService.formatCurrency(
                                  installment.paymentAmount,
                                ),
                                style: const TextStyle(
                                  fontSize: 14,
                                  fontFamily: AppTypography.fontHeading,
                                  fontWeight: FontWeight.bold,
                                  color: AppColors.textPrimary,
                                ),
                              ),
                            ],
                          ),
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.end,
                            children: [
                              Text(
                                'Next Payment',
                                style: TextStyle(
                                  fontSize: 11,
                                  fontFamily: AppTypography.fontBody,
                                  color: Colors.grey[600],
                                ),
                              ),
                              Text(
                                DateFormat.MMMMd()
                                    .format(installment.nextPaymentDate),
                                style: const TextStyle(
                                  fontSize: 14,
                                  fontFamily: AppTypography.fontHeading,
                                  fontWeight: FontWeight.bold,
                                  color: AppColors.textPrimary,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),

                      // Amount Summary
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            'Total: ${_localizationService.formatCurrency(installment.totalAmount)}',
                            style: TextStyle(
                              fontSize: 12,
                              fontFamily: AppTypography.fontBody,
                              color: Colors.grey[600],
                            ),
                          ),
                          Text(
                            'Paid: ${_localizationService.formatCurrency(installment.totalPaid)}',
                            style: TextStyle(
                              fontSize: 12,
                              fontFamily: AppTypography.fontBody,
                              fontWeight: FontWeight.w600,
                              color: Colors.grey[600],
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),

                // Quick Action Buttons
                if (installment.status.isActive)
                  Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 12,
                    ),
                    child: Row(
                      children: [
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: () {
                              _handleMarkPaymentMade(installment);
                            },
                            icon: const Icon(Icons.check, size: 18),
                            label: const Text(
                              'Mark Paid',
                              style: TextStyle(fontFamily: AppTypography.fontHeading),
                            ),
                            style: OutlinedButton.styleFrom(
                              foregroundColor: AppColors.successLight,
                              side: const BorderSide(
                                color: AppColors.successLight,
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: () {
                              _handleCancelInstallment(installment);
                            },
                            icon: const Icon(Icons.close, size: 18),
                            label: const Text(
                              'Cancel',
                              style: TextStyle(fontFamily: AppTypography.fontHeading),
                            ),
                            style: OutlinedButton.styleFrom(
                              foregroundColor: Colors.red,
                              side: const BorderSide(color: Colors.red),
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
      ),
    );
  }

  void _showInstallmentDetails(Installment installment) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (context) => _buildDetailsSheet(installment),
    );
  }

  Widget _buildDetailsSheet(Installment installment) {
    return Container(
      padding: EdgeInsets.only(
        left: 24,
        right: 24,
        top: 24,
        bottom: MediaQuery.of(context).viewInsets.bottom + 24,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                installment.itemName,
                style: const TextStyle(
                  fontSize: 20,
                  fontFamily: AppTypography.fontHeading,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  color: _getStatusColor(installment.status).withOpacity(0.2),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  installment.status.displayName,
                  style: TextStyle(
                    fontSize: 12,
                    fontFamily: AppTypography.fontBody,
                    fontWeight: FontWeight.w600,
                    color: _getStatusColor(installment.status),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),

          // Details Grid
          _buildDetailRow('Category', installment.category.displayName),
          const SizedBox(height: 16),
          _buildDetailRow(
            'Total Amount',
            _localizationService.formatCurrency(installment.totalAmount),
          ),
          const SizedBox(height: 16),
          _buildDetailRow(
            'Monthly Payment',
            _localizationService.formatCurrency(installment.paymentAmount),
          ),
          const SizedBox(height: 16),
          _buildDetailRow(
            'Interest Rate',
            '${installment.interestRate.toStringAsFixed(2)}%',
          ),
          const SizedBox(height: 16),
          _buildDetailRow(
            'Total Payments',
            '${installment.paymentsMade} / ${installment.totalPayments}',
          ),
          const SizedBox(height: 16),
          _buildDetailRow(
            'Next Payment Date',
            DateFormat.yMMMMd().format(installment.nextPaymentDate),
          ),
          const SizedBox(height: 16),
          _buildDetailRow(
            'Final Payment Date',
            DateFormat.yMMMMd().format(installment.finalPaymentDate),
          ),
          const SizedBox(height: 16),
          _buildDetailRow(
            'Total Paid',
            _localizationService.formatCurrency(installment.totalPaid),
          ),
          const SizedBox(height: 16),
          _buildDetailRow(
            'Remaining Balance',
            _localizationService.formatCurrency(installment.remainingBalance),
          ),

          if (installment.notes != null && installment.notes!.isNotEmpty)
            ...[
              const SizedBox(height: 24),
              const Text(
                'Notes',
                style: TextStyle(
                  fontSize: 14,
                  fontFamily: AppTypography.fontHeading,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                installment.notes!,
                style: TextStyle(
                  fontSize: 13,
                  fontFamily: AppTypography.fontBody,
                  color: Colors.grey[700],
                ),
              ),
            ],

          const SizedBox(height: 24),

          // Close Button
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: () => Navigator.pop(context),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.textPrimary,
                padding: const EdgeInsets.symmetric(vertical: 12),
              ),
              child: const Text(
                'Close',
                style: TextStyle(
                  color: Colors.white,
                  fontFamily: AppTypography.fontHeading,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDetailRow(String label, String value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: TextStyle(
            fontSize: 13,
            fontFamily: AppTypography.fontBody,
            color: Colors.grey[600],
          ),
        ),
        Text(
          value,
          style: const TextStyle(
            fontSize: 13,
            fontFamily: AppTypography.fontHeading,
            fontWeight: FontWeight.w600,
            color: AppColors.textPrimary,
          ),
        ),
      ],
    );
  }
}

// Shimmer Loading Widget
class _ShimmerLoader extends StatefulWidget {
  const _ShimmerLoader();

  @override
  State<_ShimmerLoader> createState() => _ShimmerLoaderState();
}

class _ShimmerLoaderState extends State<_ShimmerLoader>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _animation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    )..repeat();
    _animation = Tween<double>(begin: -1, end: 2).animate(_controller);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Summary Card Shimmer
        Container(
          margin: const EdgeInsets.all(16),
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.05),
                blurRadius: 10,
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _ShimmerBar(animation: _animation, width: 150),
              const SizedBox(height: 12),
              _ShimmerBar(animation: _animation, width: 200),
              const SizedBox(height: 16),
              _ShimmerBar(animation: _animation, width: double.infinity),
            ],
          ),
        ),
        // Tabs Shimmer
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(
            children: [
              _ShimmerBar(animation: _animation, width: 70),
              const SizedBox(width: 8),
              _ShimmerBar(animation: _animation, width: 70),
              const SizedBox(width: 8),
              _ShimmerBar(animation: _animation, width: 70),
            ],
          ),
        ),
        // Cards Shimmer
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: 3,
            itemBuilder: (context, index) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Container(
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                ),
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _ShimmerBar(animation: _animation, width: 200),
                    const SizedBox(height: 12),
                    _ShimmerBar(animation: _animation, width: double.infinity),
                    const SizedBox(height: 12),
                    _ShimmerBar(animation: _animation, width: 150),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _ShimmerBar extends StatelessWidget {
  final Animation<double> animation;
  final double width;

  const _ShimmerBar({
    required this.animation,
    required this.width,
  });

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: animation,
      builder: (context, child) {
        return ShaderMask(
          shaderCallback: (bounds) {
            return LinearGradient(
              begin: Alignment.centerLeft,
              end: Alignment.centerRight,
              colors: const [
                Colors.grey,
                Colors.white30,
                Colors.grey,
              ],
              stops: [
                animation.value - 1,
                animation.value,
                animation.value + 1,
              ],
            ).createShader(bounds);
          },
          child: Container(
            width: width,
            height: 12,
            decoration: BoxDecoration(
              color: Colors.grey[300],
              borderRadius: BorderRadius.circular(6),
            ),
          ),
        );
      },
    );
  }
}

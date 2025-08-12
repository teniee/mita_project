import 'package:flutter/material.dart';
import '../l10n/generated/app_localizations.dart';
import '../utils/financial_formatters.dart';
import '../services/text_direction_service.dart';

/// Example screen demonstrating proper i18n usage in MITA
/// This serves as a template for developers implementing new screens
class I18nExampleScreen extends StatefulWidget {
  const I18nExampleScreen({super.key});

  @override
  State<I18nExampleScreen> createState() => _I18nExampleScreenState();
}

class _I18nExampleScreenState extends State<I18nExampleScreen> {
  final double _sampleBudget = 1000.0;
  final double _sampleSpent = 750.0;
  String _selectedCategory = 'food';

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final textDir = TextDirectionService.instance;

    return Scaffold(
      // Proper app bar with RTL support
      appBar: textDir.createDirectionalAppBar(
        title: Text(l10n.appTitle),
        leading: IconButton(
          icon: Icon(textDir.backIcon),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      
      body: SingleChildScrollView(
        padding: textDir.getDirectionalPadding(
          start: 16.0,
          end: 16.0,
          top: 16.0,
          bottom: 16.0,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Localized title
            Text(
              l10n.dailyBudget,
              style: theme.textTheme.headlineMedium,
              textAlign: textDir.getTextAlign(),
            ),
            
            const SizedBox(height: 24),
            
            // Currency formatting examples
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      l10n.budget,
                      style: theme.textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    
                    // Using FinancialFormatters for proper locale formatting
                    Text(
                      FinancialFormatters.formatCurrency(context, _sampleBudget),
                      style: theme.textTheme.headlineSmall?.copyWith(
                        color: theme.colorScheme.primary,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    
                    const SizedBox(height: 16),
                    
                    // Spent amount
                    textDir.createDirectionalRow(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(l10n.spent),
                        Text(
                          FinancialFormatters.formatCurrency(context, _sampleSpent),
                          style: TextStyle(
                            color: FinancialFormatters.getAmountColor(
                              context, 
                              _sampleSpent, 
                              isExpense: true,
                            ),
                          ),
                        ),
                      ],
                    ),
                    
                    const SizedBox(height: 8),
                    
                    // Remaining amount using extension method
                    textDir.createDirectionalRow(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(l10n.remaining),
                        Text(
                          context.formatMoney(_sampleBudget - _sampleSpent),
                          style: const TextStyle(
                            color: Colors.green,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            
            const SizedBox(height: 24),
            
            // Budget status with localized messaging
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Budget Status',
                      style: theme.textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: FinancialFormatters.getBudgetStatusColor(
                          context, 
                          _sampleSpent, 
                          _sampleBudget,
                        ).withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(
                          color: FinancialFormatters.getBudgetStatusColor(
                            context, 
                            _sampleSpent, 
                            _sampleBudget,
                          ),
                          width: 1,
                        ),
                      ),
                      child: Text(
                        FinancialFormatters.formatBudgetStatus(
                          context, 
                          _sampleSpent, 
                          _sampleBudget,
                        ),
                        style: TextStyle(
                          color: FinancialFormatters.getBudgetStatusColor(
                            context, 
                            _sampleSpent, 
                            _sampleBudget,
                          ),
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                    
                    const SizedBox(height: 16),
                    
                    // Progress indicator
                    LinearProgressIndicator(
                      value: (_sampleSpent / _sampleBudget).clamp(0.0, 1.0),
                      backgroundColor: theme.colorScheme.surfaceContainerHighest,
                      valueColor: AlwaysStoppedAnimation<Color>(
                        FinancialFormatters.getBudgetStatusColor(
                          context, 
                          _sampleSpent, 
                          _sampleBudget,
                        ),
                      ),
                    ),
                    
                    const SizedBox(height: 8),
                    
                    Text(
                      FinancialFormatters.formatBudgetProgress(
                        context, 
                        _sampleSpent, 
                        _sampleBudget,
                      ),
                      style: theme.textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            ),
            
            const SizedBox(height: 24),
            
            // Category selection with localized names
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      l10n.category,
                      style: theme.textTheme.titleMedium,
                    ),
                    const SizedBox(height: 12),
                    
                    Wrap(
                      spacing: 8.0,
                      children: [
                        'food',
                        'transportation', 
                        'entertainment',
                        'shopping',
                        'utilities',
                        'health',
                        'other',
                      ].map((category) {
                        final isSelected = category == _selectedCategory;
                        return FilterChip(
                          label: Text(context.formatExpenseCategory(category)),
                          selected: isSelected,
                          onSelected: (selected) {
                            setState(() {
                              _selectedCategory = category;
                            });
                          },
                          selectedColor: theme.colorScheme.primaryContainer,
                          backgroundColor: theme.colorScheme.surfaceContainerHighest,
                        );
                      }).toList(),
                    ),
                  ],
                ),
              ),
            ),
            
            const SizedBox(height: 24),
            
            // Date formatting examples
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Date Formatting Examples',
                      style: theme.textTheme.titleMedium,
                    ),
                    const SizedBox(height: 12),
                    
                    _buildDateExample(context, l10n.today, DateTime.now()),
                    _buildDateExample(context, l10n.yesterday, DateTime.now().subtract(const Duration(days: 1))),
                    _buildDateExample(context, 'Last Week', DateTime.now().subtract(const Duration(days: 7))),
                    _buildDateExample(context, 'Last Month', DateTime(2024, 11, 15)),
                  ],
                ),
              ),
            ),
            
            const SizedBox(height: 24),
            
            // Action buttons with proper RTL support
            textDir.createDirectionalRow(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                OutlinedButton.icon(
                  onPressed: () => _showLocalizedDialog(context),
                  icon: Icon(Icons.info_outline),
                  label: Text(l10n.insights),
                ),
                FilledButton.icon(
                  onPressed: () => _showLocalizedSnackBar(context),
                  icon: Icon(textDir.forwardIcon),
                  label: Text(l10n.addExpense),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDateExample(BuildContext context, String label, DateTime date) {
    final theme = Theme.of(context);
    final textDir = TextDirectionService.instance;
    
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: textDir.createDirectionalRow(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: theme.textTheme.bodyMedium,
          ),
          Text(
            FinancialFormatters.formatTransactionDate(context, date),
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }

  void _showLocalizedDialog(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.insights),
        content: Text(
          'This dialog demonstrates proper localization with:\n\n'
          '• Localized title: ${l10n.insights}\n'
          '• Localized buttons: ${l10n.yes} / ${l10n.no}\n'
          '• Proper text direction support\n'
          '• Currency: ${FinancialFormatters.getCurrencySymbol()}\n'
          '• Sample amount: ${context.formatMoney(123.45)}',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: Text(l10n.cancel),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(),
            child: Text(l10n.yes),
          ),
        ],
      ),
    );
  }

  void _showLocalizedSnackBar(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('${l10n.expenseAdded} ${context.formatMoney(50.0)}'),
        action: SnackBarAction(
          label: l10n.dismiss,
          onPressed: () => ScaffoldMessenger.of(context).hideCurrentSnackBar(),
        ),
      ),
    );
  }
}
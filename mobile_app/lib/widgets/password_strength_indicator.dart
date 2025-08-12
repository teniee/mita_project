import 'package:flutter/material.dart';
import '../services/password_validation_service.dart';

/// Real-time password strength indicator widget
/// Shows visual feedback and suggestions as user types their password
class PasswordStrengthIndicator extends StatelessWidget {
  final String password;
  final bool showDetailedFeedback;
  final EdgeInsets? padding;

  const PasswordStrengthIndicator({
    super.key,
    required this.password,
    this.showDetailedFeedback = true,
    this.padding,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    
    if (password.isEmpty) {
      return const SizedBox.shrink();
    }
    
    final validation = PasswordValidationService.validatePassword(password);
    
    return Container(
      padding: padding ?? const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Strength meter
          _buildStrengthMeter(validation, colorScheme),
          
          const SizedBox(height: 12),
          
          // Strength description and score
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Password Strength: ${validation.strengthDescription}',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: _getStrengthColor(validation.strength, colorScheme),
                  fontWeight: FontWeight.w600,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: _getStrengthColor(validation.strength, colorScheme).withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: _getStrengthColor(validation.strength, colorScheme).withValues(alpha: 0.3),
                  ),
                ),
                child: Text(
                  '${validation.securityScore}/100',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: _getStrengthColor(validation.strength, colorScheme),
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          
          if (showDetailedFeedback) ...[
            const SizedBox(height: 16),
            
            // Requirements checklist
            _buildRequirementsChecklist(validation, theme),
            
            if (validation.issues.isNotEmpty) ...[
              const SizedBox(height: 12),
              _buildIssuesList(validation.issues, theme, true),
            ],
            
            if (validation.warnings.isNotEmpty) ...[
              const SizedBox(height: 12),
              _buildIssuesList(validation.warnings, theme, false),
            ],
            
            if (validation.suggestions.isNotEmpty) ...[
              const SizedBox(height: 12),
              _buildSuggestionsList(validation.suggestions, theme),
            ],
          ],
        ],
      ),
    );
  }

  Widget _buildStrengthMeter(PasswordValidationResult validation, ColorScheme colorScheme) {
    final strengthColor = _getStrengthColor(validation.strength, colorScheme);
    
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Progress bar
        Container(
          height: 8,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(4),
            color: colorScheme.surfaceContainerHighest,
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: validation.strength,
              backgroundColor: Colors.transparent,
              valueColor: AlwaysStoppedAnimation<Color>(strengthColor),
            ),
          ),
        ),
        
        const SizedBox(height: 4),
        
        // Entropy info
        Text(
          'Entropy: ${validation.entropy.toStringAsFixed(1)} bits',
          style: const TextStyle(
            fontSize: 11,
            color: colorScheme.onSurface.withValues(alpha: 0.6),
          ),
        ),
      ],
    );
  }

  Widget _buildRequirementsChecklist(PasswordValidationResult validation, ThemeData theme) {
    final requirements = [
      _ChecklistItem('At least 8 characters', password.length >= 8),
      _ChecklistItem('Uppercase letter', password.contains(RegExp(r'[A-Z]'))),
      _ChecklistItem('Lowercase letter', password.contains(RegExp(r'[a-z]'))),
      _ChecklistItem('Number', password.contains(RegExp(r'\d'))),
      _ChecklistItem('Special character', password.contains(RegExp(r'[!@#$%^&*()_+\-=\[\]{};:"\\|,.<>\/?]'))),
      _ChecklistItem('Strong password', validation.isStrong),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Requirements:',
          style: theme.textTheme.bodyMedium?.copyWith(
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 8),
        ...requirements.map((item) => _buildChecklistItem(item, theme)),
      ],
    );
  }

  Widget _buildChecklistItem(_ChecklistItem item, ThemeData theme) {
    final color = item.isComplete ? Colors.green : theme.colorScheme.onSurface.withValues(alpha: 0.6);
    
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        children: [
          Icon(
            item.isComplete ? Icons.check_circle : Icons.radio_button_unchecked,
            size: 16,
            color: color,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              item.text,
              style: theme.textTheme.bodySmall?.copyWith(
                color: color,
                decoration: item.isComplete ? null : null,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildIssuesList(List<String> items, ThemeData theme, bool isError) {
    final color = isError ? Colors.red : Colors.orange;
    final icon = isError ? Icons.error_outline : Icons.warning_outlined;
    final title = isError ? 'Issues:' : 'Warnings:';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: theme.textTheme.bodyMedium?.copyWith(
            fontWeight: FontWeight.w600,
            color: color,
          ),
        ),
        const SizedBox(height: 4),
        ...items.map((item) => Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, size: 16, color: color),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  item,
                  style: theme.textTheme.bodySmall?.copyWith(color: color),
                ),
              ),
            ],
          ),
        )),
      ],
    );
  }

  Widget _buildSuggestionsList(List<String> suggestions, ThemeData theme) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Suggestions:',
          style: theme.textTheme.bodyMedium?.copyWith(
            fontWeight: FontWeight.w600,
            color: theme.colorScheme.primary,
          ),
        ),
        const SizedBox(height: 4),
        ...suggestions.map((suggestion) => Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                Icons.lightbulb_outline,
                size: 16,
                color: theme.colorScheme.primary,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  suggestion,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.primary,
                  ),
                ),
              ),
            ],
          ),
        )),
      ],
    );
  }

  Color _getStrengthColor(double strength, ColorScheme colorScheme) {
    if (strength >= 0.8) return Colors.green;
    if (strength >= 0.6) return Colors.lightGreen;
    if (strength >= 0.4) return Colors.orange;
    if (strength >= 0.2) return Colors.red;
    return Colors.red.shade700;
  }
}

class _ChecklistItem {
  final String text;
  final bool isComplete;

  const _ChecklistItem(this.text, this.isComplete);
}

/// Compact version of password strength indicator
class CompactPasswordStrengthIndicator extends StatelessWidget {
  final String password;
  final EdgeInsets? padding;

  const CompactPasswordStrengthIndicator({
    super.key,
    required this.password,
    this.padding,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    
    if (password.isEmpty) {
      return const SizedBox.shrink();
    }
    
    final validation = PasswordValidationService.validatePassword(password);
    final strengthColor = _getStrengthColor(validation.strength, colorScheme);
    
    return Container(
      padding: padding ?? const EdgeInsets.symmetric(vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Container(
                  height: 4,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(2),
                    color: colorScheme.surfaceContainerHighest,
                  ),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(2),
                    child: LinearProgressIndicator(
                      value: validation.strength,
                      backgroundColor: Colors.transparent,
                      valueColor: AlwaysStoppedAnimation<Color>(strengthColor),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Text(
                validation.strengthDescription,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: strengthColor,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          if (validation.issues.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                validation.issues.first,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: Colors.red,
                ),
              ),
            ),
        ],
      ),
    );
  }

  Color _getStrengthColor(double strength, ColorScheme colorScheme) {
    if (strength >= 0.8) return Colors.green;
    if (strength >= 0.6) return Colors.lightGreen;
    if (strength >= 0.4) return Colors.orange;
    if (strength >= 0.2) return Colors.red;
    return Colors.red.shade700;
  }
}
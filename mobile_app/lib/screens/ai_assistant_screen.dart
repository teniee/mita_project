import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../providers/user_provider.dart';
import '../providers/budget_provider.dart';
import '../providers/advice_provider.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';

class AIAssistantScreen extends StatefulWidget {
  const AIAssistantScreen({super.key});

  @override
  State<AIAssistantScreen> createState() => _AIAssistantScreenState();
}

class _AIAssistantScreenState extends State<AIAssistantScreen> {
  final ApiService _apiService = ApiService();
  final TextEditingController _questionController = TextEditingController();

  // Local UI state - kept with setState as these are purely local to this screen
  final List<Map<String, String>> _messages = [];
  bool _isLoading = false;

  @override
  void dispose() {
    _questionController.dispose();
    super.dispose();
  }

  /// Build user context from providers for AI assistant
  /// Uses context.read for one-time access since this is called from a method
  Map<String, dynamic> _buildUserContext(BuildContext context) {
    // Use context.read for one-time access in methods
    final userProvider = context.read<UserProvider>();
    final budgetProvider = context.read<BudgetProvider>();
    final adviceProvider = context.read<AdviceProvider>();

    // Build context map with user's financial information
    final userContext = <String, dynamic>{
      'userName': userProvider.userName,
      'currency': userProvider.userCurrency,
      'income': userProvider.userIncome,
      'region': userProvider.userRegion,
    };

    // Add goals if available
    if (userProvider.userGoals.isNotEmpty) {
      userContext['goals'] = userProvider.userGoals;
    }

    // Add financial context if available
    final financialContext = userProvider.financialContext;
    if (financialContext.isNotEmpty) {
      userContext['financialContext'] = financialContext;
    }

    // Add budget context from BudgetProvider
    if (budgetProvider.state == BudgetState.loaded) {
      userContext['budgetContext'] = {
        'totalBudget': budgetProvider.totalBudget,
        'totalSpent': budgetProvider.totalSpent,
        'remaining': budgetProvider.remaining,
        'spendingPercentage': budgetProvider.spendingPercentage,
        'budgetMode': budgetProvider.budgetMode,
        'budgetStatus': budgetProvider.getBudgetStatus(),
      };

      // Add budget suggestions if available
      if (budgetProvider.budgetSuggestions.isNotEmpty) {
        userContext['budgetSuggestions'] = budgetProvider.budgetSuggestions;
      }
    }

    // Add latest advice context from AdviceProvider
    if (adviceProvider.latestAdvice != null) {
      userContext['latestAdvice'] = adviceProvider.latestAdvice;
    }

    return userContext;
  }

  Future<void> _sendQuestion() async {
    final question = _questionController.text.trim();
    if (question.isEmpty) return;

    setState(() {
      _messages.add({'role': 'user', 'content': question});
      _isLoading = true;
    });

    _questionController.clear();

    try {
      // Get user context from provider
      final userContext = _buildUserContext(context);

      // Call API with user context for personalized responses
      final response = await _apiService.askAIAssistant(
        question,
        context: userContext,
      );

      if (mounted) {
        setState(() {
          _messages.add({'role': 'assistant', 'content': response});
          _isLoading = false;
        });
      }
    } catch (e) {
      logError('Error asking AI assistant: $e');
      if (mounted) {
        setState(() {
          _messages.add({
            'role': 'assistant',
            'content': 'Sorry, I encountered an error. Please try again later.'
          });
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    // Use context.watch for reactive rebuilds - when userName changes, UI updates
    final userProvider = context.watch<UserProvider>();

    // Watch BudgetProvider to show loading states or budget warnings if needed
    final budgetProvider = context.watch<BudgetProvider>();

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.accent,
        title: Text(
          'AI Financial Assistant',
          style: AppTypography.heading3.copyWith(color: AppColors.textLight),
        ),
        elevation: 0,
        iconTheme: const IconThemeData(color: AppColors.textLight),
      ),
      body: Column(
        children: [
          Expanded(
            child: _messages.isEmpty
                ? _buildEmptyState(
                    userName: userProvider.userName,
                    budgetStatus: budgetProvider.getBudgetStatus(),
                    spendingPercentage: budgetProvider.spendingPercentage,
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _messages.length,
                    itemBuilder: (context, index) {
                      final message = _messages[index];
                      final isUser = message['role'] == 'user';
                      return _buildMessageBubble(
                        message['content']!,
                        isUser,
                      );
                    },
                  ),
          ),
          if (_isLoading)
            const Padding(
              padding: EdgeInsets.all(8.0),
              child: CircularProgressIndicator(),
            ),
          _buildInputField(),
        ],
      ),
    );
  }

  Widget _buildEmptyState({
    required String userName,
    required String budgetStatus,
    required double spendingPercentage,
  }) {
    // Determine contextual hint based on budget status
    String contextualHint = 'I can help you with budgeting tips, spending insights, savings goals, and more.';

    if (budgetStatus == 'exceeded') {
      contextualHint = 'I notice you\'ve exceeded your budget. Ask me for tips on getting back on track!';
    } else if (budgetStatus == 'warning') {
      contextualHint = 'You\'re approaching your budget limit. I can help you find ways to save!';
    }

    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.psychology,
            size: 80,
            color: AppColors.accent.withValues(alpha: 0.3),
          ),
          const SizedBox(height: 16),
          Text(
            'Hi $userName! Ask me anything about your finances!',
            style: AppTypography.heading4,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 8),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 40),
            child: Text(
              contextualHint,
              style: AppTypography.bodyMedium.copyWith(color: AppColors.textSecondary),
              textAlign: TextAlign.center,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMessageBubble(String content, bool isUser) {
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(12),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.75,
        ),
        decoration: BoxDecoration(
          color: isUser ? AppColors.accent : AppColors.surface,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(
              color: AppColors.shadow,
              blurRadius: 4,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Text(
          content,
          style: AppTypography.bodyMedium.copyWith(
            color: isUser ? AppColors.textLight : AppColors.textPrimary,
            height: 1.4,
          ),
        ),
      ),
    );
  }

  Widget _buildInputField() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        boxShadow: [
          BoxShadow(
            color: AppColors.shadow,
            blurRadius: 8,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _questionController,
              decoration: InputDecoration(
                hintText: 'Ask a question...',
                hintStyle: AppTypography.hint,
                filled: true,
                fillColor: AppColors.inputBackground,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24),
                  borderSide: BorderSide.none,
                ),
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 12,
                ),
              ),
              maxLines: null,
              textInputAction: TextInputAction.send,
              onSubmitted: (_) => _sendQuestion(),
            ),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: _isLoading ? null : _sendQuestion,
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: _isLoading
                    ? AppColors.accent.withValues(alpha: 0.5)
                    : AppColors.accent,
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.send,
                color: AppColors.textLight,
                size: 20,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../services/iap_service.dart';
import '../providers/user_provider.dart';
import '../services/iap_service.dart';

class SubscriptionScreen extends StatefulWidget {
  const SubscriptionScreen({super.key});

  @override
  State<SubscriptionScreen> createState() => _SubscriptionScreenState();
}

class _SubscriptionScreenState extends State<SubscriptionScreen> {
  bool _isProcessing = false;
  bool _isPremium = false;
  SubscriptionInfo? _subscriptionInfo;

  @override
  void initState() {
    super.initState();
    // Initialize IAP service after the first frame
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _initializeAndLoadStatus();
    });
  }

  Future<void> _initializeAndLoadStatus() async {
    final userProvider = context.read<UserProvider>();

    try {
      // Initialize IAP service
      await userProvider.initializeIap();

      // Load initial premium status and subscription info
      await _loadSubscriptionStatus();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to initialize: $e')),
        );
      }
    }
  }

  Future<void> _loadSubscriptionStatus() async {
    final userProvider = context.read<UserProvider>();

    final isPremium = await userProvider.isPremiumUser();
    final subscriptionInfo = await userProvider.getSubscriptionInfo();

    if (mounted) {
      setState(() {
        _isPremium = isPremium;
        _subscriptionInfo = subscriptionInfo;
      });
    }
  }

  Future<void> _buyPremium() async {
    setState(() => _isProcessing = true);

    try {
      await context.read<UserProvider>().buyPremium();
      // Reload status after purchase
      await _loadSubscriptionStatus();

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Premium purchase successful!')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Purchase failed: $e')),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isProcessing = false);
      }
    }
  }

  Future<void> _restorePurchases() async {
    setState(() => _isProcessing = true);

    try {
      await context.read<UserProvider>().restorePurchases();
      // Reload status after restore
      await _loadSubscriptionStatus();

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Purchases restored successfully!')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Restore failed: $e')),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isProcessing = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    // Watch UserProvider for reactive rebuilds
    final userProvider = context.watch<UserProvider>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Go Premium'),
        backgroundColor: AppColors.background,
        foregroundColor: AppColors.textPrimary,
        elevation: 0,
      ),
      body: StreamBuilder<bool>(
        stream: userProvider.premiumStatusStream,
        initialData: _isPremium,
        builder: (context, snapshot) {
          final isPremium = snapshot.data ?? _isPremium;

          if (_isProcessing || userProvider.isLoading) {
            return const Center(
              child: CircularProgressIndicator(),
            );
          }

          return SingleChildScrollView(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Premium status card
                Card(
                  elevation: 2,
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Column(
                      children: [
                        Icon(
                          isPremium ? Icons.star : Icons.star_border,
                          size: 48,
                          color:
                              isPremium ? AppColors.premium : AppColors.primary,
                        ),
                        const SizedBox(height: 8),
                        Text(
                          isPremium ? 'Premium Active' : 'Free Plan',
                          style: Theme.of(context)
                              .textTheme
                              .headlineSmall
                              ?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: AppColors.primary,
                              ),
                        ),
                        if (_subscriptionInfo != null && isPremium) ...[
                          const SizedBox(height: 8),
                          Text(
                            'Expires: ${_subscriptionInfo!.expiresAt.toString().split(' ').first}',
                            style: Theme.of(context)
                                .textTheme
                                .bodyMedium
                                ?.copyWith(
                                  color: Colors.grey[600],
                                ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 24),

                // Premium features list
                if (!isPremium) ...[
                  const Text(
                    'Premium Features:',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: AppColors.primary,
                    ),
                  ),
                  const SizedBox(height: 12),
                  _buildFeatureItem('Unlimited budget tracking'),
                  _buildFeatureItem('Advanced analytics'),
                  _buildFeatureItem('Priority support'),
                  _buildFeatureItem('Ad-free experience'),
                  const SizedBox(height: 24),
                ],

                // Action buttons
                if (!isPremium) ...[
                  ElevatedButton(
                    onPressed: _isProcessing ? null : _buyPremium,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.primary,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                    child: const Text(
                      'Buy Premium',
                      style:
                          TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                  ),
                  const SizedBox(height: 12),
                ],

                // Restore purchases button
                TextButton(
                  onPressed: _isProcessing ? null : _restorePurchases,
                  child: const Text(
                    'Restore Purchases',
                    style: TextStyle(color: AppColors.primary),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildFeatureItem(String feature) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        children: [
          const Icon(
            Icons.check_circle,
            color: AppColors.success,
            size: 20,
          ),
          const SizedBox(width: 8),
          Text(
            feature,
            style: const TextStyle(fontSize: 14),
          ),
        ],
      ),
    );
  }
}

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../providers/user_provider.dart';

class ReferralScreen extends StatefulWidget {
  const ReferralScreen({super.key});

  @override
  State<ReferralScreen> createState() => _ReferralScreenState();
}

class _ReferralScreenState extends State<ReferralScreen> {
  @override
  void initState() {
    super.initState();
    // Load referral code via provider on screen initialization
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<UserProvider>().loadReferralCode();
    });
  }

  @override
  Widget build(BuildContext context) {
    // Watch provider for reactive updates
    final userProvider = context.watch<UserProvider>();
    final isLoading = userProvider.isLoadingReferral;
    final code = userProvider.referralCode;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Invite Friends'),
        backgroundColor: AppColors.background,
        foregroundColor: AppColors.textPrimary,
        elevation: 0,
      ),
      body: Center(
        child: isLoading
            ? const CircularProgressIndicator()
            : Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    code ?? '-',
                    style: const TextStyle(
                      fontFamily: AppTypography.fontHeading,
                      fontSize: 32,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 10),
                  const Text('Share this code with your friends!'),
                ],
              ),
      ),
    );
  }
}

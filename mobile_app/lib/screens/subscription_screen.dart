import 'package:flutter/material.dart';
import '../services/iap_service.dart';

class SubscriptionScreen extends StatefulWidget {
  const SubscriptionScreen({super.key});

  @override
  State<SubscriptionScreen> createState() => _SubscriptionScreenState();
}

class _SubscriptionScreenState extends State<SubscriptionScreen> {
  final IapService _iapService = IapService();
  bool _processing = false;

  Future<void> _buy() async {
    setState(() => _processing = true);
    try {
      await _iapService.buyPremium();
    } catch (e) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Error: $e')));
    } finally {
      setState(() => _processing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Go Premium'),
        backgroundColor: const Color(0xFFFFF9F0),
        foregroundColor: const Color(0xFF193C57),
        elevation: 0,
      ),
      body: Center(
        child: _processing
            ? const CircularProgressIndicator()
            : ElevatedButton(
                onPressed: _buy,
                child: const Text('Buy Premium'),
              ),
      ),
    );
  }
}

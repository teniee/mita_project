import 'dart:async';

import 'package:flutter/material.dart';
import 'package:in_app_purchase/in_app_purchase.dart';

import '../services/api_service.dart';

class PremiumSubscriptionScreen extends StatefulWidget {
  const PremiumSubscriptionScreen({Key? key}) : super(key: key);

  @override
  State<PremiumSubscriptionScreen> createState() => _PremiumSubscriptionScreenState();
}

class _PremiumSubscriptionScreenState extends State<PremiumSubscriptionScreen> {
  final InAppPurchase _iap = InAppPurchase.instance;
  final ApiService _api = ApiService();
  late StreamSubscription<List<PurchaseDetails>> _sub;
  bool _loading = true;
  bool _isPremium = false;
  List<ProductDetails> _products = [];

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    final available = await _iap.isAvailable();
    if (available) {
      const ids = {'mita_premium_monthly', 'mita_premium_annual'};
      final resp = await _iap.queryProductDetails(ids);
      _products = resp.productDetails;
      _sub = _iap.purchaseStream.listen(_listenPurchases);
    }
    final profile = await _api.getUserProfile();
    setState(() {
      _isPremium = profile['data']['is_premium'] as bool? ?? false;
      _loading = false;
    });
  }

  Future<void> _listenPurchases(List<PurchaseDetails> purchases) async {
    for (var p in purchases) {
      if (p.status == PurchaseStatus.purchased) {
        final platform = Theme.of(context).platform == TargetPlatform.iOS ? 'ios' : 'android';
        await _api.validateReceipt(p.verificationData.serverVerificationData, platform);
        setState(() => _isPremium = true);
      }
    }
  }

  @override
  void dispose() {
    _sub.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Premium Subscription'),
        backgroundColor: const Color(0xFFFFF9F0),
        iconTheme: const IconThemeData(color: Color(0xFF193C57)),
        centerTitle: true,
      ),
      backgroundColor: const Color(0xFFFFF9F0),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: _isPremium
            ? const Center(child: Text('You are a premium user!'))
            : Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Upgrade to access premium features',
                    style: TextStyle(fontFamily: 'Manrope', fontSize: 16),
                  ),
                  const SizedBox(height: 20),
                  ..._products.map(
                    (p) => ElevatedButton(
                      onPressed: () {
                        final param = PurchaseParam(productDetails: p);
                        _iap.buyNonConsumable(purchaseParam: param);
                      },
                      child: Text('Buy ${p.title} – ${p.price}'),
                    ),
                  ),
                ],
              ),
      ),
    );
  }
}

import 'dart:async';
import 'dart:io';

import 'package:in_app_purchase/in_app_purchase.dart';
import 'api_service.dart';

class IapService {
  final InAppPurchase _iap = InAppPurchase.instance;
  final ApiService _apiService = ApiService();
  StreamSubscription<List<PurchaseDetails>>? _sub;

  Future<void> buyPremium() async {
    final response = await _iap.queryProductDetails({'premium'});
    if (response.notFoundIDs.isNotEmpty) {
      throw Exception('Product not found');
    }
    final product = response.productDetails.first;
    final purchaseParam = PurchaseParam(productDetails: product);

    _sub ??= _iap.purchaseStream.listen(_handlePurchaseUpdate);

    await _iap.buyNonConsumable(purchaseParam: purchaseParam);
  }

  Future<void> _handlePurchaseUpdate(List<PurchaseDetails> purchases) async {
    for (final purchase in purchases) {
      if (purchase.status == PurchaseStatus.purchased) {
        await _validatePurchase(purchase);
        await _iap.completePurchase(purchase);
      }
    }
  }

  Future<void> _validatePurchase(PurchaseDetails purchase) async {
    final userId = await _apiService.getUserId();
    final receipt = purchase.verificationData.serverVerificationData;
    final platform = Platform.isIOS ? 'ios' : 'android';
    if (userId != null) {
      await _apiService.validateReceipt(userId, receipt, platform);
    }
  }

  void dispose() {
    _sub?.cancel();
    _sub = null;
  }
}

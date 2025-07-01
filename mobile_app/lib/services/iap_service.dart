import 'package:in_app_purchase/in_app_purchase.dart';

class IapService {
  final InAppPurchase _iap = InAppPurchase.instance;

  Future<void> buyPremium() async {
    final response = await _iap.queryProductDetails({'premium'});
    if (response.notFoundIDs.isNotEmpty) {
      throw Exception('Product not found');
    }
    final product = response.productDetails.first;
    final purchaseParam = PurchaseParam(productDetails: product);
    await _iap.buyNonConsumable(purchaseParam: purchaseParam);
  }
}

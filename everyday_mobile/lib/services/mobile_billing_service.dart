import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:in_app_purchase/in_app_purchase.dart';

import 'api_client.dart';

class MobileBillingService {
  MobileBillingService._();

  static final MobileBillingService instance = MobileBillingService._();

  static const productId = String.fromEnvironment(
    'IAP_PRODUCT_ID',
    defaultValue: 'screens_monthly',
  );

  bool get usesNativeStore =>
      !kIsWeb &&
      (defaultTargetPlatform == TargetPlatform.iOS ||
          defaultTargetPlatform == TargetPlatform.android);

  String get storeName {
    if (defaultTargetPlatform == TargetPlatform.iOS) {
      return 'Apple App Store';
    }
    if (defaultTargetPlatform == TargetPlatform.android) {
      return 'Google Play';
    }
    return 'Stripe';
  }

  Future<void> purchase({required ApiClient apiClient}) async {
    if (!usesNativeStore) {
      throw StateError('Native mobile billing is unavailable on this device.');
    }

    final billing = InAppPurchase.instance;
    if (!await billing.isAvailable()) {
      throw StateError('$storeName billing is unavailable right now.');
    }

    final response = await billing.queryProductDetails({productId});
    if (response.error != null) {
      throw StateError(response.error!.message);
    }
    if (response.productDetails.isEmpty) {
      throw StateError(
        'Subscription product "$productId" is not available yet. '
        'Finish its setup in $storeName and try again.',
      );
    }

    final product = response.productDetails.first;
    final result = Completer<void>();
    late final StreamSubscription<List<PurchaseDetails>> subscription;

    Future<void> handlePurchase(PurchaseDetails purchase) async {
      if (result.isCompleted || purchase.productID != product.id) {
        return;
      }
      if (purchase.status == PurchaseStatus.pending) {
        return;
      }
      if (purchase.status == PurchaseStatus.error) {
        result.completeError(
          StateError(purchase.error?.message ?? 'Purchase failed.'),
        );
        return;
      }
      if (purchase.status == PurchaseStatus.canceled) {
        result.completeError(StateError('Purchase was cancelled.'));
        return;
      }
      if (purchase.status != PurchaseStatus.purchased &&
          purchase.status != PurchaseStatus.restored) {
        return;
      }

      try {
        await apiClient.verifyMobilePurchase(
          provider:
              defaultTargetPlatform == TargetPlatform.iOS ? 'apple' : 'google',
          productId: purchase.productID,
          serverVerificationData:
              purchase.verificationData.serverVerificationData,
          localVerificationData:
              purchase.verificationData.localVerificationData,
          purchaseId: purchase.purchaseID,
        );
        if (purchase.pendingCompletePurchase) {
          await billing.completePurchase(purchase);
        }
        if (!result.isCompleted) {
          result.complete();
        }
      } catch (error) {
        if (!result.isCompleted) {
          result.completeError(error);
        }
      }
    }

    subscription = billing.purchaseStream.listen(
      (purchases) {
        for (final purchase in purchases) {
          unawaited(handlePurchase(purchase));
        }
      },
      onError: (Object error) {
        if (!result.isCompleted) {
          result.completeError(error);
        }
      },
    );

    try {
      final started = await billing.buyNonConsumable(
        purchaseParam: PurchaseParam(productDetails: product),
      );
      if (!started && !result.isCompleted) {
        result.completeError(StateError('Could not open the purchase screen.'));
      }
      await result.future.timeout(
        const Duration(minutes: 5),
        onTimeout: () =>
            throw StateError('Purchase timed out. Please try again.'),
      );
    } finally {
      await subscription.cancel();
    }
  }
}

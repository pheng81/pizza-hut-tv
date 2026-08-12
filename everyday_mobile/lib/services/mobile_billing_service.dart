import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:in_app_purchase/in_app_purchase.dart';

import 'api_client.dart';

class MobileBillingService {
  MobileBillingService._();

  static final MobileBillingService instance = MobileBillingService._();

  /// Fallback product id, used only when the server does not supply one.
  static const productId = String.fromEnvironment(
    'IAP_PRODUCT_ID',
    defaultValue: 'screens_monthly',
  );

  /// The product id the server wants this platform to buy.
  ///
  /// Comes from APPLE_IAP_PRODUCT_ID / GOOGLE_PLAY_PRODUCT_ID via
  /// /api/subscription/summary, so the store product can be changed without
  /// shipping a new build.
  String productIdFrom(Map<String, dynamic>? summary) {
    final key = defaultTargetPlatform == TargetPlatform.android
        ? 'google_product_id'
        : 'apple_product_id';
    final fromServer = (summary?[key] ?? '').toString().trim();
    return fromServer.isNotEmpty ? fromServer : productId;
  }

  /// Looks up the store listing so the paywall can show the price the store
  /// will actually charge. Returns null when the product is unavailable.
  Future<ProductDetails?> loadProduct({String? productId}) async {
    if (!usesNativeStore) {
      return null;
    }
    final billing = InAppPurchase.instance;
    if (!await billing.isAvailable()) {
      return null;
    }
    final id = (productId ?? '').trim().isNotEmpty
        ? productId!.trim()
        : MobileBillingService.productId;
    final response = await billing.queryProductDetails({id});
    if (response.error != null || response.productDetails.isEmpty) {
      return null;
    }
    return response.productDetails.first;
  }

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

  /// Re-verifies subscriptions the user already owns.
  ///
  /// The App Store requires a way to restore purchases on a new device or
  /// after a reinstall. Returns the number of subscriptions the server
  /// accepted, so the caller can tell the user when nothing was found.
  Future<int> restore({required ApiClient apiClient, String? productId}) async {
    if (!usesNativeStore) {
      throw StateError('Native mobile billing is unavailable on this device.');
    }

    final billing = InAppPurchase.instance;
    if (!await billing.isAvailable()) {
      throw StateError('$storeName billing is unavailable right now.');
    }

    final wantedId = (productId ?? '').trim().isNotEmpty
        ? productId!.trim()
        : MobileBillingService.productId;

    var restored = 0;
    final done = Completer<void>();
    late final StreamSubscription<List<PurchaseDetails>> subscription;

    Future<void> handleRestored(PurchaseDetails purchase) async {
      if (purchase.status != PurchaseStatus.restored &&
          purchase.status != PurchaseStatus.purchased) {
        return;
      }
      if (purchase.productID != wantedId) {
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
        restored += 1;
      } catch (_) {
        // An expired or already-consumed receipt is not a restore failure.
      }
      if (purchase.pendingCompletePurchase) {
        await billing.completePurchase(purchase);
      }
    }

    subscription = billing.purchaseStream.listen(
      (purchases) async {
        for (final purchase in purchases) {
          await handleRestored(purchase);
        }
        if (!done.isCompleted) {
          done.complete();
        }
      },
      onError: (Object error) {
        if (!done.isCompleted) {
          done.completeError(error);
        }
      },
    );

    try {
      await billing.restorePurchases();
      // restorePurchases() replays past purchases through purchaseStream, but
      // emits nothing at all when there are none - so stop waiting rather than
      // hang when the account has no subscription.
      await done.future.timeout(
        const Duration(seconds: 20),
        onTimeout: () {},
      );
    } finally {
      await subscription.cancel();
    }

    return restored;
  }

  Future<void> purchase({required ApiClient apiClient, String? productId}) async {
    if (!usesNativeStore) {
      throw StateError('Native mobile billing is unavailable on this device.');
    }

    final billing = InAppPurchase.instance;
    if (!await billing.isAvailable()) {
      throw StateError('$storeName billing is unavailable right now.');
    }

    final wantedId = (productId ?? '').trim().isNotEmpty
        ? productId!.trim()
        : MobileBillingService.productId;

    final response = await billing.queryProductDetails({wantedId});
    if (response.error != null) {
      throw StateError(response.error!.message);
    }
    if (response.productDetails.isEmpty) {
      throw StateError(
        'Subscription product "$wantedId" is not available yet. '
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

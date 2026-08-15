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

  /// Looks up several store listings at once, for a tier comparison screen.
  /// Keyed by product id; missing/unavailable products are simply absent.
  Future<Map<String, ProductDetails>> loadProducts(
    List<String> productIds,
  ) async {
    final ids = productIds.map((e) => e.trim()).where((e) => e.isNotEmpty).toSet();
    if (!usesNativeStore || ids.isEmpty) {
      return {};
    }
    final billing = InAppPurchase.instance;
    if (!await billing.isAvailable()) {
      return {};
    }
    final response = await billing.queryProductDetails(ids);
    return {for (final p in response.productDetails) p.id: p};
  }

  /// Spells out a store error, including its code.
  ///
  /// StoreKit's message is often just "SKErrorDomain", which says nothing about
  /// what went wrong, so the code and any details are kept.
  static String _describeIapError(IAPError error) {
    final parts = <String>[];
    final message = error.message.trim();
    if (message.isNotEmpty) {
      parts.add(message);
    }
    if (error.code.trim().isNotEmpty) {
      parts.add('code ${error.code.trim()}');
    }
    final details = error.details?.toString().trim() ?? '';
    if (details.isNotEmpty && details != 'null') {
      parts.add(details.length > 100 ? '${details.substring(0, 100)}...' : details);
    }
    return parts.isEmpty ? 'Purchase failed.' : parts.join(' - ');
  }

  /// Turns a store failure into something a user can act on.
  ///
  /// StoreKit surfaces failures as PlatformException with a full stack trace
  /// attached, which is unreadable if shown directly.
  static String friendlyError(Object error) {
    final raw = error.toString();
    final lower = raw.toLowerCase();

    if (lower.contains('not authorized to make purchases') ||
        lower.contains("doesn't have permission to make in-app purchases")) {
      return 'This Apple Account is not allowed to make purchases. '
          'In testing, sign in with a Sandbox test account under '
          'Settings > Developer > Sandbox Apple Account, then try again.';
    }
    if (lower.contains('cancel')) {
      return 'Purchase was cancelled.';
    }
    if (lower.contains('duplicate_product_object') ||
        lower.contains('pending transaction for the same product')) {
      return 'The App Store is still processing an earlier attempt at this '
          'plan. Wait about a minute and try again. If it keeps happening, '
          'close the app completely and reopen it.';
    }
    if (lower.contains('is not available yet')) {
      // Already a written explanation from purchase().
      return raw.replaceFirst('Exception: ', '');
    }
    if (lower.contains('storekiterror') || lower.contains('platformexception')) {
      // Keep a short tail of the platform detail. Without it this message is
      // untraceable, which cost real time diagnosing a stuck purchase queue.
      final detail = raw.split('Stacktrace').first.replaceFirst('Exception: ', '').trim();
      final hint = detail.length > 120 ? '${detail.substring(0, 120)}...' : detail;
      return 'The App Store could not complete this purchase. '
          'Check that you are signed in to the App Store and try again.\n\n($hint)';
    }
    if (lower.contains('billing is unavailable')) {
      return raw.replaceFirst('Exception: ', '');
    }

    final cleaned = raw.replaceFirst('Exception: ', '').trim();
    // Never dump a stack trace into the UI.
    if (cleaned.length > 200) {
      return 'Something went wrong with the purchase. Please try again.';
    }
    return cleaned;
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

  /// Clears transactions the store is still holding as unfinished.
  ///
  /// The store replays unfinished transactions on every launch and refuses new
  /// purchases while they are queued, so this drains them at startup: each is
  /// verified if possible, then finished either way. Safe to call when there is
  /// nothing queued - it simply times out.
  /// Returns the product ids still mid-flight, which cannot be finished and
  /// which block a fresh purchase of the same product.
  Future<Set<String>> drainPendingTransactions({
    required ApiClient apiClient,
  }) async {
    if (!usesNativeStore) {
      return {};
    }
    final billing = InAppPurchase.instance;
    if (!await billing.isAvailable()) {
      return {};
    }

    final stillPending = <String>{};
    late final StreamSubscription<List<PurchaseDetails>> subscription;
    final idle = Completer<void>();
    Timer? quiet;

    void markQuiet() {
      quiet?.cancel();
      // Stop once the stream has been silent briefly, since it never signals
      // that a replay is finished.
      quiet = Timer(const Duration(seconds: 3), () {
        if (!idle.isCompleted) {
          idle.complete();
        }
      });
    }

    subscription = billing.purchaseStream.listen(
      (purchases) async {
        for (final purchase in purchases) {
          if (purchase.status == PurchaseStatus.pending) {
            // Still mid-flight and cannot be finished. Record it so the caller
            // can avoid starting a second purchase of the same product, which
            // the store rejects as a duplicate.
            stillPending.add(purchase.productID);
            continue;
          }
          stillPending.remove(purchase.productID);
          if (purchase.status == PurchaseStatus.purchased ||
              purchase.status == PurchaseStatus.restored) {
            try {
              await apiClient.verifyMobilePurchase(
                provider: defaultTargetPlatform == TargetPlatform.iOS
                    ? 'apple'
                    : 'google',
                productId: purchase.productID,
                serverVerificationData:
                    purchase.verificationData.serverVerificationData,
                localVerificationData:
                    purchase.verificationData.localVerificationData,
                purchaseId: purchase.purchaseID,
              );
            } catch (_) {
              // Still finish it; a stuck queue is worse than an unverified
              // purchase, and the receipt keeps it recoverable via restore.
            }
          }
          if (purchase.pendingCompletePurchase) {
            try {
              await billing.completePurchase(purchase);
            } catch (_) {}
          }
        }
        markQuiet();
      },
      onError: (Object _) {
        if (!idle.isCompleted) {
          idle.complete();
        }
      },
    );

    markQuiet();
    try {
      await idle.future.timeout(const Duration(seconds: 12), onTimeout: () {});
    } finally {
      quiet?.cancel();
      await subscription.cancel();
    }
    return stillPending;
  }

  /// Re-verifies subscriptions the user already owns.
  ///
  /// The App Store requires a way to restore purchases on a new device or
  /// after a reinstall. Returns the number of subscriptions the server
  /// accepted, so the caller can tell the user when nothing was found.
  Future<int> restore({
    required ApiClient apiClient,
    String? productId,
    List<String>? productIds,
  }) async {
    if (!usesNativeStore) {
      throw StateError('Native mobile billing is unavailable on this device.');
    }

    final billing = InAppPurchase.instance;
    if (!await billing.isAvailable()) {
      throw StateError('$storeName billing is unavailable right now.');
    }

    // A user could have bought any tier, not just the one currently
    // recommended for their screen count, so match against all of them.
    final wantedIds = (productIds ?? const [])
        .map((e) => e.trim())
        .where((e) => e.isNotEmpty)
        .toSet();
    if (wantedIds.isEmpty) {
      wantedIds.add((productId ?? '').trim().isNotEmpty
          ? productId!.trim()
          : MobileBillingService.productId);
    }

    var restored = 0;
    String? lastError;
    final skipped = <String>{};
    final done = Completer<void>();
    late final StreamSubscription<List<PurchaseDetails>> subscription;

    Future<void> handleRestored(PurchaseDetails purchase) async {
      if (purchase.status != PurchaseStatus.restored &&
          purchase.status != PurchaseStatus.purchased) {
        return;
      }
      // Do not filter by product id here. The server maps renamed and legacy
      // products onto their current tier, so a purchase this screen was not
      // asking about may still be valid - and dropping it locally means the
      // server never gets the chance to accept it. Send everything and let the
      // server decide; note the ones it refuses.
      if (!wantedIds.contains(purchase.productID)) {
        skipped.add(purchase.productID);
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
      } catch (error) {
        // Do not hide this. A rejected receipt used to look identical to
        // "you never bought anything", which sends people to buy twice.
        lastError = error.toString().replaceFirst('Exception: ', '');
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

    if (restored == 0 && lastError != null) {
      // The store had a purchase; the server would not accept it.
      throw StateError(lastError!);
    }
    if (restored == 0 && skipped.isNotEmpty) {
      // Everything owned was offered to the server and none of it was accepted.
      throw StateError(
        'This account owns ${skipped.join(', ')}, which the server did not '
        'accept. Contact support so it can be moved across.',
      );
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

    // A transaction left unfinished by an earlier failure blocks new purchases,
    // so clear the queue before asking for another one.
    final stillPending = await drainPendingTransactions(apiClient: apiClient);
    if (stillPending.contains(wantedId)) {
      // Asking again would fail with a duplicate-product error that explains
      // nothing, so say what is actually happening.
      throw StateError(
        'The App Store is still processing an earlier attempt at this plan. '
        'Wait about a minute and try again. If it keeps happening, close the '
        'app completely and reopen it.',
      );
    }

    final response = await billing.queryProductDetails({wantedId});
    if (response.error != null) {
      throw StateError(_describeIapError(response.error!));
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
        final err = purchase.error;
        result.completeError(
          StateError(err == null ? 'Purchase failed.' : _describeIapError(err)),
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

      Object? verifyError;
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
      } catch (error) {
        verifyError = error;
      }

      // Finish the transaction even when the server rejected it. An unfinished
      // transaction stays in the store queue forever, gets replayed on every
      // launch, and blocks further purchases. Finishing does not remove it from
      // the app receipt, so it can still be verified later with a restore.
      if (purchase.pendingCompletePurchase) {
        try {
          await billing.completePurchase(purchase);
        } catch (_) {
          // Nothing useful to do; do not mask the original failure.
        }
      }

      if (!result.isCompleted) {
        if (verifyError != null) {
          result.completeError(verifyError);
        } else {
          result.complete();
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
    } catch (error) {
      // The store refuses to sell a subscription the account already owns, and
      // reports it as a generic failure. That happens whenever a purchase went
      // through but the server never recorded it, so recover by verifying what
      // the account owns instead of leaving the user stuck on an error.
      final lower = error.toString().toLowerCase();
      final looksAlreadyOwned = lower.contains('asdservererror') ||
          lower.contains('already') ||
          lower.contains('skerrordomain');
      if (!looksAlreadyOwned) {
        rethrow;
      }
      final restored = await restore(apiClient: apiClient, productId: wantedId);
      if (restored == 0) {
        rethrow;
      }
    } finally {
      await subscription.cancel();
    }
  }
}

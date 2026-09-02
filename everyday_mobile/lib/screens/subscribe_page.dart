import 'package:flutter/material.dart';
import 'package:in_app_purchase/in_app_purchase.dart';
import 'package:url_launcher/url_launcher.dart';

import '../services/api_client.dart';
import '../services/mobile_billing_service.dart';

/// The plans screen, reachable from the account page at any time.
///
/// It exists so In-App Purchase is never more than two taps away. Before, the
/// only paywall was the sheet that fires when adding a screen past the free
/// allowance, so an account that already had a subscription bought on the
/// website could use the app without ever being shown a way to buy through
/// the App Store - which is what App Review rejected under guideline 3.1.1.
class SubscribePage extends StatefulWidget {
  const SubscribePage({
    super.key,
    required this.apiClient,
    this.priceDisplay,
    this.trialDays,
  });

  final ApiClient apiClient;
  final String? priceDisplay;
  final int? trialDays;

  @override
  State<SubscribePage> createState() => _SubscribePageState();
}

class _SubscribePageState extends State<SubscribePage> {
  bool _loading = true;
  bool _busy = false;
  String? _error;
  String? _notice;

  Map<String, dynamic> _summary = const {};
  List<Map<String, Object>> _tiers = const [];
  Map<String, ProductDetails> _products = const {};
  String? _selectedProductId;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final summary = await widget.apiClient.getSubscriptionSummary();
      // The tier ladder comes from the server so product ids are never
      // hardcoded here; the price shown always comes from the store itself.
      final tiers = ((summary['mobile_tiers'] as List?) ?? const [])
          .whereType<Map>()
          .map((t) => <String, Object>{
                'product_id': (t['product_id'] ?? '').toString(),
                'screens': int.tryParse('${t['screens'] ?? 0}') ?? 0,
              })
          .where((t) => (t['product_id'] as String).isNotEmpty)
          .toList();

      final products = tiers.isEmpty
          ? <String, ProductDetails>{}
          : await MobileBillingService.instance.loadProducts(
              tiers.map((t) => t['product_id'] as String).toList(),
            );

      if (!mounted) {
        return;
      }
      setState(() {
        _summary = Map<String, dynamic>.from(summary);
        _tiers = tiers;
        _products = products;
        _selectedProductId =
            MobileBillingService.instance.productIdFrom(_summary);
        _loading = false;
      });
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = MobileBillingService.friendlyError(e);
        _loading = false;
      });
    }
  }

  Future<void> _restorePurchases() async {
    if (_busy) {
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _notice = null;
    });
    try {
      final restored = await MobileBillingService.instance.restore(
        apiClient: widget.apiClient,
        productIds: _tiers.isNotEmpty
            ? _tiers.map((t) => t['product_id'] as String).toList()
            : null,
        productId: _selectedProductId,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _notice = restored > 0
            ? 'Subscription restored.'
            : 'No previous subscription was found for this '
                '${MobileBillingService.instance.storeName} account.';
      });
      if (restored > 0) {
        await _load();
      }
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = MobileBillingService.friendlyError(e);
      });
    } finally {
      if (mounted) {
        setState(() {
          _busy = false;
        });
      }
    }
  }

  Future<void> _openLink(String path) async {
    final base = widget.apiClient.baseUrl.replaceAll(RegExp(r'/$'), '');
    await launchUrl(
      Uri.parse('$base$path'),
      mode: LaunchMode.externalApplication,
    );
  }

  /// Opens the store's own subscription settings. Apple requires a way to
  /// reach these, and its own page is not an external purchase mechanism.
  Future<void> _openStoreSubscriptions() async {
    final url = MobileBillingService.instance.storeName == 'Google Play'
        ? 'https://play.google.com/store/account/subscriptions'
        : 'https://apps.apple.com/account/subscriptions';
    await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
  }

  Future<void> _startCheckout() async {
    if (_busy) {
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _notice = null;
    });
    try {
      if (MobileBillingService.instance.usesNativeStore) {
        await MobileBillingService.instance.purchase(
          apiClient: widget.apiClient,
          productId: _selectedProductId,
        );
        if (!mounted) {
          return;
        }
        setState(() {
          _notice = 'Purchase complete. Your screens are now active.';
        });
        await _load();
      } else {
        final checkoutUrl = await widget.apiClient.createBillingCheckoutSession();
        final ok = await launchUrl(
          Uri.parse(checkoutUrl),
          mode: LaunchMode.externalApplication,
        );
        if (!ok) {
          throw StateError('Unable to open checkout link.');
        }
      }
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = MobileBillingService.friendlyError(e);
      });
    } finally {
      if (mounted) {
        setState(() {
          _busy = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final billing = MobileBillingService.instance;
    final nativeBilling = billing.usesNativeStore;
    final store = billing.storeName;

    final price = widget.priceDisplay?.trim().isNotEmpty == true
        ? widget.priceDisplay!.trim()
        : (_summary['price_display'] ?? r'$5 per screen / month').toString();
    final trial = widget.trialDays ??
        (int.tryParse('${_summary['trial_days'] ?? 14}') ?? 14);
    final screenCount = int.tryParse('${_summary['screen_count'] ?? 0}') ?? 0;
    final hasActive = _summary['has_active'] == true;
    final hasWebSubscription = _summary['has_web_subscription'] == true;
    final canSubscribe = _summary['can_subscribe'] != false;
    final blockedReason =
        (_summary['subscribe_blocked_reason'] ?? '').toString().trim();
    final recommendedId = billing.productIdFrom(_summary);
    // Over the top tier, iOS sells the largest plan anyway and support covers
    // the overflow. Pointing at the website here would fail guideline 3.1.1.
    final overLargestTier = nativeBilling &&
        billing.forbidsExternalPurchase &&
        _summary['mobile_plan_exceeds_largest_tier'] == true;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Subscription Plans'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _busy || _loading ? null : _load,
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: SafeArea(
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Text(
                    'Activate Your Screens',
                    style: theme.textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    nativeBilling
                        ? 'Secure billing through $store keeps your menu '
                            'boards online 24/7.'
                        : 'Secure checkout powered by Stripe keeps your menu '
                            'boards online 24/7.',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 14),
                  if (nativeBilling && _tiers.isNotEmpty)
                    ..._tiers.map((tier) {
                      final id = tier['product_id'] as String;
                      final screens = tier['screens'] as int;
                      final product = _products[id];
                      return _TierCard(
                        // A tier the store has no listing for cannot be sold,
                        // so it is shown as unavailable rather than silently
                        // failing at the point of purchase.
                        price: product?.price ?? 'Unavailable',
                        screens: screens,
                        selected: _selectedProductId == id,
                        recommended: id == recommendedId,
                        tooSmall: screens < screenCount,
                        enabled: product != null && !_busy,
                        onTap: () => setState(() {
                          _selectedProductId = id;
                        }),
                      );
                    })
                  else
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: scheme.outlineVariant),
                        color: scheme.primaryContainer.withAlpha(110),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            price,
                            style: theme.textTheme.headlineMedium?.copyWith(
                              fontWeight: FontWeight.w900,
                              color: scheme.primary,
                              height: 0.96,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            '$trial-day free trial. Cancel anytime.',
                            style: theme.textTheme.bodyMedium?.copyWith(
                              color: scheme.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ),
                    ),
                  const SizedBox(height: 12),
                  const _FeatureLine(text: 'Unlimited menu updates'),
                  const _FeatureLine(text: 'Perfectly synchronized screens'),
                  const _FeatureLine(text: 'Full HD/4K video support'),
                  const _FeatureLine(text: 'Cloud backups + version history'),
                  const _FeatureLine(text: 'Instant Pi/Android pairing'),
                  const _FeatureLine(text: '24/7 priority support'),
                  const SizedBox(height: 14),
                  if (hasWebSubscription)
                    _Note(
                      text: 'This account already has a subscription billed '
                          'elsewhere. Subscribing through $store replaces it - '
                          'the earlier subscription is stopped so you are '
                          'never charged twice.',
                    ),
                  if (overLargestTier)
                    _Note(
                      text: 'You have $screenCount screens, more than the '
                          'largest plan covers. Subscribe to the largest plan '
                          'and email ${MobileBillingService.supportEmail} - '
                          'we will cover the rest.',
                    ),
                  if (!canSubscribe)
                    _Note(
                      text: blockedReason.isNotEmpty
                          ? blockedReason
                          : 'This account cannot subscribe yet. Finish setting '
                              'it up, then try again.',
                    ),
                  FilledButton(
                    onPressed: _busy || !canSubscribe ? null : _startCheckout,
                    style: FilledButton.styleFrom(
                      minimumSize: const Size.fromHeight(50),
                    ),
                    child: Text(
                      _busy
                          ? 'Opening checkout...'
                          : nativeBilling
                              ? (hasActive
                                  ? 'Subscribe with $store'
                                  : 'Subscribe with $store')
                              : 'Start Subscription Securely',
                    ),
                  ),
                  if (nativeBilling)
                    TextButton(
                      onPressed: _busy ? null : _restorePurchases,
                      child: const Text('Restore purchases'),
                    ),
                  if (nativeBilling)
                    TextButton(
                      onPressed: _busy ? null : _openStoreSubscriptions,
                      child: Text('Manage $store subscriptions'),
                    ),
                  TextButton(
                    onPressed: _busy ? null : () => Navigator.of(context).pop(),
                    child: const Text('Close'),
                  ),
                  if (nativeBilling) ...[
                    const SizedBox(height: 4),
                    Text(
                      'Payment is charged to your $store account at '
                      'confirmation of purchase. The subscription renews '
                      'automatically each month unless it is cancelled at '
                      'least 24 hours before the end of the current period, '
                      'and your account is charged for renewal within 24 '
                      'hours before the period ends. You can manage or cancel '
                      'your subscription in your device account settings.',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Wrap(
                      alignment: WrapAlignment.center,
                      children: [
                        TextButton(
                          onPressed: () => _openLink('/terms'),
                          child: const Text('Terms of Use'),
                        ),
                        TextButton(
                          onPressed: () => _openLink('/privacy'),
                          child: const Text('Privacy Policy'),
                        ),
                      ],
                    ),
                  ],
                  if (_notice != null)
                    Container(
                      margin: const EdgeInsets.only(top: 8),
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(10),
                        color: scheme.primaryContainer,
                      ),
                      child: Text(_notice!),
                    ),
                  if (_error != null)
                    Container(
                      margin: const EdgeInsets.only(top: 8),
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(10),
                        color: const Color(0xFFFEE2E2),
                      ),
                      child: Text(
                        _error!,
                        style: const TextStyle(color: Color(0xFF991B1B)),
                      ),
                    ),
                ],
              ),
      ),
    );
  }
}

class _TierCard extends StatelessWidget {
  const _TierCard({
    required this.price,
    required this.screens,
    required this.selected,
    required this.recommended,
    required this.tooSmall,
    required this.enabled,
    required this.onTap,
  });

  final String price;
  final int screens;
  final bool selected;
  final bool recommended;
  final bool tooSmall;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: enabled ? onTap : null,
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: selected ? scheme.primary : scheme.outlineVariant,
              width: selected ? 2 : 1,
            ),
            color: selected
                ? scheme.primaryContainer.withAlpha(90)
                : Colors.transparent,
          ),
          child: Row(
            children: [
              Icon(
                selected
                    ? Icons.radio_button_checked
                    : Icons.radio_button_unchecked,
                color: selected ? scheme.primary : scheme.outline,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          '$screens screen${screens == 1 ? '' : 's'}',
                          style: theme.textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        if (recommended) ...[
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 3,
                            ),
                            decoration: BoxDecoration(
                              color: scheme.primaryContainer,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(
                              'RECOMMENDED',
                              style: theme.textTheme.labelSmall?.copyWith(
                                color: scheme.primary,
                                fontWeight: FontWeight.w900,
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                    if (tooSmall)
                      Text(
                        'Fewer screens than you have',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: scheme.onSurfaceVariant,
                        ),
                      ),
                  ],
                ),
              ),
              Text(
                price,
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w900,
                  color: scheme.primary,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Note extends StatelessWidget {
  const _Note({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        text,
        style: theme.textTheme.bodySmall?.copyWith(
          color: scheme.onSurfaceVariant,
        ),
      ),
    );
  }
}

class _FeatureLine extends StatelessWidget {
  const _FeatureLine({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 7),
      child: Row(
        children: [
          const Text(
            '✓',
            style: TextStyle(
              color: Color(0xFF10B981),
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(child: Text(text)),
        ],
      ),
    );
  }
}

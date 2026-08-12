import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../services/api_client.dart';
import '../services/mobile_billing_service.dart';

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
  bool _busy = false;
  String? _error;
  String? _notice;

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
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = e.toString().replaceFirst('Exception: ', '');
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
    final uri = Uri.parse('${widget.apiClient.baseUrl}$path');
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  Future<void> _startCheckout() async {
    if (_busy) {
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      if (MobileBillingService.instance.usesNativeStore) {
        await MobileBillingService.instance.purchase(
          apiClient: widget.apiClient,
        );
      } else {
        final checkoutUrl =
            await widget.apiClient.createBillingCheckoutSession();
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
        _error = e.toString().replaceFirst('Exception: ', '');
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
    final price = widget.priceDisplay?.trim().isNotEmpty == true
        ? widget.priceDisplay!.trim()
        : r'$5 per screen / month';
    final trial = widget.trialDays ?? 14;

    return Scaffold(
      appBar: AppBar(title: const Text('Activate Your Screens')),
      body: SafeArea(
        child: ListView(
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
              MobileBillingService.instance.usesNativeStore
                  ? 'Secure billing through ${MobileBillingService.instance.storeName} keeps your menu boards online 24/7.'
                  : 'Secure checkout powered by Stripe keeps your menu boards online 24/7.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: scheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 14),
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
                  const SizedBox(height: 12),
                  const _FeatureLine(text: 'Unlimited menu updates'),
                  const _FeatureLine(text: 'Perfectly synchronized screens'),
                  const _FeatureLine(text: 'Full HD/4K video support'),
                  const _FeatureLine(text: 'Cloud backups + version history'),
                  const _FeatureLine(text: 'Instant Pi/Android pairing'),
                  const _FeatureLine(text: '24/7 priority support'),
                ],
              ),
            ),
            const SizedBox(height: 14),
            FilledButton(
              onPressed: _busy ? null : _startCheckout,
              child: Text(
                _busy
                    ? 'Opening checkout...'
                    : MobileBillingService.instance.usesNativeStore
                        ? 'Subscribe with ${MobileBillingService.instance.storeName}'
                        : 'Start Subscription Securely',
              ),
            ),
            if (MobileBillingService.instance.usesNativeStore)
              TextButton(
                onPressed: _busy ? null : _restorePurchases,
                child: const Text('Restore purchases'),
              ),
            TextButton(
              onPressed: _busy ? null : () => Navigator.of(context).pop(),
              child: const Text('Skip for now'),
            ),
            if (MobileBillingService.instance.usesNativeStore) ...[
              const SizedBox(height: 4),
              Text(
                'Payment is charged to your ${MobileBillingService.instance.storeName} '
                'account at confirmation of purchase. The subscription renews '
                'automatically each month unless it is cancelled at least 24 hours '
                'before the end of the current period, and your account is charged '
                'for renewal within 24 hours before the period ends. You can manage '
                'or cancel your subscription in your device account settings.',
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

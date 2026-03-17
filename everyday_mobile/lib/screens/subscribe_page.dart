import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../services/api_client.dart';

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

  Future<void> _startCheckout() async {
    if (_busy) {
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final checkoutUrl = await widget.apiClient.createBillingCheckoutSession();
      final ok = await launchUrl(
        Uri.parse(checkoutUrl),
        mode: LaunchMode.externalApplication,
      );
      if (!ok && mounted) {
        setState(() {
          _error = 'Unable to open checkout link.';
        });
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
              'Secure checkout powered by Stripe keeps your menu boards online 24/7.',
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
                _busy ? 'Opening checkout...' : 'Start Subscription Securely',
              ),
            ),
            TextButton(
              onPressed: _busy ? null : () => Navigator.of(context).pop(),
              child: const Text('Skip for now'),
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

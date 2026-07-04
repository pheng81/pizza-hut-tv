import 'dart:async';

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/app_models.dart';
import '../services/api_client.dart';
import 'login_screen.dart';

class AccountPage extends StatefulWidget {
  const AccountPage({
    super.key,
    required this.apiClient,
    this.initialUsername,
  });

  final ApiClient apiClient;
  final String? initialUsername;

  @override
  State<AccountPage> createState() => _AccountPageState();
}

class _AccountPageState extends State<AccountPage> {
  final _phoneController = TextEditingController();
  final _phoneCodeController = TextEditingController();

  Map<String, dynamic>? _account;
  UserProfile? _meProfile;
  String? _cachedLoginEmail;
  bool _autoRecoveryTriggered = false;
  bool _loading = true;
  bool _actionBusy = false;
  bool _showPhoneEdit = false;
  bool _showPhoneCodeEntry = false;
  int _resendCountdown = 0;
  String? _message;
  Timer? _countdownTimer;
  _PhoneCountry _selectedPhoneCountry = _phoneCountries.first;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _countdownTimer?.cancel();
    _phoneController.dispose();
    _phoneCodeController.dispose();
    super.dispose();
  }

  void _showNotice(String text) {
    if (!mounted) {
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(text)),
    );
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _message = null;
    });
    _autoRecoveryTriggered = false;

    final hasSession = await widget.apiClient.checkSession();
    if (!hasSession) {
      if (mounted) {
        setState(() {
          _loading = false;
          _message = 'Session expired. Please login again.';
        });
      }
      await _reloginAndReload();
      return;
    }

    try {
      final account = await widget.apiClient.getAccountOverview();
      UserProfile? me;
      String? remembered;
      try {
        me = await widget.apiClient.getMe();
      } catch (_) {
        me = null;
      }
      try {
        remembered = await widget.apiClient.getRememberedLoginUsername();
      } catch (_) {
        remembered = null;
      }

      if (!mounted) {
        return;
      }

      final phone = (account['phone_number'] ?? '').toString();
      final phoneVerified = account['phone_verified'] == true;
      final userInfo = Map<String, dynamic>.from(
        (account['user_info'] as Map?) ?? const <String, dynamic>{},
      );
      final accountEmail = (userInfo['email'] ?? '').toString().trim();
      final meEmail = (me?.username ?? '').trim();
      final rememberedEmail = (remembered ?? '').trim();
      final resolved = accountEmail.isNotEmpty
          ? accountEmail
          : (meEmail.isNotEmpty ? meEmail : rememberedEmail);

      setState(() {
        _account = account;
        _meProfile = me;
        _cachedLoginEmail = remembered;
        _applyPhoneToEditor(phone);
        if (phoneVerified) {
          _showPhoneCodeEntry = false;
          _phoneCodeController.clear();
          _countdownTimer?.cancel();
          _resendCountdown = 0;
        } else if (phone.isEmpty) {
          _showPhoneCodeEntry = false;
        }
      });

      if (resolved.isEmpty && !_autoRecoveryTriggered && mounted) {
        _autoRecoveryTriggered = true;
        _showNotice('Session is out of sync. Please login again.');
        WidgetsBinding.instance.addPostFrameCallback((_) async {
          if (!mounted) {
            return;
          }
          await _reloginAndReload();
        });
      }
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _message = e.toString().replaceFirst('Exception: ', '');
      });
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
        });
      }
    }
  }

  Future<void> _runAction(Future<void> Function() action) async {
    if (_actionBusy) {
      return;
    }
    setState(() {
      _actionBusy = true;
      _message = null;
    });
    try {
      await action();
    } catch (e) {
      final errText = e.toString().replaceFirst('Exception: ', '');
      if (mounted) {
        setState(() {
          _message = errText;
        });
        _showNotice(errText);
      }
    } finally {
      if (mounted) {
        setState(() {
          _actionBusy = false;
        });
      }
    }
  }

  void _startResendCountdown(int seconds) {
    _countdownTimer?.cancel();
    setState(() {
      _resendCountdown = seconds;
    });
    _countdownTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }
      if (_resendCountdown <= 1) {
        timer.cancel();
        setState(() {
          _resendCountdown = 0;
        });
        return;
      }
      setState(() {
        _resendCountdown -= 1;
      });
    });
  }

  Future<void> _openExternal(String url) async {
    final uri = Uri.parse(url);
    final ok = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!ok && mounted) {
      setState(() {
        _message = 'Unable to open external link';
      });
    }
  }

  Future<void> _startSubscriptionCheckout() async {
    await _runAction(() async {
      final url = await widget.apiClient.createBillingCheckoutSession();
      await _openExternal(url);
      if (mounted) {
        setState(() {
          _message =
              'Checkout opened. Complete payment, then return and refresh.';
        });
      }
    });
  }

  Future<void> _openBillingPortal() async {
    await _runAction(() async {
      final url = await widget.apiClient.createBillingPortalSession();
      await _openExternal(url);
      if (mounted) {
        setState(() {
          _message = 'Billing portal opened.';
        });
      }
    });
  }

  Future<void> _cancelSubscription() async {
    final ok = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Cancel Subscription'),
            content: const Text(
              'Are you sure you want to cancel your subscription? It will remain active until the end of your billing period.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(false),
                child: const Text('Keep Subscription'),
              ),
              FilledButton(
                onPressed: () => Navigator.of(context).pop(true),
                child: const Text('Cancel Subscription'),
              ),
            ],
          ),
        ) ??
        false;
    if (!ok) {
      return;
    }

    await _runAction(() async {
      final message = await widget.apiClient.cancelSubscription();
      if (mounted) {
        setState(() {
          _message = message;
        });
        _showNotice(message);
      }
      await _load();
    });
  }

  Future<void> _reactivateSubscription() async {
    await _runAction(() async {
      final message = await widget.apiClient.reactivateSubscription();
      if (mounted) {
        setState(() {
          _message = message;
        });
        _showNotice(message);
      }
      await _load();
    });
  }

  Future<void> _savePhone() async {
    final rawPhone = _phoneController.text.trim();
    if (rawPhone.isEmpty) {
      setState(() {
        _message = 'Phone number is required';
      });
      return;
    }

    String normalizedPhone;
    try {
      normalizedPhone = _normalizePhoneNumber(rawPhone, _selectedPhoneCountry);
    } catch (e) {
      setState(() {
        _message = e.toString().replaceFirst('Exception: ', '');
      });
      return;
    }

    await _runAction(() async {
      final message =
          await widget.apiClient.updateAccountPhone(normalizedPhone);
      _phoneCodeController.clear();
      if (mounted) {
        setState(() {
          _message = message;
          _showPhoneEdit = false;
          _showPhoneCodeEntry = true;
        });
        _showNotice(message);
      }
      await _load();
    });
  }

  Future<void> _resendVerificationEmail() async {
    final accountEmail = _resolvedAccountEmail();
    if (accountEmail.isEmpty) {
      const msg =
          'Account email is missing. Please logout and login again so we can resend verification to the correct account.';
      setState(() {
        _message = msg;
      });
      _showNotice(msg);
      return;
    }
    await _runAction(() async {
      final apiMessage =
          await widget.apiClient.resendVerificationEmail(email: accountEmail);
      if (mounted) {
        setState(() {
          _message = apiMessage;
        });
        _showNotice(apiMessage);
      }
      await _load();
    });
  }

  Future<void> _sendPhoneCode() async {
    if (_resendCountdown > 0) {
      setState(() {
        _message =
            'Please wait $_resendCountdown seconds before requesting a new code';
      });
      return;
    }

    await _runAction(() async {
      final message = await widget.apiClient.sendPhoneVerificationCode();
      if (mounted) {
        setState(() {
          _message = message;
          _showPhoneCodeEntry = true;
        });
        _showNotice(message);
      }
      _startResendCountdown(60);
    });
  }

  Future<void> _verifyPhoneCode() async {
    final code = _phoneCodeController.text.trim();
    if (code.length != 6) {
      setState(() {
        _message = 'Please enter the 6-digit code';
      });
      return;
    }
    await _runAction(() async {
      final message = await widget.apiClient.verifyPhoneCode(code);
      _phoneCodeController.clear();
      _countdownTimer?.cancel();
      if (mounted) {
        setState(() {
          _message = message;
          _showPhoneCodeEntry = false;
          _resendCountdown = 0;
        });
        _showNotice(message);
      }
      await _load();
    });
  }

  Future<void> _cancelScreenSubscription(Map<String, dynamic> sub) async {
    final id = int.tryParse('${sub['id'] ?? 0}') ?? 0;
    final screenName =
        (sub['screen_name'] ?? sub['screen_id'] ?? 'Screen').toString();
    if (id <= 0) {
      return;
    }

    final confirmed = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: Text('Cancel "$screenName"?'),
            content: const Text(
              'The screen will be removed and billing will stop immediately. This action cannot be undone.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(false),
                child: const Text('Keep Screen'),
              ),
              FilledButton(
                onPressed: () => Navigator.of(context).pop(true),
                child: const Text('Cancel Screen'),
              ),
            ],
          ),
        ) ??
        false;
    if (!confirmed) {
      return;
    }
    if (!mounted) {
      return;
    }

    final reasonResult = await showDialog<_CancellationReasonResult>(
      context: context,
      builder: (context) => _CancellationReasonDialog(screenName: screenName),
    );
    if (reasonResult == null) {
      return;
    }

    await _runAction(() async {
      final result = await widget.apiClient.cancelScreenSubscription(
        screenSubscriptionId: id,
        reason: reasonResult.reason,
        feedback: reasonResult.feedback,
      );
      final newCount = int.tryParse('${result['new_count'] ?? ''}');
      final message = newCount == null
          ? 'Screen subscription cancelled.'
          : 'Screen subscription cancelled. Remaining screens: $newCount';
      if (mounted) {
        setState(() {
          _message = message;
        });
        _showNotice(message);
      }
      await _load();
    });
  }

  Future<void> _cancelAllScreens() async {
    final screenSubs =
        ((_account?['screen_subscriptions'] as List?) ?? const [])
            .whereType<Map>()
            .toList();
    if (screenSubs.isEmpty) {
      return;
    }

    final firstConfirm = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Cancel All Screen Subscriptions'),
            content: Text(
              'This will cancel all ${screenSubs.length} screen subscriptions immediately. All screens will be removed and billing will stop. This action cannot be undone.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(false),
                child: const Text('No'),
              ),
              FilledButton(
                onPressed: () => Navigator.of(context).pop(true),
                child: const Text('Yes, Continue'),
              ),
            ],
          ),
        ) ??
        false;
    if (!firstConfirm) {
      return;
    }
    if (!mounted) {
      return;
    }

    final doubleConfirmed = await showDialog<bool>(
      context: context,
          builder: (context) => const _DeleteAllConfirmDialog(),
        ) ??
        false;
    if (!doubleConfirmed) {
      return;
    }

    await _runAction(() async {
      final result = await widget.apiClient.cancelAllScreenSubscriptions();
      final cancelledCount = int.tryParse('${result['cancelled_count'] ?? ''}');
      final message = cancelledCount == null
          ? (result['message'] ?? 'All screen subscriptions cancelled.')
              .toString()
          : 'All $cancelledCount screen subscriptions cancelled.';
      if (mounted) {
        setState(() {
          _message = message;
        });
        _showNotice(message);
      }
      await _load();
    });
  }

  Future<void> _reloginAndReload() async {
    await widget.apiClient.logout();
    if (!mounted) {
      return;
    }
    final result = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => LoginScreen(
          apiClient: widget.apiClient,
          onLoginSuccess: () async {
            if (Navigator.of(context).canPop()) {
              Navigator.of(context).pop(true);
            }
          },
        ),
      ),
    );
    if (result == true && mounted) {
      await _load();
    }
  }

  String _resolvedAccountEmail() {
    final userInfo = Map<String, dynamic>.from(
      (_account?['user_info'] as Map?) ?? const <String, dynamic>{},
    );
    final apiEmail = (userInfo['email'] ?? '').toString().trim();
    if (apiEmail.isNotEmpty && apiEmail != '-') {
      return apiEmail;
    }
    final meEmail = (_meProfile?.username ?? '').trim();
    if (meEmail.isNotEmpty) {
      return meEmail;
    }
    final remembered = (_cachedLoginEmail ?? '').trim();
    if (remembered.isNotEmpty) {
      return remembered;
    }
    final initialUsername = (widget.initialUsername ?? '').trim();
    if (initialUsername.isNotEmpty) {
      return initialUsername;
    }
    return '';
  }

  void _applyPhoneToEditor(String phone) {
    final resolved = _resolvePhoneParts(phone);
    _selectedPhoneCountry = resolved.country;
    _phoneController.text = resolved.localNumber;
  }

  _ResolvedPhoneParts _resolvePhoneParts(String phone) {
    final clean = phone.trim();
    if (clean.isEmpty) {
      return _ResolvedPhoneParts(
        country: _phoneCountries.first,
        localNumber: '',
      );
    }

    final digits = clean.replaceAll(RegExp(r'[^0-9+]'), '');
    if (!digits.startsWith('+')) {
      return _ResolvedPhoneParts(
        country: _selectedPhoneCountry,
        localNumber: digits,
      );
    }

    final rawDigits = digits.substring(1);
    final sorted = [..._phoneCountries]
      ..sort((a, b) => b.dialDigits.length.compareTo(a.dialDigits.length));
    for (final country in sorted) {
      if (rawDigits.startsWith(country.dialDigits)) {
        var local = rawDigits.substring(country.dialDigits.length);
        if (country.usesTrunkPrefix &&
            local.isNotEmpty &&
            !local.startsWith('0')) {
          local = '0$local';
        }
        return _ResolvedPhoneParts(country: country, localNumber: local);
      }
    }

    return _ResolvedPhoneParts(
      country: _phoneCountries.first,
      localNumber: rawDigits,
    );
  }

  String _normalizePhoneNumber(String input, _PhoneCountry country) {
    final clean = input.trim();
    if (clean.isEmpty) {
      throw Exception('Phone number is required');
    }

    if (clean.startsWith('+')) {
      final full = '+${clean.replaceAll(RegExp(r'[^0-9]'), '')}';
      if (full.length < 8) {
        throw Exception('Please enter a valid phone number');
      }
      return full;
    }

    var digits = clean.replaceAll(RegExp(r'[^0-9]'), '');
    if (digits.startsWith('00')) {
      return '+${digits.substring(2)}';
    }

    if (digits.startsWith(country.dialDigits)) {
      digits = digits.substring(country.dialDigits.length);
    }

    digits = digits.replaceFirst(RegExp(r'^0+'), '');
    if (digits.length < country.minLocalDigits) {
      throw Exception('Please enter a valid phone number');
    }

    return '${country.dialCode}$digits';
  }

  _SubscriptionViewData _subscriptionViewData() {
    final subscriptionInfo = Map<String, dynamic>.from(
      (_account?['subscription_info'] as Map?) ?? const <String, dynamic>{},
    );
    final status = (subscriptionInfo['status'] ?? '').toString().toLowerCase();
    if (status == 'active') {
      return const _SubscriptionViewData(
        text: 'Active',
        badgeText: 'Active',
        valueColor: Color(0xFF166534),
        badgeBackground: Color(0xFFDCFCE7),
      );
    }
    if (status == 'trialing') {
      return const _SubscriptionViewData(
        text: 'Trial',
        badgeText: 'Trial',
        valueColor: Color(0xFF1D4ED8),
        badgeBackground: Color(0xFFDBEAFE),
      );
    }
    if (subscriptionInfo.isNotEmpty) {
      return const _SubscriptionViewData(
        text: 'Inactive',
        badgeText: 'Inactive',
        valueColor: Color(0xFF6B7280),
        badgeBackground: Color(0xFFF3F4F6),
      );
    }
    return const _SubscriptionViewData(
      text: 'No Subscription',
      badgeText: 'No Subscription',
      valueColor: Color(0xFF6B7280),
      badgeBackground: Color(0xFFF3F4F6),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final account = _account;
    final userInfo = Map<String, dynamic>.from(
      (account?['user_info'] as Map?) ?? const <String, dynamic>{},
    );
    final subscriptionInfo = Map<String, dynamic>.from(
      (account?['subscription_info'] as Map?) ?? const <String, dynamic>{},
    );
    final subscriptionView = _subscriptionViewData();
    final hasActive = account?['has_active'] == true;
    final isCanceled = account?['is_canceled'] == true;
    final nextBilling = (account?['next_billing_date'] ?? 'N/A').toString();
    final screenCount = int.tryParse('${account?['screen_count'] ?? 0}') ?? 0;
    final monthlyCost = double.tryParse('${account?['monthly_cost'] ?? 0}') ??
        (screenCount * 5).toDouble();
    final phone = (account?['phone_number'] ?? '').toString();
    final phoneVerified = account?['phone_verified'] == true;
    final email = _resolvedAccountEmail();
    final emailVerified = userInfo['email_verified'] == true;
    final isAdmin = userInfo['is_admin'] == true;
    final accountCreated =
        (account?['account_created'] ?? 'Unknown').toString();
    final isTrial = account?['is_trial'] == true;
    final trialDaysLeft = int.tryParse('${account?['trial_days_left'] ?? ''}');
    final screenSubs = ((account?['screen_subscriptions'] as List?) ?? const [])
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .toList();
    final billingHistory = ((account?['billing_history'] as List?) ?? const [])
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .toList();

    final currentPeriod = subscriptionInfo.isNotEmpty &&
            subscriptionInfo['current_period_end'] != null
        ? 'Until $nextBilling'
        : 'No active period';
    final autoRenew = isCanceled
        ? 'Canceled (ends $nextBilling)'
        : (hasActive ? 'Enabled' : 'N/A');

    return Scaffold(
      appBar: AppBar(
        title: const Text('My Account'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _actionBusy ? null : _load,
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : ListView(
                children: [
                  Text(
                    'Manage your subscription and billing information',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                  if (isTrial && trialDaysLeft != null) ...[
                    const SizedBox(height: 12),
                    _TrialBanner(daysLeft: trialDaysLeft),
                  ],
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    children: [
                      _statBox(
                        context,
                        label: 'Subscription Status',
                        value: subscriptionView.text,
                        valueColor: subscriptionView.valueColor,
                        badge: _StatusBadge(
                          text: subscriptionView.badgeText,
                          background: subscriptionView.badgeBackground,
                          foreground: subscriptionView.valueColor,
                        ),
                      ),
                      _statBox(
                        context,
                        label: 'Next Billing Date',
                        value: nextBilling,
                      ),
                      _statBox(
                        context,
                        label: 'Active Screens',
                        value: '$screenCount',
                      ),
                      _statBox(
                        context,
                        label: 'Monthly Cost',
                        value: '\$${monthlyCost.toStringAsFixed(2)}',
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(14),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Subscription Details',
                              style: theme.textTheme.titleMedium),
                          const SizedBox(height: 12),
                          _kvRow(context, 'Plan', '\$5 per screen / month'),
                          const SizedBox(height: 8),
                          _kvRow(context, 'Current Period', currentPeriod),
                          const SizedBox(height: 8),
                          _kvRow(context, 'Auto-renew', autoRenew),
                          const SizedBox(height: 14),
                          if (hasActive)
                            FilledButton(
                              onPressed:
                                  _actionBusy ? null : _openBillingPortal,
                              child: const Text('Manage Subscription'),
                            )
                          else
                            FilledButton(
                              onPressed: _actionBusy
                                  ? null
                                  : () {
                                      if (!emailVerified) {
                                        const msg =
                                            'Please verify your email address before subscribing.';
                                        setState(() {
                                          _message = msg;
                                        });
                                        _showNotice(msg);
                                        return;
                                      }
                                      if (phone.isEmpty || !phoneVerified) {
                                        const msg =
                                            'Please verify your phone number before subscribing.';
                                        setState(() {
                                          _message = msg;
                                        });
                                        _showNotice(msg);
                                        return;
                                      }
                                      _startSubscriptionCheckout();
                                    },
                              child: const Text('Subscribe Now'),
                            ),
                          const SizedBox(height: 8),
                          if (hasActive && !isCanceled)
                            OutlinedButton(
                              onPressed:
                                  _actionBusy ? null : _cancelSubscription,
                              child: const Text('Cancel Subscription'),
                            ),
                          if (hasActive && isCanceled)
                            OutlinedButton(
                              onPressed:
                                  _actionBusy ? null : _reactivateSubscription,
                              child: const Text('Reactivate Subscription'),
                            ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 10),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(14),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Account Information',
                              style: theme.textTheme.titleMedium),
                          const SizedBox(height: 10),
                          _emailInfoRow(
                            context,
                            email: email,
                            emailVerified: emailVerified,
                          ),
                          const SizedBox(height: 8),
                          _kvRow(context, 'Account Type',
                              isAdmin ? 'Administrator' : 'Standard User'),
                          const SizedBox(height: 8),
                          _kvRow(context, 'Member Since', accountCreated),
                          const SizedBox(height: 8),
                          _kvRow(context, 'Total Screens', '$screenCount'),
                          const SizedBox(height: 8),
                          Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Expanded(
                                child: Text(
                                  'Phone Number',
                                  style: TextStyle(
                                    color: scheme.onSurfaceVariant,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ),
                              Flexible(
                                flex: 2,
                                child: Wrap(
                                  alignment: WrapAlignment.end,
                                  spacing: 8,
                                  runSpacing: 6,
                                  children: [
                                    Text(
                                      phone.isEmpty ? 'Not set' : phone,
                                      textAlign: TextAlign.right,
                                      style: TextStyle(
                                        color: phone.isEmpty
                                            ? scheme.onSurfaceVariant
                                            : scheme.onSurface,
                                        fontWeight: FontWeight.w600,
                                      ),
                                    ),
                                    if (phone.isNotEmpty)
                                      _StatusBadge(
                                        text: phoneVerified
                                            ? 'Verified'
                                            : 'Not verified',
                                        background: phoneVerified
                                            ? const Color(0xFFDCFCE7)
                                            : const Color(0xFFFEF3C7),
                                        foreground: phoneVerified
                                            ? const Color(0xFF166534)
                                            : const Color(0xFF92400E),
                                      ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                          if (_showPhoneEdit) ...[
                            const SizedBox(height: 14),
                            Container(
                              padding: const EdgeInsets.all(14),
                              decoration: BoxDecoration(
                                color: scheme.surfaceContainerLow,
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      SizedBox(
                                        width: 138,
                                        child: DropdownButtonFormField<
                                            _PhoneCountry>(
                                          value: _selectedPhoneCountry,
                                          decoration: const InputDecoration(
                                            labelText: 'Country',
                                          ),
                                          isExpanded: true,
                                          items: _phoneCountries
                                              .map(
                                                (country) => DropdownMenuItem<
                                                    _PhoneCountry>(
                                                  value: country,
                                                  child: Text(country.label),
                                                ),
                                              )
                                              .toList(),
                                          onChanged: _actionBusy
                                              ? null
                                              : (value) {
                                                  if (value == null) {
                                                    return;
                                                  }
                                                  setState(() {
                                                    _selectedPhoneCountry =
                                                        value;
                                                  });
                                                },
                                        ),
                                      ),
                                      const SizedBox(width: 10),
                                      Expanded(
                                        child: TextField(
                                          controller: _phoneController,
                                          keyboardType: TextInputType.phone,
                                          decoration: InputDecoration(
                                            labelText: 'Phone number',
                                            hintText:
                                                _selectedPhoneCountry.example,
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 8),
                                  Text(
                                    'Choose your country code, then enter the phone number with or without the starting 0. We will format it automatically.',
                                    style: theme.textTheme.bodySmall?.copyWith(
                                      color: scheme.onSurfaceVariant,
                                    ),
                                  ),
                                  const SizedBox(height: 12),
                                  Row(
                                    children: [
                                      Expanded(
                                        child: FilledButton(
                                          onPressed:
                                              _actionBusy ? null : _savePhone,
                                          child: const Text('Save Phone'),
                                        ),
                                      ),
                                      const SizedBox(width: 8),
                                      Expanded(
                                        child: OutlinedButton(
                                          onPressed: _actionBusy
                                              ? null
                                              : () {
                                                  setState(() {
                                                    _showPhoneEdit = false;
                                                    _applyPhoneToEditor(phone);
                                                  });
                                                },
                                          child: const Text('Cancel'),
                                        ),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                            ),
                          ],
                          if (phone.isNotEmpty && !phoneVerified) ...[
                            const SizedBox(height: 14),
                            Container(
                              padding: const EdgeInsets.all(14),
                              decoration: BoxDecoration(
                                color: const Color(0xFFFEF3C7),
                                borderRadius: BorderRadius.circular(12),
                                border: Border.all(
                                  color: const Color(0xFFFBBF24),
                                ),
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'Verify Your Phone Number',
                                    style: theme.textTheme.titleSmall?.copyWith(
                                      color: const Color(0xFF92400E),
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  Text(
                                    'We will send a 6-digit verification code to $phone.',
                                    style: theme.textTheme.bodySmall?.copyWith(
                                      color: const Color(0xFF78350F),
                                    ),
                                  ),
                                  if (_showPhoneCodeEntry) ...[
                                    const SizedBox(height: 12),
                                    TextField(
                                      controller: _phoneCodeController,
                                      maxLength: 6,
                                      keyboardType: TextInputType.number,
                                      textAlign: TextAlign.center,
                                      decoration: const InputDecoration(
                                        labelText: 'Enter verification code',
                                        counterText: '',
                                      ),
                                    ),
                                  ],
                                  const SizedBox(height: 12),
                                  if (!_showPhoneCodeEntry)
                                    FilledButton(
                                      onPressed:
                                          _actionBusy ? null : _sendPhoneCode,
                                      style: FilledButton.styleFrom(
                                        backgroundColor:
                                            const Color(0xFFF59E0B),
                                      ),
                                      child: Text(_resendCountdown > 0
                                          ? 'Resend in $_resendCountdown s'
                                          : 'Send Verification Code'),
                                    )
                                  else ...[
                                    FilledButton(
                                      onPressed:
                                          _actionBusy ? null : _verifyPhoneCode,
                                      style: FilledButton.styleFrom(
                                        backgroundColor:
                                            const Color(0xFF10B981),
                                      ),
                                      child: const Text('Verify Code'),
                                    ),
                                    const SizedBox(height: 8),
                                    OutlinedButton(
                                      onPressed:
                                          (_actionBusy || _resendCountdown > 0)
                                              ? null
                                              : _sendPhoneCode,
                                      child: Text(_resendCountdown > 0
                                          ? 'Resend available in $_resendCountdown s'
                                          : 'Resend Code'),
                                    ),
                                  ],
                                ],
                              ),
                            ),
                          ],
                          const SizedBox(height: 14),
                          OutlinedButton(
                            onPressed: _actionBusy
                                ? null
                                : () {
                                    setState(() {
                                      _showPhoneEdit = !_showPhoneEdit;
                                      if (!_showPhoneEdit) {
                                        _applyPhoneToEditor(phone);
                                      } else {
                                        _applyPhoneToEditor(phone);
                                      }
                                    });
                                  },
                            child: Text(
                              phone.isEmpty
                                  ? 'Add Phone Number'
                                  : 'Update Phone Number',
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  if (screenSubs.isNotEmpty) ...[
                    const SizedBox(height: 10),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(14),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Manage Screen Subscriptions',
                                style: theme.textTheme.titleMedium),
                            const SizedBox(height: 8),
                            Text(
                              'Each screen has its own subscription billed individually at \$5/month. Cancel any screen subscription at any time.',
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: scheme.onSurfaceVariant,
                              ),
                            ),
                            const SizedBox(height: 12),
                            ...screenSubs.map((sub) {
                              final title = (sub['screen_name'] ??
                                      sub['screen_id'] ??
                                      '-')
                                  .toString();
                              final status = (sub['status'] ?? '-')
                                  .toString()
                                  .toLowerCase();
                              final storeId =
                                  (sub['store_id'] ?? '-').toString();
                              final nextScreenBilling =
                                  (sub['next_billing'] ?? '').toString();
                              final billingStart =
                                  (sub['billing_start'] ?? '').toString();
                              final cancelAtPeriodEnd =
                                  sub['cancel_at_period_end'] == true;
                              return Container(
                                margin: const EdgeInsets.only(bottom: 10),
                                padding: const EdgeInsets.all(12),
                                decoration: BoxDecoration(
                                  borderRadius: BorderRadius.circular(12),
                                  border:
                                      Border.all(color: scheme.outlineVariant),
                                  color: scheme.surfaceContainerLow,
                                ),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Row(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Expanded(
                                          child: Column(
                                            crossAxisAlignment:
                                                CrossAxisAlignment.start,
                                            children: [
                                              Text(
                                                title,
                                                style: theme
                                                    .textTheme.titleSmall
                                                    ?.copyWith(
                                                  fontWeight: FontWeight.w700,
                                                ),
                                              ),
                                              const SizedBox(height: 6),
                                              Wrap(
                                                spacing: 8,
                                                runSpacing: 6,
                                                children: [
                                                  Text('Store: $storeId'),
                                                  _statusForScreen(status),
                                                  if (cancelAtPeriodEnd &&
                                                      nextScreenBilling
                                                          .isNotEmpty)
                                                    Text(
                                                      'Cancels on $nextScreenBilling',
                                                      style: const TextStyle(
                                                        color:
                                                            Color(0xFFB45309),
                                                        fontWeight:
                                                            FontWeight.w600,
                                                      ),
                                                    ),
                                                ],
                                              ),
                                              if (billingStart.isNotEmpty ||
                                                  nextScreenBilling.isNotEmpty)
                                                Padding(
                                                  padding:
                                                      const EdgeInsets.only(
                                                          top: 6),
                                                  child: Wrap(
                                                    spacing: 12,
                                                    runSpacing: 6,
                                                    children: [
                                                      if (billingStart
                                                          .isNotEmpty)
                                                        Text(
                                                            'Started: $billingStart'),
                                                      if (nextScreenBilling
                                                              .isNotEmpty &&
                                                          !cancelAtPeriodEnd)
                                                        Text(
                                                            'Next billing: $nextScreenBilling'),
                                                    ],
                                                  ),
                                                ),
                                            ],
                                          ),
                                        ),
                                        const SizedBox(width: 8),
                                        Column(
                                          crossAxisAlignment:
                                              CrossAxisAlignment.end,
                                          children: [
                                            const Text(
                                              '\$5.00/mo',
                                              style: TextStyle(
                                                color: Color(0xFF10B981),
                                                fontWeight: FontWeight.w700,
                                              ),
                                            ),
                                            const SizedBox(height: 8),
                                            if (status != 'canceled' &&
                                                status != 'incomplete_expired')
                                              OutlinedButton(
                                                onPressed: _actionBusy
                                                    ? null
                                                    : () =>
                                                        _cancelScreenSubscription(
                                                            sub),
                                                child: const Text('Cancel'),
                                              )
                                            else
                                              Text(
                                                'Cancelled',
                                                style: TextStyle(
                                                  color:
                                                      scheme.onSurfaceVariant,
                                                  fontStyle: FontStyle.italic,
                                                ),
                                              ),
                                          ],
                                        ),
                                      ],
                                    ),
                                  ],
                                ),
                              );
                            }),
                            Container(
                              width: double.infinity,
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: const Color(0xFFFEF3C7),
                                borderRadius: BorderRadius.circular(12),
                                border: Border.all(
                                  color: const Color(0xFFFDE68A),
                                ),
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Text(
                                    'Cancel All Screen Subscriptions',
                                    style: TextStyle(
                                      color: Color(0xFF92400E),
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                  const SizedBox(height: 6),
                                  Text(
                                    'This will immediately cancel all ${screenSubs.length} screen subscriptions and remove all screens. Each subscription will stop billing. This action cannot be undone.',
                                    style: theme.textTheme.bodySmall?.copyWith(
                                      color: const Color(0xFF92400E),
                                    ),
                                  ),
                                  const SizedBox(height: 10),
                                  FilledButton(
                                    onPressed:
                                        _actionBusy ? null : _cancelAllScreens,
                                    style: FilledButton.styleFrom(
                                      backgroundColor: const Color(0xFFDC2626),
                                    ),
                                    child: Text(
                                        'Cancel All ${screenSubs.length} Subscriptions'),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                  if (billingHistory.isNotEmpty) ...[
                    const SizedBox(height: 10),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(14),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Invoice History',
                                style: theme.textTheme.titleMedium),
                            const SizedBox(height: 8),
                            ...billingHistory.map((inv) {
                              final date = (inv['date'] ?? '-').toString();
                              final amount = (inv['amount'] ?? '-').toString();
                              final status = (inv['status'] ?? '-')
                                  .toString()
                                  .toLowerCase();
                              final pdfUrl =
                                  (inv['invoice_pdf'] ?? '').toString();
                              final hostedUrl =
                                  (inv['hosted_invoice_url'] ?? '').toString();
                              return Container(
                                margin: const EdgeInsets.only(bottom: 8),
                                padding: const EdgeInsets.all(10),
                                decoration: BoxDecoration(
                                  borderRadius: BorderRadius.circular(10),
                                  border:
                                      Border.all(color: scheme.outlineVariant),
                                ),
                                child: Row(
                                  children: [
                                    Expanded(
                                      child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Text(date),
                                          const SizedBox(height: 4),
                                          Wrap(
                                            spacing: 8,
                                            runSpacing: 6,
                                            children: [
                                              Text(
                                                amount,
                                                style: const TextStyle(
                                                  color: Color(0xFF10B981),
                                                  fontWeight: FontWeight.w700,
                                                ),
                                              ),
                                              _statusForInvoice(status),
                                            ],
                                          ),
                                        ],
                                      ),
                                    ),
                                    if (pdfUrl.isNotEmpty)
                                      TextButton(
                                        onPressed: () => _openExternal(pdfUrl),
                                        child: const Text('PDF'),
                                      )
                                    else if (hostedUrl.isNotEmpty)
                                      TextButton(
                                        onPressed: () =>
                                            _openExternal(hostedUrl),
                                        child: const Text('Open'),
                                      ),
                                  ],
                                ),
                              );
                            }),
                          ],
                        ),
                      ),
                    ),
                  ],
                  if (_message != null) ...[
                    const SizedBox(height: 10),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: scheme.surfaceContainer,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(_message!),
                    ),
                  ],
                ],
              ),
      ),
    );
  }

  Widget _kvRow(BuildContext context, String key, String value) {
    final scheme = Theme.of(context).colorScheme;
    return Row(
      children: [
        Expanded(
          child: Text(
            key,
            style: TextStyle(
              color: scheme.onSurfaceVariant,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
        Expanded(
          child: Text(
            value,
            textAlign: TextAlign.right,
            style: const TextStyle(fontWeight: FontWeight.w600),
          ),
        ),
      ],
    );
  }

  Widget _emailInfoRow(BuildContext context,
      {required String email, required bool emailVerified}) {
    final scheme = Theme.of(context).colorScheme;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Expanded(
          child: Text(
            'Email',
            style: TextStyle(
              color: scheme.onSurfaceVariant,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
        Flexible(
          flex: 2,
          child: Wrap(
            alignment: WrapAlignment.end,
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 8,
            runSpacing: 6,
            children: [
              Text(
                email.isEmpty ? '-' : email,
                textAlign: TextAlign.right,
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
              _StatusBadge(
                text: emailVerified ? 'Verified' : 'Not verified',
                background: emailVerified
                    ? const Color(0xFFDCFCE7)
                    : const Color(0xFFFEF3C7),
                foreground: emailVerified
                    ? const Color(0xFF166534)
                    : const Color(0xFF92400E),
              ),
              if (!emailVerified)
                TextButton(
                  onPressed: _actionBusy ? null : _resendVerificationEmail,
                  style: TextButton.styleFrom(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    minimumSize: const Size(0, 0),
                  ),
                  child: const Text('Resend Verification Email'),
                ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _statusForScreen(String status) {
    switch (status) {
      case 'active':
        return const _StatusBadge(
          text: 'active',
          background: Color(0xFFD1FAE5),
          foreground: Color(0xFF059669),
        );
      case 'trialing':
        return const _StatusBadge(
          text: 'trialing',
          background: Color(0xFFDBEAFE),
          foreground: Color(0xFF1E40AF),
        );
      case 'canceled':
        return const _StatusBadge(
          text: 'canceled',
          background: Color(0xFFFEE2E2),
          foreground: Color(0xFFDC2626),
        );
      default:
        return _StatusBadge(
          text: status,
          background: const Color(0xFFF3F4F6),
          foreground: const Color(0xFF6B7280),
        );
    }
  }

  Widget _statusForInvoice(String status) {
    switch (status) {
      case 'paid':
        return const _StatusBadge(
          text: 'paid',
          background: Color(0xFFD1FAE5),
          foreground: Color(0xFF059669),
        );
      case 'open':
        return const _StatusBadge(
          text: 'open',
          background: Color(0xFFFEF3C7),
          foreground: Color(0xFFD97706),
        );
      default:
        return _StatusBadge(
          text: status,
          background: const Color(0xFFF3F4F6),
          foreground: const Color(0xFF6B7280),
        );
    }
  }

  Widget _statBox(
    BuildContext context, {
    required String label,
    required String value,
    Color? valueColor,
    Widget? badge,
  }) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      width: 156,
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 11,
              color: scheme.onSurfaceVariant,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 6),
          if (badge != null) ...[
            badge,
            const SizedBox(height: 6),
          ],
          Text(
            value,
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w700,
              color: valueColor,
            ),
          ),
        ],
      ),
    );
  }
}

class _PhoneCountry {
  const _PhoneCountry({
    required this.name,
    required this.dialCode,
    required this.example,
    required this.usesTrunkPrefix,
    this.minLocalDigits = 6,
  });

  final String name;
  final String dialCode;
  final String example;
  final bool usesTrunkPrefix;
  final int minLocalDigits;

  String get dialDigits => dialCode.replaceAll('+', '');
  String get label => '$name ($dialCode)';
}

class _ResolvedPhoneParts {
  const _ResolvedPhoneParts({
    required this.country,
    required this.localNumber,
  });

  final _PhoneCountry country;
  final String localNumber;
}

const List<_PhoneCountry> _phoneCountries = [
  _PhoneCountry(
    name: 'Australia',
    dialCode: '+61',
    example: '0400 000 000',
    usesTrunkPrefix: true,
    minLocalDigits: 9,
  ),
  _PhoneCountry(
    name: 'New Zealand',
    dialCode: '+64',
    example: '020 000 0000',
    usesTrunkPrefix: true,
    minLocalDigits: 8,
  ),
  _PhoneCountry(
    name: 'United States',
    dialCode: '+1',
    example: '000 000 0000',
    usesTrunkPrefix: false,
    minLocalDigits: 10,
  ),
  _PhoneCountry(
    name: 'United Kingdom',
    dialCode: '+44',
    example: '07000 000000',
    usesTrunkPrefix: true,
    minLocalDigits: 9,
  ),
  _PhoneCountry(
    name: 'Singapore',
    dialCode: '+65',
    example: '0000 0000',
    usesTrunkPrefix: false,
    minLocalDigits: 8,
  ),
  _PhoneCountry(
    name: 'Malaysia',
    dialCode: '+60',
    example: '010 000 0000',
    usesTrunkPrefix: true,
    minLocalDigits: 8,
  ),
  _PhoneCountry(
    name: 'Indonesia',
    dialCode: '+62',
    example: '0800 0000 0000',
    usesTrunkPrefix: true,
    minLocalDigits: 8,
  ),
  _PhoneCountry(
    name: 'Philippines',
    dialCode: '+63',
    example: '0900 000 0000',
    usesTrunkPrefix: true,
    minLocalDigits: 9,
  ),
  _PhoneCountry(
    name: 'India',
    dialCode: '+91',
    example: '00000 00000',
    usesTrunkPrefix: true,
    minLocalDigits: 10,
  ),
];

class _TrialBanner extends StatelessWidget {
  const _TrialBanner({required this.daysLeft});

  final int daysLeft;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        gradient: const LinearGradient(
          colors: [Color(0xFF1D4ED8), Color(0xFF7C3AED)],
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Free Trial Active',
            style: theme.textTheme.titleMedium?.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '$daysLeft days remaining',
            style: theme.textTheme.headlineSmall?.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            'Enjoy full access to all features during your trial period.',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: Colors.white.withValues(alpha: 0.92),
            ),
          ),
        ],
      ),
    );
  }
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({
    required this.text,
    required this.background,
    required this.foreground,
  });

  final String text;
  final Color background;
  final Color foreground;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: foreground,
          fontWeight: FontWeight.w700,
          fontSize: 12,
        ),
      ),
    );
  }
}

class _SubscriptionViewData {
  const _SubscriptionViewData({
    required this.text,
    required this.badgeText,
    required this.valueColor,
    required this.badgeBackground,
  });

  final String text;
  final String badgeText;
  final Color valueColor;
  final Color badgeBackground;
}

class _CancellationReasonResult {
  const _CancellationReasonResult({
    required this.reason,
    required this.feedback,
  });

  final String reason;
  final String feedback;
}

class _CancellationReasonDialog extends StatefulWidget {
  const _CancellationReasonDialog({required this.screenName});

  final String screenName;

  @override
  State<_CancellationReasonDialog> createState() =>
      _CancellationReasonDialogState();
}

class _CancellationReasonDialogState extends State<_CancellationReasonDialog> {
  static const _presetReasons = <String>[
    'I found an alternative',
    'I no longer need it',
    'It\'s too expensive',
    'Other reason',
  ];

  String _selectedReason = _presetReasons.first;
  final TextEditingController _feedbackController = TextEditingController();

  @override
  void dispose() {
    _feedbackController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text('Why cancel "${widget.screenName}"?'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ..._presetReasons.map(
              (reason) => RadioListTile<String>(
                value: reason,
                groupValue: _selectedReason,
                contentPadding: EdgeInsets.zero,
                title: Text(reason),
                onChanged: (value) {
                  if (value == null) {
                    return;
                  }
                  setState(() {
                    _selectedReason = value;
                  });
                },
              ),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _feedbackController,
              maxLines: 3,
              decoration: InputDecoration(
                labelText: _selectedReason == 'Other reason'
                    ? 'Tell us more'
                    : 'Optional feedback',
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(
            _CancellationReasonResult(
              reason: _selectedReason,
              feedback: _feedbackController.text.trim(),
            ),
          ),
          child: const Text('Continue'),
        ),
      ],
    );
  }
}

class _DeleteAllConfirmDialog extends StatefulWidget {
  const _DeleteAllConfirmDialog();

  @override
  State<_DeleteAllConfirmDialog> createState() =>
      _DeleteAllConfirmDialogState();
}

class _DeleteAllConfirmDialogState extends State<_DeleteAllConfirmDialog> {
  final TextEditingController _confirmController = TextEditingController();

  @override
  void dispose() {
    _confirmController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final canDelete = _confirmController.text == 'DELETE ALL';
    return AlertDialog(
      title: const Text('Final Confirmation'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Type DELETE ALL to confirm this action.'),
          const SizedBox(height: 10),
          TextField(
            controller: _confirmController,
            onChanged: (_) => setState(() {}),
            decoration: const InputDecoration(
              labelText: 'DELETE ALL',
            ),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: canDelete ? () => Navigator.of(context).pop(true) : null,
          child: const Text('Delete All'),
        ),
      ],
    );
  }
}

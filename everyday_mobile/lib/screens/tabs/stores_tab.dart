import 'dart:async';
import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:video_player/video_player.dart';

import '../account_page.dart';
import '../../models/app_models.dart';
import '../../services/api_client.dart';

class StoresTab extends StatefulWidget {
  const StoresTab({
    super.key,
    required this.apiClient,
    required this.selectedStoreId,
    required this.selectedScreenId,
    required this.onSelectionChanged,
  });

  final ApiClient apiClient;
  final String? selectedStoreId;
  final String? selectedScreenId;
  final void Function(String? storeId, String? screenId) onSelectionChanged;

  @override
  State<StoresTab> createState() => _StoresTabState();
}

class _StoresTabState extends State<StoresTab> {
  bool _loading = true;
  String? _error;
  List<StoreItem> _stores = const [];
  List<ScreenItem> _screens = const [];
  Map<String, String> _screenStatus = const {};
  final Map<String, Future<_ScreenCardPreviewData>> _screenPreviewUrlFutures =
      {};

  bool _isPhoneVerificationError(String? message) {
    final text = (message ?? '').toLowerCase();
    return text.contains('verify your phone number');
  }

  Future<void> _openAccountCenter() async {
    if (!mounted) {
      return;
    }
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => AccountPage(apiClient: widget.apiClient),
      ),
    );
    if (mounted) {
      await _loadStores();
    }
  }

  @override
  void initState() {
    super.initState();
    _loadStores();
  }

  Future<void> _loadStores() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final stores = await widget.apiClient.getStores();
      String? storeId = widget.selectedStoreId;
      if (storeId == null || stores.every((s) => s.id != storeId)) {
        storeId = stores.isNotEmpty ? stores.first.id : null;
      }

      List<ScreenItem> screens = const [];
      String? screenId = widget.selectedScreenId;
      if (storeId != null) {
        screens = await widget.apiClient.getScreens(storeId);
        _screenStatus = await widget.apiClient.getScreenStatus(storeId);
        if (screenId == null || screens.every((s) => s.id != screenId)) {
          screenId = screens.isNotEmpty ? screens.first.id : null;
        }
      } else {
        screenId = null;
        _screenStatus = const {};
      }

      if (!mounted) {
        return;
      }
      setState(() {
        _stores = stores;
        _screens = screens;
        _screenPreviewUrlFutures.clear();
      });
      widget.onSelectionChanged(storeId, screenId);
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
          _loading = false;
        });
      }
    }
  }

  Future<void> _onSelectStore(String? storeId) async {
    if (storeId == null) {
      widget.onSelectionChanged(null, null);
      setState(() {
        _screens = const [];
      });
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final screens = await widget.apiClient.getScreens(storeId);
      final status = await widget.apiClient.getScreenStatus(storeId);
      final screenId = screens.isNotEmpty ? screens.first.id : null;
      if (!mounted) {
        return;
      }
      setState(() {
        _screens = screens;
        _screenStatus = status;
        _screenPreviewUrlFutures.clear();
      });
      widget.onSelectionChanged(storeId, screenId);
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
          _loading = false;
        });
      }
    }
  }

  Future<void> _addStore() async {
    final idController = TextEditingController();
    final nameController = TextEditingController();
    void disposeControllersSafely() {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        idController.dispose();
        nameController.dispose();
      });
    }

    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Add Store'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: idController,
              decoration: const InputDecoration(labelText: 'Store ID'),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: nameController,
              decoration: const InputDecoration(labelText: 'Store Name'),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Add'),
          ),
        ],
      ),
    );

    if (accepted != true) {
      disposeControllersSafely();
      return;
    }

    final storeId = idController.text.trim();
    final storeName = nameController.text.trim();
    disposeControllersSafely();

    if (storeId.isEmpty || storeName.isEmpty) {
      setState(() {
        _error = 'Store ID and Store Name are required.';
      });
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await widget.apiClient.addStore(storeId: storeId, storeName: storeName);
      await _loadStores();
      widget.onSelectionChanged(storeId, null);
      await _onSelectStore(storeId);
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = e.toString().replaceFirst('Exception: ', '');
        _loading = false;
      });
    }
  }

  Future<void> _deleteSelectedStore() async {
    final storeId = widget.selectedStoreId;
    if (storeId == null) {
      return;
    }

    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Store'),
        content: Text('Delete store $storeId and all related screens?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (accepted != true) {
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await widget.apiClient.deleteStore(storeId);
      await _loadStores();
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = e.toString().replaceFirst('Exception: ', '');
        _loading = false;
      });
    }
  }

  Future<void> _addScreen() async {
    final storeId = widget.selectedStoreId;
    if (storeId == null) {
      return;
    }

    final canProceed = await _checkSubscriptionBeforeAddScreen();
    if (!canProceed) {
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final newScreenId = await widget.apiClient.addScreen(storeId: storeId);
      final screens = await widget.apiClient.getScreens(storeId);
      final status = await widget.apiClient.getScreenStatus(storeId);
      if (!mounted) {
        return;
      }
      setState(() {
        _screens = screens;
        _screenStatus = status;
        _loading = false;
      });
      widget.onSelectionChanged(
          storeId, newScreenId.isEmpty ? null : newScreenId);
    } catch (e) {
      final message = e.toString().replaceFirst('Exception: ', '');
      if (message.toLowerCase().contains('subscription required')) {
        await _openSubscriptionPromptFromServer();
      }
      if (!mounted) {
        return;
      }
      setState(() {
        _error = message;
        _loading = false;
      });
    }
  }

  Future<bool> _checkSubscriptionBeforeAddScreen() async {
    try {
      final summary = await widget.apiClient.getSubscriptionSummary();
      final requires = summary['requires_subscription'] == true;
      if (!requires) {
        return true;
      }
      await _showSubscriptionSheet(summary);
      return false;
    } catch (_) {
      // If summary endpoint is unavailable, keep current behavior and let
      // add_screen server-side validation enforce access.
      return true;
    }
  }

  Future<void> _openSubscriptionPromptFromServer() async {
    try {
      final summary = await widget.apiClient.getSubscriptionSummary();
      if (!mounted) {
        return;
      }
      await _showSubscriptionSheet(summary);
    } catch (_) {
      // Ignore and keep error text in UI.
    }
  }

  Future<void> _showSubscriptionSheet(Map<String, dynamic> summary) async {
    if (!mounted) {
      return;
    }
    final priceDisplay =
        (summary['price_display'] ?? r'$5 per screen / month').toString();
    final trialDays = int.tryParse('${summary['trial_days'] ?? 14}') ?? 14;

    await showModalBottomSheet<void>(
      context: context,
      useSafeArea: true,
      isScrollControlled: true,
      builder: (context) {
        var busy = false;
        return StatefulBuilder(
          builder: (context, setModalState) {
            Future<void> startCheckout() async {
              if (busy) {
                return;
              }
              setModalState(() {
                busy = true;
              });
              try {
                final checkoutUrl =
                    await widget.apiClient.createBillingCheckoutSession();
                final uri = Uri.parse(checkoutUrl);
                final launched =
                    await launchUrl(uri, mode: LaunchMode.externalApplication);
                if (!launched && mounted) {
                  setState(() {
                    _error = 'Unable to open checkout link.';
                  });
                }
                if (context.mounted) {
                  Navigator.of(context).pop();
                }
              } catch (e) {
                if (mounted) {
                  setState(() {
                    _error = e.toString().replaceFirst('Exception: ', '');
                  });
                }
              } finally {
                if (context.mounted) {
                  setModalState(() {
                    busy = false;
                  });
                }
              }
            }

            return Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 20),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Activate Your Screens',
                      style: Theme.of(context).textTheme.headlineSmall),
                  const SizedBox(height: 8),
                  Text(
                    'Secure checkout powered by Stripe keeps your menu boards online 24/7.',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant),
                  ),
                  const SizedBox(height: 14),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(12),
                      color: Theme.of(context).colorScheme.primaryContainer,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          priceDisplay,
                          style: Theme.of(context)
                              .textTheme
                              .headlineMedium
                              ?.copyWith(fontWeight: FontWeight.w800),
                        ),
                        const SizedBox(height: 6),
                        Text('$trialDays-day free trial. Cancel anytime.'),
                        const SizedBox(height: 10),
                        const Text('• Unlimited menu updates'),
                        const Text('• Perfectly synchronized screens'),
                        const Text('• Full HD/4K video support'),
                        const Text('• Instant Pi/Android pairing'),
                      ],
                    ),
                  ),
                  const SizedBox(height: 14),
                  FilledButton(
                    onPressed: busy ? null : startCheckout,
                    child: Text(
                      busy
                          ? 'Opening checkout...'
                          : 'Start Subscription Securely',
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text('Skip for now'),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  Future<void> _renameScreen(ScreenItem screen) async {
    final storeId = widget.selectedStoreId;
    if (storeId == null) {
      return;
    }

    final controller = TextEditingController(text: screen.name);
    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Rename Screen'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(labelText: 'Screen Name'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Save'),
          ),
        ],
      ),
    );
    if (accepted != true) {
      controller.dispose();
      return;
    }
    final name = controller.text.trim();
    controller.dispose();
    if (name.isEmpty) {
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await widget.apiClient.renameScreen(
        storeId: storeId,
        screenId: screen.id,
        name: name,
      );
      final screens = await widget.apiClient.getScreens(storeId);
      if (!mounted) {
        return;
      }
      setState(() {
        _screens = screens;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = e.toString().replaceFirst('Exception: ', '');
        _loading = false;
      });
    }
  }

  Future<void> _deleteScreen(ScreenItem screen) async {
    final storeId = widget.selectedStoreId;
    if (storeId == null) {
      return;
    }

    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Screen'),
        content: Text('Delete screen ${screen.id}?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (accepted != true) {
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await widget.apiClient
          .deleteScreen(storeId: storeId, screenId: screen.id);
      final screens = await widget.apiClient.getScreens(storeId);
      final status = await widget.apiClient.getScreenStatus(storeId);
      if (!mounted) {
        return;
      }
      setState(() {
        _screens = screens;
        _screenStatus = status;
        _loading = false;
      });
      final selectedScreenId = widget.selectedScreenId;
      if (selectedScreenId == screen.id) {
        widget.onSelectionChanged(
            storeId, screens.isNotEmpty ? screens.first.id : null);
      }
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = e.toString().replaceFirst('Exception: ', '');
        _loading = false;
      });
    }
  }

  Widget _buildStatusBadge(String screenId) {
    final status = (_screenStatus[screenId] ?? 'offline').toLowerCase();
    final online = status == 'online';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: online ? const Color(0xFFDCFCE7) : const Color(0xFFFEE2E2),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        online ? 'Online' : 'Offline',
        style: TextStyle(
          color: online ? const Color(0xFF166534) : const Color(0xFF991B1B),
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  String _encodePathPreservingSlashes(String path) {
    return path
        .split('/')
        .where((s) => s.trim().isNotEmpty)
        .map(Uri.encodeComponent)
        .join('/');
  }

  String _toAbsoluteUrlForPreview(String value) {
    final text = value.trim();
    if (text.isEmpty) {
      return '';
    }
    if (text.startsWith('http://') || text.startsWith('https://')) {
      return text;
    }
    final base = widget.apiClient.baseUrl.replaceAll(RegExp(r'/$'), '');
    if (text.startsWith('/')) {
      return '$base$text';
    }
    return '$base/$text';
  }

  Future<_ScreenCardPreviewData> _loadScreenCardPreviewData({
    required String storeId,
    required String screenId,
  }) async {
    if (storeId.trim().isEmpty || screenId.trim().isEmpty) {
      return const _ScreenCardPreviewData(urls: []);
    }
    final playlist = await widget.apiClient.getPlaylist(
      storeId: storeId,
      screenId: screenId,
    );
    if (playlist.isEmpty) {
      return const _ScreenCardPreviewData(urls: []);
    }

    final candidates = <String>[];
    void addCandidate(String raw) {
      final resolved = _toAbsoluteUrlForPreview(raw);
      if (resolved.isNotEmpty && !candidates.contains(resolved)) {
        candidates.add(resolved);
      }
    }

    void addItemCandidates(Map<String, dynamic> item) {
      final file = (item['file'] ?? '').toString().trim();
      if (file.startsWith('youtube:')) {
        final id = file.substring('youtube:'.length).trim();
        if (id.length == 11) {
          addCandidate('https://img.youtube.com/vi/$id/hqdefault.jpg');
        }
      }

      if (file.isNotEmpty &&
          !file.startsWith('http://') &&
          !file.startsWith('https://')) {
        final normalizedFile = file.startsWith('/') ? file.substring(1) : file;
        final lower = normalizedFile.toLowerCase();
        final encoded = _encodePathPreservingSlashes(normalizedFile);
        final isVideo = lower.contains('.mp4') ||
            lower.contains('.mov') ||
            lower.contains('.webm') ||
            lower.contains('.mkv') ||
            lower.contains('.m3u8');
        if (isVideo) {
          addCandidate('/vthumb/320/$encoded');
          addCandidate('/vthumb/160/$encoded');
        } else {
          addCandidate('/thumb/320/$encoded');
          addCandidate('/thumb/160/$encoded');
        }
        addCandidate('/static/uploads/$normalizedFile');
      }

      if (file.startsWith('http://') || file.startsWith('https://')) {
        addCandidate(file);
      }

      addCandidate((item['preferred_url'] ?? '').toString());
      addCandidate((item['url'] ?? '').toString());
      addCandidate((item['slice_url'] ?? '').toString());
    }

    // Prefer newest enabled media first, then fall back to any remaining
    // playlist items so one broken item does not blank the card preview.
    for (int i = playlist.length - 1; i >= 0; i--) {
      final item = playlist[i];
      if ((item['enabled'] ?? true) == true) {
        addItemCandidates(item);
      }
    }
    for (int i = playlist.length - 1; i >= 0; i--) {
      final item = playlist[i];
      if ((item['enabled'] ?? true) != true) {
        addItemCandidates(item);
      }
    }

    if (candidates.isEmpty) {
      return const _ScreenCardPreviewData(urls: []);
    }

    Map<String, String> headers = const {};
    try {
      headers = await widget.apiClient.getAuthHeadersForUrl(candidates.first);
    } catch (_) {
      headers = const {};
    }

    return _ScreenCardPreviewData(urls: candidates, headers: headers);
  }

  Future<_ScreenCardPreviewData> _getScreenCardPreviewData({
    required String storeId,
    required String screenId,
  }) {
    final key = '$storeId|$screenId';
    return _screenPreviewUrlFutures.putIfAbsent(
      key,
      () => _loadScreenCardPreviewData(storeId: storeId, screenId: screenId),
    );
  }

  Future<void> _openScreenMediaEditor(ScreenItem screen) async {
    final storeId = widget.selectedStoreId;
    if (storeId == null) {
      return;
    }

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: Theme.of(context).scaffoldBackgroundColor,
      builder: (context) {
        return FractionallySizedBox(
          heightFactor: 0.94,
          child: _ScreenMediaEditorSheet(
            apiClient: widget.apiClient,
            storeId: storeId,
            screenId: screen.id,
            screenName: screen.name,
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final onlineCount = _screens
        .where((screen) =>
            (_screenStatus[screen.id] ?? '').toLowerCase() == 'online')
        .length;

    return RefreshIndicator(
      onRefresh: _loadStores,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (_error != null)
            Material(
              color: Colors.transparent,
              child: InkWell(
                onTap: _isPhoneVerificationError(_error)
                    ? _openAccountCenter
                    : null,
                borderRadius: BorderRadius.circular(12),
                child: Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: scheme.errorContainer,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          _error!,
                          style: TextStyle(color: scheme.onErrorContainer),
                        ),
                      ),
                      if (_isPhoneVerificationError(_error)) ...[
                        const SizedBox(width: 12),
                        Icon(
                          Icons.chevron_right,
                          color: scheme.onErrorContainer,
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          if (_error != null) const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        height: 34,
                        width: 34,
                        decoration: BoxDecoration(
                          color: scheme.primaryContainer,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Icon(
                          Icons.storefront,
                          color: scheme.onPrimaryContainer,
                          size: 18,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          'Select Store',
                          style: theme.textTheme.titleMedium,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      IconButton(
                        onPressed: _loading ? null : _loadStores,
                        icon: const Icon(Icons.refresh),
                        tooltip: 'Refresh',
                      ),
                    ],
                  ),
                  Text(
                    'Pick a store and screen before upload or commands.',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 8),
                  DropdownButtonFormField<String>(
                    value: widget.selectedStoreId,
                    items: _stores
                        .map((store) => DropdownMenuItem(
                              value: store.id,
                              child: Text('${store.id} - ${store.name}'),
                            ))
                        .toList(),
                    onChanged: _loading ? null : _onSelectStore,
                    decoration: const InputDecoration(labelText: 'Store'),
                  ),
                  const SizedBox(height: 10),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      OutlinedButton.icon(
                        onPressed: _loading ? null : _addStore,
                        icon: const Icon(Icons.add_business),
                        label: const Text('Add Store'),
                      ),
                      OutlinedButton.icon(
                        onPressed: _loading || widget.selectedStoreId == null
                            ? null
                            : _deleteSelectedStore,
                        icon: const Icon(Icons.delete_outline),
                        label: const Text('Delete Store'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  DropdownButtonFormField<String>(
                    value: widget.selectedScreenId,
                    items: _screens
                        .map((screen) => DropdownMenuItem(
                              value: screen.id,
                              child: Text('${screen.id} - ${screen.name}'),
                            ))
                        .toList(),
                    onChanged: _loading
                        ? null
                        : (value) {
                            widget.onSelectionChanged(
                                widget.selectedStoreId, value);
                          },
                    decoration: const InputDecoration(labelText: 'Screen'),
                  ),
                  const SizedBox(height: 10),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: OutlinedButton.icon(
                      onPressed: _loading || widget.selectedStoreId == null
                          ? null
                          : _addScreen,
                      icon: const Icon(Icons.add_to_photos_outlined),
                      label: const Text('Add Screen'),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                Chip(
                  backgroundColor: const Color(0xFFDBEAFE),
                  visualDensity: VisualDensity.compact,
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  avatar: const Icon(Icons.storefront, size: 14),
                  label: Text(
                    'Stores: ${_stores.length}',
                    style: theme.textTheme.bodySmall,
                  ),
                  labelPadding: const EdgeInsets.symmetric(horizontal: 4),
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                ),
                const SizedBox(width: 6),
                Chip(
                  backgroundColor: scheme.surfaceContainerHigh,
                  visualDensity: VisualDensity.compact,
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  avatar: const Icon(Icons.tv, size: 14),
                  label: Text(
                    'Screens: ${_screens.length}',
                    style: theme.textTheme.bodySmall,
                  ),
                  labelPadding: const EdgeInsets.symmetric(horizontal: 4),
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                ),
                const SizedBox(width: 6),
                Chip(
                  backgroundColor: scheme.surfaceContainerHigh,
                  visualDensity: VisualDensity.compact,
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  avatar: const Icon(Icons.wifi_tethering, size: 14),
                  label: Text(
                    'Online: $onlineCount',
                    style: theme.textTheme.bodySmall,
                  ),
                  labelPadding: const EdgeInsets.symmetric(horizontal: 4),
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                ),
                if (widget.selectedStoreId != null) ...[
                  const SizedBox(width: 6),
                  Chip(
                    backgroundColor: const Color(0xFFEDE9FE),
                    visualDensity: VisualDensity.compact,
                    materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    avatar: const Icon(Icons.tag, size: 14),
                    label: Text(
                      'Store ${widget.selectedStoreId}',
                      style: theme.textTheme.bodySmall,
                    ),
                    labelPadding: const EdgeInsets.symmetric(horizontal: 4),
                    padding: const EdgeInsets.symmetric(horizontal: 4),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: 12),
          if (_loading)
            const Padding(
              padding: EdgeInsets.only(top: 24),
              child: Center(child: CircularProgressIndicator()),
            )
          else if (_screens.isEmpty)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Text(
                  'No screens found for this store.',
                  style: theme.textTheme.bodyMedium,
                ),
              ),
            )
          else
            ..._screens.map((screen) {
              final selected = screen.id == widget.selectedScreenId;
              final storeIdForPreview = widget.selectedStoreId ?? '';
              return Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Card(
                  child: InkWell(
                    borderRadius: BorderRadius.circular(14),
                    onTap: () {
                      widget.onSelectionChanged(
                          widget.selectedStoreId, screen.id);
                      _openScreenMediaEditor(screen);
                    },
                    child: Padding(
                      padding: const EdgeInsets.all(14),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(
                                Icons.tv,
                                color: selected
                                    ? scheme.primary
                                    : scheme.onSurfaceVariant,
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  screen.name,
                                  style: theme.textTheme.titleMedium,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                              _buildStatusBadge(screen.id),
                              PopupMenuButton<String>(
                                tooltip: 'Screen actions',
                                onSelected: (value) {
                                  if (value == 'rename') {
                                    _renameScreen(screen);
                                  }
                                  if (value == 'delete') {
                                    _deleteScreen(screen);
                                  }
                                },
                                itemBuilder: (context) => const [
                                  PopupMenuItem(
                                    value: 'rename',
                                    child: Text('Rename'),
                                  ),
                                  PopupMenuItem(
                                    value: 'delete',
                                    child: Text('Delete'),
                                  ),
                                ],
                              ),
                            ],
                          ),
                          const SizedBox(height: 6),
                          Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      screen.id,
                                      style: theme.textTheme.bodySmall
                                          ?.copyWith(
                                              color: scheme.onSurfaceVariant),
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      'Tap to manage media and timeline',
                                      style:
                                          theme.textTheme.bodySmall?.copyWith(
                                        color: scheme.primary,
                                        fontWeight: FontWeight.w600,
                                      ),
                                    ),
                                    if (selected) ...[
                                      const SizedBox(height: 6),
                                      Container(
                                        padding: const EdgeInsets.symmetric(
                                            horizontal: 8, vertical: 4),
                                        decoration: BoxDecoration(
                                          color: scheme.primaryContainer,
                                          borderRadius:
                                              BorderRadius.circular(999),
                                        ),
                                        child: Text(
                                          'Active',
                                          style: TextStyle(
                                            color: scheme.onPrimaryContainer,
                                            fontSize: 12,
                                            fontWeight: FontWeight.w600,
                                          ),
                                        ),
                                      ),
                                    ],
                                  ],
                                ),
                              ),
                              const SizedBox(width: 10),
                              Container(
                                width: 120,
                                height: 120,
                                decoration: BoxDecoration(
                                  borderRadius: BorderRadius.circular(8),
                                  border: Border.all(
                                    color: scheme.outlineVariant,
                                  ),
                                  color: scheme.surfaceContainerHighest,
                                ),
                                child: FutureBuilder<_ScreenCardPreviewData>(
                                  future: _getScreenCardPreviewData(
                                    storeId: storeIdForPreview,
                                    screenId: screen.id,
                                  ),
                                  builder: (context, snapshot) {
                                    final data = snapshot.data ??
                                        const _ScreenCardPreviewData(urls: []);
                                    final urls = data.urls;
                                    if (snapshot.connectionState ==
                                        ConnectionState.waiting) {
                                      return Center(
                                        child: Icon(
                                          Icons.image_outlined,
                                          color: scheme.onSurfaceVariant,
                                        ),
                                      );
                                    }
                                    if (urls.isEmpty) {
                                      return const Center(
                                        child: Icon(Icons.image_not_supported),
                                      );
                                    }
                                    return ClipRRect(
                                      borderRadius: BorderRadius.circular(7),
                                      child: _ScreenCardPreviewImage(
                                        urls: urls,
                                        headers: data.headers,
                                      ),
                                    );
                                  },
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              );
            }),
        ],
      ),
    );
  }
}

class _ScreenCardPreviewImage extends StatefulWidget {
  const _ScreenCardPreviewImage({required this.urls, this.headers = const {}});

  final List<String> urls;
  final Map<String, String> headers;

  @override
  State<_ScreenCardPreviewImage> createState() =>
      _ScreenCardPreviewImageState();
}

class _ScreenCardPreviewImageState extends State<_ScreenCardPreviewImage> {
  int _index = 0;

  @override
  void didUpdateWidget(covariant _ScreenCardPreviewImage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!listEquals(oldWidget.urls, widget.urls)) {
      _index = 0;
    }
  }

  @override
  Widget build(BuildContext context) {
    if (widget.urls.isEmpty || _index >= widget.urls.length) {
      return const Center(child: Icon(Icons.broken_image_outlined));
    }

    final url = widget.urls[_index];
    return Image.network(
      url,
      headers: url.contains('img.youtube.com') || widget.headers.isEmpty
          ? null
          : widget.headers,
      fit: BoxFit.cover,
      cacheWidth: 320,
      cacheHeight: 320,
      filterQuality: FilterQuality.medium,
      gaplessPlayback: true,
      errorBuilder: (_, __, ___) {
        if (_index < widget.urls.length - 1) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) {
              setState(() {
                _index += 1;
              });
            }
          });
          return const Center(child: Icon(Icons.image_not_supported));
        }
        return const Center(child: Icon(Icons.broken_image_outlined));
      },
    );
  }
}

class _ScreenCardPreviewData {
  const _ScreenCardPreviewData({
    required this.urls,
    this.headers = const {},
  });

  final List<String> urls;
  final Map<String, String> headers;
}

class ScreenMediaEditorSheet extends StatelessWidget {
  const ScreenMediaEditorSheet({
    super.key,
    required this.apiClient,
    required this.storeId,
    required this.screenId,
    required this.screenName,
  });

  final ApiClient apiClient;
  final String storeId;
  final String screenId;
  final String screenName;

  @override
  Widget build(BuildContext context) {
    return _ScreenMediaEditorSheet(
      apiClient: apiClient,
      storeId: storeId,
      screenId: screenId,
      screenName: screenName,
    );
  }
}

class _ScreenMediaEditorSheet extends StatefulWidget {
  const _ScreenMediaEditorSheet({
    required this.apiClient,
    required this.storeId,
    required this.screenId,
    required this.screenName,
  });

  final ApiClient apiClient;
  final String storeId;
  final String screenId;
  final String screenName;

  @override
  State<_ScreenMediaEditorSheet> createState() =>
      _ScreenMediaEditorSheetState();
}

class _ScreenMediaEditorSheetState extends State<_ScreenMediaEditorSheet> {
  static const List<String> _weekDays = [
    'mon',
    'tue',
    'wed',
    'thu',
    'fri',
    'sat',
    'sun'
  ];
  static const Map<int, String> _effectById = {
    0: '',
    1: 'cut',
    2: 'fade',
    3: 'dissolve',
    4: 'slide-l',
    5: 'slide-r',
    6: 'slide-up',
    7: 'slide-down',
    8: 'zoom-in',
    9: 'zoom-out',
    10: 'wipe-lr',
  };
  static final Map<String, int> _effectIdByName = {
    for (final entry in _effectById.entries) entry.value: entry.key,
  };

  final _startController = TextEditingController();
  final _endController = TextEditingController();
  final _windowStartController = TextEditingController();
  final _windowEndController = TextEditingController();

  Timer? _liveSyncTimer;
  Timer? _autoSaveTimer;
  bool _syncing = false;
  bool _loading = true;
  bool _saving = false;
  String? _message;
  String? _selectedItemId;
  Map<String, String> _previewHeaders = const {};
  bool _itemEnabled = true;
  bool _itemRepeat = true;
  int _itemDuration = 10;
  int _itemEffectId = 1;
  Set<String> _itemDays = <String>{};
  bool _windowEnabled = true;
  Set<String> _windowDays = <String>{};
  bool _showNewWindowForm = false;
  bool _quickActionBusy = false;
  int _screenRotation = 0;
  bool _screenMuted = false;
  File? _pickedFile;
  List<Map<String, dynamic>> _playlist = const [];

  Map<String, dynamic>? get _currentItem {
    if (_playlist.isEmpty) {
      return null;
    }
    if (_selectedItemId != null) {
      for (final item in _playlist) {
        if (item['id']?.toString() == _selectedItemId) {
          return item;
        }
      }
    }
    for (final item in _playlist) {
      if (_looksRunning(item) && _hasDisplayableMedia(item)) {
        return item;
      }
    }
    for (final item in _playlist) {
      if ((item['enabled'] ?? true) == true && _hasDisplayableMedia(item)) {
        return item;
      }
    }
    for (final item in _playlist) {
      if (_hasDisplayableMedia(item)) {
        return item;
      }
    }
    return _playlist.first;
  }

  bool _looksRunning(Map<String, dynamic> item) {
    final status = item['last_status'];
    if (status is! Map) {
      return false;
    }
    final lower =
        status.values.map((value) => value.toString().toLowerCase()).join(' ');
    return lower.contains('load_ok') ||
        lower.contains('playing') ||
        lower.contains('ok') ||
        lower.contains('success');
  }

  bool _hasDisplayableMedia(Map<String, dynamic> item) {
    final url = _resolvePreviewUrl(item);
    final mediaType = _resolveMediaType(item, url);
    return url.isNotEmpty && (mediaType == 'image' || mediaType == 'video');
  }

  String _resolvePreviewUrl(Map<String, dynamic>? item) {
    if (item == null) {
      return '';
    }

    final file = (item['file'] ?? '').toString().trim();
    if (file.startsWith('youtube:')) {
      final videoId = file.substring('youtube:'.length).trim();
      if (videoId.length == 11) {
        return 'https://img.youtube.com/vi/$videoId/hqdefault.jpg';
      }
      return '';
    }

    if (file.isNotEmpty &&
        !file.startsWith('youtube:') &&
        !file.startsWith('http://') &&
        !file.startsWith('https://') &&
        !file.startsWith('/')) {
      final lower = file.toLowerCase();
      final encoded = _encodePathPreservingSlashes(file);
      final isVideo = lower.contains('.mp4') ||
          lower.contains('.mov') ||
          lower.contains('.webm') ||
          lower.contains('.mkv') ||
          lower.contains('.m3u8');
      final isImage = lower.contains('.jpg') ||
          lower.contains('.jpeg') ||
          lower.contains('.png') ||
          lower.contains('.gif') ||
          lower.contains('.webp') ||
          lower.contains('.bmp');

      if (isVideo) {
        return _toAbsoluteUrl('/vpreview/640/$encoded');
      }
      if (isImage) {
        return _toAbsoluteUrl('/thumb/960/$encoded');
      }
    }

    final preferred = _toAbsoluteUrl((item['preferred_url'] ?? '').toString());
    if (preferred.isNotEmpty) {
      return preferred;
    }
    final direct = _toAbsoluteUrl((item['url'] ?? '').toString());
    if (direct.isNotEmpty) {
      return direct;
    }
    final slice = _toAbsoluteUrl((item['slice_url'] ?? '').toString());
    if (slice.isNotEmpty) {
      return slice;
    }

    if (file.isEmpty || file.startsWith('youtube:')) {
      return '';
    }
    if (file.startsWith('http://') || file.startsWith('https://')) {
      return file;
    }
    if (file.startsWith('/')) {
      return _toAbsoluteUrl(file);
    }
    return _toAbsoluteUrl('/static/uploads/$file');
  }

  String _encodePathPreservingSlashes(String value) {
    return value
        .split('/')
        .where((segment) => segment.trim().isNotEmpty)
        .map(Uri.encodeComponent)
        .join('/');
  }

  String _toAbsoluteUrl(String raw) {
    final value = raw.trim();
    if (value.isEmpty) {
      return '';
    }
    if (value.startsWith('http://') || value.startsWith('https://')) {
      return value;
    }

    Uri? base;
    try {
      base = Uri.parse(widget.apiClient.baseUrl);
    } catch (_) {
      return value;
    }

    String toJoin = value;
    if (!toJoin.startsWith('/')) {
      toJoin = '/$toJoin';
    }

    Uri primary = base.resolve(toJoin);

    // If API subdomain is being used, media files are often served from main domain.
    if (base.host.startsWith('api.')) {
      final mainHost = base.host.substring(4);
      final mainUri = Uri(
        scheme: base.scheme,
        host: mainHost,
        port: base.hasPort ? base.port : null,
      ).resolve(toJoin);

      if (toJoin.startsWith('/static/') || toJoin.startsWith('/media/')) {
        return mainUri.toString();
      }
    }

    return primary.toString();
  }

  String _resolveMediaType(Map<String, dynamic>? item, String resolvedUrl) {
    final file = (item?['file'] ?? '').toString().trim().toLowerCase();
    if (file.startsWith('youtube:')) {
      return 'video';
    }

    final rawType = (item?['media_type'] ?? '').toString().toLowerCase().trim();
    if (rawType == 'image' || rawType == 'video') {
      return rawType;
    }
    if (rawType == 'animated') {
      return 'image';
    }

    final probe = '${item?['file'] ?? ''} $resolvedUrl'.toLowerCase();
    if (probe.contains('.mp4') ||
        probe.contains('.mov') ||
        probe.contains('.webm') ||
        probe.contains('.mkv') ||
        probe.contains('.m3u8')) {
      return 'video';
    }
    if (probe.contains('.jpg') ||
        probe.contains('.jpeg') ||
        probe.contains('.png') ||
        probe.contains('.gif') ||
        probe.contains('.webp') ||
        probe.contains('.bmp')) {
      return 'image';
    }
    return rawType;
  }

  @override
  void initState() {
    super.initState();
    _loadPlaylist();
    _liveSyncTimer = Timer.periodic(const Duration(seconds: 5), (_) {
      _refreshLivePlaylist();
    });
  }

  @override
  void dispose() {
    _liveSyncTimer?.cancel();
    _autoSaveTimer?.cancel();
    _startController.dispose();
    _endController.dispose();
    _windowStartController.dispose();
    _windowEndController.dispose();
    super.dispose();
  }

  void _queueAutoSave() {
    if (_loading || _saving || _currentItem == null) {
      return;
    }
    _autoSaveTimer?.cancel();
    _autoSaveTimer = Timer(const Duration(milliseconds: 700), () {
      if (!mounted || _loading || _saving || _currentItem == null) {
        return;
      }
      _saveItemSettings(silentSuccess: true);
    });
  }

  Future<void> _refreshLivePlaylist() async {
    if (!mounted || _saving || _loading || _syncing) {
      return;
    }
    _syncing = true;
    try {
      final playlist = await widget.apiClient.getPlaylist(
        storeId: widget.storeId,
        screenId: widget.screenId,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _playlist = playlist;
        if (_selectedItemId != null &&
            !_playlist.any((p) => p['id']?.toString() == _selectedItemId)) {
          _selectedItemId = null;
        }
      });
      await _refreshPreviewHeaders();
    } catch (_) {
      // keep current UI when transient sync errors happen
    } finally {
      _syncing = false;
    }
  }

  Future<void> _loadPlaylist() async {
    setState(() {
      _loading = true;
      _message = null;
    });
    try {
      final playlist = await widget.apiClient.getPlaylist(
        storeId: widget.storeId,
        screenId: widget.screenId,
      );
      final screens = await widget.apiClient.getScreens(widget.storeId);
      int rotation = _screenRotation;
      bool muted = _screenMuted;
      for (final screen in screens) {
        if (screen.id == widget.screenId) {
          rotation = screen.rotation;
          muted = screen.muted;
          break;
        }
      }
      if (!mounted) {
        return;
      }
      setState(() {
        _playlist = playlist;
        _screenRotation = rotation;
        _screenMuted = muted;
        if (_selectedItemId != null &&
            !_playlist.any((p) => p['id']?.toString() == _selectedItemId)) {
          _selectedItemId = null;
        }
      });

      _loadItemFieldsFromCurrent();
      await _refreshPreviewHeaders();
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

  String _itemLabel(Map<String, dynamic> item) {
    final file = (item['file'] ?? '').toString();
    if (file.isEmpty) {
      return 'Untitled media';
    }
    final segments = file.split('/');
    return segments.isEmpty ? file : segments.last;
  }

  Future<void> _pickPlaylistItemVisual() async {
    if (_playlist.length <= 1) {
      return;
    }
    final selected = await showModalBottomSheet<String>(
      context: context,
      useSafeArea: true,
      isScrollControlled: true,
      builder: (context) {
        return FractionallySizedBox(
          heightFactor: 0.72,
          child: Column(
            children: [
              ListTile(
                title: const Text('Select Playlist Item'),
                trailing: IconButton(
                  onPressed: () => Navigator.of(context).pop(),
                  icon: const Icon(Icons.close),
                ),
              ),
              const Divider(height: 1),
              Expanded(
                child: ListView.separated(
                  itemCount: _playlist.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (context, index) {
                    final item = _playlist[index];
                    final itemId = (item['id'] ?? '').toString();
                    final label = _itemLabel(item);
                    final url = _resolvePreviewUrl(item);
                    return ListTile(
                      selected: itemId == _selectedItemId,
                      leading: ClipRRect(
                        borderRadius: BorderRadius.circular(6),
                        child: url.isNotEmpty
                            ? Image.network(
                                url,
                                headers: _previewHeaders,
                                width: 52,
                                height: 34,
                                fit: BoxFit.cover,
                                errorBuilder: (_, __, ___) => Container(
                                  width: 52,
                                  height: 34,
                                  color: Theme.of(context)
                                      .colorScheme
                                      .surfaceContainerHighest,
                                  alignment: Alignment.center,
                                  child: const Icon(Icons.image_not_supported,
                                      size: 16),
                                ),
                              )
                            : Container(
                                width: 52,
                                height: 34,
                                color: Theme.of(context)
                                    .colorScheme
                                    .surfaceContainerHighest,
                                alignment: Alignment.center,
                                child: const Icon(Icons.image, size: 16),
                              ),
                      ),
                      title: Text(
                        label,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      subtitle: Text(
                        itemId,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      onTap: itemId.isEmpty
                          ? null
                          : () => Navigator.of(context).pop(itemId),
                    );
                  },
                ),
              ),
            ],
          ),
        );
      },
    );

    if (selected == null || selected == _selectedItemId || !mounted) {
      return;
    }
    setState(() {
      _selectedItemId = selected;
      _loadItemFieldsFromCurrent();
    });
    await _refreshPreviewHeaders();
  }

  Map<String, dynamic> _asMap(dynamic value) {
    if (value is Map<String, dynamic>) {
      return value;
    }
    if (value is Map) {
      return value.map((key, val) => MapEntry(key.toString(), val));
    }
    return <String, dynamic>{};
  }

  List<String> _normalizeDays(dynamic days) {
    final raw = days is List ? days : const [];
    final normalized = <String>[];
    for (final d in raw) {
      final code = d.toString().toLowerCase().trim();
      if (_weekDays.contains(code)) {
        normalized.add(code);
      }
    }
    return normalized;
  }

  void _loadItemFieldsFromCurrent() {
    final item = _currentItem;
    _startController.text = _formatDisplayDateTime(item?['start']);
    _endController.text = _formatDisplayDateTime(item?['end']);
    _itemEnabled = (item?['enabled'] ?? true) == true;
    _itemRepeat = (item?['repeat'] ?? true) == true;
    final duration = int.tryParse('${item?['duration'] ?? 10}') ?? 10;
    _itemDuration = duration < 1 ? 1 : duration;
    _itemEffectId = _effectIdFromItem(item);
    _itemDays = _normalizeDays(item?['days']).toSet();
  }

  String _formatDisplayDateTime(dynamic value) {
    final text = (value ?? '').toString().trim();
    if (text.isEmpty) {
      return '';
    }
    return text.replaceFirst('T', ' ');
  }

  void _showSheetMessage(String message) {
    if (!mounted) {
      return;
    }
    setState(() {
      _message = message;
    });
  }

  String? _extractYouTubeId(String input) {
    final value = input.trim();
    if (value.isEmpty) {
      return null;
    }

    final idOnly = RegExp(r'^[a-zA-Z0-9_-]{11}$');
    if (idOnly.hasMatch(value)) {
      return value;
    }

    final regex = RegExp(
      r'(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})',
      caseSensitive: false,
    );
    final match = regex.firstMatch(value);
    if (match == null) {
      return value;
    }
    return match.group(1);
  }

  Future<void> _quickAddYouTube() async {
    final urlController = TextEditingController();
    final durationController = TextEditingController(text: '30');
    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('▶️ Add YouTube Video'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Paste a YouTube video URL or video ID to add it to the schedule.',
            ),
            const SizedBox(height: 12),
            TextField(
              controller: urlController,
              decoration: const InputDecoration(
                labelText: 'YouTube URL or Video ID',
                hintText: 'https://www.youtube.com/watch?v=... or video ID',
              ),
            ),
            const SizedBox(height: 4),
            const Text(
              'Examples: https://www.youtube.com/watch?v=dQw4w9WgXcQ or dQw4w9WgXcQ',
              style: TextStyle(fontSize: 12),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: durationController,
              keyboardType: TextInputType.number,
              decoration:
                  const InputDecoration(labelText: 'Duration (seconds)'),
            ),
            const SizedBox(height: 4),
            const Text(
              'How long to display this video in the playlist rotation',
              style: TextStyle(fontSize: 12),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Icon(Icons.close),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Icon(Icons.add),
          ),
        ],
      ),
    );

    final rawUrl = urlController.text;
    final parsedDuration = int.tryParse(durationController.text.trim()) ?? 30;
    final duration = parsedDuration.clamp(5, 3600);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      urlController.dispose();
      durationController.dispose();
    });

    if (accepted != true) {
      return;
    }

    if (rawUrl.trim().isEmpty) {
      _showSheetMessage('Please enter a YouTube URL or video ID.');
      return;
    }

    final videoId = _extractYouTubeId(rawUrl);
    if (videoId == null || videoId.isEmpty) {
      _showSheetMessage('Invalid YouTube URL or video ID.');
      return;
    }

    setState(() {
      _quickActionBusy = true;
    });
    try {
      await widget.apiClient.assignToScreen(
        storeId: widget.storeId,
        screenId: widget.screenId,
        filename: 'youtube:$videoId',
      );

      if (duration > 0 && duration != 10) {
        final playlist = await widget.apiClient.getPlaylist(
          storeId: widget.storeId,
          screenId: widget.screenId,
        );
        String? targetItemId;
        for (int i = playlist.length - 1; i >= 0; i--) {
          final file = (playlist[i]['file'] ?? '').toString();
          if (file.contains(videoId)) {
            targetItemId = (playlist[i]['id'] ?? '').toString();
            break;
          }
        }
        if (targetItemId != null && targetItemId.isNotEmpty) {
          await widget.apiClient.updatePlaylistItem(
            storeId: widget.storeId,
            screenId: widget.screenId,
            itemId: targetItemId,
            duration: duration,
          );
        }
      }

      _showSheetMessage('YouTube video added.');
      await _loadPlaylist();
    } catch (e) {
      _showSheetMessage(e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) {
        setState(() {
          _quickActionBusy = false;
        });
      }
    }
  }

  Future<void> _openDisplayPlayer() async {
    try {
      final profile = await widget.apiClient.getMe();
      final code = (profile.linkCode ?? '').trim();

      final base = Uri.parse(widget.apiClient.baseUrl);
      final playerUri = base
          .resolve('/webplayer/play')
          .replace(queryParameters: <String, String>{
        'store_id': widget.storeId,
        'screen_id': widget.screenId,
        if (code.isNotEmpty) 'code': code,
      });

      final externalOk =
          await launchUrl(playerUri, mode: LaunchMode.externalApplication);
      if (externalOk || !mounted) {
        return;
      }

      final browserOk =
          await launchUrl(playerUri, mode: LaunchMode.inAppBrowserView);
      if (browserOk || !mounted) {
        return;
      }

      _showSheetMessage('Could not open display player on this device.');
    } catch (e) {
      _showSheetMessage(e.toString().replaceFirst('Exception: ', ''));
    }
  }

  Future<void> _quickAutoSlice() async {
    File? selectedVideo;
    bool running = false;
    bool showingProgress = false;
    double progress = 0;
    String statusText = 'Processing...';
    String detailText = '';
    String? localError;

    void setBusy(bool value) {
      if (!mounted) {
        return;
      }
      setState(() {
        _quickActionBusy = value;
      });
    }

    Future<List<Map<String, dynamic>>> parseSlicedFiles(dynamic raw) async {
      if (raw is! List) {
        return const [];
      }
      return raw
          .map((item) {
            if (item is Map<String, dynamic>) {
              return item;
            }
            if (item is Map) {
              return item.map((k, v) => MapEntry(k.toString(), v));
            }
            return <String, dynamic>{};
          })
          .where((item) => item.isNotEmpty)
          .toList();
    }

    final created = await showDialog<bool>(
      context: context,
      barrierDismissible: !running,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            Future<void> checkRecentJobs() async {
              setModalState(() {
                running = true;
                showingProgress = true;
                localError = null;
                statusText = 'Checking recent jobs...';
                detailText = 'Fetching completed slicing jobs';
                progress = 0.5;
              });
              setBusy(true);
              try {
                final jobs = await widget.apiClient.listSliceJobs();
                Map<String, dynamic>? completed;
                for (final job in jobs) {
                  final isComplete =
                      (job['status'] ?? '').toString().toLowerCase() ==
                          'complete';
                  final result = job['result'];
                  final hasResult = result is List && result.isNotEmpty;
                  if (isComplete && hasResult) {
                    completed = job;
                    break;
                  }
                }

                if (completed == null) {
                  setModalState(() {
                    running = false;
                    statusText = 'No completed jobs found';
                    detailText =
                        'Upload a new multi-screen video or try again later';
                    progress = 1;
                  });
                  return;
                }

                setModalState(() {
                  statusText = 'Completed job found. Creating screens...';
                  detailText =
                      'Layout: ${(completed!['layout'] ?? 'horizontal').toString()}';
                  progress = 0.8;
                });

                final slicedFiles = await parseSlicedFiles(completed['result']);
                if (slicedFiles.isEmpty) {
                  throw Exception('Completed job has no sliced files.');
                }

                final created = await widget.apiClient.autoCreateSyncScreens(
                  storeId: widget.storeId,
                  layout: (completed['layout'] ?? 'horizontal').toString(),
                  slicedFiles: slicedFiles,
                );
                final count =
                    int.tryParse('${created['count'] ?? slicedFiles.length}') ??
                        slicedFiles.length;

                setModalState(() {
                  progress = 1;
                  statusText = 'Success';
                  detailText = 'Created $count screens from recent job';
                });

                if (dialogContext.mounted) {
                  Navigator.of(dialogContext).pop(true);
                }
              } catch (e) {
                setModalState(() {
                  localError = e.toString().replaceFirst('Exception: ', '');
                  running = false;
                });
              } finally {
                setBusy(false);
              }
            }

            Future<void> runUploadFlow() async {
              if (selectedVideo == null) {
                setModalState(() {
                  localError = 'Please select a multi-screen video file.';
                });
                return;
              }

              setModalState(() {
                running = true;
                showingProgress = true;
                localError = null;
                statusText = 'Uploading video...';
                detailText = 'Preparing upload';
                progress = 0.05;
              });
              setBusy(true);

              try {
                final uploadResult =
                    await widget.apiClient.uploadMediaDetailed(selectedVideo!);
                final detectedCount =
                    int.tryParse('${uploadResult['screen_count'] ?? 1}') ?? 1;

                if (detectedCount <= 1) {
                  setModalState(() {
                    running = false;
                    localError =
                        'Single-screen video detected. Use Replace Media/Schedule instead.';
                    progress = 0;
                    showingProgress = false;
                  });
                  return;
                }

                final jobId = (uploadResult['slice_job_id'] ?? '').toString();
                if (jobId.isEmpty) {
                  throw Exception('Auto-slice job was not created.');
                }

                setModalState(() {
                  statusText =
                      'Detected $detectedCount-screen ${(uploadResult['layout'] ?? 'horizontal').toString()} layout';
                  detailText = 'Slicing video...';
                  progress = 0.1;
                });

                Map<String, dynamic>? completedStatus;
                for (int attempt = 0; attempt < 600; attempt++) {
                  await Future.delayed(const Duration(seconds: 1));
                  final status =
                      await widget.apiClient.getSliceJobStatus(jobId);
                  final state =
                      (status['status'] ?? '').toString().toLowerCase();

                  if (state == 'complete') {
                    completedStatus = status;
                    break;
                  }
                  if (state == 'error') {
                    final message =
                        (status['error'] ?? 'Auto-slice processing failed')
                            .toString();
                    throw Exception(message);
                  }

                  final backendProgress =
                      int.tryParse('${status['progress'] ?? 0}') ?? 0;
                  final displayProgress = backendProgress.clamp(0, 95) / 100;
                  setModalState(() {
                    progress = displayProgress;
                    statusText = 'Slicing video ($backendProgress%)';
                    detailText = (status['stage'] ?? 'Processing in background')
                        .toString();
                  });
                }

                if (completedStatus == null) {
                  setModalState(() {
                    running = false;
                    statusText = 'Still processing';
                    detailText =
                        'Video is taking longer than expected. Check recent jobs shortly.';
                    progress = 1;
                  });
                  return;
                }

                final slicedFiles =
                    await parseSlicedFiles(completedStatus['result']);
                if (slicedFiles.isEmpty) {
                  throw Exception('No slices were generated.');
                }

                setModalState(() {
                  statusText = 'Creating synchronized screens...';
                  detailText = 'Applying slices to current store';
                  progress = 0.97;
                });

                final layout = (completedStatus['layout'] ??
                        uploadResult['layout'] ??
                        'horizontal')
                    .toString();

                final created = await widget.apiClient.autoCreateSyncScreens(
                  storeId: widget.storeId,
                  layout: layout,
                  slicedFiles: slicedFiles,
                );
                final count =
                    int.tryParse('${created['count'] ?? slicedFiles.length}') ??
                        slicedFiles.length;

                setModalState(() {
                  statusText = 'Success';
                  detailText = 'Created $count screens';
                  progress = 1;
                });

                if (dialogContext.mounted) {
                  Navigator.of(dialogContext).pop(true);
                }
              } catch (e) {
                setModalState(() {
                  localError = e.toString().replaceFirst('Exception: ', '');
                  running = false;
                });
              } finally {
                setBusy(false);
              }
            }

            final selectedName =
                selectedVideo?.uri.pathSegments.isNotEmpty == true
                    ? selectedVideo!.uri.pathSegments.last
                    : null;
            final selectedSizeMb = selectedVideo != null
                ? (selectedVideo!.lengthSync() / (1024 * 1024))
                    .toStringAsFixed(2)
                : null;

            return AlertDialog(
              title: const Text('Auto-Slice Multi-Screen Video'),
              content: SizedBox(
                width: 520,
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: const Color(0xFFF8F9FA),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: const Color(0xFF28A745)),
                        ),
                        child: const Text(
                          'Smart Resolution Detection\nUpload a multi-screen video and the system will detect layout, slice it, and create synchronized screens.',
                        ),
                      ),
                      const SizedBox(height: 12),
                      OutlinedButton.icon(
                        onPressed: running
                            ? null
                            : () async {
                                final picked =
                                    await FilePicker.platform.pickFiles(
                                  type: FileType.video,
                                  allowMultiple: false,
                                  withData: false,
                                );
                                if (picked == null || picked.files.isEmpty) {
                                  return;
                                }
                                final path = picked.files.first.path;
                                if (path == null || path.isEmpty) {
                                  return;
                                }
                                setModalState(() {
                                  selectedVideo = File(path);
                                  localError = null;
                                });
                              },
                        icon: const Icon(Icons.video_file),
                        label: const SizedBox.shrink(),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        selectedVideo == null
                            ? 'No video selected'
                            : 'Selected: $selectedName (${selectedSizeMb ?? '0.00'} MB)',
                      ),
                      const SizedBox(height: 10),
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: const Color(0xFFFFF3CD),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: const Color(0xFFFFC107)),
                        ),
                        child: const Text(
                          'Supported layouts:\nHorizontal: 3840×1080, 5760×1080, 7680×1080...\nVertical: 1920×2160, 1920×3240, 1920×4320...',
                          style: TextStyle(fontSize: 12),
                        ),
                      ),
                      if (showingProgress) ...[
                        const SizedBox(height: 12),
                        Text(
                          statusText,
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                        const SizedBox(height: 8),
                        LinearProgressIndicator(value: progress.clamp(0, 1)),
                        const SizedBox(height: 6),
                        Text(
                          detailText,
                          style: const TextStyle(fontSize: 12),
                        ),
                      ],
                      if (localError != null) ...[
                        const SizedBox(height: 10),
                        Text(
                          localError!,
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.error,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
              actions: [
                TextButton(
                  onPressed: running
                      ? null
                      : () => Navigator.of(dialogContext).pop(false),
                  child: const Icon(Icons.close),
                ),
                OutlinedButton(
                  onPressed: running ? null : checkRecentJobs,
                  child: const Icon(Icons.history),
                ),
                FilledButton.icon(
                  onPressed: running ? null : runUploadFlow,
                  icon: const Icon(Icons.content_cut),
                  label: const SizedBox.shrink(),
                ),
              ],
            );
          },
        );
      },
    );

    if (created == true && mounted) {
      _showSheetMessage('Auto-Slice complete. Screens created.');
      await _loadPlaylist();
    }
  }

  Future<void> _quickToggleMute() async {
    setState(() {
      _quickActionBusy = true;
    });
    try {
      final newMuted = !_screenMuted;
      await widget.apiClient.updateScreenMute(
        storeId: widget.storeId,
        screenId: widget.screenId,
        muted: newMuted,
      );
      if (mounted) {
        setState(() {
          _screenMuted = newMuted;
        });
      }
      _showSheetMessage(_screenMuted ? '🔇 Screen muted' : '🔊 Screen unmuted');
    } catch (e) {
      _showSheetMessage(e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) {
        setState(() {
          _quickActionBusy = false;
        });
      }
    }
  }

  Future<void> _quickRotate() async {
    setState(() {
      _quickActionBusy = true;
    });
    try {
      final masterStoreId = await widget.apiClient.getMasterStoreId();
      final screens = await widget.apiClient.getScreens(widget.storeId);
      ScreenItem? screen;
      for (final s in screens) {
        if (s.id == widget.screenId) {
          screen = s;
          break;
        }
      }

      final isMasterStore =
          masterStoreId != null && masterStoreId == widget.storeId;
      final isProtected = screen?.protected == true;
      if (!isMasterStore && !isProtected) {
        _showSheetMessage(
          '🔒 Enable "Protect from Apply All" first to rotate this screen.',
        );
        return;
      }

      final currentRotation = screen?.rotation ?? 0;
      final nextRotation = (currentRotation + 90) % 360;

      await widget.apiClient.updateScreenRotation(
        storeId: widget.storeId,
        screenId: widget.screenId,
        rotation: nextRotation,
      );
      if (mounted) {
        setState(() {
          _screenRotation = nextRotation;
        });
      }
      _showSheetMessage('Rotated to $nextRotation°');
    } catch (e) {
      _showSheetMessage(e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) {
        setState(() {
          _quickActionBusy = false;
        });
      }
    }
  }

  Widget _buildQuickActionButton({
    required String tooltip,
    required IconData icon,
    required Color background,
    required VoidCallback? onPressed,
  }) {
    return Tooltip(
      message: tooltip,
      child: SizedBox(
        width: 36,
        height: 32,
        child: FilledButton(
          style: FilledButton.styleFrom(
            visualDensity: VisualDensity.compact,
            padding: EdgeInsets.zero,
            backgroundColor: background,
            minimumSize: const Size(36, 32),
            tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(8),
            ),
          ),
          onPressed: onPressed,
          child: Icon(icon, size: 16),
        ),
      ),
    );
  }

  int _effectIdFromItem(Map<String, dynamic>? item) {
    final rawEffectId = item?['effect_id'];
    if (rawEffectId != null) {
      final parsed = int.tryParse(rawEffectId.toString());
      if (parsed != null && _effectById.containsKey(parsed)) {
        return parsed;
      }
    }

    final rawEffect = (item?['effect'] ?? '').toString().toLowerCase().trim();
    if (rawEffect.isNotEmpty) {
      final fromName = _effectIdByName[rawEffect];
      if (fromName != null) {
        return fromName;
      }
    }
    return 0;
  }

  List<Map<String, dynamic>> _scheduleWindows() {
    final list = _currentItem?['schedule'];
    if (list is! List) {
      return const [];
    }
    return list.map((window) => _asMap(window)).toList();
  }

  Future<void> _refreshPreviewHeaders() async {
    final url = _resolvePreviewUrl(_currentItem);
    if (url.isEmpty) {
      if (mounted && _previewHeaders.isNotEmpty) {
        setState(() {
          _previewHeaders = const {};
        });
      }
      return;
    }

    final headers = await widget.apiClient.getAuthHeadersForUrl(url);
    if (!mounted) {
      return;
    }
    if (!mapEquals(_previewHeaders, headers)) {
      setState(() {
        _previewHeaders = headers;
      });
    }
  }

  Future<void> _saveItemSettings({bool silentSuccess = false}) async {
    final itemId = _currentItem?['id']?.toString() ?? '';
    if (itemId.isEmpty) {
      setState(() {
        _message = 'No media item found for this screen. Upload media first.';
      });
      return;
    }

    var refreshWithoutReload = false;

    setState(() {
      _saving = true;
      _message = null;
    });

    try {
      await widget.apiClient.updatePlaylistItem(
        storeId: widget.storeId,
        screenId: widget.screenId,
        itemId: itemId,
        start: _startController.text,
        end: _endController.text,
        enabled: _itemEnabled,
        repeat: _itemRepeat,
        duration: _itemDuration,
        days: _itemDays.toList(),
        effectId: _itemEffectId,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        if (!silentSuccess) {
          _message = 'Playlist settings saved.';
        }
      });
      if (silentSuccess) {
        refreshWithoutReload = true;
      } else {
        await _loadPlaylist();
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
          _saving = false;
        });
      }
    }

    if (refreshWithoutReload && mounted) {
      await _refreshLivePlaylist();
    }
  }

  Future<void> _addScheduleWindow() async {
    final itemId = _currentItem?['id']?.toString() ?? '';
    if (itemId.isEmpty) {
      setState(() {
        _message = 'No media item found for this screen. Upload media first.';
      });
      return;
    }

    setState(() {
      _saving = true;
      _message = null;
    });
    try {
      await widget.apiClient.addScheduleWindow(
        storeId: widget.storeId,
        screenId: widget.screenId,
        itemId: itemId,
        start: _windowStartController.text.trim().isEmpty
            ? null
            : _windowStartController.text.trim(),
        end: _windowEndController.text.trim().isEmpty
            ? null
            : _windowEndController.text.trim(),
        days: _windowDays.toList(),
        enabled: _windowEnabled,
      );

      if (!mounted) {
        return;
      }
      setState(() {
        _windowStartController.clear();
        _windowEndController.clear();
        _windowDays = <String>{};
        _windowEnabled = true;
        _showNewWindowForm = false;
        _message = 'Schedule window added.';
      });
      await _loadPlaylist();
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
          _saving = false;
        });
      }
    }
  }

  Future<void> _editScheduleWindow(
      int index, Map<String, dynamic> window) async {
    final itemId = _currentItem?['id']?.toString() ?? '';
    if (itemId.isEmpty) {
      return;
    }

    final startController = TextEditingController(
      text: _formatDisplayDateTime(window['start']),
    );
    final endController = TextEditingController(
      text: _formatDisplayDateTime(window['end']),
    );
    bool localEnabled = (window['enabled'] ?? true) == true;
    Set<String> localDays = _normalizeDays(window['days']).toSet();

    final result = await showDialog<bool>(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              title: const Text('Edit Schedule Window'),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Enabled'),
                      value: localEnabled,
                      onChanged: (value) {
                        setDialogState(() {
                          localEnabled = value;
                        });
                      },
                    ),
                    TextField(
                      controller: startController,
                      decoration: const InputDecoration(labelText: 'Start'),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: endController,
                      decoration: const InputDecoration(labelText: 'End'),
                    ),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: _weekDays.map((day) {
                        final selected = localDays.contains(day);
                        return FilterChip(
                          label: Text(day.toUpperCase()),
                          selected: selected,
                          onSelected: (value) {
                            setDialogState(() {
                              if (value) {
                                localDays.add(day);
                              } else {
                                localDays.remove(day);
                              }
                            });
                          },
                        );
                      }).toList(),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(context).pop(false),
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: () async {
                    Navigator.of(context).pop(true);
                  },
                  child: const Text('Save'),
                ),
              ],
            );
          },
        );
      },
    );

    if (result != true || !mounted) {
      startController.dispose();
      endController.dispose();
      return;
    }

    setState(() {
      _saving = true;
      _message = null;
    });
    try {
      await widget.apiClient.updateScheduleWindow(
        storeId: widget.storeId,
        screenId: widget.screenId,
        itemId: itemId,
        index: index,
        start: startController.text.trim().isEmpty
            ? null
            : startController.text.trim(),
        end: endController.text.trim().isEmpty
            ? null
            : endController.text.trim(),
        days: localDays.toList(),
        enabled: localEnabled,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _message = 'Schedule window updated.';
      });
      await _loadPlaylist();
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _message = e.toString().replaceFirst('Exception: ', '');
      });
    } finally {
      startController.dispose();
      endController.dispose();
      if (mounted) {
        setState(() {
          _saving = false;
        });
      }
    }
  }

  Future<void> _deleteScheduleWindow(int index) async {
    final itemId = _currentItem?['id']?.toString() ?? '';
    if (itemId.isEmpty) {
      return;
    }
    setState(() {
      _saving = true;
      _message = null;
    });
    try {
      await widget.apiClient.deleteScheduleWindow(
        storeId: widget.storeId,
        screenId: widget.screenId,
        itemId: itemId,
        index: index,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _message = 'Schedule window deleted.';
      });
      await _loadPlaylist();
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
          _saving = false;
        });
      }
    }
  }

  Future<void> _pickFile() async {
    final result = await FilePicker.platform.pickFiles(withData: false);
    if (result == null || result.files.isEmpty) {
      return;
    }
    final path = result.files.single.path;
    if (path == null) {
      return;
    }
    setState(() {
      _pickedFile = File(path);
      _message = null;
    });
  }

  Future<void> _replaceMedia() async {
    if (_pickedFile == null) {
      setState(() {
        _message = 'Choose an image or video first.';
      });
      return;
    }

    setState(() {
      _saving = true;
      _message = null;
    });

    try {
      final filename = await widget.apiClient.uploadMedia(_pickedFile!);
      final item = _currentItem;
      final itemId = item?['id']?.toString() ?? '';

      if (itemId.isNotEmpty) {
        await widget.apiClient.updatePlaylistItem(
          storeId: widget.storeId,
          screenId: widget.screenId,
          itemId: itemId,
          file: filename,
        );
      } else {
        await widget.apiClient.assignToScreen(
          storeId: widget.storeId,
          screenId: widget.screenId,
          filename: filename,
        );
      }

      if (!mounted) {
        return;
      }
      setState(() {
        _pickedFile = null;
        _message = 'Media updated successfully.';
      });
      await _loadPlaylist();
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
          _saving = false;
        });
      }
    }
  }

  Future<void> _replaceFromLibrary() async {
    if (_saving) {
      return;
    }

    final selected = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      builder: (context) => FractionallySizedBox(
        heightFactor: 0.88,
        child: _LibraryPickerSheet(apiClient: widget.apiClient),
      ),
    );

    if (selected == null || selected.trim().isEmpty || !mounted) {
      return;
    }

    setState(() {
      _saving = true;
      _message = null;
    });

    try {
      final item = _currentItem;
      final itemId = item?['id']?.toString() ?? '';
      if (itemId.isNotEmpty) {
        await widget.apiClient.updatePlaylistItem(
          storeId: widget.storeId,
          screenId: widget.screenId,
          itemId: itemId,
          file: selected,
        );
      } else {
        await widget.apiClient.assignToScreen(
          storeId: widget.storeId,
          screenId: widget.screenId,
          filename: selected,
        );
      }

      if (!mounted) {
        return;
      }
      setState(() {
        _pickedFile = null;
        _message = 'Media selected from library.';
      });
      await _loadPlaylist();
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
          _saving = false;
        });
      }
    }
  }

  Future<void> _openCreatePlaylistSetup() async {
    final startController = TextEditingController();
    final endController = TextEditingController();
    final durationController = TextEditingController(text: '10');

    File? selectedUpload;
    String? selectedLibraryFile;
    bool enabled = true;
    bool repeat = true;
    int effectId = 0;
    Set<String> days = <String>{};
    String? localError;
    bool creating = false;

    Future<void> pickDateFor(
      TextEditingController controller,
      void Function(void Function()) setModalState,
    ) async {
      final now = DateTime.now();
      final picked = await showDatePicker(
        context: context,
        initialDate: now,
        firstDate: DateTime(now.year - 5),
        lastDate: DateTime(now.year + 10),
      );
      if (picked == null || !mounted) {
        return;
      }
      final hhmmss = () {
        final text = controller.text.trim();
        final m = RegExp(r'(\d{2}:\d{2}:\d{2})').firstMatch(text);
        return m?.group(1) ?? '00:00:00';
      }();
      final dateStr =
          '${picked.year.toString().padLeft(4, '0')}-${picked.month.toString().padLeft(2, '0')}-${picked.day.toString().padLeft(2, '0')}';
      setModalState(() {
        controller.text = '$dateStr $hhmmss';
      });
    }

    Future<void> pickTimeFor(
      TextEditingController controller,
      void Function(void Function()) setModalState,
    ) async {
      final picked = await showTimePicker(
        context: context,
        initialTime: TimeOfDay.now(),
      );
      if (picked == null || !mounted) {
        return;
      }
      final datePart = () {
        final text = controller.text.trim();
        final m = RegExp(r'^(\d{4}-\d{2}-\d{2})').firstMatch(text);
        return m?.group(1);
      }();
      final hh = picked.hour.toString().padLeft(2, '0');
      final mm = picked.minute.toString().padLeft(2, '0');
      setModalState(() {
        controller.text =
            datePart == null ? '$hh:$mm:00' : '$datePart $hh:$mm:00';
      });
    }

    final created = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            return AlertDialog(
              title: const Text('New Playlist Schedule'),
              content: SizedBox(
                width: 520,
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: OutlinedButton.icon(
                              onPressed: creating
                                  ? null
                                  : () async {
                                      final pick = await FilePicker.platform
                                          .pickFiles(withData: false);
                                      if (pick == null ||
                                          pick.files.isEmpty ||
                                          pick.files.first.path == null) {
                                        return;
                                      }
                                      setModalState(() {
                                        selectedUpload =
                                            File(pick.files.first.path!);
                                        selectedLibraryFile = null;
                                        localError = null;
                                      });
                                    },
                              icon: const Icon(Icons.upload_file),
                              label: const Text('Upload Media'),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: OutlinedButton.icon(
                              onPressed: creating
                                  ? null
                                  : () async {
                                      final selected =
                                          await showModalBottomSheet<String>(
                                        context: context,
                                        isScrollControlled: true,
                                        builder: (context) =>
                                            FractionallySizedBox(
                                          heightFactor: 0.88,
                                          child: _LibraryPickerSheet(
                                            apiClient: widget.apiClient,
                                          ),
                                        ),
                                      );
                                      if (selected == null ||
                                          selected.trim().isEmpty) {
                                        return;
                                      }
                                      setModalState(() {
                                        selectedLibraryFile = selected;
                                        selectedUpload = null;
                                        localError = null;
                                      });
                                    },
                              icon: const Icon(Icons.collections),
                              label: const Text('Choose Library'),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Text(
                        selectedUpload != null
                            ? 'Selected upload: ${selectedUpload!.uri.pathSegments.last}'
                            : selectedLibraryFile != null
                                ? 'Selected library: ${selectedLibraryFile!}'
                                : 'No media selected yet',
                      ),
                      const SizedBox(height: 10),
                      SwitchListTile(
                        contentPadding: EdgeInsets.zero,
                        title: const Text('Enabled'),
                        value: enabled,
                        onChanged: creating
                            ? null
                            : (value) => setModalState(() {
                                  enabled = value;
                                }),
                      ),
                      SwitchListTile(
                        contentPadding: EdgeInsets.zero,
                        title: const Text('Repeat'),
                        value: repeat,
                        onChanged: creating
                            ? null
                            : (value) => setModalState(() {
                                  repeat = value;
                                }),
                      ),
                      TextField(
                        controller: durationController,
                        keyboardType: TextInputType.number,
                        decoration:
                            const InputDecoration(labelText: 'Duration (s)'),
                      ),
                      const SizedBox(height: 10),
                      const Text('Effect'),
                      const SizedBox(height: 6),
                      Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        children: [
                          ChoiceChip(
                            label: const Text('·'),
                            selected: effectId == 0,
                            onSelected: creating
                                ? null
                                : (_) => setModalState(() {
                                      effectId = 0;
                                    }),
                          ),
                          ...List.generate(10, (index) {
                            final id = index + 1;
                            return ChoiceChip(
                              label: Text('$id'),
                              selected: effectId == id,
                              onSelected: creating
                                  ? null
                                  : (_) => setModalState(() {
                                        effectId = id;
                                      }),
                            );
                          }),
                        ],
                      ),
                      const SizedBox(height: 10),
                      const Text('Days'),
                      const SizedBox(height: 6),
                      Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        children: _weekDays.map((day) {
                          final selected = days.contains(day);
                          return FilterChip(
                            label: Text(day.toUpperCase()),
                            selected: selected,
                            onSelected: creating
                                ? null
                                : (value) => setModalState(() {
                                      if (value) {
                                        days.add(day);
                                      } else {
                                        days.remove(day);
                                      }
                                    }),
                          );
                        }).toList(),
                      ),
                      const SizedBox(height: 10),
                      TextField(
                        controller: startController,
                        decoration: InputDecoration(
                          labelText: 'Start',
                          hintText: 'YYYY-MM-DD HH:MM:SS',
                          suffixIcon: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              IconButton(
                                onPressed: creating
                                    ? null
                                    : () => pickDateFor(
                                        startController, setModalState),
                                icon: const Icon(Icons.date_range),
                              ),
                              IconButton(
                                onPressed: creating
                                    ? null
                                    : () => pickTimeFor(
                                        startController, setModalState),
                                icon: const Icon(Icons.access_time),
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 10),
                      TextField(
                        controller: endController,
                        decoration: InputDecoration(
                          labelText: 'End',
                          hintText: 'YYYY-MM-DD HH:MM:SS',
                          suffixIcon: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              IconButton(
                                onPressed: creating
                                    ? null
                                    : () => pickDateFor(
                                        endController, setModalState),
                                icon: const Icon(Icons.date_range),
                              ),
                              IconButton(
                                onPressed: creating
                                    ? null
                                    : () => pickTimeFor(
                                        endController, setModalState),
                                icon: const Icon(Icons.access_time),
                              ),
                            ],
                          ),
                        ),
                      ),
                      if (localError != null) ...[
                        const SizedBox(height: 10),
                        Text(
                          localError!,
                          style: TextStyle(
                              color: Theme.of(context).colorScheme.error),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
              actions: [
                TextButton(
                  onPressed: creating
                      ? null
                      : () => Navigator.of(dialogContext).pop(false),
                  child: const Text('Cancel'),
                ),
                FilledButton.icon(
                  onPressed: creating
                      ? null
                      : () async {
                          if (selectedUpload == null &&
                              (selectedLibraryFile == null ||
                                  selectedLibraryFile!.trim().isEmpty)) {
                            setModalState(() {
                              localError =
                                  'Select media (upload or library) first.';
                            });
                            return;
                          }

                          setModalState(() {
                            creating = true;
                            localError = null;
                          });

                          try {
                            String filename;
                            if (selectedUpload != null) {
                              filename = await widget.apiClient
                                  .uploadMedia(selectedUpload!);
                            } else {
                              filename = selectedLibraryFile!.trim();
                            }

                            await widget.apiClient.assignToScreen(
                              storeId: widget.storeId,
                              screenId: widget.screenId,
                              filename: filename,
                            );

                            final playlist = await widget.apiClient.getPlaylist(
                              storeId: widget.storeId,
                              screenId: widget.screenId,
                            );

                            String? createdItemId;
                            for (int i = playlist.length - 1; i >= 0; i--) {
                              final file =
                                  (playlist[i]['file'] ?? '').toString().trim();
                              if (file == filename) {
                                createdItemId =
                                    (playlist[i]['id'] ?? '').toString().trim();
                                break;
                              }
                            }
                            createdItemId ??= (playlist.isNotEmpty
                                    ? '${playlist.last['id'] ?? ''}'
                                    : '')
                                .trim();

                            if (createdItemId.isNotEmpty) {
                              final parsedDuration = int.tryParse(
                                      durationController.text.trim()) ??
                                  10;
                              await widget.apiClient.updatePlaylistItem(
                                storeId: widget.storeId,
                                screenId: widget.screenId,
                                itemId: createdItemId,
                                start: startController.text.trim(),
                                end: endController.text.trim(),
                                enabled: enabled,
                                repeat: repeat,
                                duration:
                                    parsedDuration < 1 ? 1 : parsedDuration,
                                days: days.toList(),
                                effectId: effectId,
                              );
                            }

                            if (dialogContext.mounted) {
                              Navigator.of(dialogContext).pop(true);
                            }
                          } catch (e) {
                            setModalState(() {
                              localError =
                                  e.toString().replaceFirst('Exception: ', '');
                              creating = false;
                            });
                          }
                        },
                  icon: creating
                      ? const SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.add),
                  label:
                      Text(creating ? 'Creating...' : 'Create Playlist Item'),
                ),
              ],
            );
          },
        );
      },
    );

    startController.dispose();
    endController.dispose();
    durationController.dispose();

    if (created == true && mounted) {
      setState(() {
        _message = 'New playlist item created.';
      });
      await _loadPlaylist();
    }
  }

  Future<void> _deleteCurrentPlaylistItem() async {
    final itemId = _currentItem?['id']?.toString() ?? '';
    if (itemId.isEmpty) {
      setState(() {
        _message = 'No playlist item selected.';
      });
      return;
    }

    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Playlist Item'),
        content: const Text('Delete the currently selected media item?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (accepted != true) {
      return;
    }

    setState(() {
      _saving = true;
      _message = null;
    });
    try {
      await widget.apiClient.deletePlaylistItem(
        storeId: widget.storeId,
        screenId: widget.screenId,
        itemId: itemId,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _selectedItemId = null;
        _message = 'Playlist item deleted.';
      });
      await _loadPlaylist();
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
          _saving = false;
        });
      }
    }
  }

  Future<void> _pickDateFor(TextEditingController controller) async {
    final now = DateTime.now();
    DateTime initialDate = now;
    final text = controller.text.trim();
    if (text.length >= 10) {
      try {
        initialDate = DateTime.parse(text.substring(0, 10));
      } catch (_) {}
    }

    final picked = await showDatePicker(
      context: context,
      initialDate: initialDate,
      firstDate: DateTime(2020),
      lastDate: DateTime(2100),
    );
    if (picked == null) {
      return;
    }
    if (!mounted) {
      return;
    }

    final month = picked.month.toString().padLeft(2, '0');
    final day = picked.day.toString().padLeft(2, '0');
    final existingTime = _extractTimePart(text);
    setState(() {
      controller.text = existingTime == null
          ? '${picked.year}-$month-$day'
          : '${picked.year}-$month-$day $existingTime';
    });
    _queueAutoSave();
  }

  String? _extractTimePart(String raw) {
    final text = raw.trim();
    if (text.isEmpty) {
      return null;
    }
    final match = RegExp(r'(\d{2}:\d{2}(?::\d{2})?)').firstMatch(text);
    if (match == null) {
      return null;
    }
    final found = match.group(1) ?? '';
    if (found.length == 5) {
      return '$found:00';
    }
    return found;
  }

  String? _extractDatePart(String raw) {
    final text = raw.trim();
    if (text.isEmpty) {
      return null;
    }
    final iso = RegExp(r'^(\d{4}-\d{2}-\d{2})').firstMatch(text);
    if (iso != null) {
      return iso.group(1);
    }
    final us = RegExp(r'^(\d{2}/\d{2}/\d{4})').firstMatch(text);
    if (us != null) {
      return us.group(1);
    }
    return null;
  }

  Future<void> _pickTimeFor(TextEditingController controller) async {
    final text = controller.text.trim();
    final now = TimeOfDay.now();
    TimeOfDay initial = now;
    final existing = _extractTimePart(text);
    if (existing != null && existing.length >= 5) {
      final parts = existing.split(':');
      final h = int.tryParse(parts[0]);
      final m = int.tryParse(parts[1]);
      if (h != null && m != null && h >= 0 && h < 24 && m >= 0 && m < 60) {
        initial = TimeOfDay(hour: h, minute: m);
      }
    }

    final picked = await showTimePicker(
      context: context,
      initialTime: initial,
    );
    if (picked == null || !mounted) {
      return;
    }

    final hh = picked.hour.toString().padLeft(2, '0');
    final mm = picked.minute.toString().padLeft(2, '0');
    final datePart = _extractDatePart(text);
    setState(() {
      controller.text =
          datePart == null ? '$hh:$mm:00' : '$datePart $hh:$mm:00';
    });
    _queueAutoSave();
  }

  Widget _buildSectionCaption(String text) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Text(
      text,
      style: theme.textTheme.labelLarge?.copyWith(
        color: scheme.onSurfaceVariant,
        fontWeight: FontWeight.w600,
      ),
    );
  }

  Widget _buildCompactToggleTile({
    required String label,
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Row(
        children: [
          Expanded(child: Text(label)),
          Switch.adaptive(
            value: value,
            onChanged: _saving ? null : onChanged,
          ),
        ],
      ),
    );
  }

  Widget _buildDateTimeField({
    required TextEditingController controller,
    required String label,
    required VoidCallback onPickDate,
    required VoidCallback onPickTime,
  }) {
    return TextField(
      controller: controller,
      onChanged: _saving ? null : (_) => _queueAutoSave(),
      decoration: InputDecoration(
        labelText: label,
        hintText: 'YYYY-MM-DD HH:MM:SS',
        suffixIcon: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconButton(
              tooltip: 'Pick date',
              icon: const Icon(Icons.date_range),
              onPressed: _saving ? null : onPickDate,
            ),
            IconButton(
              tooltip: 'Pick time',
              icon: const Icon(Icons.access_time),
              onPressed: _saving ? null : onPickTime,
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final item = _currentItem;
    final itemUrl = _resolvePreviewUrl(item);
    final mediaType = _resolveMediaType(item, itemUrl);
    final currentFile = (item?['file'] ?? '').toString().trim();
    final isYouTube = currentFile.toLowerCase().startsWith(
          'youtube:',
        );
    final youTubeId =
        isYouTube ? currentFile.substring('youtube:'.length).trim() : '';
    final hasImage =
        (mediaType == 'image' || mediaType == 'animated') && itemUrl.isNotEmpty;
    final hasVideo = mediaType == 'video' && itemUrl.isNotEmpty;
    final rotationAngle = _screenRotation * (3.1415926535897932 / 180.0);

    return Column(
      children: [
        Container(
          padding: const EdgeInsets.fromLTRB(16, 12, 8, 10),
          decoration: BoxDecoration(
            color: Colors.white,
            border: Border(
              bottom: BorderSide(color: scheme.outlineVariant),
            ),
          ),
          child: Wrap(
            spacing: 8,
            runSpacing: 8,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              SizedBox(
                width: MediaQuery.of(context).size.width - 120,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      widget.screenName,
                      style: theme.textTheme.titleLarge,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '${widget.storeId} • ${widget.screenId}',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  IconButton(
                    visualDensity: VisualDensity.compact,
                    onPressed: _loading ? null : _loadPlaylist,
                    icon: const Icon(Icons.refresh),
                  ),
                  IconButton(
                    visualDensity: VisualDensity.compact,
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(Icons.close),
                  ),
                ],
              ),
            ],
          ),
        ),
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(14),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Current Media',
                                style: theme.textTheme.titleMedium),
                            if (_playlist.length > 1) ...[
                              const SizedBox(height: 10),
                              InkWell(
                                borderRadius: BorderRadius.circular(10),
                                onTap: _pickPlaylistItemVisual,
                                child: InputDecorator(
                                  decoration: const InputDecoration(
                                    labelText: 'Playlist Item',
                                  ),
                                  child: Row(
                                    children: [
                                      Expanded(
                                        child: Text(
                                          _itemLabel(_currentItem ?? const {}),
                                          maxLines: 1,
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                      ),
                                      const SizedBox(width: 8),
                                      const Icon(Icons.arrow_drop_down),
                                    ],
                                  ),
                                ),
                              ),
                            ],
                            const SizedBox(height: 10),
                            ClipRRect(
                              borderRadius: BorderRadius.circular(12),
                              child: AspectRatio(
                                aspectRatio: 16 / 9,
                                child: ColoredBox(
                                  color: const Color(0xFFF1F5F9),
                                  child: Transform.rotate(
                                    angle: rotationAngle,
                                    child: hasImage
                                        ? Image.network(
                                            itemUrl,
                                            headers: _previewHeaders,
                                            fit: BoxFit.cover,
                                            errorBuilder: (_, __, ___) =>
                                                const Center(
                                              child: Icon(Icons.broken_image,
                                                  size: 36),
                                            ),
                                          )
                                        : hasVideo
                                            ? (isYouTube &&
                                                    youTubeId.length == 11
                                                ? _YouTubePreview(
                                                    key: ValueKey(
                                                        'yt-$youTubeId'),
                                                    videoId: youTubeId,
                                                  )
                                                : const Center(
                                                    child: Column(
                                                      mainAxisSize:
                                                          MainAxisSize.min,
                                                      children: [
                                                        Icon(Icons.movie,
                                                            size: 40),
                                                        SizedBox(height: 8),
                                                        Text('Video selected'),
                                                      ],
                                                    ),
                                                  ))
                                            : const Center(
                                                child: Column(
                                                  mainAxisSize:
                                                      MainAxisSize.min,
                                                  children: [
                                                    Icon(Icons.perm_media,
                                                        size: 36),
                                                    SizedBox(height: 8),
                                                    Text(
                                                        'No media assigned yet'),
                                                  ],
                                                ),
                                              ),
                                  ),
                                ),
                              ),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              item == null
                                  ? 'Upload an image/video below to assign this screen.'
                                  : 'Type: ${mediaType.isEmpty ? 'unknown' : mediaType}',
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: scheme.onSurfaceVariant,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              'Live sync with website: every 5 seconds',
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: scheme.primary,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const SizedBox(height: 10),
                            SingleChildScrollView(
                              scrollDirection: Axis.horizontal,
                              child: Row(
                                children: [
                                  _buildQuickActionButton(
                                    tooltip: 'Schedule',
                                    icon: Icons.schedule,
                                    background: const Color(0xFF2563EB),
                                    onPressed: (_saving || _quickActionBusy)
                                        ? null
                                        : _openCreatePlaylistSetup,
                                  ),
                                  const SizedBox(width: 6),
                                  _buildQuickActionButton(
                                    tooltip: 'Auto',
                                    icon: Icons.content_cut,
                                    background: const Color(0xFF16A34A),
                                    onPressed: (_saving || _quickActionBusy)
                                        ? null
                                        : _quickAutoSlice,
                                  ),
                                  const SizedBox(width: 6),
                                  _buildQuickActionButton(
                                    tooltip: 'YouTube',
                                    icon: Icons.play_arrow,
                                    background: const Color(0xFFDC2626),
                                    onPressed: (_saving || _quickActionBusy)
                                        ? null
                                        : _quickAddYouTube,
                                  ),
                                  const SizedBox(width: 6),
                                  _buildQuickActionButton(
                                    tooltip: 'Rotate',
                                    icon: Icons.rotate_left,
                                    background: const Color(0xFF6366F1),
                                    onPressed: (_saving || _quickActionBusy)
                                        ? null
                                        : _quickRotate,
                                  ),
                                  const SizedBox(width: 6),
                                  _buildQuickActionButton(
                                    tooltip: _screenMuted
                                        ? 'Unmute Screen'
                                        : 'Mute Screen',
                                    icon: _screenMuted
                                        ? Icons.volume_off
                                        : Icons.volume_up,
                                    background: _screenMuted
                                        ? const Color(0xFF6B7280)
                                        : const Color(0xFF059669),
                                    onPressed: (_saving || _quickActionBusy)
                                        ? null
                                        : _quickToggleMute,
                                  ),
                                  const SizedBox(width: 6),
                                  _buildQuickActionButton(
                                    tooltip: 'Display',
                                    icon: Icons.open_in_browser,
                                    background: const Color(0xFF0EA5E9),
                                    onPressed: (_saving || _quickActionBusy)
                                        ? null
                                        : _openDisplayPlayer,
                                  ),
                                ],
                              ),
                            ),
                            if (_quickActionBusy) ...[
                              const SizedBox(height: 6),
                              LinearProgressIndicator(
                                minHeight: 2,
                                borderRadius: BorderRadius.circular(999),
                              ),
                            ],
                            const SizedBox(height: 10),
                            Align(
                              alignment: Alignment.centerLeft,
                              child: OutlinedButton.icon(
                                onPressed: _saving || item == null
                                    ? null
                                    : _deleteCurrentPlaylistItem,
                                icon: const Icon(Icons.delete_outline),
                                label: const Text('Delete Current Item'),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    if (_message != null) ...[
                      const SizedBox(height: 10),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: scheme.surfaceContainer,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: scheme.outlineVariant),
                        ),
                        child: Text(_message!),
                      ),
                    ],
                    const SizedBox(height: 10),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(14),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Playback & Timeline',
                                style: theme.textTheme.titleMedium),
                            const SizedBox(height: 4),
                            Text(
                              'Control enabled, repeat, duration, days, and primary timeline like website.',
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: scheme.onSurfaceVariant,
                              ),
                            ),
                            const SizedBox(height: 12),
                            _buildSectionCaption('Playback Controls'),
                            const SizedBox(height: 8),
                            LayoutBuilder(
                              builder: (context, constraints) {
                                final stacked = constraints.maxWidth < 560;
                                final enabledTile = _buildCompactToggleTile(
                                  label: 'Enabled',
                                  value: _itemEnabled,
                                  onChanged: (value) {
                                    setState(() {
                                      _itemEnabled = value;
                                    });
                                    _queueAutoSave();
                                  },
                                );
                                final repeatTile = _buildCompactToggleTile(
                                  label: 'Repeat',
                                  value: _itemRepeat,
                                  onChanged: (value) {
                                    setState(() {
                                      _itemRepeat = value;
                                    });
                                    _queueAutoSave();
                                  },
                                );
                                if (stacked) {
                                  return Column(
                                    children: [
                                      enabledTile,
                                      const SizedBox(height: 8),
                                      repeatTile,
                                    ],
                                  );
                                }
                                return Row(
                                  children: [
                                    Expanded(child: enabledTile),
                                    const SizedBox(width: 8),
                                    Expanded(child: repeatTile),
                                  ],
                                );
                              },
                            ),
                            const SizedBox(height: 12),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 12, vertical: 8),
                              decoration: BoxDecoration(
                                color: scheme.surfaceContainerLow,
                                borderRadius: BorderRadius.circular(12),
                                border:
                                    Border.all(color: scheme.outlineVariant),
                              ),
                              child: Row(
                                children: [
                                  const Expanded(child: Text('Duration (s)')),
                                  IconButton(
                                    visualDensity: VisualDensity.compact,
                                    onPressed: _saving
                                        ? null
                                        : () {
                                            setState(() {
                                              if (_itemDuration > 1) {
                                                _itemDuration--;
                                              }
                                            });
                                            _queueAutoSave();
                                          },
                                    icon:
                                        const Icon(Icons.remove_circle_outline),
                                  ),
                                  Text(
                                    '$_itemDuration',
                                    style: theme.textTheme.titleMedium,
                                  ),
                                  IconButton(
                                    visualDensity: VisualDensity.compact,
                                    onPressed: _saving
                                        ? null
                                        : () {
                                            setState(() {
                                              _itemDuration++;
                                            });
                                            _queueAutoSave();
                                          },
                                    icon: const Icon(Icons.add_circle_outline),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(height: 12),
                            _buildSectionCaption('Effect'),
                            const SizedBox(height: 8),
                            Wrap(
                              spacing: 8,
                              runSpacing: 8,
                              children: [
                                ChoiceChip(
                                  label: const Text('·'),
                                  selected: _itemEffectId == 0,
                                  onSelected: _saving
                                      ? null
                                      : (_) {
                                          setState(() {
                                            _itemEffectId = 0;
                                          });
                                          _queueAutoSave();
                                        },
                                ),
                                ...List.generate(10, (index) {
                                  final effectId = index + 1;
                                  return ChoiceChip(
                                    label: Text('$effectId'),
                                    selected: effectId == _itemEffectId,
                                    onSelected: _saving
                                        ? null
                                        : (_) {
                                            setState(() {
                                              _itemEffectId = effectId;
                                            });
                                            _queueAutoSave();
                                          },
                                  );
                                }),
                              ],
                            ),
                            const SizedBox(height: 12),
                            _buildSectionCaption('Active Days'),
                            const SizedBox(height: 8),
                            Wrap(
                              spacing: 6,
                              runSpacing: 6,
                              children: _weekDays.map((day) {
                                final selected = _itemDays.contains(day);
                                return FilterChip(
                                  label: Text(day.toUpperCase()),
                                  selected: selected,
                                  onSelected: _saving
                                      ? null
                                      : (value) {
                                          setState(() {
                                            if (value) {
                                              _itemDays.add(day);
                                            } else {
                                              _itemDays.remove(day);
                                            }
                                          });
                                          _queueAutoSave();
                                        },
                                );
                              }).toList(),
                            ),
                            const SizedBox(height: 12),
                            _buildSectionCaption('Primary Timeline'),
                            const SizedBox(height: 8),
                            LayoutBuilder(
                              builder: (context, constraints) {
                                final wide = constraints.maxWidth >= 700;
                                final startField = _buildDateTimeField(
                                  controller: _startController,
                                  label: 'Start',
                                  onPickDate: () =>
                                      _pickDateFor(_startController),
                                  onPickTime: () =>
                                      _pickTimeFor(_startController),
                                );
                                final endField = _buildDateTimeField(
                                  controller: _endController,
                                  label: 'End',
                                  onPickDate: () =>
                                      _pickDateFor(_endController),
                                  onPickTime: () =>
                                      _pickTimeFor(_endController),
                                );
                                if (!wide) {
                                  return Column(
                                    children: [
                                      startField,
                                      const SizedBox(height: 10),
                                      endField,
                                    ],
                                  );
                                }
                                return Row(
                                  children: [
                                    Expanded(child: startField),
                                    const SizedBox(width: 10),
                                    Expanded(child: endField),
                                  ],
                                );
                              },
                            ),
                            const SizedBox(height: 10),
                            SizedBox(
                              width: double.infinity,
                              child: FilledButton.icon(
                                onPressed: _saving ? null : _saveItemSettings,
                                icon: const Icon(Icons.schedule),
                                label: Text(_saving
                                    ? 'Saving...'
                                    : 'Save Playback Settings'),
                              ),
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
                            Text('Schedule Windows',
                                style: theme.textTheme.titleMedium),
                            const SizedBox(height: 4),
                            Text(
                              'Add multiple active windows like website schedule rows.',
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: scheme.onSurfaceVariant,
                              ),
                            ),
                            const SizedBox(height: 10),
                            SizedBox(
                              width: double.infinity,
                              child: FilledButton.tonalIcon(
                                onPressed: _saving
                                    ? null
                                    : () {
                                        setState(() {
                                          _showNewWindowForm = true;
                                        });
                                      },
                                icon: const Icon(Icons.add),
                                label: const Text('Add Schedule Window'),
                              ),
                            ),
                            if (_showNewWindowForm) ...[
                              const SizedBox(height: 10),
                              SwitchListTile(
                                contentPadding: EdgeInsets.zero,
                                title: const Text('New Window Enabled'),
                                value: _windowEnabled,
                                onChanged: _saving
                                    ? null
                                    : (value) {
                                        setState(() {
                                          _windowEnabled = value;
                                        });
                                      },
                              ),
                              TextField(
                                controller: _windowStartController,
                                decoration: InputDecoration(
                                  labelText: 'Window Start',
                                  hintText: 'YYYY-MM-DD HH:MM:SS',
                                  suffixIcon: Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      IconButton(
                                        tooltip: 'Pick date',
                                        icon: const Icon(Icons.date_range),
                                        onPressed: _saving
                                            ? null
                                            : () => _pickDateFor(
                                                _windowStartController),
                                      ),
                                      IconButton(
                                        tooltip: 'Pick time',
                                        icon: const Icon(Icons.access_time),
                                        onPressed: _saving
                                            ? null
                                            : () => _pickTimeFor(
                                                _windowStartController),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                              const SizedBox(height: 10),
                              TextField(
                                controller: _windowEndController,
                                decoration: InputDecoration(
                                  labelText: 'Window End',
                                  hintText: 'YYYY-MM-DD HH:MM:SS',
                                  suffixIcon: Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      IconButton(
                                        tooltip: 'Pick date',
                                        icon: const Icon(Icons.date_range),
                                        onPressed: _saving
                                            ? null
                                            : () => _pickDateFor(
                                                _windowEndController),
                                      ),
                                      IconButton(
                                        tooltip: 'Pick time',
                                        icon: const Icon(Icons.access_time),
                                        onPressed: _saving
                                            ? null
                                            : () => _pickTimeFor(
                                                _windowEndController),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                              const SizedBox(height: 8),
                              Wrap(
                                spacing: 6,
                                runSpacing: 6,
                                children: _weekDays.map((day) {
                                  final selected = _windowDays.contains(day);
                                  return FilterChip(
                                    label: Text(day.toUpperCase()),
                                    selected: selected,
                                    onSelected: _saving
                                        ? null
                                        : (value) {
                                            setState(() {
                                              if (value) {
                                                _windowDays.add(day);
                                              } else {
                                                _windowDays.remove(day);
                                              }
                                            });
                                          },
                                  );
                                }).toList(),
                              ),
                              const SizedBox(height: 10),
                              Wrap(
                                spacing: 8,
                                runSpacing: 8,
                                children: [
                                  FilledButton.icon(
                                    onPressed:
                                        _saving ? null : _addScheduleWindow,
                                    icon: const Icon(Icons.check),
                                    label: const Text('Save New Window'),
                                  ),
                                  OutlinedButton(
                                    onPressed: _saving
                                        ? null
                                        : () {
                                            setState(() {
                                              _showNewWindowForm = false;
                                              _windowStartController.clear();
                                              _windowEndController.clear();
                                              _windowDays = <String>{};
                                              _windowEnabled = true;
                                            });
                                          },
                                    child: const Text('Cancel'),
                                  ),
                                ],
                              ),
                            ],
                            const SizedBox(height: 10),
                            if (_scheduleWindows().isEmpty)
                              Text(
                                'No schedule windows yet.',
                                style: theme.textTheme.bodySmall?.copyWith(
                                  color: scheme.onSurfaceVariant,
                                ),
                              )
                            else
                              ..._scheduleWindows()
                                  .asMap()
                                  .entries
                                  .map((entry) {
                                final idx = entry.key;
                                final window = entry.value;
                                final days = _normalizeDays(window['days']);
                                return Container(
                                  margin: const EdgeInsets.only(bottom: 8),
                                  padding: const EdgeInsets.all(10),
                                  decoration: BoxDecoration(
                                    color: scheme.surfaceContainerLow,
                                    borderRadius: BorderRadius.circular(12),
                                    border: Border.all(
                                        color: scheme.outlineVariant),
                                  ),
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Row(
                                        children: [
                                          Text(
                                            'Window ${idx + 1}',
                                            style: theme.textTheme.titleSmall,
                                          ),
                                          const Spacer(),
                                          if ((window['enabled'] ?? true) ==
                                              true)
                                            const Icon(Icons.check_circle,
                                                size: 16,
                                                color: Color(0xFF16A34A))
                                          else
                                            const Icon(Icons.pause_circle,
                                                size: 16,
                                                color: Color(0xFF6B7280)),
                                        ],
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        'Start: ${_formatDisplayDateTime(window['start']).isEmpty ? '-' : _formatDisplayDateTime(window['start'])}\nEnd: ${_formatDisplayDateTime(window['end']).isEmpty ? '-' : _formatDisplayDateTime(window['end'])}',
                                        style: theme.textTheme.bodySmall,
                                      ),
                                      if (days.isNotEmpty) ...[
                                        const SizedBox(height: 6),
                                        Wrap(
                                          spacing: 6,
                                          runSpacing: 6,
                                          children: days
                                              .map((d) => Chip(
                                                    label:
                                                        Text(d.toUpperCase()),
                                                  ))
                                              .toList(),
                                        ),
                                      ],
                                      const SizedBox(height: 6),
                                      Wrap(
                                        spacing: 8,
                                        runSpacing: 8,
                                        children: [
                                          OutlinedButton.icon(
                                            onPressed: _saving
                                                ? null
                                                : () => _editScheduleWindow(
                                                      idx,
                                                      window,
                                                    ),
                                            icon: const Icon(Icons.edit),
                                            label: const Text('Edit'),
                                          ),
                                          OutlinedButton.icon(
                                            onPressed: _saving
                                                ? null
                                                : () =>
                                                    _deleteScheduleWindow(idx),
                                            icon: const Icon(Icons.delete),
                                            label: const Text('Delete'),
                                          ),
                                        ],
                                      ),
                                    ],
                                  ),
                                );
                              }),
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
                            Text('Replace Media',
                                style: theme.textTheme.titleMedium),
                            const SizedBox(height: 10),
                            Row(
                              children: [
                                Expanded(
                                  child: Text(
                                    _pickedFile == null
                                        ? 'No file selected'
                                        : _pickedFile!.uri.pathSegments.last,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                                const SizedBox(width: 8),
                                OutlinedButton.icon(
                                  onPressed: _saving ? null : _pickFile,
                                  icon: const Icon(Icons.folder_open),
                                  label: const Text('Choose'),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            SizedBox(
                              width: double.infinity,
                              child: OutlinedButton.icon(
                                onPressed: _saving ? null : _replaceFromLibrary,
                                icon: const Icon(Icons.collections),
                                label:
                                    const Text('Choose Existing from Library'),
                              ),
                            ),
                            const SizedBox(height: 10),
                            SizedBox(
                              width: double.infinity,
                              child: FilledButton.icon(
                                style: FilledButton.styleFrom(
                                  backgroundColor: const Color(0xFF16A34A),
                                  foregroundColor: Colors.white,
                                ),
                                onPressed: _saving ? null : _replaceMedia,
                                icon: const Icon(Icons.cloud_upload),
                                label: Text(_saving
                                    ? 'Updating...'
                                    : 'Replace Image/Video'),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
        ),
      ],
    );
  }
}

class _VideoPreview extends StatefulWidget {
  const _VideoPreview({
    required this.url,
  });

  final String url;
  final Map<String, String> headers;

  @override
  State<_VideoPreview> createState() => _VideoPreviewState();
}

class _LibraryPickerSheet extends StatefulWidget {
  const _LibraryPickerSheet({required this.apiClient});

  final ApiClient apiClient;

  @override
  State<_LibraryPickerSheet> createState() => _LibraryPickerSheetState();
}

class _LibraryPickerSheetState extends State<_LibraryPickerSheet> {
  bool _loading = true;
  String? _error;
  String _prefix = '';
  String _filter = 'all';
  Map<String, String> _authHeaders = const {};
  List<Map<String, dynamic>> _dirs = const [];
  List<Map<String, dynamic>> _files = const [];

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
      final data = await widget.apiClient
          .listLibrary(prefix: _prefix.isEmpty ? null : _prefix);
      if (!mounted) {
        return;
      }
      final dirs = data['dirs'] is List ? (data['dirs'] as List) : const [];
      final files = data['files'] is List ? (data['files'] as List) : const [];
      setState(() {
        _dirs = dirs
            .map((item) => item is Map
                ? item.map((k, v) => MapEntry(k.toString(), v))
                : <String, dynamic>{})
            .where((item) => item.isNotEmpty)
            .toList();
        _files = files
            .map((item) => item is Map
                ? item.map((k, v) => MapEntry(k.toString(), v))
                : <String, dynamic>{})
            .where((item) => item.isNotEmpty)
            .toList();
      });

      final sampleUrl = _files
          .map((f) => (f['url'] ?? '').toString().trim())
          .firstWhere((u) => u.isNotEmpty,
              orElse: () => widget.apiClient.baseUrl);
      final headers = await widget.apiClient.getAuthHeadersForUrl(sampleUrl);
      if (!mounted) {
        return;
      }
      setState(() {
        _authHeaders = headers;
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
          _loading = false;
        });
      }
    }
  }

  List<Map<String, dynamic>> _filteredFiles() {
    if (_filter == 'all') {
      return _files;
    }
    return _files.where((file) {
      final mediaType = (file['media_type'] ?? '').toString().toLowerCase();
      if (_filter == 'images') {
        return mediaType == 'image' || mediaType == 'animated';
      }
      if (_filter == 'videos') {
        return mediaType == 'video';
      }
      return true;
    }).toList();
  }

  String _basename(String path) {
    final cleaned = path.trim();
    if (cleaned.isEmpty) {
      return cleaned;
    }
    final parts = cleaned.split('/');
    return parts.isEmpty ? cleaned : parts.last;
  }

  String _encodePathForRoute(String value) {
    return value
        .split('/')
        .where((segment) => segment.trim().isNotEmpty)
        .map(Uri.encodeComponent)
        .join('/');
  }

  String _previewUrlForFile(Map<String, dynamic> file) {
    final name = (file['name'] ?? '').toString().trim();
    final rawUrl = (file['url'] ?? '').toString().trim();
    if (name.isEmpty) {
      return rawUrl;
    }

    final mediaType = (file['media_type'] ?? '').toString().toLowerCase();
    final base = widget.apiClient.baseUrl.replaceAll(RegExp(r'/$'), '');
    final encodedName = _encodePathForRoute(name);
    if (mediaType == 'video') {
      return '$base/vthumb/96/$encodedName';
    }
    return '$base/thumb/96/$encodedName';
  }

  Widget _fileLeading(Map<String, dynamic> file) {
    final mediaType = (file['media_type'] ?? '').toString().toLowerCase();
    final url = _previewUrlForFile(file);
    if (url.isNotEmpty) {
      return ClipRRect(
        borderRadius: BorderRadius.circular(6),
        child: Image.network(
          url,
          headers: _authHeaders,
          width: 44,
          height: 44,
          fit: BoxFit.cover,
          errorBuilder: (_, __, ___) => const SizedBox(
            width: 44,
            height: 44,
            child: Icon(Icons.broken_image),
          ),
        ),
      );
    }
    return Icon(mediaType == 'video' ? Icons.movie : Icons.image);
  }

  void _goUp() {
    if (_prefix.isEmpty) {
      return;
    }
    final idx = _prefix.lastIndexOf('/');
    setState(() {
      _prefix = idx <= 0 ? '' : _prefix.substring(0, idx);
    });
    _load();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final files = _filteredFiles();

    return SafeArea(
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 10, 8, 8),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    'Choose Existing Media',
                    style: theme.textTheme.titleMedium,
                  ),
                ),
                IconButton(
                  onPressed: () => Navigator.of(context).pop(),
                  icon: const Icon(Icons.close),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
            child: Row(
              children: [
                OutlinedButton.icon(
                  onPressed: _prefix.isEmpty || _loading ? null : _goUp,
                  icon: const Icon(Icons.arrow_upward),
                  label: const Text('Up'),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _prefix.isEmpty ? 'Library root' : _prefix,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: theme.textTheme.bodySmall,
                  ),
                ),
                IconButton(
                  onPressed: _loading ? null : _load,
                  icon: const Icon(Icons.refresh),
                  tooltip: 'Refresh',
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: SegmentedButton<String>(
              segments: const [
                ButtonSegment<String>(value: 'all', label: Text('All')),
                ButtonSegment<String>(value: 'images', label: Text('Images')),
                ButtonSegment<String>(value: 'videos', label: Text('Videos')),
              ],
              selected: <String>{_filter},
              onSelectionChanged: (selection) {
                final next = selection.isEmpty ? 'all' : selection.first;
                setState(() {
                  _filter = next;
                });
              },
            ),
          ),
          const SizedBox(height: 8),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Text(
                            _error!,
                            style: theme.textTheme.bodyMedium?.copyWith(
                              color: theme.colorScheme.error,
                            ),
                            textAlign: TextAlign.center,
                          ),
                        ),
                      )
                    : ListView(
                        padding: const EdgeInsets.fromLTRB(8, 0, 8, 12),
                        children: [
                          if (_dirs.isNotEmpty) ...[
                            Padding(
                              padding: const EdgeInsets.fromLTRB(8, 6, 8, 4),
                              child: Text('Folders',
                                  style: theme.textTheme.titleSmall),
                            ),
                            ..._dirs.map((dir) {
                              final dirName = (dir['name'] ?? '').toString();
                              final dirPrefix =
                                  (dir['prefix'] ?? '').toString().trim();
                              return ListTile(
                                leading: const Icon(Icons.folder),
                                title: Text(
                                    dirName.isEmpty ? '(Folder)' : dirName),
                                trailing: const Icon(Icons.chevron_right),
                                onTap: dirPrefix.isEmpty
                                    ? null
                                    : () {
                                        setState(() {
                                          _prefix = dirPrefix;
                                        });
                                        _load();
                                      },
                              );
                            }),
                          ],
                          Padding(
                            padding: const EdgeInsets.fromLTRB(8, 6, 8, 4),
                            child: Text('Files',
                                style: theme.textTheme.titleSmall),
                          ),
                          if (files.isEmpty)
                            Padding(
                              padding: const EdgeInsets.all(12),
                              child: Text(
                                'No files found.',
                                style: theme.textTheme.bodySmall,
                              ),
                            )
                          else
                            ...files.map((file) {
                              final name = (file['name'] ?? '').toString();
                              final label = _basename(name);
                              return ListTile(
                                leading: _fileLeading(file),
                                title: Text(
                                  label.isEmpty ? name : label,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                                subtitle: Text(
                                  name,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                                onTap: name.trim().isEmpty
                                    ? null
                                    : () => Navigator.of(context).pop(name),
                              );
                            }),
                        ],
                      ),
          ),
        ],
      ),
    );
  }
}

class _VideoPreviewState extends State<_VideoPreview> {
  VideoPlayerController? _controller;
  bool _ready = false;
  int _initToken = 0;

  @override
  void initState() {
    super.initState();
    _init(allowKeepExisting: false);
  }

  @override
  void didUpdateWidget(covariant _VideoPreview oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.url != widget.url ||
        !mapEquals(oldWidget.headers, widget.headers)) {
      _init(allowKeepExisting: true);
    }
  }

  Future<void> _init({required bool allowKeepExisting}) async {
    final token = ++_initToken;
    final previous = _controller;
    try {
      final controller = VideoPlayerController.networkUrl(
        Uri.parse(widget.url),
        httpHeaders: widget.headers,
      );
      await controller.initialize();
      await controller.setLooping(true);
      await controller.setVolume(0);
      await controller.play();
      if (!mounted || token != _initToken) {
        await controller.dispose();
        return;
      }

      setState(() {
        _controller = controller;
        _ready = true;
      });

      if (previous != null && previous != controller) {
        unawaited(previous.dispose());
      }
    } catch (_) {
      if (!mounted || token != _initToken) {
        return;
      }
      if (!allowKeepExisting || previous == null) {
        setState(() {
          _controller = null;
          _ready = false;
        });
        return;
      }
      setState(() {
        _ready = _controller != null && _controller!.value.isInitialized;
      });
    }
  }

  Future<void> _disposeController() async {
    final c = _controller;
    _controller = null;
    if (c != null) {
      await c.dispose();
    }
  }

  @override
  void dispose() {
    _initToken++;
    unawaited(_disposeController());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_ready && _controller != null && _controller!.value.isInitialized) {
      return FittedBox(
        fit: BoxFit.cover,
        child: SizedBox(
          width: _controller!.value.size.width,
          height: _controller!.value.size.height,
          child: VideoPlayer(_controller!),
        ),
      );
    }
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.video_library, size: 36),
          SizedBox(height: 8),
          Text('Video preview unavailable'),
        ],
      ),
    );
  }
}

class _YouTubePreview extends StatefulWidget {
  const _YouTubePreview({
    super.key,
    required this.videoId,
  });

  final String videoId;

  @override
  State<_YouTubePreview> createState() => _YouTubePreviewState();
}

class _YouTubePreviewState extends State<_YouTubePreview> {
  Future<void> _openOnYouTube() async {
    final uri = Uri.parse('https://www.youtube.com/watch?v=${widget.videoId}');
    final externalOk =
        await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (externalOk) {
      return;
    }

    final browserOk = await launchUrl(uri, mode: LaunchMode.inAppBrowserView);
    if (browserOk || !mounted) {
      return;
    }

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Could not open YouTube on this device.')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final thumbUrl =
        'https://img.youtube.com/vi/${widget.videoId}/hqdefault.jpg';

    return InkWell(
      onTap: _openOnYouTube,
      child: Stack(
        fit: StackFit.expand,
        children: [
          Image.network(
            thumbUrl,
            fit: BoxFit.cover,
            errorBuilder: (_, __, ___) => Container(
              color: Colors.black87,
              alignment: Alignment.center,
              child: const Text(
                'Preview unavailable',
                style: TextStyle(color: Colors.white),
              ),
            ),
          ),
          Container(color: Colors.black26),
          const Center(
            child: Icon(
              Icons.play_circle_fill,
              size: 56,
              color: Colors.white,
            ),
          ),
          Positioned(
            right: 8,
            bottom: 8,
            child: SizedBox(
              width: 40,
              height: 36,
              child: IconButton.filledTonal(
                tooltip: 'Open on YouTube',
                onPressed: _openOnYouTube,
                icon: const Icon(Icons.open_in_new, size: 16),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

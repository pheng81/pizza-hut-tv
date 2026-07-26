import 'dart:async';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:geocoding/geocoding.dart' as geocoding;
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:video_player/video_player.dart';
import 'package:youtube_player_iframe/youtube_player_iframe.dart';

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

class _StoresTabState extends State<StoresTab>
    with SingleTickerProviderStateMixin {
  bool _loading = true;
  String? _error;
  List<StoreItem> _stores = const [];
  List<ScreenItem> _screens = const [];
  Map<String, String> _screenStatus = const {};
  final Map<String, Future<_ScreenCardPreviewData>> _screenPreviewUrlFutures =
      {};
  Future<List<_StoreMapMarkerData>>? _storeMapMarkersFuture;
  final Map<String, LatLng?> _resolvedMapPoints = {};
  _StoreMapMarkerData? _activeMapMarker;
  final Map<String, BitmapDescriptor> _storeMarkerIcons = {};
  late final AnimationController _panelGradientController;

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
    _panelGradientController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 10),
    )..repeat(reverse: true);
    _loadStores();
  }

  @override
  void dispose() {
    _panelGradientController.dispose();
    super.dispose();
  }

  Future<BitmapDescriptor> _storeMarkerIconForStatus(String status) async {
    final normalized = status == 'online' ? 'online' : 'offline';
    final cached = _storeMarkerIcons[normalized];
    if (cached != null) {
      return cached;
    }

    final recorder = ui.PictureRecorder();
    final canvas = Canvas(recorder);
    const size = Size(42, 42);
    const rect = Rect.fromLTWH(3, 3, 36, 36);
    const radius = Radius.circular(9);
    const textStyle = TextStyle(
      color: Colors.white,
      fontSize: 18,
      fontWeight: FontWeight.w800,
      letterSpacing: -0.8,
    );

    final shadowPath = Path()
      ..addRRect(
        RRect.fromRectAndRadius(rect, radius),
      );
    canvas.drawShadow(shadowPath, const Color(0x380F172A), 8, false);

    final gradient = normalized == 'online'
        ? const LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              Color(0xFFFF2D84),
              Color(0xFF9D45FF),
              Color(0xFF3C6CFF),
            ],
            stops: [0.0, 0.52, 1.0],
          )
        : const LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              Color(0xFFA7A7AD),
              Color(0xFF595960),
              Color(0xFF2F2F34),
            ],
            stops: [0.0, 0.55, 1.0],
          );

    final paint = Paint()
      ..shader = gradient.createShader(rect)
      ..isAntiAlias = true;
    canvas.drawRRect(
      RRect.fromRectAndRadius(rect, radius),
      paint,
    );

    final strokePaint = Paint()
      ..color =
          Colors.white.withValues(alpha: normalized == 'online' ? 0.24 : 0.16)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.1
      ..isAntiAlias = true;
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(3.5, 3.5, 35, 35),
        const Radius.circular(8),
      ),
      strokePaint,
    );

    final textPainter = TextPainter(
      text: const TextSpan(text: 'ea', style: textStyle),
      textDirection: TextDirection.ltr,
    )..layout();
    textPainter.paint(
      canvas,
      Offset(
        (size.width - textPainter.width) / 2,
        (size.height - textPainter.height) / 2 + 0.5,
      ),
    );

    final image = await recorder.endRecording().toImage(
          size.width.toInt(),
          size.height.toInt(),
        );
    final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
    if (bytes == null) {
      return BitmapDescriptor.defaultMarker;
    }
    final descriptor = BitmapDescriptor.bytes(bytes.buffer.asUint8List());
    _storeMarkerIcons[normalized] = descriptor;
    return descriptor;
  }

  Future<void> _loadStores() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final stores = await widget.apiClient.getStores();
      String? storeId = widget.selectedStoreId;
      if (stores.every((s) => s.id != storeId)) {
        storeId = stores.isNotEmpty ? stores.first.id : null;
      }

      List<ScreenItem> screens = const [];
      String? screenId = widget.selectedScreenId;
      if (storeId != null) {
        screens = await widget.apiClient.getScreens(storeId);
        _screenStatus = await widget.apiClient.getScreenStatus(storeId);
      } else {
        _screenStatus = <String, String>{};
      }
      if (screenId == null || screens.every((s) => s.id != screenId)) {
        screenId = screens.isNotEmpty ? screens.first.id : null;
      }

      if (!mounted) {
        return;
      }
      setState(() {
        _stores = stores;
        _screens = screens;
        _screenPreviewUrlFutures.clear();
        _storeMapMarkersFuture = _loadStoreMapMarkers(
          stores: stores,
          selectedStoreId: storeId,
          selectedStoreScreens: screens,
        );
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
    final result = await showDialog<Map<String, String>>(
      context: context,
      builder: (context) => _AddStoreDialog(apiClient: widget.apiClient),
    );

    if (result == null) {
      return;
    }

    final storeId = (result['id'] ?? '').trim();
    final storeName = (result['name'] ?? '').trim();
    final storeAddress = (result['address'] ?? '').trim();

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
      await widget.apiClient.addStore(
        storeId: storeId,
        storeName: storeName,
        address: storeAddress,
      );
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

  String _normalizeUploadedMediaPath(String raw) {
    var path = raw.trim().replaceAll('\\', '/');
    while (path.startsWith('/')) {
      path = path.substring(1);
    }
    for (final prefix in const ['static/uploads/', 'uploads/', 'media/']) {
      if (path.toLowerCase().startsWith(prefix)) {
        return path.substring(prefix.length);
      }
    }
    return path;
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
    String? videoUrl;
    String? youtubeVideoId;
    String? livePosTitle;
    String? livePosBody;
    int? syncStartEpoch;
    void addCandidate(String raw) {
      final resolved = _toAbsoluteUrlForPreview(raw);
      if (resolved.isNotEmpty && !candidates.contains(resolved)) {
        candidates.add(resolved);
      }
    }

    void addVideoUrl(String raw) {
      final resolved = _toAbsoluteUrlForPreview(raw);
      if (resolved.isNotEmpty && videoUrl == null) {
        videoUrl = resolved;
      }
    }

    void addItemCandidates(Map<String, dynamic> item) {
      final file = (item['file'] ?? '').toString().trim();
      final mediaType = (item['media_type'] ?? '').toString().toLowerCase();
      final isLivePos =
          mediaType == 'live_pos' || file.toLowerCase().startsWith('livepos:');
      if (isLivePos && livePosTitle == null) {
        final activeItem = item['live_pos_active_item'];
        final activeMap = activeItem is Map ? activeItem : const {};
        livePosTitle = (item['live_pos_title'] ??
                activeMap['title'] ??
                item['displayName'] ??
                'Live POS')
            .toString()
            .trim();
        livePosBody = (item['live_pos_body'] ?? activeMap['body'] ?? '')
            .toString()
            .trim();
        return;
      }
      final syncRef = item['sync_ref'];
      final isSyncSlice = syncRef is Map &&
          (syncRef['group'] ?? '').toString().trim().isNotEmpty;
      if (syncStartEpoch == null && syncRef is Map) {
        syncStartEpoch = int.tryParse(
          (syncRef['start_epoch'] ?? '').toString(),
        );
      }
      if (file.startsWith('youtube:')) {
        final id = file.substring('youtube:'.length).trim();
        if (id.length == 11) {
          youtubeVideoId ??= id;
          addCandidate('https://img.youtube.com/vi/$id/hqdefault.jpg');
        }
      }

      if (file.isNotEmpty &&
          !file.startsWith('http://') &&
          !file.startsWith('https://')) {
        final normalizedFile = _normalizeUploadedMediaPath(file);
        final lower = normalizedFile.toLowerCase();
        final encoded = _encodePathPreservingSlashes(normalizedFile);
        final isVideo = lower.contains('.mp4') ||
            lower.contains('.mov') ||
            lower.contains('.webm') ||
            lower.contains('.mkv') ||
            lower.contains('.m3u8');
        if (isVideo) {
          // The preview route produces a low-bitrate H.264 baseline clip,
          // which is reliable across Android devices and emulator codecs.
          addVideoUrl(
            isSyncSlice
                ? '/syncpreview/320/$encoded'
                : '/vpreview/320/$encoded',
          );
          addCandidate('/vthumb/320/$encoded');
          addCandidate('/vthumb/160/$encoded');
        } else {
          addCandidate('/thumb/320/$encoded');
          addCandidate('/thumb/160/$encoded');
        }
        addCandidate('/static/uploads/$normalizedFile');
      }

      if (file.startsWith('http://') || file.startsWith('https://')) {
        final lower = file.toLowerCase();
        if (lower.contains('.mp4') ||
            lower.contains('.mov') ||
            lower.contains('.webm') ||
            lower.contains('.mkv') ||
            lower.contains('.m3u8')) {
          addVideoUrl(file);
        }
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

    if (candidates.isEmpty && livePosTitle == null) {
      return const _ScreenCardPreviewData(urls: []);
    }

    Map<String, String> headers = const {};
    final headerUrl =
        videoUrl ?? (candidates.isNotEmpty ? candidates.first : '');
    if (headerUrl.isNotEmpty) {
      try {
        headers = await widget.apiClient.getAuthHeadersForUrl(headerUrl);
      } catch (_) {
        headers = const {};
      }
    }

    return _ScreenCardPreviewData(
      urls: candidates,
      videoUrl: videoUrl,
      youtubeVideoId: youtubeVideoId,
      livePosTitle: livePosTitle,
      livePosBody: livePosBody,
      syncStartEpoch: syncStartEpoch,
      headers: headers,
    );
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

    await showDialog<void>(
      context: context,
      useSafeArea: false,
      builder: (context) {
        return Dialog.fullscreen(
          child: _ScreenMediaEditorSheet(
            apiClient: widget.apiClient,
            storeId: storeId,
            screenId: screen.id,
            screenName: screen.name,
            screenStatus: _screenStatus[screen.id] ?? 'offline',
            screenAddress: screen.address,
            screenProtected: screen.protected,
            screenVertical: screen.vertical,
            screenHorizontal: screen.horizontal,
            screenPanelZone: screen.panelZone,
          ),
        );
      },
    );
  }

  Future<List<_StoreMapMarkerData>> _loadStoreMapMarkers({
    required List<StoreItem> stores,
    required String? selectedStoreId,
    required List<ScreenItem> selectedStoreScreens,
  }) async {
    final markers = await Future.wait(
      stores.map(
        (store) => _resolveStoreMapMarker(
          store: store,
          selectedStoreId: selectedStoreId,
          selectedStoreScreens: selectedStoreScreens,
        ),
      ),
    );
    final resolved = markers.whereType<_StoreMapMarkerData>().toList();
    for (final marker in resolved) {
      marker.icon = await _storeMarkerIconForStatus(marker.status);
    }
    return resolved;
  }

  Future<_StoreMapMarkerData?> _resolveStoreMapMarker({
    required StoreItem store,
    required String? selectedStoreId,
    required List<ScreenItem> selectedStoreScreens,
  }) async {
    final directPoint = _toLatLng(store.latitude, store.longitude);
    String detail = store.address.trim();

    String previewStatus = 'offline';
    void syncPreviewStatus(ScreenItem? previewScreen) {
      if (previewScreen == null) {
        return;
      }
      previewStatus =
          (_screenStatus[previewScreen.id] ?? '').toLowerCase() == 'online'
              ? 'online'
              : 'offline';
    }

    if (directPoint != null) {
      List<ScreenItem> directScreens = const [];
      if (store.id == selectedStoreId) {
        directScreens = selectedStoreScreens;
      } else {
        try {
          directScreens = await widget.apiClient.getScreens(store.id);
        } catch (_) {
          directScreens = const [];
        }
      }
      final directPreview = directScreens.cast<ScreenItem?>().firstWhere(
            (screen) => screen != null,
            orElse: () => null,
          );
      syncPreviewStatus(directPreview);
      return _StoreMapMarkerData(
        store: store,
        point: directPoint,
        detail: detail,
        previewScreenId: directPreview?.id,
        previewScreenName: directPreview?.name,
        status: previewStatus,
      );
    }

    List<ScreenItem> screensForStore = const [];
    if (store.id == selectedStoreId) {
      screensForStore = selectedStoreScreens;
    } else {
      try {
        screensForStore = await widget.apiClient.getScreens(store.id);
      } catch (_) {
        screensForStore = const [];
      }
    }
    final previewScreen = screensForStore.cast<ScreenItem?>().firstWhere(
          (screen) => screen != null,
          orElse: () => null,
        );
    syncPreviewStatus(previewScreen);

    final screenWithAddress = screensForStore.cast<ScreenItem?>().firstWhere(
          (screen) => (screen?.address.trim().isNotEmpty ?? false),
          orElse: () => null,
        );
    if (screenWithAddress != null) {
      detail = screenWithAddress.address.trim();
      final point = await _resolveMapPoint(detail);
      if (point != null) {
        return _StoreMapMarkerData(
          store: store,
          point: point,
          detail: detail,
          previewScreenId: previewScreen?.id,
          previewScreenName: previewScreen?.name,
          status: previewStatus,
        );
      }
    }

    if (store.address.trim().isNotEmpty) {
      final point = await _resolveMapPoint(store.address.trim());
      if (point != null) {
        return _StoreMapMarkerData(
          store: store,
          point: point,
          detail: store.address.trim(),
          previewScreenId: previewScreen?.id,
          previewScreenName: previewScreen?.name,
          status: previewStatus,
        );
      }
    }

    final fallbackQuery = '${store.name} ${store.id}'.trim();
    final point = await _resolveMapPoint(fallbackQuery);
    if (point == null) {
      return null;
    }
    return _StoreMapMarkerData(
      store: store,
      point: point,
      detail: detail,
      previewScreenId: previewScreen?.id,
      previewScreenName: previewScreen?.name,
      status: previewStatus,
    );
  }

  LatLng? _toLatLng(double? latitude, double? longitude) {
    if (latitude == null || longitude == null) {
      return null;
    }
    return LatLng(latitude, longitude);
  }

  Future<LatLng?> _resolveMapPoint(String query) async {
    final normalized = query.trim();
    if (normalized.isEmpty) {
      return null;
    }
    if (_resolvedMapPoints.containsKey(normalized)) {
      return _resolvedMapPoints[normalized];
    }
    try {
      final matches = await geocoding.locationFromAddress(normalized);
      if (matches.isEmpty) {
        _resolvedMapPoints[normalized] = null;
        return null;
      }
      final point = LatLng(matches.first.latitude, matches.first.longitude);
      _resolvedMapPoints[normalized] = point;
      return point;
    } catch (_) {
      _resolvedMapPoints[normalized] = null;
      return null;
    }
  }

  LatLngBounds _boundsFromPoints(List<LatLng> points) {
    var minLat = points.first.latitude;
    var maxLat = points.first.latitude;
    var minLng = points.first.longitude;
    var maxLng = points.first.longitude;
    for (final point in points.skip(1)) {
      if (point.latitude < minLat) minLat = point.latitude;
      if (point.latitude > maxLat) maxLat = point.latitude;
      if (point.longitude < minLng) minLng = point.longitude;
      if (point.longitude > maxLng) maxLng = point.longitude;
    }
    return LatLngBounds(
      southwest: LatLng(minLat, minLng),
      northeast: LatLng(maxLat, maxLng),
    );
  }

  Widget _buildStoreMapCard({
    required ThemeData theme,
    required ColorScheme scheme,
  }) {
    final future = _storeMapMarkersFuture;
    return ClipRRect(
      borderRadius: BorderRadius.zero,
      child: AspectRatio(
        aspectRatio: 1,
        child: future == null
            ? const Center(child: CircularProgressIndicator())
            : FutureBuilder<List<_StoreMapMarkerData>>(
                future: future,
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  final markers =
                      snapshot.data ?? const <_StoreMapMarkerData>[];
                  if (markers.isEmpty) {
                    return Container(
                      alignment: Alignment.center,
                      color: scheme.surfaceContainerLow,
                      padding: const EdgeInsets.all(20),
                      child: Text(
                        'No store locations found yet. Add an address or coordinates to your stores/screens and pins will appear here.',
                        textAlign: TextAlign.center,
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: scheme.onSurfaceVariant,
                        ),
                      ),
                    );
                  }

                  final points = markers.map((marker) => marker.point).toList();
                  final selectedMarker = markers.where(
                    (marker) => marker.store.id == widget.selectedStoreId,
                  );
                  final initialCenter = selectedMarker.isNotEmpty
                      ? selectedMarker.first.point
                      : points.first;
                  _StoreMapMarkerData? activeMarker;
                  if (_activeMapMarker != null) {
                    for (final marker in markers) {
                      if (marker.store.id == _activeMapMarker!.store.id) {
                        activeMarker = marker;
                        break;
                      }
                    }
                  }

                  return Stack(
                    children: [
                      GoogleMap(
                        initialCameraPosition: CameraPosition(
                          target: initialCenter,
                          zoom: markers.length == 1 ? 13 : 10,
                        ),
                        mapType: MapType.hybrid,
                        myLocationButtonEnabled: false,
                        zoomControlsEnabled: false,
                        compassEnabled: true,
                        onMapCreated: (controller) {
                          if (markers.length > 1) {
                            WidgetsBinding.instance.addPostFrameCallback((_) {
                              controller.animateCamera(
                                CameraUpdate.newLatLngBounds(
                                  _boundsFromPoints(points),
                                  42,
                                ),
                              );
                            });
                          }
                        },
                        onTap: (_) {
                          if (_activeMapMarker != null && mounted) {
                            setState(() {
                              _activeMapMarker = null;
                            });
                          }
                        },
                        markers: markers
                            .map(
                              (marker) => Marker(
                                markerId: MarkerId(marker.store.id),
                                position: marker.point,
                                icon: marker.icon ?? BitmapDescriptor.defaultMarker,
                                zIndexInt:
                                    marker.store.id == _activeMapMarker?.store.id
                                        ? 1000
                                        : (marker.status == 'online' ? 100 : 0),
                                infoWindow: InfoWindow.noText,
                                onTap: () {
                                  _onSelectStore(marker.store.id);
                                  if (!mounted) {
                                    return;
                                  }
                                  setState(() {
                                    _activeMapMarker = marker;
                                  });
                                },
                              ),
                            )
                            .toSet(),
                      ),
                      if (activeMarker != null)
                        Positioned(
                          left: 12,
                          right: 12,
                          bottom: 12,
                          child: Builder(
                            builder: (context) {
                              final marker = activeMarker!;
                              return _StoreMapPreviewCard(
                                marker: marker,
                                theme: theme,
                                scheme: scheme,
                                previewFuture:
                                    marker.previewScreenId == null
                                        ? null
                                        : _getScreenCardPreviewData(
                                            storeId: marker.store.id,
                                            screenId:
                                                marker.previewScreenId!,
                                          ),
                                onOpen: () async {
                                  await _onSelectStore(marker.store.id);
                                  if (!mounted) {
                                    return;
                                  }
                                  final previewId = marker.previewScreenId;
                                  if (previewId != null) {
                                    widget.onSelectionChanged(
                                      marker.store.id,
                                      previewId,
                                    );
                                  }
                                },
                                onClose: () {
                                  if (!mounted) {
                                    return;
                                  }
                                  setState(() {
                                    _activeMapMarker = null;
                                  });
                                },
                              );
                            },
                          ),
                        ),
                    ],
                  );
                },
              ),
      ),
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

    Widget compactPickerAction({
      required VoidCallback? onPressed,
      required IconData icon,
      required String tooltip,
      Color? iconColor,
    }) {
      return Tooltip(
        message: tooltip,
        child: SizedBox(
          width: 42,
          height: 42,
          child: FilledButton.tonal(
            onPressed: onPressed,
            style: FilledButton.styleFrom(
              padding: EdgeInsets.zero,
              visualDensity: VisualDensity.compact,
              elevation: 0,
              backgroundColor: const Color(0xFFF8FAFC),
              foregroundColor: iconColor ?? scheme.onSurfaceVariant,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
            child: Icon(icon, size: 18, color: iconColor),
          ),
        ),
      );
    }

    InputDecoration flatPickerDecoration(String label) {
      return InputDecoration(
        labelText: label,
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(
            color: scheme.primary.withValues(alpha: 0.2),
          ),
        ),
        disabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      );
    }

    Widget statsPill({
      required IconData icon,
      required String text,
      Color? background,
    }) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
        decoration: BoxDecoration(
          color: background ?? const Color(0xFFF4F5FB),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: scheme.primary),
            const SizedBox(width: 6),
            Text(
              text,
              style: theme.textTheme.bodySmall?.copyWith(
                color: scheme.onSurfaceVariant,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      );
    }

    final validSelectedStoreId = _stores.any((store) => store.id == widget.selectedStoreId)
        ? widget.selectedStoreId
        : null;
    final validSelectedScreenId = _screens.any((screen) => screen.id == widget.selectedScreenId)
        ? widget.selectedScreenId
        : null;

    return RefreshIndicator(
      onRefresh: _loadStores,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(0, 0, 0, 16),
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
          Padding(
            padding: EdgeInsets.zero,
            child: AnimatedBuilder(
              animation: _panelGradientController,
              builder: (context, _) {
                return Container(
                  color: Colors.transparent,
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Expanded(
                              child: DropdownButtonFormField<String>(
                                value: validSelectedStoreId,
                                isExpanded: true,
                                items: _stores
                                    .map((store) => DropdownMenuItem(
                                          value: store.id,
                                          child: Text(
                                            '${store.id} - ${store.name}',
                                            overflow: TextOverflow.ellipsis,
                                          ),
                                        ))
                                    .toList(),
                                onChanged: _loading ? null : _onSelectStore,
                                decoration: flatPickerDecoration(''),
                              ),
                            ),
                            const SizedBox(width: 8),
                            compactPickerAction(
                              onPressed: _loading ? null : _addStore,
                              icon: Icons.add_business,
                              tooltip: 'Add store',
                            ),
                            const SizedBox(width: 6),
                            compactPickerAction(
                              onPressed: _loading || widget.selectedStoreId == null
                                  ? null
                                  : _deleteSelectedStore,
                              icon: Icons.delete_outline,
                              tooltip: 'Delete store',
                              iconColor: widget.selectedStoreId == null || _loading
                                  ? null
                                  : scheme.error,
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Expanded(
                              child: DropdownButtonFormField<String>(
                                value: validSelectedScreenId,
                                isExpanded: true,
                                items: _screens
                                    .map((screen) => DropdownMenuItem(
                                          value: screen.id,
                                          child: Text(
                                            '${screen.id} - ${screen.name}',
                                            overflow: TextOverflow.ellipsis,
                                          ),
                                        ))
                                    .toList(),
                                onChanged: _loading
                                    ? null
                                    : (value) {
                                        widget.onSelectionChanged(
                                            widget.selectedStoreId, value);
                                      },
                                decoration: flatPickerDecoration(''),
                              ),
                            ),
                            const SizedBox(width: 8),
                            compactPickerAction(
                              onPressed: _loading || widget.selectedStoreId == null
                                  ? null
                                  : _addScreen,
                              icon: Icons.add_to_photos_outlined,
                              tooltip: 'Add screen',
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 8),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
              children: [
                statsPill(
                  icon: Icons.storefront_outlined,
                  text: 'Stores ${_stores.length}',
                  background: const Color(0xFFEAF1FF),
                ),
                const SizedBox(width: 6),
                statsPill(
                  icon: Icons.tv_outlined,
                  text: 'Screens ${_screens.length}',
                ),
                const SizedBox(width: 6),
                statsPill(
                  icon: Icons.wifi_tethering_outlined,
                  text: 'Online $onlineCount',
                ),
                if (widget.selectedStoreId != null) ...[
                  const SizedBox(width: 6),
                  statsPill(
                    icon: Icons.tag_outlined,
                    text: 'Store ${widget.selectedStoreId}',
                    background: const Color(0xFFF1EEFF),
                  ),
                ],
              ],
            ),
          ),
          ),
          const SizedBox(height: 12),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 0),
            child: _buildStoreMapCard(theme: theme, scheme: scheme),
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
                  shape: const RoundedRectangleBorder(
                    borderRadius: BorderRadius.zero,
                  ),
                  child: InkWell(
                    borderRadius: BorderRadius.zero,
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
                                          borderRadius: BorderRadius.zero,
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
                                width: 196,
                                height: 132,
                                decoration: BoxDecoration(
                                  borderRadius: BorderRadius.zero,
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
                                    if (data.livePosTitle != null) {
                                      return _LivePosCardPreview(
                                        title: data.livePosTitle!,
                                        body: data.livePosBody ?? '',
                                      );
                                    }
                                    if (data.videoUrl != null) {
                                      return _VideoPreview(
                                        key: ValueKey(
                                            'screen-card-${data.videoUrl}'),
                                        url: data.videoUrl!,
                                        headers: data.headers,
                                        compact: true,
                                        syncStartEpoch: data.syncStartEpoch,
                                      );
                                    }
                                    if (data.youtubeVideoId != null) {
                                      return _YouTubeCardPreview(
                                        key: ValueKey(
                                          'screen-card-youtube-${data.youtubeVideoId}',
                                        ),
                                        videoId: data.youtubeVideoId!,
                                      );
                                    }
                                    return _ScreenCardPreviewImage(
                                      urls: urls,
                                      headers: data.headers,
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
    return ClipRect(
      child: Transform.scale(
        scale: 1.18,
        child: Image.network(
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
        ),
      ),
    );
  }
}

class _StoreMapPreviewCard extends StatelessWidget {
  const _StoreMapPreviewCard({
    required this.marker,
    required this.theme,
    required this.scheme,
    required this.onOpen,
    required this.onClose,
    this.previewFuture,
  });

  final _StoreMapMarkerData marker;
  final ThemeData theme;
  final ColorScheme scheme;
  final Future<_ScreenCardPreviewData>? previewFuture;
  final Future<void> Function() onOpen;
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.16),
              blurRadius: 18,
              offset: const Offset(0, 10),
            ),
          ],
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 96,
              height: 96,
              decoration: BoxDecoration(
                color: scheme.surfaceContainerHigh,
                borderRadius: BorderRadius.circular(16),
              ),
              clipBehavior: Clip.antiAlias,
              child: previewFuture == null
                  ? Icon(
                      Icons.image_outlined,
                      color: scheme.onSurfaceVariant,
                    )
                  : FutureBuilder<_ScreenCardPreviewData>(
                      future: previewFuture,
                      builder: (context, snapshot) {
                        final data = snapshot.data ??
                            const _ScreenCardPreviewData(urls: []);
                        if (snapshot.connectionState ==
                            ConnectionState.waiting) {
                          return const Center(
                            child: SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            ),
                          );
                        }
                        if (data.livePosTitle != null) {
                          return _LivePosCardPreview(
                            title: data.livePosTitle!,
                            body: data.livePosBody ?? '',
                          );
                        }
                        if (data.videoUrl != null) {
                          return _VideoPreview(
                            url: data.videoUrl!,
                            headers: data.headers,
                            compact: true,
                            syncStartEpoch: data.syncStartEpoch,
                          );
                        }
                        if (data.youtubeVideoId != null) {
                          return _YouTubePreview(videoId: data.youtubeVideoId!);
                        }
                        if (data.urls.isEmpty) {
                          return Icon(
                            Icons.image_not_supported_outlined,
                            color: scheme.onSurfaceVariant,
                          );
                        }
                        return _ScreenCardPreviewImage(
                          urls: data.urls,
                          headers: data.headers,
                        );
                      },
                    ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          marker.store.name,
                          style: theme.textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      IconButton(
                        onPressed: onClose,
                        icon: const Icon(Icons.close),
                        iconSize: 18,
                        visualDensity: VisualDensity.compact,
                        tooltip: 'Close preview',
                      ),
                    ],
                  ),
                  if (marker.previewScreenName != null) ...[
                    Text(
                      marker.previewScreenName!,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: scheme.primary,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 4),
                  ],
                  Text(
                    marker.detail.trim().isEmpty
                        ? 'Tap to open this store'
                        : marker.detail,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 10),
                  FilledButton.tonal(
                    onPressed: onOpen,
                    style: FilledButton.styleFrom(
                      visualDensity: VisualDensity.compact,
                      minimumSize: const Size(0, 38),
                    ),
                    child: const Text('Open store'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ScreenCardPreviewData {
  const _ScreenCardPreviewData({
    required this.urls,
    this.videoUrl,
    this.youtubeVideoId,
    this.livePosTitle,
    this.livePosBody,
    this.syncStartEpoch,
    this.headers = const {},
  });

  final List<String> urls;
  final String? videoUrl;
  final String? youtubeVideoId;
  final String? livePosTitle;
  final String? livePosBody;
  final int? syncStartEpoch;
  final Map<String, String> headers;
}

class _StoreMapMarkerData {
  _StoreMapMarkerData({
    required this.store,
    required this.point,
    this.detail = '',
    this.previewScreenId,
    this.previewScreenName,
    this.status = 'offline',
  });

  final StoreItem store;
  final LatLng point;
  final String detail;
  final String? previewScreenId;
  final String? previewScreenName;
  final String status;
  BitmapDescriptor? icon;
}

class ScreenMediaEditorSheet extends StatelessWidget {
  const ScreenMediaEditorSheet({
    super.key,
    required this.apiClient,
    required this.storeId,
    required this.screenId,
    required this.screenName,
    this.screenStatus = 'offline',
    this.screenAddress = '',
    this.screenProtected = false,
    this.screenVertical = false,
    this.screenHorizontal = true,
  });

  final ApiClient apiClient;
  final String storeId;
  final String screenId;
  final String screenName;
  final String screenStatus;
  final String screenAddress;
  final bool screenProtected;
  final bool screenVertical;
  final bool screenHorizontal;

  @override
  Widget build(BuildContext context) {
    return _ScreenMediaEditorSheet(
      apiClient: apiClient,
      storeId: storeId,
      screenId: screenId,
      screenName: screenName,
      screenStatus: screenStatus,
      screenAddress: screenAddress,
      screenProtected: screenProtected,
      screenVertical: screenVertical,
      screenHorizontal: screenHorizontal,
    );
  }
}

class _ScreenMediaEditorSheet extends StatefulWidget {
  const _ScreenMediaEditorSheet({
    required this.apiClient,
    required this.storeId,
    required this.screenId,
    required this.screenName,
    this.screenStatus = 'offline',
    this.screenAddress = '',
    this.screenProtected = false,
    this.screenVertical = false,
    this.screenHorizontal = true,
    this.screenPanelZone = const {},
  });

  final ApiClient apiClient;
  final String storeId;
  final String screenId;
  final String screenName;
  final String screenStatus;
  final String screenAddress;
  final bool screenProtected;
  final bool screenVertical;
  final bool screenHorizontal;
  final Map<String, dynamic> screenPanelZone;

  @override
  State<_ScreenMediaEditorSheet> createState() =>
      _ScreenMediaEditorSheetState();
}

class _ScreenMediaEditorSheetState extends State<_ScreenMediaEditorSheet>
    with SingleTickerProviderStateMixin {
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
  bool _quickActionBusy = false;
  int _screenRotation = 0;
  bool _screenMuted = false;
  String _screenAddress = '';
  bool _screenProtected = false;
  bool _screenVertical = false;
  bool _screenHorizontal = true;
  Map<String, dynamic> _screenPanelZone = const {};
  bool _isPanelInfoExpanded = false;
  final Set<String> _expandedPanelItemIds = <String>{};
  bool _isMasterStore = false;
  File? _pickedFile;
  List<Map<String, dynamic>> _playlist = const [];
  late final AnimationController _headerAnim;

  static const Map<String, String> _panelLayoutLabels = {
    'off': 'Off',
    'split-right-25': 'Right 25%',
    'split-left-25': 'Left 25%',
    'split-bottom-25': 'Bottom 25%',
    'full-screen': 'Full screen 100%',
  };

  static const Map<String, String> _panelSourceLabels = {
    'manual': 'Manual cards',
    'pos_webhook': 'Live POS',
  };

  static const Map<String, String> _panelScopeTitles = {
    'screen': 'This screen only',
    'store': 'This store',
    'chain': 'Multi-store chain',
  };

  static const Map<String, String> _panelScopeSubtitles = {
    'screen': 'One webhook just for this screen',
    'store': 'One shared webhook for screens in this store',
    'chain': 'One shared webhook across many stores',
  };

  static const Map<String, String> _panelConnectorLabels = {
    'generic_webhook': 'Direct webhook',
    'zapier': 'Zapier',
    'make': 'Make',
    'n8n': 'n8n',
    'developer': 'Developer',
  };

  static const Map<String, String> _panelConnectorSubtitles = {
    'generic_webhook':
        'Connect any POS through a direct webhook or a bridge like Zapier, Make, or n8n.',
    'zapier': 'Use when the POS already connects to Zapier.',
    'make': 'Good for multi-step automations.',
    'n8n': 'Best for self-hosted workflows.',
    'developer': 'Use your own backend, plugin, or script.',
  };

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

  bool _isLivePosPlaylistItem(Map<String, dynamic> item) {
    final mediaType = (item['media_type'] ?? '').toString().toLowerCase();
    final file = (item['file'] ?? '').toString().toLowerCase();
    return mediaType == 'live_pos' || file.startsWith('livepos:');
  }

  bool get _hasLivePosSchedule {
    return _playlist.any(_isLivePosPlaylistItem);
  }

  Map<String, dynamic> _normalizedPanelZone(Map<String, dynamic>? raw) {
    final zone = _asMap(raw);
    final posFeed = _asMap(zone['pos_feed']);
    final fieldMap = _asMap(posFeed['field_map']);
    final appearance = _asMap(zone['appearance']);
    return {
      'enabled': zone['enabled'] == true,
      'layout_mode': (zone['layout_mode'] ?? 'off').toString().trim(),
      'source_mode': (zone['source_mode'] ?? 'manual').toString().trim(),
      'feed_scope': (zone['feed_scope'] ?? 'screen').toString().trim(),
      'playlist': zone['playlist'] is List
          ? (zone['playlist'] as List).map(_asMap).toList()
          : const <Map<String, dynamic>>[],
      'live_queue': zone['live_queue'] is List
          ? (zone['live_queue'] as List).map(_asMap).toList()
          : const <Map<String, dynamic>>[],
      'appearance': {
        'background_color':
            (appearance['background_color'] ?? '#201206').toString(),
        'content_align': (appearance['content_align'] ?? 'center').toString(),
        'body_rows': int.tryParse('${appearance['body_rows'] ?? 4}') ?? 4,
      },
      'pos_feed': {
        'name': (posFeed['name'] ?? '').toString(),
        'webhook_token': (posFeed['webhook_token'] ?? '').toString(),
        'connector_type':
            (posFeed['connector_type'] ?? 'generic_webhook').toString(),
        'field_map': {
          'customer_name':
              (fieldMap['customer_name'] ?? 'customer.name').toString(),
          'order_number':
              (fieldMap['order_number'] ?? 'order.number').toString(),
          'status': (fieldMap['status'] ?? 'order.status').toString(),
          'external_id': (fieldMap['external_id'] ?? 'order.id').toString(),
        },
        'title_template':
            (posFeed['title_template'] ?? 'Now serving').toString(),
        'body_template': (posFeed['body_template'] ??
                '{{customer_name}}\nOrder #{{order_number}}')
            .toString(),
        'allowed_statuses': posFeed['allowed_statuses'] is List
            ? (posFeed['allowed_statuses'] as List)
                .map((value) => value.toString().trim())
                .where((value) => value.isNotEmpty)
                .toList()
            : const <String>['ready', 'serving'],
        'display_seconds':
            int.tryParse('${posFeed['display_seconds'] ?? 10}') ?? 10,
        'max_items': int.tryParse('${posFeed['max_items'] ?? 5}') ?? 5,
        'store_selector_path':
            (posFeed['store_selector_path'] ?? 'store.id').toString(),
        'event_count': int.tryParse('${posFeed['event_count'] ?? 0}') ?? 0,
        'last_event_at': (posFeed['last_event_at'] ?? '').toString(),
        'last_event_result': (posFeed['last_event_result'] ?? '').toString(),
        'last_event_summary': _asMap(posFeed['last_event_summary']),
        'last_payload_preview':
            (posFeed['last_payload_preview'] ?? '').toString(),
      },
    };
  }

  String _panelLayoutLabel(String layoutMode) {
    return _panelLayoutLabels[layoutMode] ?? 'Custom';
  }

  String _panelTimeSummary(dynamic value) {
    final text = (value ?? '').toString().trim();
    if (text.isEmpty) {
      return '';
    }
    final normalized = text.contains('T') ? text.split('T').last : text;
    final match = RegExp(r'^(\d{1,2}):(\d{2})').firstMatch(normalized);
    if (match == null) {
      return normalized;
    }
    final hour = int.tryParse(match.group(1) ?? '') ?? 0;
    final minute = int.tryParse(match.group(2) ?? '') ?? 0;
    final suffix = hour >= 12 ? 'PM' : 'AM';
    final hour12 = hour % 12 == 0 ? 12 : hour % 12;
    return '$hour12:${minute.toString().padLeft(2, '0')} $suffix';
  }

  String _panelTimeRangeSummary({
    dynamic start,
    dynamic end,
  }) {
    final startLabel = _panelTimeSummary(start);
    final endLabel = _panelTimeSummary(end);
    if (startLabel.isNotEmpty && endLabel.isNotEmpty) {
      return '$startLabel - $endLabel';
    }
    if (startLabel.isNotEmpty) {
      return 'Starts $startLabel';
    }
    if (endLabel.isNotEmpty) {
      return 'Until $endLabel';
    }
    return 'No time window';
  }

  List<Map<String, dynamic>> _activePanelItems(Map<String, dynamic> panelZone) {
    final sourceMode = (panelZone['source_mode'] ?? 'manual').toString();
    final rawItems = sourceMode == 'pos_webhook'
        ? panelZone['live_queue']
        : panelZone['playlist'];
    if (rawItems is! List) {
      return const [];
    }
    return rawItems.map(_asMap).where((item) => item.isNotEmpty).toList();
  }

  String _panelQueueStatusLabel(String result, bool hasItems, bool hasToken) {
    final normalized = result.trim().toLowerCase();
    if (normalized == 'accepted' || (hasItems && hasToken)) {
      return 'Connected';
    }
    if (normalized == 'filtered') {
      return 'Filtered';
    }
    if (normalized == 'error') {
      return 'Error';
    }
    return hasToken ? 'Waiting' : 'Not set';
  }

  Color _panelQueueStatusBackground(String label) {
    switch (label) {
      case 'Connected':
        return const Color(0xFFDDF7E7);
      case 'Filtered':
        return const Color(0xFFFFF3CD);
      case 'Error':
        return const Color(0xFFFCE2E2);
      default:
        return const Color(0xFFE8EEF8);
    }
  }

  Color _panelQueueStatusForeground(String label) {
    switch (label) {
      case 'Connected':
        return const Color(0xFF166534);
      case 'Filtered':
        return const Color(0xFF92400E);
      case 'Error':
        return const Color(0xFFB91C1C);
      default:
        return const Color(0xFF1D4ED8);
    }
  }

  Widget _buildPanelStatusBadge(String label) {
    final background = _panelQueueStatusBackground(label);
    final foreground = _panelQueueStatusForeground(label);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: foreground.withValues(alpha: 0.18)),
      ),
      child: Text(
        label,
        style: Theme.of(context).textTheme.labelMedium?.copyWith(
              color: foreground,
              fontWeight: FontWeight.w700,
            ),
      ),
    );
  }

  String _panelItemScheduleSummary(Map<String, dynamic> panelItem) {
    final range = _panelTimeRangeSummary(
      start: panelItem['start'],
      end: panelItem['end'],
    );
    final days = _normalizeDays(panelItem['days'])
        .map((day) => day.toUpperCase())
        .join(' ');
    final parts = <String>[];
    parts.add(range);
    if (days.isNotEmpty) {
      parts.add(days);
    }
    return parts.join(' • ');
  }

  Future<void> _updatePanelZone({
    String? layoutMode,
    String? sourceMode,
  }) async {
    setState(() {
      _saving = true;
      _message = null;
    });
    try {
      final data = await widget.apiClient.updatePanelZone(
        storeId: widget.storeId,
        screenId: widget.screenId,
        layoutMode: layoutMode,
        sourceMode: sourceMode,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        final updatedZone = _asMap(data['panel_zone']);
        _screenPanelZone = _normalizedPanelZone(updatedZone);
        _isPanelInfoExpanded = true;
        if (sourceMode != null) {
          _message = sourceMode == 'pos_webhook'
              ? 'Live POS mode enabled.'
              : 'Manual info cards enabled.';
        } else if (layoutMode != null) {
          _message = layoutMode == 'off'
              ? 'Info panel turned off.'
              : 'Info panel layout updated.';
        }
      });
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

  Future<void> _addLivePosScheduleFromPanel() async {
    if (_hasLivePosSchedule) {
      return;
    }
    final panelZone = _normalizedPanelZone(_screenPanelZone);
    final posFeed = _asMap(panelZone['pos_feed']);
    final displayName = (posFeed['name'] ?? '').toString().trim();
    final parsedDuration = int.tryParse('${posFeed['display_seconds'] ?? 10}');
    final duration = (parsedDuration ?? 10).clamp(1, 120).toInt();
    setState(() {
      _saving = true;
      _message = null;
    });
    try {
      final data = await widget.apiClient.addLivePosPlaylistItem(
        storeId: widget.storeId,
        screenId: widget.screenId,
        displayName: displayName.isEmpty ? 'Live POS' : displayName,
        duration: duration,
        reuseExisting: true,
      );
      if (!mounted) {
        return;
      }
      final updatedZone = _normalizedPanelZone(_asMap(data['panel_zone']));
      setState(() {
        _screenPanelZone = updatedZone;
        _isPanelInfoExpanded = true;
        _message = 'Live POS added to this screen schedule.';
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

  Future<void> _togglePanelCardEnabled(Map<String, dynamic> panelItem) async {
    final itemId = (panelItem['id'] ?? '').toString();
    if (itemId.isEmpty) {
      return;
    }
    final nextEnabled = !((panelItem['enabled'] ?? true) == true);
    setState(() {
      _saving = true;
      _message = null;
    });
    try {
      await widget.apiClient.updatePanelPlaylistItem(
        storeId: widget.storeId,
        screenId: widget.screenId,
        itemId: itemId,
        enabled: nextEnabled,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _message = nextEnabled ? 'Info card enabled.' : 'Info card disabled.';
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

  Future<void> _togglePanelCardDay(
    Map<String, dynamic> panelItem,
    String day,
  ) async {
    final itemId = (panelItem['id'] ?? '').toString();
    if (itemId.isEmpty) {
      return;
    }
    final nextDays = _normalizeDays(panelItem['days']).toSet();
    if (nextDays.contains(day)) {
      nextDays.remove(day);
    } else {
      nextDays.add(day);
    }

    setState(() {
      _saving = true;
      _message = null;
    });
    try {
      await widget.apiClient.updatePanelPlaylistItem(
        storeId: widget.storeId,
        screenId: widget.screenId,
        itemId: itemId,
        days: nextDays.toList(),
      );
      if (!mounted) {
        return;
      }
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

  Future<void> _updatePanelCardBoundary({
    required Map<String, dynamic> panelItem,
    required bool isStart,
    required bool pickDate,
  }) async {
    final itemId = (panelItem['id'] ?? '').toString();
    if (itemId.isEmpty) {
      return;
    }
    final existing =
        _formatDisplayDateTime(panelItem[isStart ? 'start' : 'end']).trim();
    final nextValue = pickDate
        ? await _selectDateValue(existing)
        : await _selectTimeValue(existing);
    if (nextValue == null || !mounted) {
      return;
    }

    setState(() {
      _saving = true;
      _message = null;
    });
    try {
      await widget.apiClient.updatePanelPlaylistItem(
        storeId: widget.storeId,
        screenId: widget.screenId,
        itemId: itemId,
        start: isStart ? nextValue : null,
        end: isStart ? null : nextValue,
      );
      if (!mounted) {
        return;
      }
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

  Future<void> _clearPanelCardBoundary({
    required Map<String, dynamic> panelItem,
    required bool isStart,
  }) async {
    final itemId = (panelItem['id'] ?? '').toString();
    if (itemId.isEmpty) {
      return;
    }
    setState(() {
      _saving = true;
      _message = null;
    });
    try {
      await widget.apiClient.updatePanelPlaylistItem(
        storeId: widget.storeId,
        screenId: widget.screenId,
        itemId: itemId,
        start: isStart ? '' : null,
        end: isStart ? null : '',
      );
      if (!mounted) {
        return;
      }
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

  void _applyPanelZoneResponse(
    Map<String, dynamic> data, {
    String? message,
  }) {
    final updatedZone = _normalizedPanelZone(_asMap(data['panel_zone']));
    setState(() {
      _screenPanelZone = updatedZone;
      _isPanelInfoExpanded = true;
      if (message != null) {
        _message = message;
      }
    });
  }

  List<String> _parsePanelStatusList(String text) {
    return text
        .split(',')
        .map((value) => value.trim().toLowerCase())
        .where((value) => value.isNotEmpty)
        .toSet()
        .toList();
  }

  String _normalizePanelColor(String raw) {
    final text = raw.trim();
    if (RegExp(r'^#?[0-9a-fA-F]{6}$').hasMatch(text)) {
      return '#${text.replaceFirst('#', '').toLowerCase()}';
    }
    if (RegExp(r'^#?[0-9a-fA-F]{3}$').hasMatch(text)) {
      final compact = text.replaceFirst('#', '').toLowerCase();
      return '#${compact.split('').map((ch) => '$ch$ch').join()}';
    }
    return '#201206';
  }

  String _panelPosWebhookUrl(String token) {
    final cleanToken = token.trim();
    if (cleanToken.isEmpty) {
      return '';
    }
    try {
      final base = Uri.parse(widget.apiClient.baseUrl);
      return base
          .resolve('/api/panel-pos-webhook/${Uri.encodeComponent(cleanToken)}')
          .toString();
    } catch (_) {
      return '/api/panel-pos-webhook/$cleanToken';
    }
  }

  Widget _buildPanelPosMetricBadge({
    required String label,
    required IconData icon,
  }) {
    return _buildInfoBadge(
      icon: icon,
      label: label,
      background: const Color(0xFFE8F0FE),
      foreground: const Color(0xFF1D4ED8),
    );
  }

  Future<void> _openPanelPosSetupSheet() async {
    final panelZone = _normalizedPanelZone(_screenPanelZone);
    final posFeed = _asMap(panelZone['pos_feed']);
    final fieldMap = _asMap(posFeed['field_map']);
    final appearance = _asMap(panelZone['appearance']);

    final nameController = TextEditingController(
      text: (posFeed['name'] ?? '').toString(),
    );
    final statusesController = TextEditingController(
      text: (posFeed['allowed_statuses'] as List? ?? const ['ready', 'serving'])
          .map((value) => value.toString())
          .join(', '),
    );
    final durationController = TextEditingController(
      text: '${int.tryParse('${posFeed['display_seconds'] ?? 10}') ?? 10}',
    );
    final maxItemsController = TextEditingController(
      text: '${int.tryParse('${posFeed['max_items'] ?? 5}') ?? 5}',
    );
    final titleController = TextEditingController(
      text: (posFeed['title_template'] ?? 'Now serving').toString(),
    );
    final bodyController = TextEditingController(
      text: (posFeed['body_template'] ??
              '{{customer_name}}\nOrder #{{order_number}}')
          .toString(),
    );
    final customerController = TextEditingController(
      text: (fieldMap['customer_name'] ?? 'customer.name').toString(),
    );
    final orderController = TextEditingController(
      text: (fieldMap['order_number'] ?? 'order.number').toString(),
    );
    final statusController = TextEditingController(
      text: (fieldMap['status'] ?? 'order.status').toString(),
    );
    final externalController = TextEditingController(
      text: (fieldMap['external_id'] ?? 'order.id').toString(),
    );
    final storeSelectorController = TextEditingController(
      text: (posFeed['store_selector_path'] ?? 'store.id').toString(),
    );
    final backgroundController = TextEditingController(
      text: (appearance['background_color'] ?? '#201206').toString(),
    );
    final bodyRowsController = TextEditingController(
      text: '${int.tryParse('${appearance['body_rows'] ?? 4}') ?? 4}',
    );

    var localScope = (panelZone['feed_scope'] ?? 'screen').toString();
    var localConnector =
        (posFeed['connector_type'] ?? 'generic_webhook').toString();
    var localAlign = (appearance['content_align'] ?? 'center').toString();
    var localWebhookToken = (posFeed['webhook_token'] ?? '').toString();
    var localEventCount = int.tryParse('${posFeed['event_count'] ?? 0}') ?? 0;
    var localLastEventAt = (posFeed['last_event_at'] ?? '').toString();
    var localLastEventResult = (posFeed['last_event_result'] ?? '').toString();
    var localLastEventSummary = _asMap(posFeed['last_event_summary']);
    var localLastPayload = (posFeed['last_payload_preview'] ?? '').toString();
    var localQueueCount = _activePanelItems(panelZone).length;
    var localSaving = false;

    Future<void> saveSetup(StateSetter setSheetState) async {
      setSheetState(() {
        localSaving = true;
      });
      try {
        final data = await widget.apiClient.updatePanelPosFeed(
          storeId: widget.storeId,
          screenId: widget.screenId,
          payload: {
            'enable_source': true,
            'feed_scope': localScope,
            'name': nameController.text.trim(),
            'connector_type': localConnector,
            'field_map': {
              'customer_name': customerController.text.trim(),
              'order_number': orderController.text.trim(),
              'status': statusController.text.trim(),
              'external_id': externalController.text.trim(),
            },
            'store_selector_path': storeSelectorController.text.trim(),
            'title_template': titleController.text.trim(),
            'body_template': bodyController.text.trim(),
            'allowed_statuses':
                _parsePanelStatusList(statusesController.text.trim()),
            'display_seconds':
                int.tryParse(durationController.text.trim()) ?? 10,
            'max_items': int.tryParse(maxItemsController.text.trim()) ?? 5,
            'appearance': {
              'background_color':
                  _normalizePanelColor(backgroundController.text.trim()),
              'content_align': localAlign,
              'body_rows': int.tryParse(bodyRowsController.text.trim()) ?? 4,
            },
          },
        );
        if (!mounted) {
          return;
        }
        final updatedZone = _normalizedPanelZone(_asMap(data['panel_zone']));
        final updatedFeed = _asMap(updatedZone['pos_feed']);
        localWebhookToken = (updatedFeed['webhook_token'] ?? '').toString();
        localEventCount =
            int.tryParse('${updatedFeed['event_count'] ?? 0}') ?? 0;
        localLastEventAt = (updatedFeed['last_event_at'] ?? '').toString();
        localLastEventResult =
            (updatedFeed['last_event_result'] ?? '').toString();
        localLastEventSummary = _asMap(updatedFeed['last_event_summary']);
        localLastPayload =
            (updatedFeed['last_payload_preview'] ?? '').toString();
        localQueueCount = _activePanelItems(updatedZone).length;
        _applyPanelZoneResponse(data, message: 'Live POS setup saved.');
      } catch (e) {
        if (!mounted) {
          return;
        }
        setState(() {
          _message = e.toString().replaceFirst('Exception: ', '');
        });
      } finally {
        if (mounted) {
          setSheetState(() {
            localSaving = false;
          });
        }
      }
    }

    Future<void> updateQueueAction(
      StateSetter setSheetState, {
      bool resetToken = false,
      bool clearQueue = false,
      String? successMessage,
    }) async {
      setSheetState(() {
        localSaving = true;
      });
      try {
        final data = await widget.apiClient.updatePanelPosFeed(
          storeId: widget.storeId,
          screenId: widget.screenId,
          payload: {
            'enable_source': true,
            'feed_scope': localScope,
            if (resetToken) 'reset_token': true,
            if (clearQueue) 'clear_queue': true,
          },
        );
        if (!mounted) {
          return;
        }
        final updatedZone = _normalizedPanelZone(_asMap(data['panel_zone']));
        final updatedFeed = _asMap(updatedZone['pos_feed']);
        localWebhookToken = (updatedFeed['webhook_token'] ?? '').toString();
        localEventCount =
            int.tryParse('${updatedFeed['event_count'] ?? 0}') ?? 0;
        localLastEventAt = (updatedFeed['last_event_at'] ?? '').toString();
        localLastEventResult =
            (updatedFeed['last_event_result'] ?? '').toString();
        localLastEventSummary = _asMap(updatedFeed['last_event_summary']);
        localLastPayload =
            (updatedFeed['last_payload_preview'] ?? '').toString();
        localQueueCount = _activePanelItems(updatedZone).length;
        _applyPanelZoneResponse(data, message: successMessage);
      } catch (e) {
        if (!mounted) {
          return;
        }
        setState(() {
          _message = e.toString().replaceFirst('Exception: ', '');
        });
      } finally {
        if (mounted) {
          setSheetState(() {
            localSaving = false;
          });
        }
      }
    }

    Future<void> sendSample(StateSetter setSheetState) async {
      setSheetState(() {
        localSaving = true;
      });
      try {
        final data = await widget.apiClient.sendPanelPosSample(
          storeId: widget.storeId,
          screenId: widget.screenId,
        );
        if (!mounted) {
          return;
        }
        final updatedZone = _normalizedPanelZone(_asMap(data['panel_zone']));
        final updatedFeed = _asMap(updatedZone['pos_feed']);
        localWebhookToken = (updatedFeed['webhook_token'] ?? '').toString();
        localEventCount =
            int.tryParse('${updatedFeed['event_count'] ?? 0}') ?? 0;
        localLastEventAt = (updatedFeed['last_event_at'] ?? '').toString();
        localLastEventResult =
            (updatedFeed['last_event_result'] ?? '').toString();
        localLastEventSummary = _asMap(updatedFeed['last_event_summary']);
        localLastPayload =
            (updatedFeed['last_payload_preview'] ?? '').toString();
        localQueueCount = _activePanelItems(updatedZone).length;
        _applyPanelZoneResponse(data, message: 'Sample POS event sent.');
      } catch (e) {
        if (!mounted) {
          return;
        }
        setState(() {
          _message = e.toString().replaceFirst('Exception: ', '');
        });
      } finally {
        if (mounted) {
          setSheetState(() {
            localSaving = false;
          });
        }
      }
    }

    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheetContext) {
        return StatefulBuilder(
          builder: (context, setSheetState) {
            final webhookUrl = _panelPosWebhookUrl(localWebhookToken);
            final statusLabel = _panelQueueStatusLabel(
              localLastEventResult,
              localEventCount > 0,
              localWebhookToken.isNotEmpty,
            );
            final previewTitle = titleController.text.trim().isEmpty
                ? 'Now serving'
                : titleController.text.trim();
            final previewBody = bodyController.text.trim().isEmpty
                ? 'Jane Smith\nOrder #A104'
                : bodyController.text.trim();
            final lastSummaryLine =
                '${(localLastEventSummary['customer_name'] ?? '').toString().trim()}${(localLastEventSummary['order_number'] ?? '').toString().trim().isNotEmpty ? ' • Order #${(localLastEventSummary['order_number'] ?? '').toString().trim()}' : ''}${(localLastEventSummary['status'] ?? '').toString().trim().isNotEmpty ? ' • ${(localLastEventSummary['status'] ?? '').toString().trim()}' : ''}';

            return SafeArea(
              child: Padding(
                padding: EdgeInsets.only(
                  left: 16,
                  right: 16,
                  top: 8,
                  bottom: MediaQuery.of(sheetContext).viewInsets.bottom + 16,
                ),
                child: SizedBox(
                  height: MediaQuery.of(sheetContext).size.height * 0.9,
                  child: ListView(
                    children: [
                      Text('Live POS Setup', style: theme.textTheme.titleLarge),
                      const SizedBox(height: 4),
                      Text(
                        'Connect any POS through a direct webhook or a bridge like Zapier, Make, or n8n.',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: scheme.onSurfaceVariant,
                        ),
                      ),
                      const SizedBox(height: 10),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          _buildPanelStatusBadge(statusLabel),
                          _buildPanelPosMetricBadge(
                            label:
                                '$localEventCount event${localEventCount == 1 ? '' : 's'}',
                            icon: Icons.bolt_outlined,
                          ),
                          _buildPanelPosMetricBadge(
                            label:
                                '$localQueueCount/${int.tryParse(maxItemsController.text.trim()) ?? 5} queued',
                            icon: Icons.queue_outlined,
                          ),
                        ],
                      ),
                      const SizedBox(height: 14),
                      DropdownButtonFormField<String>(
                        value: localScope,
                        items: _panelScopeTitles.entries
                            .map(
                              (entry) => DropdownMenuItem<String>(
                                value: entry.key,
                                child: Text(entry.value),
                              ),
                            )
                            .toList(),
                        onChanged: localSaving
                            ? null
                            : (value) {
                                if (value == null) {
                                  return;
                                }
                                setSheetState(() {
                                  localScope = value;
                                });
                              },
                        decoration: const InputDecoration(
                          labelText: 'Webhook scope',
                        ),
                      ),
                      const SizedBox(height: 10),
                      DropdownButtonFormField<String>(
                        value: localConnector,
                        items: _panelConnectorLabels.entries
                            .map(
                              (entry) => DropdownMenuItem<String>(
                                value: entry.key,
                                child: Text(entry.value),
                              ),
                            )
                            .toList(),
                        onChanged: localSaving
                            ? null
                            : (value) {
                                if (value == null) {
                                  return;
                                }
                                setSheetState(() {
                                  localConnector = value;
                                });
                              },
                        decoration: const InputDecoration(
                          labelText: 'How will you connect?',
                        ),
                      ),
                      const SizedBox(height: 10),
                      TextField(
                        controller: nameController,
                        enabled: !localSaving,
                        decoration: const InputDecoration(
                          labelText: 'POS or feed name',
                          hintText: 'Front Counter POS',
                        ),
                      ),
                      const SizedBox(height: 10),
                      TextField(
                        controller: statusesController,
                        enabled: !localSaving,
                        decoration: const InputDecoration(
                          labelText: 'Statuses to show',
                          hintText: 'ready, serving',
                        ),
                      ),
                      const SizedBox(height: 10),
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: durationController,
                              enabled: !localSaving,
                              keyboardType: TextInputType.number,
                              decoration: const InputDecoration(
                                labelText: 'Seconds visible',
                              ),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: TextField(
                              controller: maxItemsController,
                              enabled: !localSaving,
                              keyboardType: TextInputType.number,
                              decoration: const InputDecoration(
                                labelText: 'Max queue size',
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 14),
                      Text(
                        'On-screen template',
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 10),
                      TextField(
                        controller: titleController,
                        enabled: !localSaving,
                        decoration: const InputDecoration(
                          labelText: 'Title template',
                        ),
                        onChanged: (_) => setSheetState(() {}),
                      ),
                      const SizedBox(height: 10),
                      TextField(
                        controller: bodyController,
                        enabled: !localSaving,
                        minLines: 3,
                        maxLines: 5,
                        decoration: const InputDecoration(
                          labelText: 'Body template',
                        ),
                        onChanged: (_) => setSheetState(() {}),
                      ),
                      const SizedBox(height: 10),
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: backgroundController,
                              enabled: !localSaving,
                              decoration: const InputDecoration(
                                labelText: 'Background colour',
                                hintText: '#201206',
                              ),
                              onChanged: (_) => setSheetState(() {}),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: DropdownButtonFormField<String>(
                              value: localAlign,
                              items: const [
                                DropdownMenuItem(
                                  value: 'top',
                                  child: Text('Top'),
                                ),
                                DropdownMenuItem(
                                  value: 'center',
                                  child: Text('Center'),
                                ),
                                DropdownMenuItem(
                                  value: 'bottom',
                                  child: Text('Bottom'),
                                ),
                              ],
                              onChanged: localSaving
                                  ? null
                                  : (value) {
                                      if (value == null) {
                                        return;
                                      }
                                      setSheetState(() {
                                        localAlign = value;
                                      });
                                    },
                              decoration: const InputDecoration(
                                labelText: 'Content position',
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      TextField(
                        controller: bodyRowsController,
                        enabled: !localSaving,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'Visible body rows',
                        ),
                      ),
                      const SizedBox(height: 10),
                      Container(
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: Color(
                            int.parse(
                              _normalizePanelColor(backgroundController.text)
                                  .replaceFirst('#', '0xFF'),
                            ),
                          ),
                          borderRadius: BorderRadius.circular(14),
                          border: Border.all(color: const Color(0xFFF3C48C)),
                        ),
                        child: Column(
                          crossAxisAlignment: localAlign == 'top'
                              ? CrossAxisAlignment.start
                              : localAlign == 'bottom'
                                  ? CrossAxisAlignment.end
                                  : CrossAxisAlignment.center,
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 10,
                                vertical: 6,
                              ),
                              decoration: BoxDecoration(
                                color: Colors.white.withValues(alpha: 0.12),
                                borderRadius: BorderRadius.circular(999),
                              ),
                              child: const Text(
                                'LIVE ORDER INFO',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 11,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                            const SizedBox(height: 10),
                            Text(
                              previewTitle,
                              textAlign: localAlign == 'center'
                                  ? TextAlign.center
                                  : localAlign == 'bottom'
                                      ? TextAlign.right
                                      : TextAlign.left,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 22,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                            const SizedBox(height: 6),
                            Text(
                              previewBody,
                              textAlign: localAlign == 'center'
                                  ? TextAlign.center
                                  : localAlign == 'bottom'
                                      ? TextAlign.right
                                      : TextAlign.left,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 13,
                                height: 1.4,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 14),
                      Text(
                        'Advanced mapping',
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 10),
                      TextField(
                        controller: customerController,
                        enabled: !localSaving,
                        decoration: const InputDecoration(
                          labelText: 'Customer path',
                          hintText: 'customer.name',
                        ),
                      ),
                      const SizedBox(height: 10),
                      TextField(
                        controller: orderController,
                        enabled: !localSaving,
                        decoration: const InputDecoration(
                          labelText: 'Order path',
                          hintText: 'order.number',
                        ),
                      ),
                      const SizedBox(height: 10),
                      TextField(
                        controller: statusController,
                        enabled: !localSaving,
                        decoration: const InputDecoration(
                          labelText: 'Status path',
                          hintText: 'order.status',
                        ),
                      ),
                      const SizedBox(height: 10),
                      TextField(
                        controller: externalController,
                        enabled: !localSaving,
                        decoration: const InputDecoration(
                          labelText: 'External id path',
                          hintText: 'order.id',
                        ),
                      ),
                      const SizedBox(height: 10),
                      TextField(
                        controller: storeSelectorController,
                        enabled: !localSaving,
                        decoration: const InputDecoration(
                          labelText: 'Store id path (chain)',
                          hintText: 'store.id',
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        readOnly: true,
                        controller: TextEditingController(text: webhookUrl),
                        decoration: InputDecoration(
                          labelText: 'Webhook URL',
                          suffixIcon: IconButton(
                            tooltip: 'Copy webhook URL',
                            onPressed: webhookUrl.isEmpty
                                ? null
                                : () async {
                                    await Clipboard.setData(
                                      ClipboardData(text: webhookUrl),
                                    );
                                    if (mounted) {
                                      _showSheetMessage('Webhook URL copied.');
                                    }
                                  },
                            icon: const Icon(Icons.copy_outlined),
                          ),
                        ),
                      ),
                      const SizedBox(height: 10),
                      if (localLastEventAt.isNotEmpty ||
                          lastSummaryLine.isNotEmpty)
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: scheme.surfaceContainerLow,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: scheme.outlineVariant),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Latest order snapshot',
                                style: theme.textTheme.labelLarge?.copyWith(
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                              if (localLastEventAt.isNotEmpty) ...[
                                const SizedBox(height: 6),
                                Text(
                                  localLastEventAt.replaceFirst('T', ' '),
                                  style: theme.textTheme.bodySmall?.copyWith(
                                    color: scheme.onSurfaceVariant,
                                  ),
                                ),
                              ],
                              if (lastSummaryLine.isNotEmpty) ...[
                                const SizedBox(height: 6),
                                Text(
                                  lastSummaryLine,
                                  style: theme.textTheme.bodySmall,
                                ),
                              ],
                            ],
                          ),
                        ),
                      if (localLastPayload.trim().isNotEmpty) ...[
                        const SizedBox(height: 10),
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: scheme.surfaceContainerLow,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: scheme.outlineVariant),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Last payload received',
                                style: theme.textTheme.labelLarge?.copyWith(
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                              const SizedBox(height: 8),
                              SelectableText(
                                localLastPayload,
                                style: theme.textTheme.bodySmall?.copyWith(
                                  fontFamily: 'Consolas',
                                  height: 1.45,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                      const SizedBox(height: 16),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          FilledButton.icon(
                            onPressed: localSaving
                                ? null
                                : () => saveSetup(setSheetState),
                            icon: localSaving
                                ? const SizedBox(
                                    width: 16,
                                    height: 16,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                    ),
                                  )
                                : const Icon(Icons.save_outlined),
                            label: const Text('Save setup'),
                          ),
                          OutlinedButton.icon(
                            onPressed: localSaving
                                ? null
                                : () => sendSample(setSheetState),
                            icon: const Icon(Icons.send_outlined),
                            label: const Text('Send sample'),
                          ),
                          OutlinedButton.icon(
                            onPressed: localSaving
                                ? null
                                : () => updateQueueAction(
                                      setSheetState,
                                      resetToken: true,
                                      successMessage:
                                          'Webhook URL regenerated.',
                                    ),
                            icon: const Icon(Icons.refresh_outlined),
                            label: const Text('Reset webhook'),
                          ),
                          OutlinedButton.icon(
                            onPressed: localSaving
                                ? null
                                : () => updateQueueAction(
                                      setSheetState,
                                      clearQueue: true,
                                      successMessage: 'POS queue cleared.',
                                    ),
                            icon: const Icon(Icons.layers_clear_outlined),
                            label: const Text('Clear queue'),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        );
      },
    );

    nameController.dispose();
    statusesController.dispose();
    durationController.dispose();
    maxItemsController.dispose();
    titleController.dispose();
    bodyController.dispose();
    customerController.dispose();
    orderController.dispose();
    statusController.dispose();
    externalController.dispose();
    storeSelectorController.dispose();
    backgroundController.dispose();
    bodyRowsController.dispose();
  }

  void _togglePanelItemExpanded(String itemId) {
    if (itemId.isEmpty) {
      return;
    }
    setState(() {
      if (_expandedPanelItemIds.contains(itemId)) {
        _expandedPanelItemIds.remove(itemId);
      } else {
        _expandedPanelItemIds.add(itemId);
      }
    });
  }

  Future<void> _openPanelCardEditor({Map<String, dynamic>? panelItem}) async {
    final isEditing = panelItem != null;
    final titleController = TextEditingController(
      text: (panelItem?['title'] ?? '').toString(),
    );
    final bodyController = TextEditingController(
      text: (panelItem?['body'] ?? '').toString(),
    );
    final startController = TextEditingController(
      text: _formatDisplayDateTime(panelItem?['start']),
    );
    final endController = TextEditingController(
      text: _formatDisplayDateTime(panelItem?['end']),
    );
    final durationController = TextEditingController(
      text: '${int.tryParse('${panelItem?['duration'] ?? 10}') ?? 10}',
    );
    var localEnabled = (panelItem?['enabled'] ?? true) == true;
    var localRepeat = (panelItem?['repeat'] ?? true) == true;
    final localDays = _normalizeDays(panelItem?['days']).toSet();

    final saved = await showDialog<bool>(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              title: Text(isEditing ? 'Edit Info Card' : 'Add Info Card'),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    TextField(
                      controller: titleController,
                      decoration: const InputDecoration(labelText: 'Title'),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: bodyController,
                      minLines: 3,
                      maxLines: 5,
                      decoration: const InputDecoration(labelText: 'Body'),
                    ),
                    const SizedBox(height: 12),
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
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Repeat'),
                      value: localRepeat,
                      onChanged: (value) {
                        setDialogState(() {
                          localRepeat = value;
                        });
                      },
                    ),
                    TextField(
                      controller: durationController,
                      keyboardType: TextInputType.number,
                      decoration:
                          const InputDecoration(labelText: 'Duration (s)'),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: startController,
                      decoration: const InputDecoration(
                        labelText: 'Start',
                        hintText: 'YYYY-MM-DD HH:MM:SS',
                      ),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: endController,
                      decoration: const InputDecoration(
                        labelText: 'End',
                        hintText: 'YYYY-MM-DD HH:MM:SS',
                      ),
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
                  onPressed: () => Navigator.of(context).pop(true),
                  child: Text(isEditing ? 'Save' : 'Add'),
                ),
              ],
            );
          },
        );
      },
    );

    if (saved != true || !mounted) {
      titleController.dispose();
      bodyController.dispose();
      startController.dispose();
      endController.dispose();
      durationController.dispose();
      return;
    }

    final title = titleController.text.trim();
    final duration = int.tryParse(durationController.text.trim()) ?? 10;

    setState(() {
      _saving = true;
      _message = null;
    });
    try {
      if (isEditing) {
        final itemId = (panelItem['id'] ?? '').toString();
        if (itemId.isEmpty) {
          throw Exception('Info card id missing');
        }
        await widget.apiClient.updatePanelPlaylistItem(
          storeId: widget.storeId,
          screenId: widget.screenId,
          itemId: itemId,
          title: title,
          body: bodyController.text,
          start:
              startController.text.trim().isEmpty ? null : startController.text,
          end: endController.text.trim().isEmpty ? null : endController.text,
          enabled: localEnabled,
          repeat: localRepeat,
          duration: duration < 1 ? 1 : duration,
          days: localDays.toList(),
        );
        if (!mounted) {
          return;
        }
        setState(() {
          _message = 'Info card updated.';
        });
      } else {
        final created = await widget.apiClient.addPanelPlaylistItem(
          storeId: widget.storeId,
          screenId: widget.screenId,
          title: title,
          body: bodyController.text,
        );
        final createdItem = _asMap(created['item']);
        final createdItemId = (createdItem['id'] ?? '').toString();
        if (createdItemId.isNotEmpty) {
          await widget.apiClient.updatePanelPlaylistItem(
            storeId: widget.storeId,
            screenId: widget.screenId,
            itemId: createdItemId,
            title: title,
            body: bodyController.text,
            start: startController.text.trim().isEmpty
                ? null
                : startController.text,
            end: endController.text.trim().isEmpty ? null : endController.text,
            enabled: localEnabled,
            repeat: localRepeat,
            duration: duration < 1 ? 1 : duration,
            days: localDays.toList(),
          );
        }
        if (!mounted) {
          return;
        }
        setState(() {
          _message = 'Info card added.';
        });
      }
      await _loadPlaylist();
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _message = e.toString().replaceFirst('Exception: ', '');
      });
    } finally {
      titleController.dispose();
      bodyController.dispose();
      startController.dispose();
      endController.dispose();
      durationController.dispose();
      if (mounted) {
        setState(() {
          _saving = false;
        });
      }
    }
  }

  void _togglePanelInfoExpanded() {
    setState(() {
      _isPanelInfoExpanded = !_isPanelInfoExpanded;
    });
  }

  Future<void> _openLivePosQueueSheet(List<Map<String, dynamic>> items) async {
    if (items.isEmpty) {
      return;
    }
    final theme = Theme.of(context);
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheetContext) {
        return SafeArea(
          child: Padding(
            padding: EdgeInsets.only(
              left: 16,
              right: 16,
              top: 8,
              bottom: MediaQuery.of(sheetContext).viewInsets.bottom + 16,
            ),
            child: SizedBox(
              height: MediaQuery.of(sheetContext).size.height * 0.72,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Live POS Orders', style: theme.textTheme.titleLarge),
                  const SizedBox(height: 4),
                  Text(
                    '${items.length} queued ${items.length == 1 ? 'order' : 'orders'} for this screen',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Expanded(
                    child: ListView.builder(
                      itemCount: items.length,
                      itemBuilder: (context, index) {
                        return _buildPanelItemTile(
                          panelItem: items[index],
                          sourceMode: 'pos_webhook',
                          allowActions: false,
                        );
                      },
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildPanelItemTile({
    required Map<String, dynamic> panelItem,
    required String sourceMode,
    required bool allowActions,
  }) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final panelItemId = (panelItem['id'] ?? '').toString();
    final isExpanded =
        panelItemId.isNotEmpty && _expandedPanelItemIds.contains(panelItemId);
    final title = (panelItem['title'] ?? 'Panel item').toString();
    final body = (panelItem['body'] ?? '').toString().trim();
    final status = (panelItem['status'] ?? 'live').toString();
    final duration = int.tryParse('${panelItem['duration'] ?? 10}') ?? 10;
    final createdAt = _formatDisplayDateTime(panelItem['created_at']).trim();
    return InkWell(
      borderRadius: BorderRadius.circular(14),
      onTap: () => _togglePanelItemExpanded(panelItemId),
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: sourceMode == 'pos_webhook'
              ? const Color(0xFFFFF7ED)
              : scheme.surfaceContainerLow,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: sourceMode == 'pos_webhook'
                ? const Color(0xFFFED7AA)
                : scheme.outlineVariant,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: isExpanded ? 92 : 72,
                  height: isExpanded ? 56 : 42,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: sourceMode == 'pos_webhook'
                        ? const Color(0xFFFFE9BF)
                        : scheme.surfaceContainerHigh,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                      color: sourceMode == 'pos_webhook'
                          ? const Color(0xFFF7D08A)
                          : scheme.outlineVariant,
                    ),
                  ),
                  child: Text(
                    sourceMode == 'pos_webhook' ? 'POS' : 'CARD',
                    style: theme.textTheme.titleSmall?.copyWith(
                      color: sourceMode == 'pos_webhook'
                          ? const Color(0xFF9A5A00)
                          : scheme.primary,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0.4,
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${status.isEmpty ? 'live' : status}  $duration s',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: scheme.onSurfaceVariant,
                        ),
                      ),
                      if (!isExpanded &&
                          sourceMode == 'pos_webhook' &&
                          createdAt.isNotEmpty) ...[
                        const SizedBox(height: 4),
                        Text(
                          createdAt,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: scheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                      if (!isExpanded && sourceMode != 'pos_webhook') ...[
                        const SizedBox(height: 4),
                        Text(
                          _panelItemScheduleSummary(panelItem),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: scheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Icon(
                  isExpanded
                      ? Icons.expand_less_rounded
                      : Icons.expand_more_rounded,
                  color: scheme.onSurfaceVariant,
                ),
              ],
            ),
            if (isExpanded) ...[
              const SizedBox(height: 8),
              if (body.isNotEmpty) ...[
                Text(
                  body,
                  style: theme.textTheme.bodyMedium,
                ),
                const SizedBox(height: 6),
              ],
              if (sourceMode != 'pos_webhook') ...[
                Text(
                  _panelItemScheduleSummary(panelItem),
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: scheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    _buildInfoBadge(
                      icon: (panelItem['enabled'] ?? true) == true
                          ? Icons.check_circle_outline
                          : Icons.pause_circle_outline,
                      label: (panelItem['enabled'] ?? true) == true
                          ? 'Enabled'
                          : 'Disabled',
                      background: (panelItem['enabled'] ?? true) == true
                          ? scheme.primaryContainer
                          : scheme.surfaceContainerHigh,
                      foreground: (panelItem['enabled'] ?? true) == true
                          ? scheme.onPrimaryContainer
                          : scheme.onSurfaceVariant,
                    ),
                    _buildInfoBadge(
                      icon: Icons.repeat,
                      label: (panelItem['repeat'] ?? true) == true
                          ? 'Repeat'
                          : 'Once',
                    ),
                  ],
                ),
                if (allowActions) ...[
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      OutlinedButton.icon(
                        onPressed: _saving
                            ? null
                            : () => _openPanelCardEditor(
                                  panelItem: panelItem,
                                ),
                        icon: const Icon(Icons.edit_outlined),
                        label: const Text('Edit'),
                      ),
                      const SizedBox(width: 8),
                      OutlinedButton.icon(
                        onPressed:
                            _saving ? null : () => _deletePanelCard(panelItem),
                        icon: const Icon(Icons.delete_outline),
                        label: const Text('Delete'),
                      ),
                    ],
                  ),
                ],
              ],
            ],
          ],
        ),
      ),
    );
  }

  Future<void> _deletePanelCard(Map<String, dynamic> panelItem) async {
    final itemId = (panelItem['id'] ?? '').toString();
    if (itemId.isEmpty) {
      return;
    }

    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Info Card'),
        content: const Text('Delete this info panel card?'),
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

    if (accepted != true || !mounted) {
      return;
    }

    setState(() {
      _saving = true;
      _message = null;
    });
    try {
      await widget.apiClient.deletePanelPlaylistItem(
        storeId: widget.storeId,
        screenId: widget.screenId,
        itemId: itemId,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _message = 'Info card deleted.';
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

  Widget _buildPanelMenuButton({
    required IconData icon,
    required String value,
    required Map<String, String> options,
    required ValueChanged<String> onSelected,
    bool enabled = true,
  }) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return PopupMenuButton<String>(
      enabled: enabled,
      tooltip: '',
      onSelected: onSelected,
      itemBuilder: (context) {
        return options.entries
            .map(
              (entry) => PopupMenuItem<String>(
                value: entry.key,
                child: Text(entry.value),
              ),
            )
            .toList();
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
        decoration: BoxDecoration(
          color: enabled ? Colors.white : scheme.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: scheme.outlineVariant),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 16, color: scheme.onSurfaceVariant),
            const SizedBox(width: 6),
            Text(
              options[value] ?? value,
              style: theme.textTheme.labelLarge?.copyWith(
                color: enabled
                    ? scheme.onSurface
                    : scheme.onSurfaceVariant.withValues(alpha: 0.8),
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(width: 4),
            Icon(
              Icons.arrow_drop_down_rounded,
              color: scheme.onSurfaceVariant,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPanelBoundaryCard({
    required String label,
    required dynamic value,
    required VoidCallback? onPickDate,
    required VoidCallback? onPickTime,
    required VoidCallback? onClear,
  }) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final text = _formatDisplayDateTime(value).trim();
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: theme.textTheme.labelMedium?.copyWith(
              color: scheme.onSurfaceVariant,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            text.isEmpty ? 'No time set' : text,
            style: theme.textTheme.bodySmall?.copyWith(
              color: text.isEmpty ? scheme.onSurfaceVariant : scheme.onSurface,
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              IconButton(
                onPressed: onPickDate,
                tooltip: 'Pick date',
                icon: const Icon(Icons.date_range_outlined, size: 18),
                visualDensity: VisualDensity.compact,
              ),
              IconButton(
                onPressed: onPickTime,
                tooltip: 'Pick time',
                icon: const Icon(Icons.access_time_outlined, size: 18),
                visualDensity: VisualDensity.compact,
              ),
              IconButton(
                onPressed: onClear,
                tooltip: 'Clear',
                icon: const Icon(Icons.close_rounded, size: 18),
                visualDensity: VisualDensity.compact,
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildManualPanelItemTile(Map<String, dynamic> panelItem) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final title = (panelItem['title'] ?? 'Info card').toString();
    final body = (panelItem['body'] ?? '').toString().trim();
    final rangeSummary = _panelTimeRangeSummary(
      start: panelItem['start'],
      end: panelItem['end'],
    );
    final duration = int.tryParse('${panelItem['duration'] ?? 10}') ?? 10;
    final enabled = (panelItem['enabled'] ?? true) == true;
    final days = _normalizeDays(panelItem['days']).toSet();

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLowest,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 82,
                height: 50,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: const Color(0xFFFFF3D8),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: const Color(0xFFF3C48C)),
                ),
                child: Text(
                  'INFO',
                  style: theme.textTheme.titleSmall?.copyWith(
                    color: const Color(0xFF8A4B00),
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0.5,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '$rangeSummary  •  ${duration}s',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: scheme.outlineVariant),
            ),
            child: Text(
              body.isEmpty ? 'No body text' : body,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: body.isEmpty ? scheme.onSurfaceVariant : null,
              ),
            ),
          ),
          const SizedBox(height: 10),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Repeat:',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: scheme.onSurfaceVariant,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: _weekDays.map((day) {
                    final selected = days.contains(day);
                    return FilterChip(
                      label: Text(day[0].toUpperCase()),
                      selected: selected,
                      visualDensity: VisualDensity.compact,
                      onSelected: _saving
                          ? null
                          : (_) => _togglePanelCardDay(panelItem, day),
                    );
                  }).toList(),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: _buildPanelBoundaryCard(
                  label: 'Start',
                  value: panelItem['start'],
                  onPickDate: _saving
                      ? null
                      : () => _updatePanelCardBoundary(
                            panelItem: panelItem,
                            isStart: true,
                            pickDate: true,
                          ),
                  onPickTime: _saving
                      ? null
                      : () => _updatePanelCardBoundary(
                            panelItem: panelItem,
                            isStart: true,
                            pickDate: false,
                          ),
                  onClear: _saving
                      ? null
                      : () => _clearPanelCardBoundary(
                            panelItem: panelItem,
                            isStart: true,
                          ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _buildPanelBoundaryCard(
                  label: 'End',
                  value: panelItem['end'],
                  onPickDate: _saving
                      ? null
                      : () => _updatePanelCardBoundary(
                            panelItem: panelItem,
                            isStart: false,
                            pickDate: true,
                          ),
                  onPickTime: _saving
                      ? null
                      : () => _updatePanelCardBoundary(
                            panelItem: panelItem,
                            isStart: false,
                            pickDate: false,
                          ),
                  onClear: _saving
                      ? null
                      : () => _clearPanelCardBoundary(
                            panelItem: panelItem,
                            isStart: false,
                          ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              FilledButton.tonal(
                onPressed:
                    _saving ? null : () => _togglePanelCardEnabled(panelItem),
                child: Text(enabled ? 'On' : 'Off'),
              ),
              OutlinedButton.icon(
                onPressed: _saving
                    ? null
                    : () => _openPanelCardEditor(panelItem: panelItem),
                icon: const Icon(Icons.schedule_outlined),
                label: Text('${duration}s'),
              ),
              OutlinedButton.icon(
                onPressed: _saving
                    ? null
                    : () => _openPanelCardEditor(panelItem: panelItem),
                icon: const Icon(Icons.edit_outlined),
                label: const Text('Edit'),
              ),
              OutlinedButton.icon(
                onPressed: _saving ? null : () => _deletePanelCard(panelItem),
                icon: const Icon(Icons.delete_outline),
                label: const Text('Delete'),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildPanelInfoCard() {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final panelZone = _normalizedPanelZone(_screenPanelZone);
    final sourceMode = (panelZone['source_mode'] ?? 'manual').toString();
    final layoutMode = (panelZone['layout_mode'] ?? 'off').toString();
    final enabled = panelZone['enabled'] == true;
    final items = _activePanelItems(panelZone);
    final posFeed = _asMap(panelZone['pos_feed']);
    final connectorType =
        (posFeed['connector_type'] ?? 'generic_webhook').toString();
    final connectorLabel =
        _panelConnectorLabels[connectorType] ?? 'Direct webhook';
    final connectorSubtitle = _panelConnectorSubtitles[connectorType] ??
        _panelConnectorSubtitles['generic_webhook']!;
    final feedScope = (panelZone['feed_scope'] ?? 'screen').toString();
    final scopeTitle = _panelScopeTitles[feedScope] ?? 'This screen only';
    final scopeSubtitle =
        _panelScopeSubtitles[feedScope] ?? 'One webhook just for this screen';
    final lastEventSummary = _asMap(posFeed['last_event_summary']);
    final eventCount = int.tryParse('${posFeed['event_count'] ?? 0}') ?? 0;
    final maxItems = int.tryParse('${posFeed['max_items'] ?? 5}') ?? 5;
    final hasToken =
        (posFeed['webhook_token'] ?? '').toString().trim().isNotEmpty;
    final statusLabel = _panelQueueStatusLabel(
      (posFeed['last_event_result'] ?? '').toString(),
      items.isNotEmpty,
      hasToken,
    );
    final hasLivePosSchedule = _hasLivePosSchedule;
    final collapsedSummary = sourceMode == 'pos_webhook'
        ? '$statusLabel | $eventCount event${eventCount == 1 ? '' : 's'} | ${items.length}/$maxItems queued | ${enabled ? _panelLayoutLabel(layoutMode) : 'Off'}'
        : '${items.length} info card${items.length == 1 ? '' : 's'} | ${enabled ? _panelLayoutLabel(layoutMode) : 'Off'}';
    final panelBackground =
        sourceMode == 'pos_webhook' ? const Color(0xFFF8FBFF) : scheme.surface;
    final panelBorder = sourceMode == 'pos_webhook'
        ? const Color(0xFFD8E4FB)
        : scheme.outlineVariant;

    return Card(
      elevation: 0,
      color: panelBackground,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: BorderSide(color: panelBorder),
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 12, 14, 14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            InkWell(
              borderRadius: BorderRadius.circular(12),
              onTap: _togglePanelInfoExpanded,
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  children: [
                    Icon(
                      sourceMode == 'pos_webhook'
                          ? Icons.receipt_long_outlined
                          : Icons.view_sidebar_outlined,
                      size: 20,
                      color: enabled ? scheme.primary : scheme.onSurfaceVariant,
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'Info Panel Schedule',
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    Text(
                      enabled ? _panelLayoutLabel(layoutMode) : 'Off',
                      style: theme.textTheme.labelMedium?.copyWith(
                        color: scheme.onSurfaceVariant,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Icon(
                      _isPanelInfoExpanded
                          ? Icons.expand_less_rounded
                          : Icons.expand_more_rounded,
                      color: scheme.onSurfaceVariant,
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 8),
            if (!_isPanelInfoExpanded)
              Text(
                collapsedSummary,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: scheme.onSurfaceVariant,
                  fontWeight: FontWeight.w600,
                ),
              )
            else ...[
              Wrap(
                spacing: 8,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  _buildPanelMenuButton(
                    icon: Icons.tune_outlined,
                    value: sourceMode,
                    options: _panelSourceLabels,
                    enabled: !_saving,
                    onSelected: (next) {
                      if (next != sourceMode) {
                        _updatePanelZone(sourceMode: next);
                      }
                    },
                  ),
                  _buildPanelMenuButton(
                    icon: Icons.view_sidebar_outlined,
                    value: layoutMode,
                    options: _panelLayoutLabels,
                    enabled: !_saving,
                    onSelected: (next) {
                      if (next != layoutMode) {
                        _updatePanelZone(layoutMode: next);
                      }
                    },
                  ),
                  if (sourceMode != 'pos_webhook')
                    FilledButton.tonalIcon(
                      onPressed: _saving ? null : _openPanelCardEditor,
                      icon: const Icon(Icons.add),
                      label: const Text('Add Info Card'),
                    ),
                ],
              ),
              const SizedBox(height: 10),
              if (sourceMode == 'pos_webhook') ...[
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Live POS Setup',
                            style: theme.textTheme.titleSmall?.copyWith(
                              color: const Color(0xFF1E40AF),
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            connectorSubtitle,
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: scheme.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 8),
                    _buildInfoBadge(
                      icon: Icons.cable_outlined,
                      label: connectorLabel,
                      background: scheme.surfaceContainerHigh,
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  '$scopeTitle: $scopeSubtitle',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: scheme.onSurfaceVariant,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    FilledButton.tonalIcon(
                      onPressed: _saving ? null : _openPanelPosSetupSheet,
                      icon: const Icon(Icons.settings_outlined),
                      label: const Text('Configure Live POS'),
                    ),
                    if (hasToken)
                      OutlinedButton.icon(
                        onPressed: _saving
                            ? null
                            : () async {
                                final webhookUrl = _panelPosWebhookUrl(
                                  (posFeed['webhook_token'] ?? '').toString(),
                                );
                                if (webhookUrl.isEmpty) {
                                  return;
                                }
                                await Clipboard.setData(
                                  ClipboardData(text: webhookUrl),
                                );
                                if (mounted) {
                                  _showSheetMessage('Webhook URL copied.');
                                }
                              },
                        icon: const Icon(Icons.copy_outlined),
                        label: const Text('Copy webhook'),
                      ),
                  ],
                ),
                if (lastEventSummary.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text(
                    '${(lastEventSummary['customer_name'] ?? '').toString().trim()}${(lastEventSummary['order_number'] ?? '').toString().trim().isNotEmpty ? ' • Order #${(lastEventSummary['order_number'] ?? '').toString().trim()}' : ''}${(lastEventSummary['status'] ?? '').toString().trim().isNotEmpty ? ' • ${(lastEventSummary['status'] ?? '').toString().trim()}' : ''}',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                ],
                const SizedBox(height: 10),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    _buildPanelStatusBadge(statusLabel),
                    _buildInfoBadge(
                      icon: Icons.bolt_outlined,
                      label: '$eventCount events',
                      background: const Color(0xFFE8F0FE),
                      foreground: const Color(0xFF1D4ED8),
                    ),
                    _buildInfoBadge(
                      icon: Icons.queue_outlined,
                      label: '${items.length}/$maxItems queued',
                      background: const Color(0xFFE8F0FE),
                      foreground: const Color(0xFF1D4ED8),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                FilledButton.icon(
                  onPressed: _saving || hasLivePosSchedule
                      ? null
                      : _addLivePosScheduleFromPanel,
                  icon: Icon(hasLivePosSchedule
                      ? Icons.check_circle_outline
                      : Icons.add),
                  label: Text(hasLivePosSchedule
                      ? 'Live POS schedule added'
                      : 'Add Live POS to schedule'),
                ),
              ],
              const SizedBox(height: 10),
              if (sourceMode == 'pos_webhook' && items.isNotEmpty) ...[
                FilledButton.tonalIcon(
                  onPressed: () => _openLivePosQueueSheet(items),
                  icon: const Icon(Icons.receipt_long_outlined),
                  label: Text('View live orders (${items.length})'),
                ),
                const SizedBox(height: 8),
                Text(
                  'Live POS orders stay hidden here and only open when you tap the button.',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: scheme.onSurfaceVariant,
                  ),
                ),
              ] else if (items.isEmpty)
                Text(
                  sourceMode == 'pos_webhook'
                      ? 'No Live POS cards queued yet.'
                      : '(No info panel cards yet)',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: scheme.onSurfaceVariant,
                  ),
                )
              else
                ...items.map((panelItem) {
                  return sourceMode == 'pos_webhook'
                      ? _buildPanelItemTile(
                          panelItem: panelItem,
                          sourceMode: sourceMode,
                          allowActions: true,
                        )
                      : _buildManualPanelItemTile(panelItem);
                }),
              const SizedBox(height: 8),
              Text(
                'The info panel auto-hides during sync or wall video playback and only appears on normal media.',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: scheme.onSurfaceVariant,
                ),
              ),
            ],
          ],
        ),
      ),
    );
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
        !file.startsWith('https://')) {
      final normalizedFile = _normalizeUploadedMediaPath(file);
      final lower = normalizedFile.toLowerCase();
      final encoded = _encodePathPreservingSlashes(normalizedFile);
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
    return _toAbsoluteUrl(
        '/static/uploads/${_normalizeUploadedMediaPath(file)}');
  }

  String _encodePathPreservingSlashes(String value) {
    return value
        .split('/')
        .where((segment) => segment.trim().isNotEmpty)
        .map(Uri.encodeComponent)
        .join('/');
  }

  String _normalizeUploadedMediaPath(String raw) {
    var path = raw.trim().replaceAll('\\', '/');
    while (path.startsWith('/')) {
      path = path.substring(1);
    }
    for (final prefix in const ['static/uploads/', 'uploads/', 'media/']) {
      if (path.toLowerCase().startsWith(prefix)) {
        return path.substring(prefix.length);
      }
    }
    return path;
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

  Widget _buildCompactMediaThumb(
    Map<String, dynamic>? item, {
    double iconSize = 20,
  }) {
    final itemUrl = _resolvePreviewUrl(item);
    final mediaType = _resolveMediaType(item, itemUrl);
    final file = (item?['file'] ?? '').toString().trim();
    final isYouTube = file.startsWith('youtube:');

    if (mediaType == 'scrolling_text') {
      return _ScrollingTextPreview(
        key: ValueKey('scrolling-text-${item?['id'] ?? item?['file'] ?? ''}'),
        text: (item?['text'] ?? 'Your scrolling message').toString(),
        fontSize: iconSize < 12 ? 12 : (iconSize > 18 ? 18 : iconSize),
      );
    }

    if (mediaType == 'image' && itemUrl.isNotEmpty) {
      return Image.network(
        itemUrl,
        headers: _previewHeaders,
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) => Icon(
          Icons.broken_image_outlined,
          size: iconSize,
        ),
      );
    }

    if (mediaType == 'video' && itemUrl.isNotEmpty) {
      if (isYouTube) {
        return Stack(
          fit: StackFit.expand,
          children: [
            Image.network(
              itemUrl,
              headers: _previewHeaders,
              fit: BoxFit.cover,
              errorBuilder: (_, __, ___) => Icon(
                Icons.broken_image_outlined,
                size: iconSize,
              ),
            ),
            Container(color: Colors.black26),
            Center(
              child: Icon(
                Icons.play_circle_fill,
                size: iconSize + 8,
                color: Colors.white70,
              ),
            ),
          ],
        );
      }

      return _VideoPreview(
        key: ValueKey('compact-$itemUrl'),
        url: itemUrl,
        headers: _previewHeaders,
        compact: true,
      );
    }

    return Icon(
      mediaType == 'video'
          ? Icons.movie_outlined
          : mediaType == 'image'
              ? Icons.image_outlined
              : Icons.perm_media_outlined,
      size: iconSize,
    );
  }

  @override
  void initState() {
    super.initState();
    _headerAnim = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 220),
      value: 1,
    );
    _screenAddress = widget.screenAddress;
    _screenProtected = widget.screenProtected;
    _screenVertical = widget.screenVertical;
    _screenHorizontal = widget.screenHorizontal;
    _screenPanelZone = _normalizedPanelZone(widget.screenPanelZone);
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
    _headerAnim.dispose();
    super.dispose();
  }

  bool _onHeaderScroll(ScrollNotification notification) {
    if (notification.metrics.axis != Axis.vertical) {
      return false;
    }
    // Always show the header when the list is at (or near) the top.
    if (notification.metrics.pixels <=
        notification.metrics.minScrollExtent + 4) {
      _headerAnim.forward();
      return false;
    }
    if (notification is UserScrollNotification) {
      switch (notification.direction) {
        case ScrollDirection.reverse:
          _headerAnim.reverse(); // scrolling down -> hide header
          break;
        case ScrollDirection.forward:
          _headerAnim.forward(); // scrolling up -> reveal header
          break;
        case ScrollDirection.idle:
          break;
      }
    }
    return false;
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
      final screens = await widget.apiClient.getScreens(widget.storeId);
      ScreenItem? matchingScreen;
      for (final screen in screens) {
        if (screen.id == widget.screenId) {
          matchingScreen = screen;
          break;
        }
      }
      if (!mounted) {
        return;
      }
      setState(() {
        _playlist = playlist;
        if (matchingScreen != null) {
          _screenRotation = matchingScreen.rotation;
          _screenMuted = matchingScreen.muted;
          _screenAddress = matchingScreen.address;
          _screenProtected = matchingScreen.protected;
          _screenVertical = matchingScreen.vertical;
          _screenHorizontal = matchingScreen.horizontal;
          _screenPanelZone = _normalizedPanelZone(matchingScreen.panelZone);
        }
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
      String? masterStoreId;
      try {
        masterStoreId = await widget.apiClient.getMasterStoreId();
      } catch (_) {
        masterStoreId = null;
      }
      int rotation = _screenRotation;
      bool muted = _screenMuted;
      String address = _screenAddress;
      bool protected = _screenProtected;
      bool vertical = _screenVertical;
      bool horizontal = _screenHorizontal;
      Map<String, dynamic> panelZone = _screenPanelZone;
      for (final screen in screens) {
        if (screen.id == widget.screenId) {
          rotation = screen.rotation;
          muted = screen.muted;
          address = screen.address;
          protected = screen.protected;
          vertical = screen.vertical;
          horizontal = screen.horizontal;
          panelZone = _normalizedPanelZone(screen.panelZone);
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
        _screenAddress = address;
        _screenProtected = protected;
        _screenVertical = vertical;
        _screenHorizontal = horizontal;
        _screenPanelZone = panelZone;
        _isMasterStore =
            masterStoreId != null && masterStoreId == widget.storeId;
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
    final mediaType = (item['media_type'] ?? '').toString().toLowerCase();
    if (mediaType == 'scrolling_text') {
      final text = (item['text'] ?? '').toString().trim();
      if (text.isNotEmpty) {
        return 'Scrolling text: ${text.length > 44 ? '${text.substring(0, 41)}...' : text}';
      }
      return 'Scrolling text';
    }
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
                    return ListTile(
                      selected: itemId == _selectedItemId,
                      leading: Container(
                        width: 52,
                        height: 34,
                        clipBehavior: Clip.antiAlias,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(6),
                          color: Theme.of(context)
                              .colorScheme
                              .surfaceContainerHighest,
                        ),
                        child: _buildCompactMediaThumb(
                          item,
                          iconSize: 16,
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
    urlController.dispose();
    durationController.dispose();

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

  Future<void> _quickAddScrollingText() async {
    final submitted = await showModalBottomSheet<Map<String, String>>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) => const _ScrollingTextInputDialog(),
    );
    if (submitted == null) return;

    final text = (submitted['text'] ?? '').trim();
    final duration =
        (int.tryParse((submitted['duration'] ?? '').trim()) ?? 15)
            .clamp(5, 3600);
    final fontSize = (int.tryParse((submitted['font_size'] ?? '').trim()) ?? 56).clamp(16, 180);
    final scrollSpeed = (int.tryParse((submitted['scroll_speed'] ?? '').trim()) ?? duration).clamp(3, 120);
    if (text.isEmpty) {
      _showSheetMessage('Enter the message to display.');
      return;
    }

    setState(() => _quickActionBusy = true);
    try {
      await widget.apiClient.addScrollingTextToPlaylist(
        storeId: widget.storeId,
        screenId: widget.screenId,
        text: text,
        duration: duration,
        fontSize: fontSize,
        scrollSpeed: scrollSpeed,
        textColor: submitted['text_color'] ?? '#FFFFFF',
        backgroundColor: submitted['background_color'] ?? '#071B1C',
        imageUrl: submitted['image_url'] ?? '',
        icon: submitted['icon'] ?? '',
        loop: submitted['loop'] != 'false',
      );
      _showSheetMessage('Scrolling text added to the schedule.');
      await _loadPlaylist();
    } catch (e) {
      _showSheetMessage(e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _quickActionBusy = false);
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
    int? createdIndex;
    try {
      final created = await widget.apiClient.addScheduleWindow(
        storeId: widget.storeId,
        screenId: widget.screenId,
        itemId: itemId,
        start: null,
        end: null,
        days: const <String>[],
        enabled: true,
      );
      createdIndex = int.tryParse('${created['index'] ?? ''}');

      if (!mounted) {
        return;
      }
      setState(() {
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

    if (!mounted || createdIndex == null) {
      return;
    }
    final windows = _scheduleWindows();
    if (createdIndex >= 0 && createdIndex < windows.length) {
      await _editScheduleWindow(createdIndex, windows[createdIndex]);
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

  Future<void> _applyReplacementFile(File file) async {
    setState(() {
      _saving = true;
      _message = null;
    });

    try {
      final filename = await widget.apiClient.uploadMedia(file);
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

  Future<void> _applyReplacementFilename(String filename) async {
    final cleanFilename = filename.trim();
    if (cleanFilename.isEmpty) {
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
          file: cleanFilename,
        );
      } else {
        await widget.apiClient.assignToScreen(
          storeId: widget.storeId,
          screenId: widget.screenId,
          filename: cleanFilename,
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

  Future<File?> _pickReplacementFile({bool preferDrive = false}) async {
    final result = await FilePicker.platform.pickFiles(
      dialogTitle: preferDrive ? 'Choose from Google Drive' : null,
      type: FileType.custom,
      allowedExtensions: const [
        'jpg',
        'jpeg',
        'png',
        'webp',
        'gif',
        'bmp',
        'mp4',
        'mov',
        'm4v',
        'webm',
        'mkv',
        'avi',
      ],
      withData: false,
    );
    if (result == null || result.files.isEmpty) {
      return null;
    }
    final path = result.files.single.path;
    if (path == null || path.trim().isEmpty) {
      setState(() {
        _message = preferDrive
            ? 'Android did not return a readable Drive file. Download it locally from Drive and try again.'
            : 'Android did not return a readable file. Try choosing a downloaded copy.';
      });
      return null;
    }
    return File(path);
  }

  Future<void> _replaceMedia() async {
    if (_pickedFile == null) {
      setState(() {
        _message = 'Choose an image or video first.';
      });
      return;
    }
    await _applyReplacementFile(_pickedFile!);
  }

  Future<void> _quickReplaceFromDevice({bool preferDrive = false}) async {
    if (_saving) {
      return;
    }
    final file = await _pickReplacementFile(preferDrive: preferDrive);
    if (file == null || !mounted) {
      return;
    }
    await _applyReplacementFile(file);
  }

  Future<void> _quickReplaceYouTube() async {
    if (_saving) {
      return;
    }
    final currentFile = (_currentItem?['file'] ?? '').toString().trim();
    final initialValue = currentFile.toLowerCase().startsWith('youtube:')
        ? currentFile.substring('youtube:'.length).trim()
        : '';
    final submittedValue = await showDialog<String>(
      context: context,
      builder: (popupContext) {
        return _YouTubeInputDialog(initialValue: initialValue);
      },
    );
    if (submittedValue == null || submittedValue.trim().isEmpty || !mounted) {
      return;
    }
    final parsed = _extractYouTubeId(submittedValue.trim());
    if (parsed == null || parsed.trim().length != 11) {
      setState(() {
        _message = 'Enter a valid YouTube URL or video ID.';
      });
      return;
    }
    await _applyReplacementFilename('youtube:${parsed.trim()}');
  }

  Future<void> _openQuickReplaceMedia() async {
    if (_saving) {
      return;
    }
    final choice = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) {
        return SafeArea(
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 4, 20, 8),
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      'Replace media',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                    ),
                  ),
                ),
                ListTile(
                  leading: const Icon(Icons.folder_open),
                  title: const Text('Choose from device'),
                  subtitle:
                      const Text('Pick an image or video from this phone'),
                  onTap: () => Navigator.of(sheetContext).pop('device'),
                ),
                ListTile(
                  leading: const Icon(Icons.add_to_drive),
                  title: const Text('Google Drive'),
                  subtitle: const Text(
                      'If Recent opens, use the menu to choose Drive'),
                  onTap: () => Navigator.of(sheetContext).pop('drive'),
                ),
                ListTile(
                  leading: const Icon(Icons.collections),
                  title: const Text('Server library'),
                  subtitle: const Text('Use media already uploaded here'),
                  onTap: () => Navigator.of(sheetContext).pop('library'),
                ),
                const Divider(height: 8),
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 8, 20, 4),
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      'Apps',
                      style: Theme.of(context).textTheme.labelLarge?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                    ),
                  ),
                ),
                ListTile(
                  leading: const Icon(Icons.smart_display_rounded),
                  title: const Text('YouTube'),
                  subtitle:
                      const Text('Replace with a YouTube URL or video ID'),
                  onTap: () => Navigator.of(sheetContext).pop('youtube'),
                ),
                ListTile(
                  enabled: false,
                  leading: const Icon(Icons.apps_rounded),
                  title: const Text('Other apps'),
                  subtitle: const Text('More app sources coming soon'),
                ),
                const SizedBox(height: 8),
              ],
            ),
          ),
        );
      },
    );
    if (choice == null || !mounted) {
      return;
    }
    if (choice == 'library') {
      await _replaceFromLibrary();
    } else if (choice == 'drive') {
      await _quickReplaceFromDevice(preferDrive: true);
    } else if (choice == 'device') {
      await _quickReplaceFromDevice();
    } else if (choice == 'youtube') {
      await _quickReplaceYouTube();
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
    final youtubeController = TextEditingController();

    File? selectedUpload;
    String? selectedUploadSource;
    String? selectedLibraryFile;
    String? selectedYouTubeId;
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
            String selectedMediaSummary() {
              if (selectedUpload != null) {
                final source = (selectedUploadSource ?? 'upload').trim();
                return 'Selected $source: ${selectedUpload!.uri.pathSegments.last}';
              }
              if (selectedLibraryFile != null) {
                return 'Selected library: ${selectedLibraryFile!}';
              }
              if ((selectedYouTubeId ?? '').isNotEmpty) {
                return 'Selected YouTube: $selectedYouTubeId';
              }
              return 'No media selected yet';
            }

            IconData selectedMediaIcon() {
              if (selectedUpload != null) {
                if ((selectedUploadSource ?? '').toLowerCase() ==
                    'google drive') {
                  return Icons.add_to_drive;
                }
                return Icons.upload_file_rounded;
              }
              if (selectedLibraryFile != null) {
                return Icons.photo_library_rounded;
              }
              if ((selectedYouTubeId ?? '').isNotEmpty) {
                return Icons.smart_display_rounded;
              }
              return Icons.perm_media_rounded;
            }

            final theme = Theme.of(context);

            String selectedAppLabel() {
              if ((selectedYouTubeId ?? '').isNotEmpty) {
                return 'YouTube';
              }
              return 'App';
            }

            IconData selectedAppIcon() {
              if ((selectedYouTubeId ?? '').isNotEmpty) {
                return Icons.smart_display_rounded;
              }
              return Icons.apps_rounded;
            }

            Future<void> pickGoogleDriveMedia(
              void Function(void Function()) setModalState,
            ) async {
              final pick = await FilePicker.platform.pickFiles(
                dialogTitle: 'Choose from Google Drive',
                type: FileType.custom,
                allowedExtensions: const [
                  'jpg',
                  'jpeg',
                  'png',
                  'webp',
                  'gif',
                  'bmp',
                  'mp4',
                  'mov',
                  'm4v',
                  'webm',
                  'mkv',
                  'avi',
                ],
                withData: false,
              );
              if (pick == null || pick.files.isEmpty) {
                setModalState(() {
                  localError =
                      'No Drive file selected. If Google Drive is not listed, install the Google Drive app, sign in, or download the file and choose it from Downloads.';
                });
                return;
              }
              final path = pick.files.first.path;
              if (path == null || path.trim().isEmpty) {
                setModalState(() {
                  localError =
                      'Android did not return a readable Drive file. Download it locally from Drive and try again.';
                });
                return;
              }
              setModalState(() {
                selectedUpload = File(path);
                selectedUploadSource = 'Google Drive';
                selectedLibraryFile = null;
                selectedYouTubeId = null;
                youtubeController.clear();
                localError = null;
              });
            }

            Future<void> openAppPicker() async {
              final pickedApp = await showModalBottomSheet<String>(
                context: context,
                showDragHandle: true,
                builder: (sheetContext) {
                  Widget appTile({
                    required String id,
                    required String label,
                    required String subtitle,
                    required IconData icon,
                    required Color brandColor,
                    required bool enabled,
                  }) {
                    return ListTile(
                      enabled: enabled,
                      leading: Container(
                        width: 42,
                        height: 42,
                        decoration: BoxDecoration(
                          color: enabled
                              ? brandColor.withAlpha(30)
                              : theme.colorScheme.surfaceContainerHighest,
                          borderRadius: BorderRadius.circular(11),
                        ),
                        child: Icon(
                          icon,
                          size: 22,
                          color: enabled
                              ? brandColor
                              : theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                      title: Text(label),
                      subtitle: Text(subtitle),
                      trailing: enabled
                          ? null
                          : Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 9, vertical: 4),
                              decoration: BoxDecoration(
                                color:
                                    theme.colorScheme.surfaceContainerHighest,
                                borderRadius: BorderRadius.circular(20),
                              ),
                              child: Text(
                                'Soon',
                                style: theme.textTheme.labelSmall?.copyWith(
                                  fontWeight: FontWeight.w600,
                                  color: theme.colorScheme.onSurfaceVariant,
                                ),
                              ),
                            ),
                      onTap: enabled
                          ? () => Navigator.of(sheetContext).pop(id)
                          : null,
                    );
                  }

                  return SafeArea(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Padding(
                          padding: const EdgeInsets.fromLTRB(20, 4, 20, 8),
                          child: Align(
                            alignment: Alignment.centerLeft,
                            child: Text(
                              'Choose an app',
                              style: theme.textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                        ),
                        appTile(
                          id: 'youtube',
                          label: 'YouTube',
                          subtitle: 'Use a video link or ID',
                          icon: Icons.smart_display_rounded,
                          brandColor: const Color(0xFFFF0000),
                          enabled: true,
                        ),
                        appTile(
                          id: 'gdrive',
                          label: 'Google Drive',
                          subtitle:
                              'Opens Android Files. If Drive is missing, install/sign in.',
                          icon: Icons.add_to_drive,
                          brandColor: const Color(0xFF1FA463),
                          enabled: true,
                        ),
                        appTile(
                          id: 'dropbox',
                          label: 'Dropbox',
                          subtitle: 'Play media from Dropbox',
                          icon: Icons.cloud_rounded,
                          brandColor: const Color(0xFF0061FF),
                          enabled: false,
                        ),
                        appTile(
                          id: 'onedrive',
                          label: 'OneDrive',
                          subtitle: 'Play media from OneDrive',
                          icon: Icons.cloud_queue_rounded,
                          brandColor: const Color(0xFF0078D4),
                          enabled: false,
                        ),
                        if ((selectedYouTubeId ?? '').isNotEmpty)
                          ListTile(
                            leading: const Icon(Icons.clear_rounded),
                            title: const Text('Clear app source'),
                            onTap: () =>
                                Navigator.of(sheetContext).pop('clear'),
                          ),
                        const SizedBox(height: 8),
                      ],
                    ),
                  );
                },
              );
              if (pickedApp == null) {
                return;
              }
              if (pickedApp == 'clear') {
                setModalState(() {
                  selectedYouTubeId = null;
                  youtubeController.clear();
                  localError = null;
                });
                return;
              }
              if (pickedApp == 'gdrive') {
                await pickGoogleDriveMedia(setModalState);
                return;
              }
              if (pickedApp != 'youtube') {
                return;
              }
              if (!dialogContext.mounted) {
                return;
              }
              // Let the bottom sheet finish its dismiss animation before
              // opening the input dialog. Showing an autofocus field while the
              // sheet route is still deactivating triggers a framework
              // assertion (_dependents.isEmpty) and a red screen.
              await Future<void>.delayed(const Duration(milliseconds: 250));
              if (!dialogContext.mounted) {
                return;
              }

              final submittedValue = await showDialog<String>(
                context: dialogContext,
                builder: (popupContext) {
                  return _YouTubeInputDialog(
                    initialValue: youtubeController.text.trim().isNotEmpty
                        ? youtubeController.text.trim()
                        : (selectedYouTubeId ?? ''),
                  );
                },
              );
              if (submittedValue == null || submittedValue.trim().isEmpty) {
                return;
              }

              final parsed = _extractYouTubeId(submittedValue.trim());
              if (parsed == null || parsed.trim().length != 11) {
                setModalState(() {
                  localError = 'Enter a valid YouTube URL or video ID.';
                });
                return;
              }

              setModalState(() {
                selectedYouTubeId = parsed.trim();
                youtubeController.text = submittedValue.trim();
                selectedUpload = null;
                selectedUploadSource = null;
                selectedLibraryFile = null;
                localError = null;
              });
            }

            Widget compactToggle({
              required String label,
              required bool value,
              required ValueChanged<bool>? onChanged,
            }) {
              return Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: theme.textTheme.labelMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 6),
                  SizedBox(
                    height: 40,
                    child: Align(
                      alignment: Alignment.centerLeft,
                      child: GestureDetector(
                        onTap:
                            onChanged == null ? null : () => onChanged(!value),
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 160),
                          width: 46,
                          height: 26,
                          padding: const EdgeInsets.all(3),
                          decoration: BoxDecoration(
                            color: value
                                ? theme.colorScheme.primary
                                : theme.colorScheme.surfaceContainerHighest,
                            borderRadius: BorderRadius.circular(999),
                          ),
                          child: AnimatedAlign(
                            duration: const Duration(milliseconds: 160),
                            alignment: value
                                ? Alignment.centerRight
                                : Alignment.centerLeft,
                            child: Container(
                              width: 20,
                              height: 20,
                              decoration: BoxDecoration(
                                color: theme.colorScheme.surface,
                                shape: BoxShape.circle,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              );
            }

            Widget compactDurationField() {
              void adjustDuration(int delta) {
                final current =
                    int.tryParse(durationController.text.trim()) ?? 10;
                final next = (current + delta).clamp(1, 3600);
                durationController.text = next.toString();
                setModalState(() {});
              }

              Widget stepButton(IconData icon, VoidCallback onTap) {
                return InkResponse(
                  onTap: creating ? null : onTap,
                  radius: 22,
                  child: SizedBox(
                    width: 30,
                    height: 40,
                    child: Icon(
                      icon,
                      size: 22,
                      color: creating
                          ? theme.colorScheme.outline
                          : theme.colorScheme.primary,
                    ),
                  ),
                );
              }

              return Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Duration (s)',
                    style: theme.textTheme.labelMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Container(
                    height: 40,
                    padding: const EdgeInsets.symmetric(horizontal: 2),
                    decoration: BoxDecoration(
                      color: theme.colorScheme.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      children: [
                        stepButton(
                            Icons.remove_rounded, () => adjustDuration(-1)),
                        Expanded(
                          child: TextField(
                            controller: durationController,
                            keyboardType: TextInputType.number,
                            textAlign: TextAlign.center,
                            decoration: const InputDecoration(
                              isCollapsed: true,
                              border: InputBorder.none,
                              hintText: '10',
                            ),
                            style: theme.textTheme.titleSmall?.copyWith(
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                        stepButton(Icons.add_rounded, () => adjustDuration(1)),
                      ],
                    ),
                  ),
                ],
              );
            }

            bool isImageMedia(String path) {
              final p = path.toLowerCase();
              return p.endsWith('.png') ||
                  p.endsWith('.jpg') ||
                  p.endsWith('.jpeg') ||
                  p.endsWith('.gif') ||
                  p.endsWith('.webp') ||
                  p.endsWith('.bmp');
            }

            Future<void> pickUploadMedia() async {
              final pick = await FilePicker.platform.pickFiles(
                type: FileType.custom,
                allowedExtensions: const [
                  'jpg',
                  'jpeg',
                  'png',
                  'webp',
                  'gif',
                  'bmp',
                  'mp4',
                  'mov',
                  'm4v',
                  'webm',
                  'mkv',
                  'avi',
                ],
                withData: false,
              );
              if (pick == null ||
                  pick.files.isEmpty ||
                  pick.files.first.path == null) {
                return;
              }
              setModalState(() {
                selectedUpload = File(pick.files.first.path!);
                selectedUploadSource = null;
                selectedLibraryFile = null;
                selectedYouTubeId = null;
                youtubeController.clear();
                localError = null;
              });
            }

            Future<void> pickGalleryMedia() async {
              final selected = await showModalBottomSheet<String>(
                context: context,
                isScrollControlled: true,
                builder: (context) => FractionallySizedBox(
                  heightFactor: 0.88,
                  child: _LibraryPickerSheet(
                    apiClient: widget.apiClient,
                  ),
                ),
              );
              if (selected == null || selected.trim().isEmpty) {
                return;
              }
              setModalState(() {
                selectedLibraryFile = selected;
                selectedUpload = null;
                selectedUploadSource = null;
                selectedYouTubeId = null;
                youtubeController.clear();
                localError = null;
              });
            }

            Future<void> chooseMedia() async {
              final choice = await showModalBottomSheet<String>(
                context: context,
                builder: (sheetContext) => SafeArea(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      ListTile(
                        leading: const Icon(Icons.upload_file_rounded),
                        title: const Text('Upload'),
                        subtitle: const Text(
                            'Pick an image or video from this device'),
                        onTap: () => Navigator.of(sheetContext).pop('upload'),
                      ),
                      ListTile(
                        leading: const Icon(Icons.add_to_drive),
                        title: const Text('Google Drive'),
                        subtitle: const Text(
                            'If Recent opens, use the menu to choose Drive. If Drive is missing, install/sign in first.'),
                        onTap: () => Navigator.of(sheetContext).pop('gdrive'),
                      ),
                      ListTile(
                        leading: const Icon(Icons.photo_library_rounded),
                        title: const Text('Gallery'),
                        subtitle: const Text('Choose from your media library'),
                        onTap: () => Navigator.of(sheetContext).pop('gallery'),
                      ),
                    ],
                  ),
                ),
              );
              if (choice == 'upload') {
                await pickUploadMedia();
              } else if (choice == 'gdrive') {
                await pickGoogleDriveMedia(setModalState);
              } else if (choice == 'gallery') {
                await pickGalleryMedia();
              }
            }

            return Dialog.fullscreen(
              child: SafeArea(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'Add Scheduled Media',
                                  style:
                                      theme.textTheme.headlineSmall?.copyWith(
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(width: 8),
                          IconButton(
                            tooltip: 'Close',
                            onPressed: creating
                                ? null
                                : () => Navigator.of(dialogContext).pop(false),
                            icon: const Icon(Icons.close),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Expanded(
                        child: SingleChildScrollView(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Container(
                                padding: (selectedUpload != null ||
                                        selectedLibraryFile != null ||
                                        (selectedYouTubeId ?? '').isNotEmpty)
                                    ? EdgeInsets.zero
                                    : const EdgeInsets.all(14),
                                decoration: BoxDecoration(
                                  color: (selectedUpload != null ||
                                          selectedLibraryFile != null ||
                                          (selectedYouTubeId ?? '').isNotEmpty)
                                      ? theme.colorScheme.primary.withAlpha(18)
                                      : theme.colorScheme.surfaceContainerLow,
                                  borderRadius: BorderRadius.circular(20),
                                ),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Builder(
                                      builder: (context) {
                                        Widget fallback() => Column(
                                              mainAxisAlignment:
                                                  MainAxisAlignment.center,
                                              children: [
                                                Icon(
                                                  selectedMediaIcon(),
                                                  size: 40,
                                                  color:
                                                      theme.colorScheme.primary,
                                                ),
                                                const SizedBox(height: 8),
                                                Padding(
                                                  padding: const EdgeInsets
                                                      .symmetric(
                                                      horizontal: 16),
                                                  child: Text(
                                                    selectedMediaSummary(),
                                                    maxLines: 2,
                                                    textAlign: TextAlign.center,
                                                    overflow:
                                                        TextOverflow.ellipsis,
                                                    style: theme
                                                        .textTheme.bodySmall
                                                        ?.copyWith(
                                                      color: theme.colorScheme
                                                          .onSurfaceVariant,
                                                    ),
                                                  ),
                                                ),
                                              ],
                                            );

                                        final hasMedia =
                                            selectedUpload != null ||
                                                selectedLibraryFile != null ||
                                                (selectedYouTubeId ?? '')
                                                    .isNotEmpty;

                                        if (!hasMedia) {
                                          return Material(
                                            color: Colors.transparent,
                                            child: InkWell(
                                              onTap:
                                                  creating ? null : chooseMedia,
                                              borderRadius:
                                                  BorderRadius.circular(16),
                                              child: Container(
                                                width: double.infinity,
                                                height: 150,
                                                decoration: BoxDecoration(
                                                  color: theme.colorScheme
                                                      .surfaceContainerHighest,
                                                  borderRadius:
                                                      BorderRadius.circular(16),
                                                ),
                                                child: Column(
                                                  mainAxisAlignment:
                                                      MainAxisAlignment.center,
                                                  children: [
                                                    Container(
                                                      width: 52,
                                                      height: 52,
                                                      decoration: BoxDecoration(
                                                        color: theme
                                                            .colorScheme.primary
                                                            .withAlpha(20),
                                                        shape: BoxShape.circle,
                                                      ),
                                                      child: Icon(
                                                        Icons
                                                            .add_photo_alternate_rounded,
                                                        size: 26,
                                                        color: theme.colorScheme
                                                            .primary,
                                                      ),
                                                    ),
                                                    const SizedBox(height: 10),
                                                    Text(
                                                      'Upload or Gallery',
                                                      style: theme
                                                          .textTheme.titleSmall
                                                          ?.copyWith(
                                                        fontWeight:
                                                            FontWeight.w700,
                                                      ),
                                                    ),
                                                    const SizedBox(height: 2),
                                                    Text(
                                                      'Tap to choose an image or video',
                                                      style: theme
                                                          .textTheme.bodySmall
                                                          ?.copyWith(
                                                        color: theme.colorScheme
                                                            .onSurfaceVariant,
                                                      ),
                                                    ),
                                                  ],
                                                ),
                                              ),
                                            ),
                                          );
                                        }

                                        Widget preview;
                                        if (selectedUpload != null &&
                                            isImageMedia(
                                                selectedUpload!.path)) {
                                          preview = Image.file(
                                            selectedUpload!,
                                            width: double.infinity,
                                            height: double.infinity,
                                            fit: BoxFit.cover,
                                          );
                                        } else if (selectedLibraryFile !=
                                            null) {
                                          final base = widget.apiClient.baseUrl
                                              .replaceAll(RegExp(r'/$'), '');
                                          var rel = selectedLibraryFile!
                                              .trim()
                                              .replaceAll('\\', '/');
                                          while (rel.startsWith('/')) {
                                            rel = rel.substring(1);
                                          }
                                          for (final prefix in const [
                                            'static/uploads/',
                                            'uploads/',
                                            'media/'
                                          ]) {
                                            if (rel
                                                .toLowerCase()
                                                .startsWith(prefix)) {
                                              rel =
                                                  rel.substring(prefix.length);
                                              break;
                                            }
                                          }
                                          final encoded = rel
                                              .split('/')
                                              .where((s) => s.trim().isNotEmpty)
                                              .map(Uri.encodeComponent)
                                              .join('/');
                                          final lower = rel.toLowerCase();
                                          final isVideo =
                                              lower.contains('.mp4') ||
                                                  lower.contains('.mov') ||
                                                  lower.contains('.webm') ||
                                                  lower.contains('.mkv') ||
                                                  lower.contains('.m3u8');
                                          final thumbUrl =
                                              '$base/${isVideo ? 'vthumb' : 'thumb'}/320/$encoded';
                                          preview = Image.network(
                                            thumbUrl,
                                            width: double.infinity,
                                            height: double.infinity,
                                            fit: BoxFit.cover,
                                            errorBuilder:
                                                (context, error, stack) =>
                                                    fallback(),
                                          );
                                        } else if ((selectedYouTubeId ?? '')
                                            .isNotEmpty) {
                                          final ytId = selectedYouTubeId!;
                                          preview = Stack(
                                            fit: StackFit.expand,
                                            children: [
                                              Image.network(
                                                'https://img.youtube.com/vi/$ytId/hqdefault.jpg',
                                                width: double.infinity,
                                                height: double.infinity,
                                                fit: BoxFit.cover,
                                                errorBuilder:
                                                    (context, error, stack) =>
                                                        fallback(),
                                              ),
                                              Center(
                                                child: Container(
                                                  width: 54,
                                                  height: 54,
                                                  decoration: BoxDecoration(
                                                    color:
                                                        const Color(0xFFFF0000),
                                                    borderRadius:
                                                        BorderRadius.circular(
                                                            12),
                                                  ),
                                                  child: const Icon(
                                                    Icons.play_arrow_rounded,
                                                    color: Colors.white,
                                                    size: 34,
                                                  ),
                                                ),
                                              ),
                                            ],
                                          );
                                        } else {
                                          preview = fallback();
                                        }

                                        return ClipRRect(
                                          borderRadius:
                                              BorderRadius.circular(20),
                                          child: Stack(
                                            children: [
                                              AspectRatio(
                                                aspectRatio: 16 / 9,
                                                child: Container(
                                                  width: double.infinity,
                                                  color: theme.colorScheme
                                                      .surfaceContainerHighest,
                                                  child: preview,
                                                ),
                                              ),
                                              Positioned(
                                                top: 8,
                                                right: 8,
                                                child: Material(
                                                  color: Colors.black
                                                      .withAlpha(140),
                                                  borderRadius:
                                                      BorderRadius.circular(20),
                                                  child: InkWell(
                                                    borderRadius:
                                                        BorderRadius.circular(
                                                            20),
                                                    onTap: creating
                                                        ? null
                                                        : chooseMedia,
                                                    child: const Padding(
                                                      padding:
                                                          EdgeInsets.symmetric(
                                                        horizontal: 12,
                                                        vertical: 7,
                                                      ),
                                                      child: Row(
                                                        mainAxisSize:
                                                            MainAxisSize.min,
                                                        children: [
                                                          Icon(
                                                            Icons.edit_rounded,
                                                            size: 16,
                                                            color: Colors.white,
                                                          ),
                                                          SizedBox(width: 6),
                                                          Text(
                                                            'Change',
                                                            style: TextStyle(
                                                              color:
                                                                  Colors.white,
                                                              fontSize: 13,
                                                              fontWeight:
                                                                  FontWeight
                                                                      .w600,
                                                            ),
                                                          ),
                                                        ],
                                                      ),
                                                    ),
                                                  ),
                                                ),
                                              ),
                                            ],
                                          ),
                                        );
                                      },
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(height: 12),
                              Container(
                                padding: const EdgeInsets.all(14),
                                decoration: BoxDecoration(
                                  color: theme.colorScheme.surfaceContainerLow,
                                  borderRadius: BorderRadius.circular(20),
                                ),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      'Playback',
                                      style:
                                          theme.textTheme.titleSmall?.copyWith(
                                        fontWeight: FontWeight.w700,
                                      ),
                                    ),
                                    const SizedBox(height: 12),
                                    LayoutBuilder(
                                      builder: (context, constraints) {
                                        final hasApp = (selectedYouTubeId ?? '')
                                            .isNotEmpty;
                                        return Row(
                                          crossAxisAlignment:
                                              CrossAxisAlignment.start,
                                          children: [
                                            Expanded(
                                              child: Column(
                                                mainAxisSize: MainAxisSize.min,
                                                crossAxisAlignment:
                                                    CrossAxisAlignment.start,
                                                children: [
                                                  Text(
                                                    'App',
                                                    style: theme
                                                        .textTheme.labelMedium
                                                        ?.copyWith(
                                                      fontWeight:
                                                          FontWeight.w700,
                                                      color: theme.colorScheme
                                                          .onSurfaceVariant,
                                                    ),
                                                  ),
                                                  const SizedBox(height: 6),
                                                  Material(
                                                    color: Colors.transparent,
                                                    child: InkWell(
                                                      onTap: creating
                                                          ? null
                                                          : openAppPicker,
                                                      borderRadius:
                                                          BorderRadius.circular(
                                                              12),
                                                      child: Ink(
                                                        height: 40,
                                                        padding:
                                                            const EdgeInsets
                                                                .symmetric(
                                                          horizontal: 10,
                                                        ),
                                                        decoration:
                                                            BoxDecoration(
                                                          color: hasApp
                                                              ? theme
                                                                  .colorScheme
                                                                  .primary
                                                                  .withAlpha(22)
                                                              : theme
                                                                  .colorScheme
                                                                  .surfaceContainerHighest,
                                                          borderRadius:
                                                              BorderRadius
                                                                  .circular(12),
                                                        ),
                                                        child: Row(
                                                          children: [
                                                            Icon(
                                                              selectedAppIcon(),
                                                              size: 16,
                                                              color: hasApp
                                                                  ? theme
                                                                      .colorScheme
                                                                      .primary
                                                                  : theme
                                                                      .colorScheme
                                                                      .onSurfaceVariant,
                                                            ),
                                                            const SizedBox(
                                                                width: 6),
                                                            Expanded(
                                                              child: Text(
                                                                selectedAppLabel(),
                                                                maxLines: 1,
                                                                overflow:
                                                                    TextOverflow
                                                                        .ellipsis,
                                                                style: theme
                                                                    .textTheme
                                                                    .labelLarge
                                                                    ?.copyWith(
                                                                  fontWeight:
                                                                      FontWeight
                                                                          .w700,
                                                                  fontSize: 13,
                                                                ),
                                                              ),
                                                            ),
                                                            Icon(
                                                              Icons
                                                                  .expand_more_rounded,
                                                              size: 18,
                                                              color: theme
                                                                  .colorScheme
                                                                  .onSurfaceVariant,
                                                            ),
                                                          ],
                                                        ),
                                                      ),
                                                    ),
                                                  ),
                                                ],
                                              ),
                                            ),
                                            const SizedBox(width: 10),
                                            compactToggle(
                                              label: 'Enable',
                                              value: enabled,
                                              onChanged: creating
                                                  ? null
                                                  : (value) =>
                                                      setModalState(() {
                                                        enabled = value;
                                                      }),
                                            ),
                                            const SizedBox(width: 12),
                                            compactToggle(
                                              label: 'Repeat',
                                              value: repeat,
                                              onChanged: creating
                                                  ? null
                                                  : (value) =>
                                                      setModalState(() {
                                                        repeat = value;
                                                      }),
                                            ),
                                            const SizedBox(width: 10),
                                            SizedBox(
                                              width: 116,
                                              child: compactDurationField(),
                                            ),
                                          ],
                                        );
                                      },
                                    ),
                                    const SizedBox(height: 10),
                                    Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          'Effect',
                                          style: theme.textTheme.labelMedium
                                              ?.copyWith(
                                            fontWeight: FontWeight.w700,
                                            color: theme
                                                .colorScheme.onSurfaceVariant,
                                          ),
                                        ),
                                        const SizedBox(height: 6),
                                        Row(
                                          children: List.generate(11, (i) {
                                            final selected = effectId == i;
                                            final isLast = i == 10;
                                            return Expanded(
                                              child: Padding(
                                                padding: EdgeInsets.only(
                                                    right: isLast ? 0 : 4),
                                                child: GestureDetector(
                                                  onTap: creating
                                                      ? null
                                                      : () => setModalState(() {
                                                            effectId = i;
                                                          }),
                                                  child: Container(
                                                    height: 34,
                                                    alignment: Alignment.center,
                                                    decoration: BoxDecoration(
                                                      color: selected
                                                          ? theme.colorScheme
                                                              .primary
                                                          : theme.colorScheme
                                                              .surfaceContainerHighest,
                                                      borderRadius:
                                                          BorderRadius.circular(
                                                              8),
                                                    ),
                                                    child: Text(
                                                      i == 0 ? '·' : '$i',
                                                      style: theme
                                                          .textTheme.labelSmall
                                                          ?.copyWith(
                                                        fontSize: 11,
                                                        fontWeight:
                                                            FontWeight.w700,
                                                        color: selected
                                                            ? theme.colorScheme
                                                                .onPrimary
                                                            : theme.colorScheme
                                                                .onSurfaceVariant,
                                                      ),
                                                    ),
                                                  ),
                                                ),
                                              ),
                                            );
                                          }),
                                        ),
                                      ],
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(height: 12),
                              Container(
                                padding: const EdgeInsets.all(14),
                                decoration: BoxDecoration(
                                  color: theme.colorScheme.surfaceContainerLow,
                                  borderRadius: BorderRadius.circular(20),
                                ),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text('Days',
                                        style: theme.textTheme.titleSmall),
                                    const SizedBox(height: 6),
                                    Row(
                                      children: _weekDays.map((day) {
                                        final selected = days.contains(day);
                                        final isLast = day == _weekDays.last;
                                        return Expanded(
                                          child: Padding(
                                            padding: EdgeInsets.only(
                                                right: isLast ? 0 : 4),
                                            child: GestureDetector(
                                              onTap: creating
                                                  ? null
                                                  : () => setModalState(() {
                                                        if (selected) {
                                                          days.remove(day);
                                                        } else {
                                                          days.add(day);
                                                        }
                                                      }),
                                              child: Container(
                                                height: 36,
                                                alignment: Alignment.center,
                                                decoration: BoxDecoration(
                                                  color: selected
                                                      ? theme
                                                          .colorScheme.primary
                                                      : theme.colorScheme
                                                          .surfaceContainerHighest,
                                                  borderRadius:
                                                      BorderRadius.circular(8),
                                                ),
                                                child: Text(
                                                  day.toUpperCase(),
                                                  style: theme
                                                      .textTheme.labelSmall
                                                      ?.copyWith(
                                                    fontSize: 11,
                                                    fontWeight: FontWeight.w700,
                                                    color: selected
                                                        ? theme.colorScheme
                                                            .onPrimary
                                                        : theme.colorScheme
                                                            .onSurfaceVariant,
                                                  ),
                                                ),
                                              ),
                                            ),
                                          ),
                                        );
                                      }).toList(),
                                    ),
                                    const SizedBox(height: 14),
                                    Text('Start / End',
                                        style: theme.textTheme.titleSmall),
                                    const SizedBox(height: 6),
                                    LayoutBuilder(
                                      builder: (context, constraints) {
                                        final startField = TextField(
                                          controller: startController,
                                          decoration: InputDecoration(
                                            labelText: 'Start',
                                            isDense: true,
                                            contentPadding:
                                                const EdgeInsets.symmetric(
                                                    horizontal: 10,
                                                    vertical: 14),
                                            suffixIcon: Row(
                                              mainAxisSize: MainAxisSize.min,
                                              children: [
                                                IconButton(
                                                  visualDensity:
                                                      VisualDensity.compact,
                                                  constraints:
                                                      const BoxConstraints(),
                                                  padding:
                                                      const EdgeInsets.all(4),
                                                  onPressed: creating
                                                      ? null
                                                      : () => pickDateFor(
                                                            startController,
                                                            setModalState,
                                                          ),
                                                  icon: const Icon(
                                                      Icons.date_range,
                                                      size: 20),
                                                ),
                                                IconButton(
                                                  visualDensity:
                                                      VisualDensity.compact,
                                                  constraints:
                                                      const BoxConstraints(),
                                                  padding:
                                                      const EdgeInsets.all(4),
                                                  onPressed: creating
                                                      ? null
                                                      : () => pickTimeFor(
                                                            startController,
                                                            setModalState,
                                                          ),
                                                  icon: const Icon(
                                                      Icons.access_time,
                                                      size: 20),
                                                ),
                                              ],
                                            ),
                                          ),
                                        );
                                        final endField = TextField(
                                          controller: endController,
                                          decoration: InputDecoration(
                                            labelText: 'End',
                                            isDense: true,
                                            contentPadding:
                                                const EdgeInsets.symmetric(
                                                    horizontal: 10,
                                                    vertical: 14),
                                            suffixIcon: Row(
                                              mainAxisSize: MainAxisSize.min,
                                              children: [
                                                IconButton(
                                                  visualDensity:
                                                      VisualDensity.compact,
                                                  constraints:
                                                      const BoxConstraints(),
                                                  padding:
                                                      const EdgeInsets.all(4),
                                                  onPressed: creating
                                                      ? null
                                                      : () => pickDateFor(
                                                            endController,
                                                            setModalState,
                                                          ),
                                                  icon: const Icon(
                                                      Icons.date_range,
                                                      size: 20),
                                                ),
                                                IconButton(
                                                  visualDensity:
                                                      VisualDensity.compact,
                                                  constraints:
                                                      const BoxConstraints(),
                                                  padding:
                                                      const EdgeInsets.all(4),
                                                  onPressed: creating
                                                      ? null
                                                      : () => pickTimeFor(
                                                            endController,
                                                            setModalState,
                                                          ),
                                                  icon: const Icon(
                                                      Icons.access_time,
                                                      size: 20),
                                                ),
                                              ],
                                            ),
                                          ),
                                        );
                                        return Column(
                                          children: [
                                            startField,
                                            const SizedBox(height: 12),
                                            endField,
                                          ],
                                        );
                                      },
                                    ),
                                  ],
                                ),
                              ),
                              if (localError != null) ...[
                                const SizedBox(height: 12),
                                Text(
                                  localError!,
                                  style: TextStyle(
                                    color: theme.colorScheme.error,
                                  ),
                                ),
                              ],
                              const SizedBox(height: 24),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          TextButton(
                            onPressed: creating
                                ? null
                                : () => Navigator.of(dialogContext).pop(false),
                            child: const Text('Cancel'),
                          ),
                          const Spacer(),
                          FilledButton.icon(
                            onPressed: creating
                                ? null
                                : () async {
                                    final parsedYouTube =
                                        (selectedYouTubeId ?? '').trim();
                                    if (selectedUpload == null &&
                                        (selectedLibraryFile == null ||
                                            selectedLibraryFile!
                                                .trim()
                                                .isEmpty) &&
                                        parsedYouTube.isEmpty) {
                                      setModalState(() {
                                        localError =
                                            'Select media first: upload, library, or YouTube.';
                                      });
                                      return;
                                    }

                                    if (selectedUpload == null &&
                                        (selectedLibraryFile == null ||
                                            selectedLibraryFile!
                                                .trim()
                                                .isEmpty) &&
                                        parsedYouTube.length != 11) {
                                      setModalState(() {
                                        localError =
                                            'Enter a valid YouTube URL or video ID.';
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
                                      } else if (selectedLibraryFile != null &&
                                          selectedLibraryFile!
                                              .trim()
                                              .isNotEmpty) {
                                        filename = selectedLibraryFile!.trim();
                                      } else {
                                        filename = 'youtube:$parsedYouTube';
                                      }

                                      await widget.apiClient.assignToScreen(
                                        storeId: widget.storeId,
                                        screenId: widget.screenId,
                                        filename: filename,
                                      );

                                      final playlist =
                                          await widget.apiClient.getPlaylist(
                                        storeId: widget.storeId,
                                        screenId: widget.screenId,
                                      );

                                      String? createdItemId;
                                      for (int i = playlist.length - 1;
                                          i >= 0;
                                          i--) {
                                        final file = (playlist[i]['file'] ?? '')
                                            .toString()
                                            .trim();
                                        if (file == filename) {
                                          createdItemId =
                                              (playlist[i]['id'] ?? '')
                                                  .toString()
                                                  .trim();
                                          break;
                                        }
                                      }
                                      createdItemId ??= (playlist.isNotEmpty
                                              ? '${playlist.last['id'] ?? ''}'
                                              : '')
                                          .trim();

                                      if (createdItemId.isNotEmpty) {
                                        final parsedDuration = int.tryParse(
                                                durationController.text
                                                    .trim()) ??
                                            10;
                                        await widget.apiClient
                                            .updatePlaylistItem(
                                          storeId: widget.storeId,
                                          screenId: widget.screenId,
                                          itemId: createdItemId,
                                          start: startController.text.trim(),
                                          end: endController.text.trim(),
                                          enabled: enabled,
                                          repeat: repeat,
                                          duration: parsedDuration < 1
                                              ? 1
                                              : parsedDuration,
                                          days: days.toList(),
                                          effectId: effectId,
                                        );
                                      }

                                      if (dialogContext.mounted) {
                                        Navigator.of(dialogContext).pop(true);
                                      }
                                    } catch (e) {
                                      setModalState(() {
                                        localError = e
                                            .toString()
                                            .replaceFirst('Exception: ', '');
                                        creating = false;
                                      });
                                    }
                                  },
                            icon: creating
                                ? const SizedBox(
                                    width: 14,
                                    height: 14,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                    ),
                                  )
                                : const Icon(Icons.add),
                            label: Text(
                                creating ? 'Creating...' : 'Add to Screen'),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        );
      },
    );

    startController.dispose();
    endController.dispose();
    durationController.dispose();
    youtubeController.dispose();

    if (created == true && mounted) {
      setState(() {
        _message = 'Scheduled media added.';
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

  Future<String?> _selectDateValue(String raw) async {
    final now = DateTime.now();
    DateTime initialDate = now;
    final text = raw.trim();
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
      return null;
    }

    final month = picked.month.toString().padLeft(2, '0');
    final day = picked.day.toString().padLeft(2, '0');
    final existingTime = _extractTimePart(text);
    return existingTime == null
        ? '${picked.year}-$month-$day'
        : '${picked.year}-$month-$day $existingTime';
  }

  Future<void> _pickDateFor(TextEditingController controller) async {
    final nextValue = await _selectDateValue(controller.text);
    if (nextValue == null || !mounted) {
      return;
    }
    setState(() {
      controller.text = nextValue;
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

  Future<String?> _selectTimeValue(String raw) async {
    final text = raw.trim();
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
    if (picked == null) {
      return null;
    }

    final hh = picked.hour.toString().padLeft(2, '0');
    final mm = picked.minute.toString().padLeft(2, '0');
    final datePart = _extractDatePart(text);
    return datePart == null ? '$hh:$mm:00' : '$datePart $hh:$mm:00';
  }

  Future<void> _pickTimeFor(TextEditingController controller) async {
    final nextValue = await _selectTimeValue(controller.text);
    if (nextValue == null || !mounted) {
      return;
    }
    setState(() {
      controller.text = nextValue;
    });
    _queueAutoSave();
  }

  Widget _buildInfoBadge({
    required IconData icon,
    required String label,
    Color? background,
    Color? foreground,
  }) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final chipBackground = background ?? scheme.surfaceContainerHigh;
    final chipForeground = foreground ?? scheme.onSurfaceVariant;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: chipBackground,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: chipForeground),
          const SizedBox(width: 6),
          Text(
            label,
            style: theme.textTheme.labelMedium?.copyWith(
              color: chipForeground,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPillToggle({
    required String label,
    required bool value,
    required ValueChanged<bool>? onChanged,
  }) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: theme.textTheme.labelMedium?.copyWith(
            fontWeight: FontWeight.w700,
            color: scheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 6),
        SizedBox(
          height: 40,
          child: Align(
            alignment: Alignment.centerLeft,
            child: GestureDetector(
              onTap: onChanged == null ? null : () => onChanged(!value),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 160),
                width: 46,
                height: 26,
                padding: const EdgeInsets.all(3),
                decoration: BoxDecoration(
                  color:
                      value ? scheme.primary : scheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(999),
                ),
                child: AnimatedAlign(
                  duration: const Duration(milliseconds: 160),
                  alignment:
                      value ? Alignment.centerRight : Alignment.centerLeft,
                  child: Container(
                    width: 20,
                    height: 20,
                    decoration: BoxDecoration(
                      color: scheme.surface,
                      shape: BoxShape.circle,
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildPillDurationField() {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    void adjust(int delta) {
      setState(() {
        _itemDuration = (_itemDuration + delta).clamp(1, 3600);
      });
      _queueAutoSave();
    }

    Widget stepButton(IconData icon, VoidCallback? onTap) {
      return InkResponse(
        onTap: onTap,
        radius: 22,
        child: SizedBox(
          width: 30,
          height: 40,
          child: Icon(
            icon,
            size: 22,
            color: onTap == null ? scheme.outline : scheme.primary,
          ),
        ),
      );
    }

    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Duration (s)',
          style: theme.textTheme.labelMedium?.copyWith(
            fontWeight: FontWeight.w700,
            color: scheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 6),
        Container(
          height: 40,
          padding: const EdgeInsets.symmetric(horizontal: 2),
          decoration: BoxDecoration(
            color: scheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Row(
            children: [
              stepButton(
                  Icons.remove_rounded, _saving ? null : () => adjust(-1)),
              Expanded(
                child: Text(
                  '$_itemDuration',
                  textAlign: TextAlign.center,
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              stepButton(Icons.add_rounded, _saving ? null : () => adjust(1)),
            ],
          ),
        ),
      ],
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
    final lowerStatus = widget.screenStatus.toLowerCase();
    final isOnline = lowerStatus == 'online';
    final addressLabel = _screenAddress.trim().isEmpty
        ? 'Screen or store address'
        : 'Saved screen address';
    final currentItemLabel = _itemLabel(item ?? const {});
    final currentDuration = item == null
        ? null
        : int.tryParse('${item['duration'] ?? _itemDuration}') ?? _itemDuration;
    final currentRunning = item != null && _looksRunning(item);
    final playlistModeLabel =
        _isMasterStore ? 'Playlist (Master Override Enabled)' : 'Playlist';

    return SafeArea(
      child: NotificationListener<ScrollNotification>(
        onNotification: _onHeaderScroll,
        child: Column(
          children: [
            SizeTransition(
              axisAlignment: -1,
              sizeFactor: _headerAnim,
              child: Container(
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
            ),
            Expanded(
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : ListView(
                      padding: const EdgeInsets.all(16),
                      children: [
                        Card(
                          child: Padding(
                            padding: const EdgeInsets.all(10),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    _buildInfoBadge(
                                      icon: isOnline
                                          ? Icons.wifi_tethering
                                          : Icons.wifi_tethering_off,
                                      label: isOnline ? 'Online' : 'Offline',
                                      background: isOnline
                                          ? const Color(0xFFDCFCE7)
                                          : const Color(0xFFFEE2E2),
                                      foreground: isOnline
                                          ? const Color(0xFF166534)
                                          : const Color(0xFF991B1B),
                                    ),
                                    if (_screenProtected) ...[
                                      const SizedBox(width: 8),
                                      _buildInfoBadge(
                                        icon: Icons.lock_outline,
                                        label: 'Protected',
                                        background: scheme.surfaceContainerHigh,
                                      ),
                                    ],
                                    const Spacer(),
                                    _buildInfoBadge(
                                      icon: Icons.screen_rotation_alt_outlined,
                                      label: '$_screenRotation°',
                                      background: scheme.surfaceContainerHigh,
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 10),
                                Text(
                                  addressLabel,
                                  style: theme.textTheme.labelMedium?.copyWith(
                                    color: scheme.onSurfaceVariant,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  _screenAddress.trim().isEmpty
                                      ? 'No saved screen or store address'
                                      : _screenAddress,
                                  style: theme.textTheme.bodyMedium?.copyWith(
                                    color: _screenAddress.trim().isEmpty
                                        ? scheme.onSurfaceVariant
                                        : scheme.onSurface,
                                  ),
                                ),
                                const SizedBox(height: 10),
                                Row(
                                  children: [
                                    Expanded(
                                      child: Text(
                                        playlistModeLabel,
                                        style: theme.textTheme.titleSmall,
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 8),
                                Container(
                                  padding: const EdgeInsets.all(10),
                                  decoration: BoxDecoration(
                                    color: scheme.surfaceContainerLow,
                                    borderRadius: BorderRadius.circular(12),
                                    border: Border.all(
                                        color: scheme.outlineVariant),
                                  ),
                                  child: Row(
                                    children: [
                                      Container(
                                        width: 48,
                                        height: 48,
                                        clipBehavior: Clip.antiAlias,
                                        decoration: BoxDecoration(
                                          borderRadius:
                                              BorderRadius.circular(10),
                                          color: scheme.surfaceContainerHigh,
                                        ),
                                        child: _buildCompactMediaThumb(
                                          item,
                                          iconSize: 22,
                                        ),
                                      ),
                                      const SizedBox(width: 10),
                                      Expanded(
                                        child: Column(
                                          crossAxisAlignment:
                                              CrossAxisAlignment.start,
                                          children: [
                                            Text(
                                              currentItemLabel,
                                              maxLines: 1,
                                              overflow: TextOverflow.ellipsis,
                                              style: theme.textTheme.titleSmall,
                                            ),
                                            const SizedBox(height: 2),
                                            Text(
                                              currentRunning
                                                  ? 'Running now'
                                                  : 'Ready in playlist',
                                              style: theme.textTheme.bodySmall
                                                  ?.copyWith(
                                                color: scheme.onSurfaceVariant,
                                              ),
                                            ),
                                          ],
                                        ),
                                      ),
                                      if (currentDuration != null)
                                        Text(
                                          '$currentDuration s',
                                          style: theme.textTheme.labelMedium
                                              ?.copyWith(
                                            color: scheme.onSurfaceVariant,
                                            fontWeight: FontWeight.w700,
                                          ),
                                        ),
                                    ],
                                  ),
                                ),
                                if (_playlist.length > 1) ...[
                                  const SizedBox(height: 10),
                                  Text(
                                    'All Playlist Items',
                                    style:
                                        theme.textTheme.labelMedium?.copyWith(
                                      color: scheme.onSurfaceVariant,
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                  const SizedBox(height: 6),
                                  ..._playlist.map((playlistItem) {
                                    final playlistItemId =
                                        (playlistItem['id'] ?? '').toString();
                                    final isSelected = (_selectedItemId ==
                                                null &&
                                            identical(playlistItem, item)) ||
                                        _selectedItemId == playlistItemId;
                                    final playlistDuration = int.tryParse(
                                          '${playlistItem['duration'] ?? 10}',
                                        ) ??
                                        10;
                                    final playlistRunning =
                                        _looksRunning(playlistItem);
                                    return Padding(
                                      padding: const EdgeInsets.only(bottom: 6),
                                      child: InkWell(
                                        borderRadius: BorderRadius.circular(12),
                                        onTap: () {
                                          setState(() {
                                            _selectedItemId = playlistItemId;
                                          });
                                          _loadItemFieldsFromCurrent();
                                          _refreshPreviewHeaders();
                                        },
                                        child: Container(
                                          padding: const EdgeInsets.all(10),
                                          decoration: BoxDecoration(
                                            color: isSelected
                                                ? scheme.primaryContainer
                                                : scheme.surface,
                                            borderRadius:
                                                BorderRadius.circular(12),
                                            border: Border.all(
                                              color: isSelected
                                                  ? scheme.primary
                                                  : scheme.outlineVariant,
                                            ),
                                          ),
                                          child: Row(
                                            children: [
                                              Container(
                                                width: 42,
                                                height: 42,
                                                clipBehavior: Clip.antiAlias,
                                                decoration: BoxDecoration(
                                                  borderRadius:
                                                      BorderRadius.circular(10),
                                                  color: scheme
                                                      .surfaceContainerHigh,
                                                ),
                                                child: _buildCompactMediaThumb(
                                                  playlistItem,
                                                  iconSize: 20,
                                                ),
                                              ),
                                              const SizedBox(width: 10),
                                              Expanded(
                                                child: Column(
                                                  crossAxisAlignment:
                                                      CrossAxisAlignment.start,
                                                  children: [
                                                    Text(
                                                      _itemLabel(playlistItem),
                                                      maxLines: 1,
                                                      overflow:
                                                          TextOverflow.ellipsis,
                                                      style: theme
                                                          .textTheme.titleSmall,
                                                    ),
                                                    const SizedBox(height: 2),
                                                    Text(
                                                      playlistRunning
                                                          ? 'Running now'
                                                          : 'Scheduled item',
                                                      style: theme
                                                          .textTheme.bodySmall
                                                          ?.copyWith(
                                                        color: scheme
                                                            .onSurfaceVariant,
                                                      ),
                                                    ),
                                                  ],
                                                ),
                                              ),
                                              Text(
                                                '$playlistDuration s',
                                                style: theme
                                                    .textTheme.labelMedium
                                                    ?.copyWith(
                                                  color:
                                                      scheme.onSurfaceVariant,
                                                  fontWeight: FontWeight.w700,
                                                ),
                                              ),
                                            ],
                                          ),
                                        ),
                                      ),
                                    );
                                  }),
                                ],
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(height: 10),
                        Card(
                          child: Padding(
                            padding: const EdgeInsets.all(12),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Text('Current Media',
                                        style: theme.textTheme.titleMedium),
                                    const Spacer(),
                                    SizedBox(
                                      width: 36,
                                      height: 36,
                                      child: IconButton.outlined(
                                        tooltip: 'Replace media',
                                        onPressed: _saving
                                            ? null
                                            : _openQuickReplaceMedia,
                                        icon: const Icon(
                                            Icons.swap_horiz_rounded,
                                            size: 18),
                                      ),
                                    ),
                                    const SizedBox(width: 8),
                                    SizedBox(
                                      width: 36,
                                      height: 36,
                                      child: IconButton.outlined(
                                        tooltip: 'Delete current item',
                                        onPressed: _saving || item == null
                                            ? null
                                            : _deleteCurrentPlaylistItem,
                                        icon: const Icon(Icons.delete_outline,
                                            size: 18),
                                      ),
                                    ),
                                  ],
                                ),
                                if (_playlist.length > 1) ...[
                                  const SizedBox(height: 8),
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
                                              _itemLabel(
                                                  _currentItem ?? const {}),
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
                                const SizedBox(height: 8),
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
                                                  child: Icon(
                                                      Icons.broken_image,
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
                                                    : itemUrl.isNotEmpty
                                                        ? _VideoPreview(
                                                            key: ValueKey(
                                                                itemUrl),
                                                            url: itemUrl,
                                                            headers:
                                                                _previewHeaders,
                                                          )
                                                        : const Center(
                                                            child: Column(
                                                              mainAxisSize:
                                                                  MainAxisSize
                                                                      .min,
                                                              children: [
                                                                Icon(
                                                                    Icons.movie,
                                                                    size: 40),
                                                                SizedBox(
                                                                    height: 8),
                                                                Text(
                                                                    'Video selected'),
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
                                if (item == null)
                                  Text(
                                    'Upload or assign media to start syncing this screen.',
                                    style: theme.textTheme.bodySmall?.copyWith(
                                      color: scheme.onSurfaceVariant,
                                    ),
                                  )
                                else
                                  Wrap(
                                    spacing: 8,
                                    runSpacing: 8,
                                    children: [
                                      _buildInfoBadge(
                                        icon: hasVideo
                                            ? Icons.movie_outlined
                                            : hasImage
                                                ? Icons.image_outlined
                                                : Icons.perm_media_outlined,
                                        label:
                                            'Type ${mediaType.isEmpty ? 'unknown' : mediaType}',
                                      ),
                                      _buildInfoBadge(
                                        icon: Icons.sync,
                                        label: 'Website sync 5s',
                                        background: scheme.primaryContainer,
                                        foreground: scheme.onPrimaryContainer,
                                      ),
                                    ],
                                  ),
                                const SizedBox(height: 8),
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
                                        tooltip: 'Scrolling Text',
                                        icon: Icons.text_fields,
                                        background: const Color(0xFF0F766E),
                                        onPressed: (_saving || _quickActionBusy)
                                            ? null
                                            : _quickAddScrollingText,
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
                                        tooltip: 'TV',
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
                        _buildPanelInfoCard(),
                        const SizedBox(height: 10),
                        Card(
                          elevation: 0,
                          color: scheme.surface,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(18),
                          ),
                          child: Padding(
                            padding: const EdgeInsets.all(14),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Container(
                                  padding: EdgeInsets.zero,
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text('Playback',
                                          style: theme.textTheme.titleSmall),
                                      const SizedBox(height: 12),
                                      Row(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          _buildPillToggle(
                                            label: 'Enabled',
                                            value: _itemEnabled,
                                            onChanged: _saving
                                                ? null
                                                : (value) {
                                                    setState(() {
                                                      _itemEnabled = value;
                                                    });
                                                    _queueAutoSave();
                                                  },
                                          ),
                                          const SizedBox(width: 18),
                                          _buildPillToggle(
                                            label: 'Repeat',
                                            value: _itemRepeat,
                                            onChanged: _saving
                                                ? null
                                                : (value) {
                                                    setState(() {
                                                      _itemRepeat = value;
                                                    });
                                                    _queueAutoSave();
                                                  },
                                          ),
                                          const Spacer(),
                                          SizedBox(
                                            width: 128,
                                            child: _buildPillDurationField(),
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 12),
                                      Text(
                                        'Effect',
                                        style: theme.textTheme.labelMedium
                                            ?.copyWith(
                                          fontWeight: FontWeight.w700,
                                          color: scheme.onSurfaceVariant,
                                        ),
                                      ),
                                      const SizedBox(height: 6),
                                      Row(
                                        children: List.generate(11, (i) {
                                          final selected = _itemEffectId == i;
                                          final isLast = i == 10;
                                          return Expanded(
                                            child: Padding(
                                              padding: EdgeInsets.only(
                                                  right: isLast ? 0 : 4),
                                              child: GestureDetector(
                                                onTap: _saving
                                                    ? null
                                                    : () {
                                                        setState(() {
                                                          _itemEffectId = i;
                                                        });
                                                        _queueAutoSave();
                                                      },
                                                child: Container(
                                                  height: 34,
                                                  alignment: Alignment.center,
                                                  decoration: BoxDecoration(
                                                    color: selected
                                                        ? scheme.primary
                                                        : scheme
                                                            .surfaceContainerHighest,
                                                    borderRadius:
                                                        BorderRadius.circular(
                                                            8),
                                                  ),
                                                  child: Text(
                                                    i == 0 ? '·' : '$i',
                                                    style: theme
                                                        .textTheme.labelSmall
                                                        ?.copyWith(
                                                      fontSize: 11,
                                                      fontWeight:
                                                          FontWeight.w700,
                                                      color: selected
                                                          ? scheme.onPrimary
                                                          : scheme
                                                              .onSurfaceVariant,
                                                    ),
                                                  ),
                                                ),
                                              ),
                                            ),
                                          );
                                        }),
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(height: 12),
                                Divider(color: scheme.outlineVariant),
                                const SizedBox(height: 12),
                                Container(
                                  padding: EdgeInsets.zero,
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text('Days',
                                          style: theme.textTheme.titleSmall),
                                      const SizedBox(height: 6),
                                      Row(
                                        children: _weekDays.map((day) {
                                          final selected =
                                              _itemDays.contains(day);
                                          final isLast = day == _weekDays.last;
                                          return Expanded(
                                            child: Padding(
                                              padding: EdgeInsets.only(
                                                  right: isLast ? 0 : 4),
                                              child: GestureDetector(
                                                onTap: _saving
                                                    ? null
                                                    : () {
                                                        setState(() {
                                                          if (selected) {
                                                            _itemDays
                                                                .remove(day);
                                                          } else {
                                                            _itemDays.add(day);
                                                          }
                                                        });
                                                        _queueAutoSave();
                                                      },
                                                child: Container(
                                                  height: 36,
                                                  alignment: Alignment.center,
                                                  decoration: BoxDecoration(
                                                    color: selected
                                                        ? scheme.primary
                                                        : scheme
                                                            .surfaceContainerHighest,
                                                    borderRadius:
                                                        BorderRadius.circular(
                                                            8),
                                                  ),
                                                  child: Text(
                                                    day.toUpperCase(),
                                                    style: theme
                                                        .textTheme.labelSmall
                                                        ?.copyWith(
                                                      fontSize: 11,
                                                      fontWeight:
                                                          FontWeight.w700,
                                                      color: selected
                                                          ? scheme.onPrimary
                                                          : scheme
                                                              .onSurfaceVariant,
                                                    ),
                                                  ),
                                                ),
                                              ),
                                            ),
                                          );
                                        }).toList(),
                                      ),
                                      const SizedBox(height: 14),
                                      Text('Start / End',
                                          style: theme.textTheme.titleSmall),
                                      const SizedBox(height: 6),
                                      _buildDateTimeField(
                                        controller: _startController,
                                        label: 'Start',
                                        onPickDate: () =>
                                            _pickDateFor(_startController),
                                        onPickTime: () =>
                                            _pickTimeFor(_startController),
                                      ),
                                      const SizedBox(height: 12),
                                      _buildDateTimeField(
                                        controller: _endController,
                                        label: 'End',
                                        onPickDate: () =>
                                            _pickDateFor(_endController),
                                        onPickTime: () =>
                                            _pickTimeFor(_endController),
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(height: 12),
                                SizedBox(
                                  width: double.infinity,
                                  child: FilledButton.icon(
                                    style: FilledButton.styleFrom(
                                      padding: const EdgeInsets.symmetric(
                                          vertical: 12),
                                    ),
                                    onPressed:
                                        _saving ? null : _saveItemSettings,
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
                                  'Add a new image, video, or YouTube item to this screen, or add extra active windows to the selected media.',
                                  style: theme.textTheme.bodySmall?.copyWith(
                                    color: scheme.onSurfaceVariant,
                                  ),
                                ),
                                const SizedBox(height: 10),
                                SizedBox(
                                  width: double.infinity,
                                  child: FilledButton.icon(
                                    onPressed: _saving
                                        ? null
                                        : _openCreatePlaylistSetup,
                                    icon: const Icon(Icons.add),
                                    label: const Text('Add Scheduled Media'),
                                  ),
                                ),
                                const SizedBox(height: 8),
                                SizedBox(
                                  width: double.infinity,
                                  child: OutlinedButton.icon(
                                    onPressed:
                                        _saving ? null : _addScheduleWindow,
                                    icon: const Icon(Icons.event_repeat),
                                    label: const Text(
                                      'Add Extra Window to Current Media',
                                    ),
                                  ),
                                ),
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
                                                style:
                                                    theme.textTheme.titleSmall,
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
                                                        label: Text(
                                                            d.toUpperCase()),
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
                                                        _deleteScheduleWindow(
                                                            idx),
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
                                            : _pickedFile!
                                                .uri.pathSegments.last,
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
                                    onPressed:
                                        _saving ? null : _replaceFromLibrary,
                                    icon: const Icon(Icons.collections),
                                    label: const Text(
                                        'Choose Existing from Library'),
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
        ),
      ),
    );
  }
}

class _ScrollingTextPreview extends StatefulWidget {
  const _ScrollingTextPreview({
    super.key,
    required this.text,
    required this.fontSize,
  });

  final String text;
  final double fontSize;

  @override
  State<_ScrollingTextPreview> createState() => _ScrollingTextPreviewState();
}

class _ScrollingTextPreviewState extends State<_ScrollingTextPreview>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 7),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      color: const Color(0xFF0F172A),
      clipBehavior: Clip.hardEdge,
      alignment: Alignment.centerLeft,
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, child) => FractionalTranslation(
          translation: Offset(1 - (_controller.value * 2), 0),
          child: child,
        ),
        child: Text(
          widget.text,
          maxLines: 1,
          softWrap: false,
          overflow: TextOverflow.visible,
          style: TextStyle(
            color: Colors.white,
            fontSize: widget.fontSize,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
    );
  }
}

class _VideoPreview extends StatefulWidget {
  const _VideoPreview({
    super.key,
    required this.url,
    required this.headers,
    this.compact = false,
    this.syncStartEpoch,
  });

  final String url;
  final Map<String, String> headers;
  final bool compact;
  final int? syncStartEpoch;

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
  bool _failed = false;
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
    if (!allowKeepExisting || previous == null) {
      setState(() {
        _failed = false;
      });
    }
    try {
      final controller = VideoPlayerController.networkUrl(
        Uri.parse(widget.url),
        httpHeaders: widget.headers,
        videoPlayerOptions: VideoPlayerOptions(mixWithOthers: true),
      );
      await controller.initialize();
      await controller.setLooping(true);
      await controller.setVolume(0);
      final syncStart = widget.syncStartEpoch;
      final duration = controller.value.duration;
      if (syncStart != null && duration > Duration.zero) {
        final elapsedMs = DateTime.now().millisecondsSinceEpoch -
            (syncStart * Duration.millisecondsPerSecond);
        final offsetMs =
            ((elapsedMs % duration.inMilliseconds) + duration.inMilliseconds) %
                duration.inMilliseconds;
        await controller.seekTo(Duration(milliseconds: offsetMs));
      }
      await controller.play();
      if (!mounted || token != _initToken) {
        await controller.dispose();
        return;
      }

      setState(() {
        _controller = controller;
        _ready = true;
        _failed = false;
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
          _failed = true;
        });
        return;
      }
      setState(() {
        _ready = _controller != null && _controller!.value.isInitialized;
        _failed = false;
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
    if (_failed) {
      if (widget.compact) {
        return const Center(
          child: Icon(Icons.video_library_outlined, size: 18),
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
    if (widget.compact) {
      return const Center(
        child: SizedBox(
          width: 16,
          height: 16,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      );
    }
    return const Center(child: CircularProgressIndicator());
  }
}

class _LivePosCardPreview extends StatelessWidget {
  const _LivePosCardPreview({
    required this.title,
    required this.body,
  });

  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          colors: [Color(0xFF0F172A), Color(0xFF1D4ED8)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.radio_button_checked,
                  color: Color(0xFF86EFAC), size: 12),
              SizedBox(width: 4),
              Text(
                'LIVE POS',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 10,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
          const Spacer(),
          Text(
            title.isEmpty ? 'Live POS Orders' : title,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: theme.textTheme.titleSmall?.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.w800,
            ),
          ),
          if (body.isNotEmpty) ...[
            const SizedBox(height: 3),
            Text(
              body,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: theme.textTheme.bodySmall?.copyWith(
                color: const Color(0xFFDBEAFE),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _YouTubeCardPreview extends StatefulWidget {
  const _YouTubeCardPreview({
    super.key,
    required this.videoId,
  });

  final String videoId;

  @override
  State<_YouTubeCardPreview> createState() => _YouTubeCardPreviewState();
}

class _YouTubeCardPreviewState extends State<_YouTubeCardPreview> {
  late final YoutubePlayerController _controller;

  @override
  void initState() {
    super.initState();
    _controller = YoutubePlayerController.fromVideoId(
      videoId: widget.videoId,
      autoPlay: true,
      params: const YoutubePlayerParams(
        mute: true,
        loop: true,
        showControls: false,
        showFullscreenButton: false,
        pointerEvents: PointerEvents.none,
      ),
    );
  }

  @override
  void dispose() {
    unawaited(_controller.close());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: Colors.black,
      child: YoutubePlayer(
        controller: _controller,
        aspectRatio: 16 / 9,
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

class _YouTubeInputDialog extends StatefulWidget {
  const _YouTubeInputDialog({required this.initialValue});

  final String initialValue;

  @override
  State<_YouTubeInputDialog> createState() => _YouTubeInputDialogState();
}

class _YouTubeInputDialogState extends State<_YouTubeInputDialog> {
  late final TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.initialValue);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('YouTube'),
      content: TextField(
        controller: _controller,
        autofocus: true,
        decoration: const InputDecoration(
          labelText: 'YouTube URL or video ID',
          hintText: 'Paste link or 11-character ID',
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(_controller.text.trim()),
          child: const Text('Use YouTube'),
        ),
      ],
    );
  }
}

class _ScrollingTextInputDialog extends StatefulWidget {
  const _ScrollingTextInputDialog();

  @override
  State<_ScrollingTextInputDialog> createState() =>
      _ScrollingTextInputDialogState();
}

class _ScrollingTextInputDialogState extends State<_ScrollingTextInputDialog> {
  late final TextEditingController _textController;
  late final TextEditingController _durationController;
  late final TextEditingController _fontSizeController;
  late final TextEditingController _speedController;
  late final TextEditingController _textColorController;
  late final TextEditingController _backgroundColorController;
  late final TextEditingController _iconController;
  late final TextEditingController _imageUrlController;

  void _closeDialog([Map<String, String>? result]) {
    FocusScope.of(context).unfocus();
    if (!mounted) {
      return;
    }
    Navigator.of(context).pop(result);
  }

  @override
  void initState() {
    super.initState();
    _textController = TextEditingController();
    _durationController = TextEditingController(text: '15');
    _fontSizeController = TextEditingController(text: '56');
    _speedController = TextEditingController(text: '15');
    _textColorController = TextEditingController(text: '#FFFFFF');
    _backgroundColorController = TextEditingController(text: '#071B1C');
    _iconController = TextEditingController();
    _imageUrlController = TextEditingController();
  }

  @override
  void dispose() {
    _textController.dispose();
    _durationController.dispose();
    _fontSizeController.dispose();
    _speedController.dispose();
    _textColorController.dispose();
    _backgroundColorController.dispose();
    _iconController.dispose();
    _imageUrlController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.of(context).viewInsets.bottom;
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(16, 8, 16, bottomInset + 16),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Add Scrolling Text',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 12),
              Text(
                'This message will scroll across the display in the schedule.',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _textController,
                maxLength: 2000,
                minLines: 2,
                maxLines: 4,
                textCapitalization: TextCapitalization.sentences,
                decoration: const InputDecoration(
                  labelText: 'Message',
                  hintText: 'e.g. Fresh deals available today',
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _durationController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Duration (seconds)',
                ),
              ),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(child: TextField(controller: _fontSizeController, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Text size'))),
                const SizedBox(width: 8),
                Expanded(child: TextField(controller: _speedController, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Scroll speed'))),
              ]),
              const SizedBox(height: 8),
              TextField(controller: _textColorController, decoration: const InputDecoration(labelText: 'Text color (#RRGGBB)')),
              const SizedBox(height: 8),
              TextField(controller: _backgroundColorController, decoration: const InputDecoration(labelText: 'Background color (#RRGGBB)')),
              const SizedBox(height: 8),
              TextField(controller: _iconController, decoration: const InputDecoration(labelText: 'Icon / emoji')),
              const SizedBox(height: 8),
              TextField(controller: _imageUrlController, decoration: const InputDecoration(labelText: 'Image URL')),
              const SizedBox(height: 16),
              Row(
                children: [
                  TextButton(
                    onPressed: () => _closeDialog(),
                    child: const Text('Cancel'),
                  ),
                  const Spacer(),
                  FilledButton(
                    onPressed: () => _closeDialog(<String, String>{
                      'text': _textController.text.trim(),
                      'duration': _durationController.text.trim(),
                      'font_size': _fontSizeController.text.trim(),
                      'scroll_speed': _speedController.text.trim(),
                      'text_color': _textColorController.text.trim(),
                      'background_color': _backgroundColorController.text.trim(),
                      'icon': _iconController.text.trim(),
                      'image_url': _imageUrlController.text.trim(),
                      'loop': 'true',
                    }),
                    child: const Text('Add to Schedule'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _AddStoreDialog extends StatefulWidget {
  const _AddStoreDialog({required this.apiClient});

  final ApiClient apiClient;

  @override
  State<_AddStoreDialog> createState() => _AddStoreDialogState();
}

class _AddStoreDialogState extends State<_AddStoreDialog> {
  final _idController = TextEditingController();
  final _nameController = TextEditingController();
  final _addressController = TextEditingController();

  Timer? _debounce;
  int _searchToken = 0;
  bool _searching = false;
  List<String> _suggestions = const [];

  @override
  void dispose() {
    _debounce?.cancel();
    _idController.dispose();
    _nameController.dispose();
    _addressController.dispose();
    super.dispose();
  }

  void _onAddressChanged(String value) {
    _debounce?.cancel();
    final query = value.trim();
    if (query.length < 3) {
      setState(() {
        _suggestions = const [];
        _searching = false;
      });
      return;
    }
    setState(() => _searching = true);
    _debounce = Timer(const Duration(milliseconds: 280), () async {
      final token = ++_searchToken;
      final results = await widget.apiClient.searchAddressSuggestions(query);
      if (!mounted || token != _searchToken) {
        return;
      }
      setState(() {
        _suggestions = results;
        _searching = false;
      });
    });
  }

  void _selectSuggestion(String value) {
    _debounce?.cancel();
    _searchToken++; // Invalidate any in-flight search.
    _addressController.value = TextEditingValue(
      text: value,
      selection: TextSelection.collapsed(offset: value.length),
    );
    setState(() {
      _suggestions = const [];
      _searching = false;
    });
    FocusScope.of(context).unfocus();
  }

  void _submit() {
    Navigator.of(context).pop(<String, String>{
      'id': _idController.text.trim(),
      'name': _nameController.text.trim(),
      'address': _addressController.text.trim(),
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return AlertDialog(
      title: const Text('Add Store'),
      content: SizedBox(
        width: double.maxFinite,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              controller: _idController,
              textInputAction: TextInputAction.next,
              decoration: const InputDecoration(labelText: 'Store ID'),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _nameController,
              textInputAction: TextInputAction.next,
              decoration: const InputDecoration(labelText: 'Store Name'),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _addressController,
              onChanged: _onAddressChanged,
              textInputAction: TextInputAction.done,
              decoration: InputDecoration(
                labelText: 'Store Address (optional)',
                hintText: 'Start typing to search…',
                suffixIcon: _searching
                    ? const Padding(
                        padding: EdgeInsets.all(12),
                        child: SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                      )
                    : const Icon(Icons.search),
              ),
            ),
            if (_suggestions.isNotEmpty)
              Container(
                margin: const EdgeInsets.only(top: 6),
                constraints: const BoxConstraints(maxHeight: 220),
                decoration: BoxDecoration(
                  color: scheme.surfaceContainerLowest,
                  border: Border.all(color: scheme.outlineVariant),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: ListView.separated(
                  shrinkWrap: true,
                  padding: EdgeInsets.zero,
                  itemCount: _suggestions.length,
                  separatorBuilder: (_, __) =>
                      Divider(height: 1, color: scheme.outlineVariant),
                  itemBuilder: (context, index) {
                    final suggestion = _suggestions[index];
                    return ListTile(
                      dense: true,
                      leading: const Icon(Icons.location_on_outlined, size: 20),
                      title: Text(
                        suggestion,
                        style: theme.textTheme.bodyMedium,
                      ),
                      onTap: () => _selectSuggestion(suggestion),
                    );
                  },
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
          onPressed: _submit,
          child: const Text('Add'),
        ),
      ],
    );
  }
}

import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:geocoding/geocoding.dart' as geocoding;
import 'package:geolocator/geolocator.dart';

import '../../models/app_models.dart';
import '../../services/api_client.dart';
import 'stores_tab.dart';

class DeviceManagerTab extends StatefulWidget {
  const DeviceManagerTab({super.key, required this.apiClient});

  final ApiClient apiClient;

  @override
  State<DeviceManagerTab> createState() => _DeviceManagerTabState();
}

class _DeviceManagerTabState extends State<DeviceManagerTab> {
  bool _loading = true;
  String? _message;
  String? _actionBusyPiId;
  List<Map<String, dynamic>> _screens = const [];
  Map<String, Map<String, dynamic>> _piStatusMap = const {};
  final Map<String, Map<String, String>> _localPiAssignments = {};
  final Map<String, Map<String, String>> _localPiAssignmentIds = {};
  Map<String, _ScreenPreview?> _piCardPreviews = const {};
  final Map<String, Future<_ScreenPreview?>> _screenPreviewFutures = {};
  final TextEditingController _piIdentifierController = TextEditingController();
  String? _checkedPiId;
  String _checkedPiIp = 'Unknown';
  bool _checkingPi = false;
  bool _checkedPiOnline = false;
  String _searchQuery = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _piIdentifierController.dispose();
    super.dispose();
  }

  String _shortPiId(String piId) {
    final text = piId.trim();
    if (text.length <= 20) {
      return text;
    }
    return '${text.substring(0, 10)}...${text.substring(text.length - 6)}';
  }

  Widget _buildRaspberryPiImageBadge(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final base = widget.apiClient.baseUrl.replaceAll(RegExp(r'/$'), '');
    final imageUrl = '$base/static/pi_raspberry.png';
    return SizedBox(
      width: 54,
      height: 36,
      child: Image.network(
        imageUrl,
        fit: BoxFit.contain,
        errorBuilder: (_, __, ___) => Icon(
          Icons.memory,
          size: 18,
          color: scheme.onSurfaceVariant,
        ),
      ),
    );
  }

  Widget _buildPiChip(
    BuildContext context, {
    required String label,
    required Color background,
    required Color foreground,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w700,
          color: foreground,
          letterSpacing: 0.1,
        ),
      ),
    );
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _message = null;
      _screenPreviewFutures.clear();
    });
    try {
      final results = await Future.wait<dynamic>([
        widget.apiClient.getAllScreensStatus(),
        widget.apiClient.getPiStatusMap(),
      ]);
      if (!mounted) {
        return;
      }
      setState(() {
        _screens = results[0] as List<Map<String, dynamic>>;
        _piStatusMap = results[1] as Map<String, Map<String, dynamic>>;
        if (_checkedPiId != null && _checkedPiId!.isNotEmpty) {
          final pi = _piStatusMap[_checkedPiId!];
          if (pi != null) {
            _checkedPiOnline =
                ((pi['status'] ?? 'offline').toString().toLowerCase() ==
                    'online');
            _checkedPiIp = (pi['ip'] ?? 'Unknown').toString();
          }
        }
      });
      _refreshPiCardPreviews();
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

  Future<_ScreenPreview?> _getScreenPreviewFuture({
    required String storeId,
    required String screenId,
  }) {
    final key = '$storeId|$screenId';
    return _screenPreviewFutures.putIfAbsent(
      key,
      () => _loadScreenPreview(storeId: storeId, screenId: screenId),
    );
  }

  Future<void> _refreshPiCardPreviews() async {
    final assignments = <String, Map<String, String>>{};

    for (final entry in _piStatusMap.entries) {
      final piId = entry.key.trim();
      if (piId.isEmpty) {
        continue;
      }
      final storeId = (entry.value['store_id'] ?? '').toString().trim();
      final screenId = (entry.value['screen_id'] ?? '').toString().trim();
      if (storeId.isNotEmpty && screenId.isNotEmpty) {
        assignments[piId] = {'store_id': storeId, 'screen_id': screenId};
      }
    }

    for (final s in _screens) {
      final piId = (s['device_id'] ?? '').toString().trim();
      if (piId.isEmpty ||
          piId == 'Not Assigned' ||
          assignments.containsKey(piId)) {
        continue;
      }
      final storeId = (s['store_id'] ?? '').toString().trim();
      final screenId = (s['screen_id'] ?? '').toString().trim();
      if (storeId.isNotEmpty && screenId.isNotEmpty) {
        assignments[piId] = {'store_id': storeId, 'screen_id': screenId};
      }
    }

    for (final entry in _localPiAssignmentIds.entries) {
      assignments[entry.key] = entry.value;
    }

    final next = <String, _ScreenPreview?>{};
    for (final entry in assignments.entries) {
      try {
        next[entry.key] = await _loadScreenPreview(
          storeId: entry.value['store_id']!,
          screenId: entry.value['screen_id']!,
        );
      } catch (_) {
        next[entry.key] = null;
      }
    }

    if (!mounted) {
      return;
    }
    setState(() {
      _piCardPreviews = next;
    });
  }

  Future<void> _checkPiIdentifier() async {
    final query = _piIdentifierController.text.trim();
    if (query.isEmpty) {
      setState(() {
        _searchQuery = '';
        _checkedPiId = null;
        _message = 'Enter a Pi Identifier or search term.';
      });
      return;
    }

    setState(() {
      _checkingPi = true;
      _searchQuery = query;
    });

    try {
      // Refresh latest snapshots, then treat input as check + search.
      final results = await Future.wait<dynamic>([
        widget.apiClient.getAllScreensStatus(),
        widget.apiClient.getPiStatusMap(),
      ]);
      if (!mounted) {
        return;
      }
      final screens = results[0] as List<Map<String, dynamic>>;
      final piMap = results[1] as Map<String, Map<String, dynamic>>;
      final pi = piMap[query];

      final q = query.toLowerCase();
      int screenMatches = 0;
      int piMatches = 0;
      for (final s in screens) {
        final hay = [
          s['store_name'],
          s['store_id'],
          s['screen_name'],
          s['screen_id'],
          s['device_id'],
          s['device_type'],
          s['ip'],
          s['location'],
        ].map((e) => (e ?? '').toString().toLowerCase()).join(' ');
        if (hay.contains(q)) {
          screenMatches += 1;
        }
      }
      for (final entry in piMap.entries) {
        final st = entry.value;
        final hay = [
          entry.key,
          st['ip'],
          st['store_name'],
          st['screen_name'],
          st['store_id'],
          st['screen_id'],
          st['status'],
        ].map((e) => (e ?? '').toString().toLowerCase()).join(' ');
        if (hay.contains(q)) {
          piMatches += 1;
        }
      }

      setState(() {
        _screens = screens;
        _piStatusMap = piMap;
        if (pi != null) {
          _checkedPiId = query;
          _checkedPiOnline =
              ((pi['status'] ?? 'offline').toString().toLowerCase() ==
                  'online');
          _checkedPiIp = (pi['ip'] ?? 'Unknown').toString();
          _message = _checkedPiOnline
              ? 'Pi connected: $query'
              : 'Pi found but currently offline: $query';
        } else {
          _checkedPiId = null;
          _checkedPiOnline = false;
          _checkedPiIp = 'Unknown';
          _message = (screenMatches == 0 && piMatches == 0)
              ? 'No results for "$query"'
              : 'Search results: $screenMatches screen(s), $piMatches Pi device(s).';
        }
      });
      _refreshPiCardPreviews();
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
          _checkingPi = false;
        });
      }
    }
  }

  Future<void> _restartPi(String piId) async {
    final ok = await showDialog<bool>(
          context: context,
          builder: (_) => AlertDialog(
            title: const Text('Restart Pi'),
            content: Text('Restart $piId now?'),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () => Navigator.of(context).pop(true),
                child: const Text('Restart'),
              ),
            ],
          ),
        ) ??
        false;
    if (!ok) {
      return;
    }

    await _runPiAction(piId, () async {
      await widget.apiClient.restartPiDevice(piId);
      _showMessage('Restart command sent to $piId.');
    });
  }

  Future<void> _deletePi(String piId) async {
    final ok = await showDialog<bool>(
          context: context,
          builder: (_) => AlertDialog(
            title: const Text('Delete Pi'),
            content: Text('Delete $piId from this account?'),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                style: FilledButton.styleFrom(
                  backgroundColor: const Color(0xFFDC2626),
                ),
                onPressed: () => Navigator.of(context).pop(true),
                child: const Text('Delete'),
              ),
            ],
          ),
        ) ??
        false;
    if (!ok) {
      return;
    }

    await _runPiAction(piId, () async {
      await widget.apiClient.deletePiDevice(piId);
      _showMessage('Deleted $piId successfully.');
    });
  }

  Future<void> _setLocation(String piId) async {
    String initialName = '';
    String initialAddress = '';
    double? initialLatitude;
    double? initialLongitude;
    try {
      final data = await widget.apiClient.getPiLocation(piId);
      initialName = (data['location_name'] ?? '').toString();
      initialAddress = (data['address'] ?? '').toString();
      initialLatitude = double.tryParse((data['latitude'] ?? '').toString());
      initialLongitude = double.tryParse((data['longitude'] ?? '').toString());
    } catch (_) {
      // Keep empty initial value if location not available.
    }
    if (!mounted) {
      return;
    }

    final result = await showDialog<_PiLocationDraft>(
      context: context,
      builder: (_) => _PiLocationDialog(
        initialLocationName: initialName,
        initialAddress: initialAddress,
        initialLatitude: initialLatitude,
        initialLongitude: initialLongitude,
      ),
    );

    if (result == null) {
      return;
    }

    await _runPiAction(piId, () async {
      await widget.apiClient.updatePiLocation(
        piId: piId,
        locationName: result.locationName,
        address: result.address,
        latitude: result.latitude,
        longitude: result.longitude,
      );
      _showMessage(
        result.hasCoordinates
            ? 'Location and coordinates updated for $piId.'
            : 'Location updated for $piId.',
      );
    });
  }

  Future<void> _assignPiToScreen({
    required String piId,
    required String fallbackIp,
  }) async {
    final stores = await widget.apiClient.getStores();
    if (!mounted) {
      return;
    }
    if (stores.isEmpty) {
      _showMessage('No stores found for this account.');
      return;
    }

    String selectedStoreId = stores.first.id;
    List<ScreenItem> screens =
        await widget.apiClient.getScreens(selectedStoreId);
    String? selectedScreenId = screens.isNotEmpty ? screens.first.id : null;
    _ScreenPreview? initialPreview;
    if (selectedScreenId != null) {
      initialPreview = await _loadScreenPreview(
        storeId: selectedStoreId,
        screenId: selectedScreenId,
      );
    }
    if (!mounted) {
      return;
    }

    final payload = await showDialog<Map<String, String>>(
      context: context,
      builder: (context) {
        bool loadingScreens = false;
        bool loadingPreview = false;
        _ScreenPreview? preview = initialPreview;
        String? selectedLibraryFile;
        File? selectedLocalFile;

        return StatefulBuilder(
          builder: (context, setStateDialog) {
            Future<void> refreshPreview() async {
              final screenId = selectedScreenId;
              if (screenId == null) {
                setStateDialog(() {
                  preview = null;
                });
                return;
              }
              setStateDialog(() {
                loadingPreview = true;
              });
              try {
                final loaded = await _loadScreenPreview(
                  storeId: selectedStoreId,
                  screenId: screenId,
                );
                setStateDialog(() {
                  preview = loaded;
                });
              } finally {
                setStateDialog(() {
                  loadingPreview = false;
                });
              }
            }

            Future<void> loadScreensForStore(String storeId) async {
              setStateDialog(() {
                loadingScreens = true;
                selectedStoreId = storeId;
                selectedScreenId = null;
              });
              try {
                final next = await widget.apiClient.getScreens(storeId);
                setStateDialog(() {
                  screens = next;
                  selectedScreenId = next.isNotEmpty ? next.first.id : null;
                });
                await refreshPreview();
              } finally {
                setStateDialog(() {
                  loadingScreens = false;
                });
              }
            }

            Future<void> pickLibrary() async {
              final picked = await showModalBottomSheet<String>(
                context: context,
                isScrollControlled: true,
                useSafeArea: true,
                builder: (_) => FractionallySizedBox(
                  heightFactor: 0.88,
                  child: _DeviceLibraryPickerSheet(apiClient: widget.apiClient),
                ),
              );
              if (picked == null || picked.trim().isEmpty) {
                return;
              }
              setStateDialog(() {
                selectedLibraryFile = picked.trim();
                selectedLocalFile = null;
              });
            }

            Future<void> pickLocalFile() async {
              final result =
                  await FilePicker.platform.pickFiles(withData: false);
              if (result == null || result.files.isEmpty) {
                return;
              }
              final path = result.files.single.path;
              if (path == null || path.trim().isEmpty) {
                return;
              }
              setStateDialog(() {
                selectedLocalFile = File(path);
                selectedLibraryFile = null;
              });
            }

            final mq = MediaQuery.of(context).size;

            return Dialog(
              insetPadding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 18),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(24),
              ),
              child: SizedBox(
                width: mq.width * 0.96,
                height: mq.height * 0.86,
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(18, 10, 18, 14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Apply Screen To Pi',
                        style: Theme.of(context).textTheme.headlineSmall,
                      ),
                      const SizedBox(height: 24),
                      Expanded(
                        child: SingleChildScrollView(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              DropdownButtonFormField<String>(
                                isExpanded: true,
                                value: selectedStoreId,
                                decoration:
                                    const InputDecoration(labelText: 'Store'),
                                items: stores
                                    .map((s) => DropdownMenuItem<String>(
                                          value: s.id,
                                          child: Text(
                                            '${s.name} (${s.id})',
                                            overflow: TextOverflow.ellipsis,
                                          ),
                                        ))
                                    .toList(),
                                onChanged: (value) {
                                  if (value != null &&
                                      value != selectedStoreId) {
                                    loadScreensForStore(value);
                                  }
                                },
                              ),
                              const SizedBox(height: 12),
                              if (loadingScreens)
                                const LinearProgressIndicator(minHeight: 2)
                              else
                                DropdownButtonFormField<String>(
                                  isExpanded: true,
                                  value: selectedScreenId,
                                  decoration: const InputDecoration(
                                    labelText: 'Screen',
                                  ),
                                  items: screens
                                      .map((s) => DropdownMenuItem<String>(
                                            value: s.id,
                                            child: Text(
                                              '${s.name} (${s.id})',
                                              overflow: TextOverflow.ellipsis,
                                            ),
                                          ))
                                      .toList(),
                                  onChanged: screens.isEmpty
                                      ? null
                                      : (value) async {
                                          setStateDialog(() {
                                            selectedScreenId = value;
                                          });
                                          await refreshPreview();
                                        },
                                ),
                              if (screens.isEmpty) ...[
                                const SizedBox(height: 8),
                                const Text('No screens in selected store.'),
                              ],
                              const SizedBox(height: 14),
                              Text(
                                'Current Screen Media',
                                style: Theme.of(context).textTheme.titleSmall,
                              ),
                              const SizedBox(height: 8),
                              Container(
                                width: double.infinity,
                                height: 170,
                                decoration: BoxDecoration(
                                  borderRadius: BorderRadius.circular(12),
                                  border: Border.all(
                                    color: Theme.of(context)
                                        .colorScheme
                                        .outlineVariant,
                                  ),
                                  color: Theme.of(context)
                                      .colorScheme
                                      .surfaceContainerLow,
                                ),
                                child: loadingPreview
                                    ? const Center(
                                        child: CircularProgressIndicator())
                                    : (preview?.url.isNotEmpty ?? false)
                                        ? ClipRRect(
                                            borderRadius:
                                                BorderRadius.circular(12),
                                            child: Image.network(
                                              preview!.url,
                                              fit: BoxFit.cover,
                                              errorBuilder: (_, __, ___) =>
                                                  Center(
                                                child: Text(
                                                  preview!.label,
                                                  textAlign: TextAlign.center,
                                                ),
                                              ),
                                            ),
                                          )
                                        : const Center(
                                            child: Text(
                                              'No media assigned to this screen',
                                            ),
                                          ),
                              ),
                              const SizedBox(height: 12),
                              Wrap(
                                spacing: 10,
                                runSpacing: 10,
                                children: [
                                  OutlinedButton.icon(
                                    onPressed: pickLibrary,
                                    icon: const Icon(Icons.collections),
                                    label: const Text('Choose Library'),
                                  ),
                                  OutlinedButton.icon(
                                    onPressed: pickLocalFile,
                                    icon: const Icon(Icons.folder_open),
                                    label: const Text('Choose Device'),
                                  ),
                                ],
                              ),
                              if (selectedLibraryFile != null) ...[
                                const SizedBox(height: 8),
                                Text(
                                  'Selected library media: $selectedLibraryFile',
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ],
                              if (selectedLocalFile != null) ...[
                                const SizedBox(height: 8),
                                Text(
                                  'Selected local file: ${selectedLocalFile!.uri.pathSegments.last}',
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ],
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 8),
                      Align(
                        alignment: Alignment.centerRight,
                        child: TextButton(
                          onPressed: () => Navigator.of(context).pop(),
                          child: const Text('Cancel'),
                        ),
                      ),
                      const SizedBox(height: 4),
                      SizedBox(
                        width: double.infinity,
                        child: FilledButton(
                          onPressed: selectedScreenId == null
                              ? null
                              : () {
                                  Navigator.of(context).pop({
                                    'store_id': selectedStoreId,
                                    'screen_id': selectedScreenId!,
                                    if (selectedLibraryFile != null)
                                      'library_file': selectedLibraryFile!,
                                    if (selectedLocalFile != null)
                                      'local_path': selectedLocalFile!.path,
                                  });
                                },
                          child: const Text('Apply'),
                        ),
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

    if (payload == null) {
      return;
    }

    final ip = (_piStatusMap[piId]?['ip'] ?? fallbackIp).toString();
    if (ip.isEmpty || ip == 'Unknown' || ip == 'N/A') {
      _showMessage('Cannot assign $piId because IP is unknown.');
      return;
    }

    final me = await widget.apiClient.getMe();
    final pairCode = (me.linkCode ?? '').trim();

    await _runPiAction(piId, () async {
      final localPath = (payload['local_path'] ?? '').trim();
      final libraryFile = (payload['library_file'] ?? '').trim();
      final assignedStoreId = payload['store_id']!;
      final assignedScreenId = payload['screen_id']!;

      String assignedStoreName = assignedStoreId;
      final matchedStore =
          stores.where((s) => s.id == assignedStoreId).toList();
      if (matchedStore.isNotEmpty) {
        assignedStoreName = matchedStore.first.name;
      }

      String assignedScreenName = assignedScreenId;
      final matchedScreen =
          screens.where((s) => s.id == assignedScreenId).toList();
      if (matchedScreen.isNotEmpty) {
        assignedScreenName = matchedScreen.first.name;
      }

      if (localPath.isNotEmpty) {
        final uploaded = await widget.apiClient.uploadMedia(File(localPath));
        await widget.apiClient.assignToScreen(
          storeId: assignedStoreId,
          screenId: assignedScreenId,
          filename: uploaded,
        );
      } else if (libraryFile.isNotEmpty) {
        await widget.apiClient.assignToScreen(
          storeId: assignedStoreId,
          screenId: assignedScreenId,
          filename: libraryFile,
        );
      }

      await widget.apiClient.addPiDeviceAssignment(
        piId: piId,
        ipAddress: ip,
        storeId: assignedStoreId,
        screenId: assignedScreenId,
      );

      bool liveApplied = false;
      if (pairCode.isNotEmpty) {
        try {
          await widget.apiClient.configurePiWebsocket(
            piId: piId,
            pairCode: pairCode,
            storeId: assignedStoreId,
            screenId: assignedScreenId,
            autoStart: true,
          );
          liveApplied = true;
        } catch (_) {
          // Keep persisted assignment even if live command cannot be delivered.
        }
      }

      if (mounted) {
        setState(() {
          _localPiAssignments[piId] = {
            'store': assignedStoreName,
            'screen': assignedScreenName,
          };
          _localPiAssignmentIds[piId] = {
            'store_id': assignedStoreId,
            'screen_id': assignedScreenId,
          };

          final existing = Map<String, dynamic>.from(_piStatusMap[piId] ?? {});
          existing['assigned'] = true;
          existing['store_name'] = assignedStoreName;
          existing['screen_name'] = assignedScreenName;
          _piStatusMap = {
            ..._piStatusMap,
            piId: existing,
          };
        });
        _refreshPiCardPreviews();
      }

      _showMessage(liveApplied
          ? 'Applied $assignedScreenId to $piId (live + saved).'
          : 'Saved assignment for $assignedScreenId to $piId. Live apply pending.');
    });
  }

  Future<_ScreenPreview?> _loadScreenPreview({
    required String storeId,
    required String screenId,
  }) async {
    final playlist = await widget.apiClient.getPlaylist(
      storeId: storeId,
      screenId: screenId,
    );
    if (playlist.isEmpty) {
      return null;
    }

    Map<String, dynamic>? item;
    String previewUrl = '';
    for (int i = playlist.length - 1; i >= 0; i--) {
      final it = playlist[i];
      if ((it['enabled'] ?? true) != true) {
        continue;
      }
      final candidate = _resolvePreviewUrlFromItem(it);
      if (candidate.isNotEmpty) {
        item = it;
        previewUrl = candidate;
        break;
      }
      item ??= it;
    }
    item ??= playlist.isNotEmpty ? playlist.last : null;
    previewUrl =
        previewUrl.isEmpty ? _resolvePreviewUrlFromItem(item) : previewUrl;

    final file = (item?['file'] ?? '').toString().trim();
    if (previewUrl.isEmpty) {
      return null;
    }
    final label = file.isEmpty ? 'Current media' : file;
    return _ScreenPreview(url: previewUrl, label: label);
  }

  String _encodePathPreservingSlashes(String path) {
    return path
        .split('/')
        .where((s) => s.trim().isNotEmpty)
        .map(Uri.encodeComponent)
        .join('/');
  }

  String _toAbsoluteUrl(String value) {
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

  String _resolvePreviewUrlFromItem(Map<String, dynamic>? item) {
    if (item == null) {
      return '';
    }

    final file = (item['file'] ?? '').toString().trim();
    if (file.startsWith('youtube:')) {
      final id = file.substring('youtube:'.length).trim();
      if (id.length == 11) {
        return 'https://img.youtube.com/vi/$id/hqdefault.jpg';
      }
      return '';
    }

    if (file.isNotEmpty &&
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

    if (file.isEmpty) {
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

  Future<void> _openScreenModifySheet({
    required String storeId,
    required String screenId,
    required String title,
  }) async {
    if (storeId.trim().isEmpty || screenId.trim().isEmpty) {
      _showMessage('Screen is missing store or screen ID.');
      return;
    }

    if (!mounted) {
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
          child: ScreenMediaEditorSheet(
            apiClient: widget.apiClient,
            storeId: storeId,
            screenId: screenId,
            screenName: title,
          ),
        );
      },
    );

    if (mounted) {
      await _load();
    }
  }

  Future<void> _showPreviewDialog({
    required String imageUrl,
    required String title,
  }) async {
    if (imageUrl.trim().isEmpty || !mounted) {
      return;
    }
    await showDialog<void>(
      context: context,
      barrierDismissible: true,
      builder: (context) => Dialog(
        insetPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 20),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        child: LayoutBuilder(
          builder: (context, constraints) {
            final maxDialogHeight = constraints.maxHeight * 0.82;
            return ConstrainedBox(
              constraints: BoxConstraints(
                maxWidth: 640,
                maxHeight: maxDialogHeight,
              ),
              child: Padding(
                padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            title,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                        ),
                        IconButton(
                          tooltip: 'Close',
                          onPressed: () => Navigator.of(context).pop(),
                          icon: const Icon(Icons.close),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Flexible(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(12),
                        child: InteractiveViewer(
                          minScale: 1,
                          maxScale: 4,
                          child: Image.network(
                            imageUrl,
                            fit: BoxFit.contain,
                            errorBuilder: (_, __, ___) => Container(
                              height: 180,
                              width: double.infinity,
                              alignment: Alignment.center,
                              child: const Text('Preview unavailable'),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ),
    );
  }

  Future<void> _runPiAction(String piId, Future<void> Function() action) async {
    setState(() {
      _actionBusyPiId = piId;
      _message = null;
    });
    try {
      await action();
      await _load();
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
          _actionBusyPiId = null;
        });
      }
    }
  }

  void _showMessage(String text) {
    if (!mounted) {
      return;
    }
    setState(() {
      _message = text;
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final piAssignments = <String, Map<String, String>>{};

    // Fast UI path: show local assignment updates immediately after apply.
    for (final entry in _localPiAssignments.entries) {
      piAssignments[entry.key] = {
        'store': (entry.value['store'] ?? '-').toString(),
        'screen': (entry.value['screen'] ?? '-').toString(),
      };
    }

    // Primary assignment source: /api/pi_status (includes config + heartbeat mapping).
    for (final entry in _piStatusMap.entries) {
      final piId = entry.key.trim();
      if (piId.isEmpty) {
        continue;
      }
      final st = entry.value;
      final assignedFlag = st['assigned'] == true;
      final storeName = (st['store_name'] ?? '').toString().trim();
      final screenName = (st['screen_name'] ?? '').toString().trim();
      if (assignedFlag || (storeName.isNotEmpty && screenName.isNotEmpty)) {
        piAssignments[piId] = {
          'store': storeName.isNotEmpty ? storeName : '-',
          'screen': screenName.isNotEmpty ? screenName : '-',
        };
      }
    }

    // Fallback source: all_screens_status list.
    for (final s in _screens) {
      final deviceId = (s['device_id'] ?? '').toString().trim();
      if (deviceId.isEmpty || deviceId == 'Not Assigned') {
        continue;
      }
      final deviceType = (s['device_type'] ?? '').toString().toLowerCase();
      if (!piAssignments.containsKey(deviceId) &&
          (deviceType == 'pi' || _piStatusMap.containsKey(deviceId))) {
        piAssignments[deviceId] = {
          'store': (s['store_name'] ?? s['store_id'] ?? '-').toString(),
          'screen': (s['screen_name'] ?? s['screen_id'] ?? '-').toString(),
        };
      }
    }
    final allPis = _piStatusMap.entries.toList()
      ..sort((a, b) => a.key.compareTo(b.key));
    final q = _searchQuery.trim().toLowerCase();
    final hasSearch = q.isNotEmpty;

    bool matchesScreen(Map<String, dynamic> s) {
      if (!hasSearch) {
        return true;
      }
      final hay = [
        s['store_name'],
        s['store_id'],
        s['screen_name'],
        s['screen_id'],
        s['device_id'],
        s['device_type'],
        s['ip'],
        s['location'],
      ].map((e) => (e ?? '').toString().toLowerCase()).join(' ');
      return hay.contains(q);
    }

    bool matchesPi(MapEntry<String, Map<String, dynamic>> entry) {
      if (!hasSearch) {
        return true;
      }
      final st = entry.value;
      final assignment = piAssignments[entry.key];
      final hay = [
        entry.key,
        st['ip'],
        st['status'],
        st['store_name'],
        st['screen_name'],
        assignment?['store'],
        assignment?['screen'],
      ].map((e) => (e ?? '').toString().toLowerCase()).join(' ');
      return hay.contains(q);
    }

    final filteredPis = allPis.where(matchesPi).toList();
    final filteredScreens = _screens.where(matchesScreen).toList();

    final totalScreens = _screens.length;
    final onlineScreens = _screens
        .where((s) => (s['status'] ?? '').toString().toLowerCase() == 'online')
        .length;
    final offlineScreens = totalScreens - onlineScreens;
    final uniqueStores = _screens
        .map((s) => (s['store_id'] ?? '').toString())
        .where((id) => id.isNotEmpty)
        .toSet()
        .length;

    return SingleChildScrollView(
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text('Pi Identifier',
                            style: theme.textTheme.titleSmall),
                        const Spacer(),
                        IconButton(
                          visualDensity: VisualDensity.compact,
                          onPressed: _loading ? null : _load,
                          icon: const Icon(Icons.refresh),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: _piIdentifierController,
                            onChanged: (value) {
                              if (value.trim().isEmpty) {
                                setState(() {
                                  _searchQuery = '';
                                  _checkedPiId = null;
                                });
                              }
                            },
                            decoration: const InputDecoration(
                              hintText: 'everydayadvertise-ce39',
                              isDense: true,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        SizedBox(
                          width: 110,
                          child: FilledButton(
                            onPressed: _checkingPi ? null : _checkPiIdentifier,
                            child: Text(_checkingPi ? 'Checking...' : 'Check'),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        if (_checkedPiId != null)
                          Text(
                            _checkedPiId!,
                            style: theme.textTheme.bodyMedium?.copyWith(
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        if (_checkedPiId != null)
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: _checkedPiOnline
                                  ? const Color(0xFFDCFCE7)
                                  : const Color(0xFFFEE2E2),
                              borderRadius: BorderRadius.circular(999),
                            ),
                            child: Text(
                              _checkedPiOnline ? 'Connected' : 'Offline',
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w700,
                                color: _checkedPiOnline
                                    ? const Color(0xFF166534)
                                    : const Color(0xFF991B1B),
                              ),
                            ),
                          ),
                        if (_checkedPiId != null)
                          OutlinedButton(
                            onPressed: () => _assignPiToScreen(
                              piId: _checkedPiId!,
                              fallbackIp: _checkedPiIp,
                            ),
                            child: const Text('Apply Screen'),
                          ),
                        if (_checkedPiId != null)
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: piAssignments[_checkedPiId!] != null
                                  ? const Color(0xFFDCFCE7)
                                  : const Color(0xFFF3F4F6),
                              borderRadius: BorderRadius.circular(999),
                            ),
                            child: Text(
                              piAssignments[_checkedPiId!] != null
                                  ? 'Assigned'
                                  : 'Not Yet',
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w700,
                                color: piAssignments[_checkedPiId!] != null
                                    ? const Color(0xFF166534)
                                    : const Color(0xFF374151),
                              ),
                            ),
                          ),
                        if (_checkedPiId != null &&
                            piAssignments[_checkedPiId!] != null)
                          Container(
                            constraints: BoxConstraints(
                              maxWidth: MediaQuery.of(context).size.width - 72,
                            ),
                            padding: const EdgeInsets.symmetric(
                                horizontal: 10, vertical: 8),
                            decoration: BoxDecoration(
                              color: theme.colorScheme.surfaceContainerLow,
                              borderRadius: BorderRadius.circular(10),
                              border: Border.all(
                                color: theme.colorScheme.outlineVariant,
                              ),
                            ),
                            child: Row(
                              children: [
                                ClipRRect(
                                  borderRadius: BorderRadius.circular(6),
                                  child: (_piCardPreviews[_checkedPiId!]
                                              ?.url
                                              .isNotEmpty ??
                                          false)
                                      ? GestureDetector(
                                          onTap: () => _showPreviewDialog(
                                            imageUrl:
                                                _piCardPreviews[_checkedPiId!]!
                                                    .url,
                                            title: 'Preview • ${_checkedPiId!}',
                                          ),
                                          child: Image.network(
                                            _piCardPreviews[_checkedPiId!]!.url,
                                            width: 72,
                                            height: 44,
                                            fit: BoxFit.cover,
                                            errorBuilder: (_, __, ___) =>
                                                Container(
                                              width: 72,
                                              height: 44,
                                              color: theme.colorScheme
                                                  .surfaceContainerHighest,
                                              alignment: Alignment.center,
                                              child: const Icon(Icons.tv,
                                                  size: 18),
                                            ),
                                          ),
                                        )
                                      : Container(
                                          width: 72,
                                          height: 44,
                                          color: theme.colorScheme
                                              .surfaceContainerHighest,
                                          alignment: Alignment.center,
                                          child: const Icon(Icons.tv, size: 18),
                                        ),
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    'Assigned to\n${piAssignments[_checkedPiId!]!['store']} • ${piAssignments[_checkedPiId!]!['screen']}',
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                    style: theme.textTheme.bodySmall?.copyWith(
                                      color: theme.colorScheme.onSurfaceVariant,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
          if (_message != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: theme.colorScheme.surfaceContainer,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(_message!),
              ),
            ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
            child: LayoutBuilder(
              builder: (context, constraints) {
                final tileWidth = (constraints.maxWidth - 8) / 2;
                return Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    _statCard(
                      context,
                      label: 'TOTAL STORES',
                      value: uniqueStores.toString(),
                      width: tileWidth,
                      compact: true,
                    ),
                    _statCard(
                      context,
                      label: 'TOTAL SCREENS',
                      value: totalScreens.toString(),
                      width: tileWidth,
                      compact: true,
                    ),
                    _statCard(
                      context,
                      label: 'SCREENS ONLINE',
                      value: onlineScreens.toString(),
                      valueColor: const Color(0xFF16A34A),
                      width: tileWidth,
                      compact: true,
                    ),
                    _statCard(
                      context,
                      label: 'SCREENS OFFLINE',
                      value: offlineScreens.toString(),
                      valueColor: const Color(0xFFEF4444),
                      width: tileWidth,
                      compact: true,
                    ),
                  ],
                );
              },
            ),
          ),
          if (_loading)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 32),
              child: Center(child: CircularProgressIndicator()),
            )
          else
            ListView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
              itemCount:
                  filteredScreens.length + (filteredPis.isNotEmpty ? 1 : 0),
              itemBuilder: (context, index) {
                if (filteredPis.isNotEmpty && index == 0) {
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Card(
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Icon(
                                  Icons.memory,
                                  size: 18,
                                  color: theme.colorScheme.primary,
                                ),
                                const SizedBox(width: 8),
                                Text(
                                  'All Pi Devices',
                                  style: theme.textTheme.titleMedium,
                                ),
                                const Spacer(),
                                Container(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 10, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: theme.colorScheme.primaryContainer,
                                    borderRadius: BorderRadius.circular(999),
                                  ),
                                  child: Text(
                                    '${filteredPis.length}',
                                    style:
                                        theme.textTheme.labelMedium?.copyWith(
                                      fontWeight: FontWeight.w700,
                                      color:
                                          theme.colorScheme.onPrimaryContainer,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            ...filteredPis.map((entry) {
                              final piId = entry.key;
                              final st = (entry.value['status'] ?? 'offline')
                                  .toString();
                              final ip =
                                  (entry.value['ip'] ?? 'Unknown').toString();
                              final assignment = piAssignments[piId];
                              final preview = _piCardPreviews[piId];
                              final busy = _actionBusyPiId == piId;
                              return Padding(
                                padding: const EdgeInsets.only(bottom: 8),
                                child: Container(
                                  padding: const EdgeInsets.all(14),
                                  decoration: BoxDecoration(
                                    borderRadius: BorderRadius.circular(14),
                                    border: Border.all(
                                      color: theme.colorScheme.outlineVariant,
                                    ),
                                    color:
                                        theme.colorScheme.surfaceContainerLow,
                                  ),
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Row(
                                        children: [
                                          Expanded(
                                            child: Text(
                                              _shortPiId(piId),
                                              maxLines: 1,
                                              overflow: TextOverflow.ellipsis,
                                              style: theme.textTheme.titleMedium
                                                  ?.copyWith(
                                                fontWeight: FontWeight.w700,
                                              ),
                                            ),
                                          ),
                                          const SizedBox(width: 8),
                                          Wrap(
                                            spacing: 6,
                                            children: [
                                              _buildPiChip(
                                                context,
                                                label: st,
                                                background: st.toLowerCase() ==
                                                        'online'
                                                    ? const Color(0xFFDCFCE7)
                                                    : const Color(0xFFFEE2E2),
                                                foreground: st.toLowerCase() ==
                                                        'online'
                                                    ? const Color(0xFF166534)
                                                    : const Color(0xFF991B1B),
                                              ),
                                              _buildPiChip(
                                                context,
                                                label: assignment != null
                                                    ? 'Assigned'
                                                    : 'Not Yet',
                                                background: assignment != null
                                                    ? const Color(0xFFDCFCE7)
                                                    : const Color(0xFFF3F4F6),
                                                foreground: assignment != null
                                                    ? const Color(0xFF166534)
                                                    : const Color(0xFF374151),
                                              ),
                                            ],
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 6),
                                      Row(
                                        children: [
                                          Icon(
                                            Icons.lan,
                                            size: 14,
                                            color: theme
                                                .colorScheme.onSurfaceVariant,
                                          ),
                                          const SizedBox(width: 6),
                                          Expanded(
                                            child: Text(
                                              ip,
                                              maxLines: 1,
                                              overflow: TextOverflow.ellipsis,
                                              style: theme.textTheme.bodyMedium
                                                  ?.copyWith(
                                                color: theme.colorScheme
                                                    .onSurfaceVariant,
                                              ),
                                            ),
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 6),
                                      Container(
                                        width: double.infinity,
                                        padding: const EdgeInsets.symmetric(
                                            horizontal: 10, vertical: 8),
                                        decoration: BoxDecoration(
                                          color: theme
                                              .colorScheme.surfaceContainerHigh,
                                          borderRadius:
                                              BorderRadius.circular(10),
                                          border: Border.all(
                                            color: theme
                                                .colorScheme.outlineVariant,
                                          ),
                                        ),
                                        child: Row(
                                          children: [
                                            ClipRRect(
                                              borderRadius:
                                                  BorderRadius.circular(6),
                                              child: (preview?.url.isNotEmpty ??
                                                      false)
                                                  ? GestureDetector(
                                                      onTap: () =>
                                                          _showPreviewDialog(
                                                        imageUrl: preview.url,
                                                        title:
                                                            'Preview • $piId',
                                                      ),
                                                      child: Image.network(
                                                        preview!.url,
                                                        width: 72,
                                                        height: 44,
                                                        fit: BoxFit.cover,
                                                        errorBuilder:
                                                            (_, __, ___) =>
                                                                Container(
                                                          width: 72,
                                                          height: 44,
                                                          color: theme
                                                              .colorScheme
                                                              .surfaceContainerHighest,
                                                          alignment:
                                                              Alignment.center,
                                                          child: const Icon(
                                                              Icons.tv,
                                                              size: 18),
                                                        ),
                                                      ),
                                                    )
                                                  : Container(
                                                      width: 72,
                                                      height: 44,
                                                      color: theme.colorScheme
                                                          .surfaceContainerHighest,
                                                      alignment:
                                                          Alignment.center,
                                                      child: const Icon(
                                                          Icons.tv,
                                                          size: 18),
                                                    ),
                                            ),
                                            const SizedBox(width: 8),
                                            Expanded(
                                              child: Text(
                                                assignment != null
                                                    ? 'Assigned to\n${assignment['store']} • ${assignment['screen']}'
                                                    : 'Assigned to\nNot assigned yet',
                                                maxLines: 2,
                                                overflow: TextOverflow.ellipsis,
                                                style: theme
                                                    .textTheme.bodyMedium
                                                    ?.copyWith(
                                                  color: theme.colorScheme
                                                      .onSurfaceVariant,
                                                ),
                                              ),
                                            ),
                                          ],
                                        ),
                                      ),
                                      if (_shortPiId(piId) != piId)
                                        Padding(
                                          padding:
                                              const EdgeInsets.only(top: 4),
                                          child: Text(
                                            'ID: $piId',
                                            maxLines: 1,
                                            overflow: TextOverflow.ellipsis,
                                            style: theme.textTheme.bodySmall
                                                ?.copyWith(
                                              color: theme
                                                  .colorScheme.onSurfaceVariant,
                                            ),
                                          ),
                                        ),
                                      const SizedBox(height: 8),
                                      Row(
                                        children: [
                                          _buildRaspberryPiImageBadge(context),
                                          const Spacer(),
                                          SizedBox(
                                            width: 150,
                                            child: FilledButton.tonal(
                                              onPressed: busy
                                                  ? null
                                                  : () => _assignPiToScreen(
                                                      piId: piId,
                                                      fallbackIp: ip),
                                              child: Text(busy
                                                  ? 'Working...'
                                                  : 'Apply Screen'),
                                            ),
                                          ),
                                        ],
                                      ),
                                    ],
                                  ),
                                ),
                              );
                            }),
                          ],
                        ),
                      ),
                    ),
                  );
                }

                final screenIndex = index - (filteredPis.isNotEmpty ? 1 : 0);
                final s = filteredScreens[screenIndex];
                final status =
                    (s['status'] ?? 'offline').toString().toLowerCase();
                final online = status == 'online';
                final store =
                    (s['store_name'] ?? s['store_id'] ?? '-').toString();
                final storeId = (s['store_id'] ?? '').toString();
                final screen =
                    (s['screen_name'] ?? s['screen_id'] ?? '-').toString();
                final screenId = (s['screen_id'] ?? '').toString();
                final deviceType = (s['device_type'] ?? 'none').toString();
                final deviceId = (s['device_id'] ?? 'Not Assigned').toString();
                final lastSeen = (s['last_seen'] ?? 'Never').toString();
                final ip = (s['ip'] ?? 'N/A').toString();
                final location = (s['location'] ?? '').toString();
                final canManagePi =
                    deviceType == 'pi' && deviceId != 'Not Assigned';
                final busy = canManagePi && _actionBusyPiId == deviceId;

                return Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: Card(
                    clipBehavior: Clip.antiAlias,
                    child: InkWell(
                      onTap: () => _openScreenModifySheet(
                        storeId: storeId,
                        screenId: screenId,
                        title: '$store • $screen',
                      ),
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Expanded(
                                  child: Text('$store • $screen',
                                      style: theme.textTheme.titleMedium),
                                ),
                                Container(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 10, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: online
                                        ? const Color(0xFFDCFCE7)
                                        : const Color(0xFFFEE2E2),
                                    borderRadius: BorderRadius.circular(999),
                                  ),
                                  child: Text(
                                    status,
                                    style: TextStyle(
                                      fontSize: 12,
                                      fontWeight: FontWeight.w700,
                                      color: online
                                          ? const Color(0xFF166534)
                                          : const Color(0xFF991B1B),
                                    ),
                                  ),
                                ),
                              ],
                            ),
                            if (storeId.isNotEmpty && screenId.isNotEmpty) ...[
                              const SizedBox(height: 8),
                              FutureBuilder<_ScreenPreview?>(
                                future: _getScreenPreviewFuture(
                                  storeId: storeId,
                                  screenId: screenId,
                                ),
                                builder: (context, snapshot) {
                                  final preview = snapshot.data;
                                  return Container(
                                    width: double.infinity,
                                    padding: const EdgeInsets.symmetric(
                                        horizontal: 10, vertical: 8),
                                    decoration: BoxDecoration(
                                      color:
                                          theme.colorScheme.surfaceContainerLow,
                                      borderRadius: BorderRadius.circular(10),
                                      border: Border.all(
                                        color: theme.colorScheme.outlineVariant,
                                      ),
                                    ),
                                    child: Row(
                                      children: [
                                        ClipRRect(
                                          borderRadius:
                                              BorderRadius.circular(6),
                                          child: (preview?.url.isNotEmpty ??
                                                  false)
                                              ? GestureDetector(
                                                  onTap: () =>
                                                      _showPreviewDialog(
                                                    imageUrl: preview.url,
                                                    title:
                                                        'Preview • $store • $screen',
                                                  ),
                                                  child: Image.network(
                                                    preview!.url,
                                                    width: 72,
                                                    height: 44,
                                                    fit: BoxFit.cover,
                                                    errorBuilder:
                                                        (_, __, ___) =>
                                                            Container(
                                                      width: 72,
                                                      height: 44,
                                                      color: theme.colorScheme
                                                          .surfaceContainerHighest,
                                                      alignment:
                                                          Alignment.center,
                                                      child: const Icon(
                                                          Icons.tv,
                                                          size: 18),
                                                    ),
                                                  ),
                                                )
                                              : Container(
                                                  width: 72,
                                                  height: 44,
                                                  color: theme.colorScheme
                                                      .surfaceContainerHighest,
                                                  alignment: Alignment.center,
                                                  child:
                                                      snapshot.connectionState ==
                                                              ConnectionState
                                                                  .waiting
                                                          ? const SizedBox(
                                                              width: 16,
                                                              height: 16,
                                                              child:
                                                                  CircularProgressIndicator(
                                                                strokeWidth: 2,
                                                              ),
                                                            )
                                                          : const Icon(Icons.tv,
                                                              size: 18),
                                                ),
                                        ),
                                        const SizedBox(width: 8),
                                        Expanded(
                                          child: Text(
                                            (preview?.url.isNotEmpty ?? false)
                                                ? 'Current screen media'
                                                : 'No media preview',
                                            maxLines: 2,
                                            overflow: TextOverflow.ellipsis,
                                            style: theme.textTheme.bodySmall
                                                ?.copyWith(
                                              color: theme
                                                  .colorScheme.onSurfaceVariant,
                                            ),
                                          ),
                                        ),
                                      ],
                                    ),
                                  );
                                },
                              ),
                            ],
                            const SizedBox(height: 6),
                            Text('Device: $deviceType • $deviceId'),
                            Text('Last seen: $lastSeen'),
                            Text('IP: $ip'),
                            if (location.isNotEmpty)
                              Text('Location: $location'),
                            const SizedBox(height: 4),
                            Text(
                              'Tap card to modify this screen',
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: theme.colorScheme.onSurfaceVariant,
                              ),
                            ),
                            if (canManagePi) ...[
                              const SizedBox(height: 10),
                              Wrap(
                                spacing: 8,
                                runSpacing: 8,
                                children: [
                                  FilledButton(
                                    onPressed: busy
                                        ? null
                                        : () => _assignPiToScreen(
                                              piId: deviceId,
                                              fallbackIp: ip,
                                            ),
                                    child: Text(
                                        busy ? 'Working...' : 'Apply Screen'),
                                  ),
                                  OutlinedButton(
                                    onPressed: busy
                                        ? null
                                        : () => _restartPi(deviceId),
                                    child: const Text('Restart'),
                                  ),
                                  OutlinedButton(
                                    onPressed: busy
                                        ? null
                                        : () => _setLocation(deviceId),
                                    child: const Text('Set Location'),
                                  ),
                                  OutlinedButton(
                                    onPressed:
                                        busy ? null : () => _deletePi(deviceId),
                                    child: const Text('Delete'),
                                  ),
                                ],
                              ),
                            ] else if (deviceId == 'Not Assigned' &&
                                screenId.isNotEmpty) ...[
                              const SizedBox(height: 10),
                              Text(
                                'No Pi assigned to this screen yet.',
                                style: theme.textTheme.bodySmall,
                              ),
                            ],
                          ],
                        ),
                      ),
                    ),
                  ),
                );
              },
            ),
        ],
      ),
    );
  }

  Widget _statCard(
    BuildContext context, {
    required String label,
    required String value,
    Color? valueColor,
    double width = 160,
    double height = 92,
    bool compact = false,
  }) {
    final theme = Theme.of(context);
    return Container(
      width: width,
      height: height,
      padding: EdgeInsets.all(compact ? 10 : 12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        color: Colors.white,
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: theme.textTheme.labelSmall?.copyWith(
              letterSpacing: 0.8,
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          SizedBox(height: compact ? 4 : 6),
          Text(
            value,
            style: (compact
                    ? theme.textTheme.headlineSmall
                    : theme.textTheme.headlineMedium)
                ?.copyWith(
              fontWeight: FontWeight.w800,
              color: valueColor,
            ),
          ),
        ],
      ),
    );
  }
}

class _ScreenPreview {
  const _ScreenPreview({required this.url, required this.label});

  final String url;
  final String label;
}

class _PiLocationDraft {
  const _PiLocationDraft({
    required this.locationName,
    required this.address,
    this.latitude,
    this.longitude,
  });

  final String locationName;
  final String address;
  final double? latitude;
  final double? longitude;

  bool get hasCoordinates => latitude != null && longitude != null;
}

class _PiLocationDialog extends StatefulWidget {
  const _PiLocationDialog({
    required this.initialLocationName,
    required this.initialAddress,
    this.initialLatitude,
    this.initialLongitude,
  });

  final String initialLocationName;
  final String initialAddress;
  final double? initialLatitude;
  final double? initialLongitude;

  @override
  State<_PiLocationDialog> createState() => _PiLocationDialogState();
}

class _PiLocationDialogState extends State<_PiLocationDialog> {
  late final TextEditingController _locationNameController;
  late final TextEditingController _addressController;
  double? _latitude;
  double? _longitude;
  bool _usingCurrentLocation = false;
  bool _searchingAddress = false;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _locationNameController =
        TextEditingController(text: widget.initialLocationName);
    _addressController = TextEditingController(text: widget.initialAddress);
    _latitude = widget.initialLatitude;
    _longitude = widget.initialLongitude;
  }

  @override
  void dispose() {
    _locationNameController.dispose();
    _addressController.dispose();
    super.dispose();
  }

  String _formatPlacemark(geocoding.Placemark placemark) {
    final parts = <String>[];

    void addPart(String? value) {
      final clean = value?.trim() ?? '';
      if (clean.isEmpty || parts.contains(clean)) {
        return;
      }
      parts.add(clean);
    }

    addPart(placemark.name);
    addPart(placemark.street);
    addPart(placemark.subLocality);
    addPart(placemark.locality);
    addPart(placemark.administrativeArea);
    addPart(placemark.postalCode);
    addPart(placemark.country);
    return parts.join(', ');
  }

  Future<String> _reverseGeocode(double latitude, double longitude) async {
    final placemarks = await geocoding.placemarkFromCoordinates(
      latitude,
      longitude,
    );
    if (placemarks.isEmpty) {
      return '';
    }
    return _formatPlacemark(placemarks.first);
  }

  Future<void> _useCurrentLocation() async {
    setState(() {
      _usingCurrentLocation = true;
      _error = null;
    });
    try {
      final serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) {
        throw Exception('Location services are turned off on this device.');
      }

      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        throw Exception('Location permission is required to use current GPS.');
      }

      final position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.high,
        ),
      );
      final address =
          await _reverseGeocode(position.latitude, position.longitude);

      if (!mounted) {
        return;
      }
      setState(() {
        _latitude = position.latitude;
        _longitude = position.longitude;
        if (address.isNotEmpty) {
          _addressController.text = address;
        }
        if (_locationNameController.text.trim().isEmpty) {
          _locationNameController.text =
              address.isNotEmpty ? address : 'Current location';
        }
      });
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = error.toString().replaceFirst('Exception: ', '');
      });
    } finally {
      if (mounted) {
        setState(() {
          _usingCurrentLocation = false;
        });
      }
    }
  }

  Future<void> _searchAddress() async {
    final query = _addressController.text.trim();
    if (query.isEmpty) {
      setState(() {
        _error = 'Enter an address or store location to search.';
      });
      return;
    }

    setState(() {
      _searchingAddress = true;
      _error = null;
    });

    try {
      final locations = await geocoding.locationFromAddress(query);
      if (locations.isEmpty) {
        throw Exception('No matching address was found.');
      }
      final location = locations.first;
      final formatted =
          await _reverseGeocode(location.latitude, location.longitude);

      if (!mounted) {
        return;
      }
      setState(() {
        _latitude = location.latitude;
        _longitude = location.longitude;
        _addressController.text = formatted.isNotEmpty ? formatted : query;
        if (_locationNameController.text.trim().isEmpty) {
          _locationNameController.text =
              formatted.isNotEmpty ? formatted : query;
        }
      });
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = error.toString().replaceFirst('Exception: ', '');
      });
    } finally {
      if (mounted) {
        setState(() {
          _searchingAddress = false;
        });
      }
    }
  }

  Future<void> _save() async {
    final locationName = _locationNameController.text.trim();
    final address = _addressController.text.trim();

    if (locationName.isEmpty && address.isEmpty) {
      setState(() {
        _error = 'Enter a location name, address, or use current GPS.';
      });
      return;
    }

    setState(() {
      _saving = true;
      _error = null;
    });

    try {
      double? nextLatitude = _latitude;
      double? nextLongitude = _longitude;
      String nextAddress = address;

      if ((nextLatitude == null || nextLongitude == null) &&
          address.isNotEmpty) {
        final locations = await geocoding.locationFromAddress(address);
        if (locations.isNotEmpty) {
          nextLatitude = locations.first.latitude;
          nextLongitude = locations.first.longitude;
          final formatted = await _reverseGeocode(nextLatitude, nextLongitude);
          if (formatted.isNotEmpty) {
            nextAddress = formatted;
          }
        }
      }

      if (!mounted) {
        return;
      }
      Navigator.of(context).pop(
        _PiLocationDraft(
          locationName: locationName.isNotEmpty
              ? locationName
              : (nextAddress.isNotEmpty ? nextAddress : 'Unknown Location'),
          address: nextAddress,
          latitude: nextLatitude,
          longitude: nextLongitude,
        ),
      );
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = error.toString().replaceFirst('Exception: ', '');
      });
    } finally {
      if (mounted) {
        setState(() {
          _saving = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final coordinatesText = (_latitude != null && _longitude != null)
        ? '${_latitude!.toStringAsFixed(6)}, ${_longitude!.toStringAsFixed(6)}'
        : 'No coordinates selected yet';

    return AlertDialog(
      title: const Text('Set Location'),
      content: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 420),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              TextField(
                controller: _locationNameController,
                decoration: const InputDecoration(
                  labelText: 'Location label',
                  hintText: 'Example: Front counter',
                ),
                textCapitalization: TextCapitalization.words,
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _addressController,
                decoration: const InputDecoration(
                  labelText: 'Address or place',
                  hintText: 'Search a street address or suburb',
                ),
                minLines: 1,
                maxLines: 2,
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  OutlinedButton.icon(
                    onPressed:
                        (_usingCurrentLocation || _searchingAddress || _saving)
                            ? null
                            : _useCurrentLocation,
                    icon: _usingCurrentLocation
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.my_location_outlined),
                    label: const Text('Use current GPS'),
                  ),
                  OutlinedButton.icon(
                    onPressed:
                        (_usingCurrentLocation || _searchingAddress || _saving)
                            ? null
                            : _searchAddress,
                    icon: _searchingAddress
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.search),
                    label: const Text('Find address'),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Text(
                'Coordinates',
                style: theme.textTheme.labelMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                coordinatesText,
                style: theme.textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(
                  _error!,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.error,
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: _saving ? null : () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _saving ? null : _save,
          child: Text(_saving ? 'Saving...' : 'Save'),
        ),
      ],
    );
  }
}

class _DeviceLibraryPickerSheet extends StatefulWidget {
  const _DeviceLibraryPickerSheet({required this.apiClient});

  final ApiClient apiClient;

  @override
  State<_DeviceLibraryPickerSheet> createState() =>
      _DeviceLibraryPickerSheetState();
}

class _DeviceLibraryPickerSheetState extends State<_DeviceLibraryPickerSheet> {
  bool _loading = true;
  String? _error;
  String _prefix = '';
  List<Map<String, dynamic>> _dirs = const [];
  List<Map<String, dynamic>> _files = const [];

  String _previewUrlForName(String name) {
    final trimmed = name.trim();
    if (trimmed.isEmpty) {
      return '';
    }
    final lower = trimmed.toLowerCase();
    final encoded = trimmed
        .split('/')
        .where((s) => s.trim().isNotEmpty)
        .map(Uri.encodeComponent)
        .join('/');
    final base = widget.apiClient.baseUrl.replaceAll(RegExp(r'/$'), '');
    final isVideo = lower.endsWith('.mp4') ||
        lower.endsWith('.mov') ||
        lower.endsWith('.webm') ||
        lower.endsWith('.mkv') ||
        lower.endsWith('.m3u8');
    return isVideo ? '$base/vthumb/96/$encoded' : '$base/thumb/96/$encoded';
  }

  Widget _fileLeading(String name) {
    final url = _previewUrlForName(name);
    if (url.isEmpty) {
      return const Icon(Icons.image);
    }
    return ClipRRect(
      borderRadius: BorderRadius.circular(6),
      child: Image.network(
        url,
        width: 40,
        height: 40,
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) => Container(
          width: 40,
          height: 40,
          color: Theme.of(context).colorScheme.surfaceContainerHighest,
          alignment: Alignment.center,
          child: const Icon(Icons.image, size: 18),
        ),
      ),
    );
  }

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
      final dirs = (data['dirs'] as List? ?? const [])
          .map((e) => e is Map
              ? e.map((k, v) => MapEntry(k.toString(), v))
              : <String, dynamic>{})
          .toList();
      final files = (data['files'] as List? ?? const [])
          .map((e) => e is Map
              ? e.map((k, v) => MapEntry(k.toString(), v))
              : <String, dynamic>{})
          .toList();
      if (!mounted) {
        return;
      }
      setState(() {
        _dirs = dirs;
        _files = files;
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

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SafeArea(
      child: Column(
        children: [
          ListTile(
            title: const Text('Choose Existing Media'),
            subtitle: Text(_prefix.isEmpty ? 'Library root' : _prefix),
            trailing: IconButton(
              onPressed: _loading ? null : _load,
              icon: const Icon(Icons.refresh),
            ),
          ),
          if (_prefix.isNotEmpty)
            Align(
              alignment: Alignment.centerLeft,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                child: OutlinedButton.icon(
                  onPressed: _loading
                      ? null
                      : () {
                          final idx = _prefix.lastIndexOf('/');
                          setState(() {
                            _prefix = idx <= 0 ? '' : _prefix.substring(0, idx);
                          });
                          _load();
                        },
                  icon: const Icon(Icons.arrow_upward),
                  label: const Text('Up'),
                ),
              ),
            ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? Center(child: Text(_error!))
                    : ListView(
                        padding: const EdgeInsets.fromLTRB(8, 0, 8, 12),
                        children: [
                          ..._dirs.map((dir) {
                            final name = (dir['name'] ?? '').toString();
                            final pref = (dir['prefix'] ?? '').toString();
                            return ListTile(
                              leading: const Icon(Icons.folder),
                              title: Text(name.isEmpty ? '(Folder)' : name),
                              trailing: const Icon(Icons.chevron_right),
                              onTap: pref.isEmpty
                                  ? null
                                  : () {
                                      setState(() {
                                        _prefix = pref;
                                      });
                                      _load();
                                    },
                            );
                          }),
                          ..._files.map((file) {
                            final name = (file['name'] ?? '').toString();
                            final label = name.contains('/')
                                ? name.split('/').last
                                : name;
                            return ListTile(
                              leading: _fileLeading(name),
                              title: Text(label),
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
                          if (_dirs.isEmpty && _files.isEmpty)
                            Padding(
                              padding: const EdgeInsets.all(14),
                              child: Text(
                                'No media found.',
                                style: theme.textTheme.bodySmall,
                              ),
                            ),
                        ],
                      ),
          ),
        ],
      ),
    );
  }
}

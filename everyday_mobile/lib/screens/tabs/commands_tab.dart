import 'package:flutter/material.dart';
import 'package:geocoding/geocoding.dart' as geocoding;
import 'package:google_maps_flutter/google_maps_flutter.dart';

import '../../services/api_client.dart';

class CommandsTab extends StatefulWidget {
  const CommandsTab({super.key, required this.apiClient});

  final ApiClient apiClient;

  @override
  State<CommandsTab> createState() => _CommandsTabState();
}

class _CommandsTabState extends State<CommandsTab> {
  bool _loading = true;
  String? _message;
  List<Map<String, dynamic>> _screens = const [];
  final Map<String, LatLng?> _resolvedMapPoints = {};

  @override
  void initState() {
    super.initState();
    _loadDevices();
  }

  Future<void> _loadDevices() async {
    setState(() {
      _loading = true;
      _message = null;
    });
    try {
      final screens = await widget.apiClient.getAllScreensStatus();
      if (!mounted) {
        return;
      }
      setState(() {
        _screens = screens;
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
          _loading = false;
        });
      }
    }
  }

  Future<void> _send(String deviceId, String command) async {
    setState(() {
      _message = null;
    });
    try {
      await widget.apiClient
          .sendAndroidTvCommand(deviceId: deviceId, command: command);
      if (!mounted) {
        return;
      }
      setState(() {
        _message = 'Sent $command to $deviceId';
      });
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _message = e.toString().replaceFirst('Exception: ', '');
      });
    }
  }

  Future<void> _openScreenActions(_CommandMapPin pin) async {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (context) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  pin.screenName,
                  style: theme.textTheme.titleLarge,
                ),
                const SizedBox(height: 4),
                Text(
                  '${pin.storeName} • ${pin.deviceId}',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: scheme.onSurfaceVariant,
                  ),
                ),
                if (pin.locationLabel.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(
                    pin.locationLabel,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                ],
                const SizedBox(height: 16),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    FilledButton(
                      style: FilledButton.styleFrom(
                        backgroundColor: const Color(0xFF2563EB),
                        foregroundColor: Colors.white,
                      ),
                      onPressed: () {
                        Navigator.of(context).pop();
                        _send(pin.deviceId, 'refresh_screen');
                      },
                      child: const Text('Refresh'),
                    ),
                    FilledButton(
                      style: FilledButton.styleFrom(
                        backgroundColor: const Color(0xFF16A34A),
                        foregroundColor: Colors.white,
                      ),
                      onPressed: () {
                        Navigator.of(context).pop();
                        _send(pin.deviceId, 'reload_playlist');
                      },
                      child: const Text('Reload'),
                    ),
                    OutlinedButton(
                      style: OutlinedButton.styleFrom(
                        foregroundColor: const Color(0xFF7C3AED),
                        side: const BorderSide(
                          color: Color(0xFF7C3AED),
                        ),
                      ),
                      onPressed: () {
                        Navigator.of(context).pop();
                        _send(pin.deviceId, 'restart_app');
                      },
                      child: const Text('Restart App'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Future<List<_CommandMapPin>> _buildPins() async {
    final candidates = _screens.where((screen) {
      final deviceId = (screen['device_id'] ?? '').toString().trim();
      return deviceId.isNotEmpty && deviceId != 'Not Assigned';
    }).toList();

    final pins = await Future.wait(
      candidates.map(_resolvePinForScreen),
    );
    return pins.whereType<_CommandMapPin>().toList();
  }

  Future<_CommandMapPin?> _resolvePinForScreen(Map<String, dynamic> screen) async {
    final deviceId = (screen['device_id'] ?? '').toString().trim();
    if (deviceId.isEmpty || deviceId == 'Not Assigned') {
      return null;
    }

    final storeName = (screen['store_name'] ?? screen['store_id'] ?? '-')
        .toString()
        .trim();
    final screenName = (screen['screen_name'] ?? screen['screen_id'] ?? '-')
        .toString()
        .trim();
    final status = (screen['status'] ?? 'offline').toString().trim();
    final locationLabel = (screen['location'] ?? '').toString().trim();

    final directPoint = _toLatLng(screen['latitude'], screen['longitude']);
    if (directPoint != null) {
      return _CommandMapPin(
        deviceId: deviceId,
        storeName: storeName,
        screenName: screenName,
        status: status,
        locationLabel: locationLabel,
        point: directPoint,
      );
    }

    final point = await _resolveMapPoint(
      locationLabel.isNotEmpty ? locationLabel : '$storeName $screenName',
    );
    if (point == null) {
      return null;
    }

    return _CommandMapPin(
      deviceId: deviceId,
      storeName: storeName,
      screenName: screenName,
      status: status,
      locationLabel: locationLabel,
      point: point,
    );
  }

  LatLng? _toLatLng(dynamic latitude, dynamic longitude) {
    final lat = double.tryParse((latitude ?? '').toString());
    final lng = double.tryParse((longitude ?? '').toString());
    if (lat == null || lng == null) {
      return null;
    }
    return LatLng(lat, lng);
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

  Widget _buildMapSection({
    required ThemeData theme,
    required ColorScheme scheme,
    required List<_CommandMapPin> pins,
  }) {
    if (pins.isEmpty) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Text(
            'No screen locations found yet. Add locations in your dashboard and the map pins will show here.',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: scheme.onSurfaceVariant,
            ),
          ),
        ),
      );
    }

    final onlineCount =
        pins.where((pin) => pin.status.toLowerCase() == 'online').length;
    final offlineCount = pins.length - onlineCount;
    final points = pins.map((pin) => pin.point).toList();

    return Card(
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
                    color: const Color(0xFFDBEAFE),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.map_outlined, size: 18),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'Screens Location',
                    style: theme.textTheme.titleMedium,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              'Live screen location pins by online and offline status. Tap a pin to open commands.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: scheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 12),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  Chip(
                    backgroundColor: const Color(0xFFDBEAFE),
                    avatar: const Icon(Icons.place_outlined, size: 14),
                    label:
                        Text('Pins: ${pins.length}', style: theme.textTheme.bodySmall),
                  ),
                  const SizedBox(width: 6),
                  Chip(
                    backgroundColor: const Color(0xFFDCFCE7),
                    avatar: const Icon(Icons.wifi_tethering, size: 14),
                    label: Text(
                      'Online: $onlineCount',
                      style: theme.textTheme.bodySmall,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Chip(
                    backgroundColor: const Color(0xFFFEE2E2),
                    avatar: const Icon(Icons.wifi_off, size: 14),
                    label: Text(
                      'Offline: $offlineCount',
                      style: theme.textTheme.bodySmall,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              height: 280,
              child: ClipRRect(
                borderRadius: BorderRadius.circular(14),
                child: GoogleMap(
                  initialCameraPosition: CameraPosition(
                    target: points.first,
                    zoom: pins.length == 1 ? 13 : 10,
                  ),
                  mapType: MapType.hybrid,
                  myLocationButtonEnabled: false,
                  zoomControlsEnabled: false,
                  compassEnabled: true,
                  onMapCreated: (controller) {
                    if (pins.length > 1) {
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
                  markers: pins
                      .map(
                        (pin) => Marker(
                          markerId: MarkerId(pin.deviceId),
                          position: pin.point,
                          infoWindow: InfoWindow(
                            title: pin.screenName,
                            snippet: pin.storeName,
                            onTap: () => _openScreenActions(pin),
                          ),
                          icon: BitmapDescriptor.defaultMarkerWithHue(
                            pin.status.toLowerCase() == 'online'
                                ? BitmapDescriptor.hueGreen
                                : BitmapDescriptor.hueRed,
                          ),
                          onTap: () => _openScreenActions(pin),
                        ),
                      )
                      .toSet(),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCommandCards(ThemeData theme, ColorScheme scheme) {
    final devices = _screens.where((screen) {
      final deviceId = (screen['device_id'] ?? '').toString().trim();
      return deviceId.isNotEmpty && deviceId != 'Not Assigned';
    }).toList();

    if (devices.isEmpty) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Text(
            'No connected screens found yet.',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: scheme.onSurfaceVariant,
            ),
          ),
        ),
      );
    }

    return Column(
      children: devices.map((screen) {
        final deviceId = (screen['device_id'] ?? '-').toString().trim();
        final storeName = (screen['store_name'] ?? screen['store_id'] ?? '-')
            .toString()
            .trim();
        final screenName = (screen['screen_name'] ?? screen['screen_id'] ?? '-')
            .toString()
            .trim();
        final status = (screen['status'] ?? 'offline').toString().trim();
        final location = (screen['location'] ?? '').toString().trim();
        final online = status.toLowerCase() == 'online';

        return Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.tv),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          deviceId,
                          style: theme.textTheme.titleMedium,
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 4,
                        ),
                        decoration: BoxDecoration(
                          color: online
                              ? scheme.primaryContainer
                              : scheme.surfaceContainerHighest,
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: Text(
                          status,
                          style: TextStyle(
                            color: online
                                ? scheme.onPrimaryContainer
                                : scheme.onSurfaceVariant,
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    '$storeName • $screenName',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                  if (location.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Text(
                      location,
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
                      FilledButton(
                        style: FilledButton.styleFrom(
                          backgroundColor: const Color(0xFF2563EB),
                          foregroundColor: Colors.white,
                        ),
                        onPressed: () => _send(deviceId, 'refresh_screen'),
                        child: const Text('Refresh'),
                      ),
                      FilledButton(
                        style: FilledButton.styleFrom(
                          backgroundColor: const Color(0xFF16A34A),
                          foregroundColor: Colors.white,
                        ),
                        onPressed: () => _send(deviceId, 'reload_playlist'),
                        child: const Text('Reload'),
                      ),
                      OutlinedButton(
                        style: OutlinedButton.styleFrom(
                          foregroundColor: const Color(0xFF7C3AED),
                          side: const BorderSide(
                            color: Color(0xFF7C3AED),
                          ),
                        ),
                        onPressed: () => _send(deviceId, 'restart_app'),
                        child: const Text('Restart App'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildCommandsBody(ThemeData theme, ColorScheme scheme) {
    return FutureBuilder<List<_CommandMapPin>>(
      future: _buildPins(),
      builder: (context, snapshot) {
        if (_loading || snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }

        final pins = snapshot.data ?? const <_CommandMapPin>[];
        return ListView(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
          children: [
            _buildMapSection(theme: theme, scheme: scheme, pins: pins),
            const SizedBox(height: 12),
            Text('Screen Commands', style: theme.textTheme.titleMedium),
            const SizedBox(height: 10),
            _buildCommandCards(theme, scheme),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
          child: Row(
            children: [
              Container(
                height: 34,
                width: 34,
                decoration: BoxDecoration(
                  color: scheme.primaryContainer,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(
                  Icons.cast_connected,
                  color: scheme.onPrimaryContainer,
                  size: 18,
                ),
              ),
              const SizedBox(width: 10),
              Text('Commands', style: theme.textTheme.titleLarge),
              const Spacer(),
              IconButton(
                onPressed: _loading ? null : _loadDevices,
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
        ),
        if (_message != null)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: scheme.surfaceContainer,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(_message!),
            ),
          ),
        const SizedBox(height: 8),
        Expanded(
          child: _buildCommandsBody(theme, scheme),
        ),
      ],
    );
  }
}

class _CommandMapPin {
  const _CommandMapPin({
    required this.deviceId,
    required this.storeName,
    required this.screenName,
    required this.status,
    required this.locationLabel,
    required this.point,
  });

  final String deviceId;
  final String storeName;
  final String screenName;
  final String status;
  final String locationLabel;
  final LatLng point;
}

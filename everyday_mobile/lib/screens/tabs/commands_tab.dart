import 'package:flutter/material.dart';
import 'package:geocoding/geocoding.dart' as geocoding;
import 'package:google_maps_flutter/google_maps_flutter.dart';

import '../../models/app_models.dart';
import '../../services/api_client.dart';
import '../../services/tv_discovery_service.dart';

enum CommandsMode { tv, remote }

class _RemoteProfile {
  const _RemoteProfile({
    required this.brand,
    required this.transport,
    required this.status,
    required this.notes,
    required this.ready,
    required this.powerReady,
  });

  final String brand;
  final String transport;
  final String status;
  final String notes;
  final bool ready;
  final bool powerReady;
}

const _remoteProfiles = [
  _RemoteProfile(
    brand: 'Android / Google TV',
    transport: 'Wi-Fi bridge',
    status: 'Ready',
    notes: 'Uses the installed EverydayAdvertise TV app and server connection.',
    ready: true,
    powerReady: false,
  ),
  _RemoteProfile(
    brand: 'Samsung',
    transport: 'SmartThings / IR',
    status: 'Setup required',
    notes:
        'Needs SmartThings authorization and the TV device ID, or an IR hub.',
    ready: false,
    powerReady: true,
  ),
  _RemoteProfile(
    brand: 'LG',
    transport: 'webOS / IR',
    status: 'Setup required',
    notes: 'Needs a paired webOS controller or an IR hub for power control.',
    ready: false,
    powerReady: true,
  ),
  _RemoteProfile(
    brand: 'Sony',
    transport: 'BRAVIA IP / IR',
    status: 'Setup required',
    notes:
        'Needs IP control enabled with the TV address and authentication key.',
    ready: false,
    powerReady: true,
  ),
  _RemoteProfile(
    brand: 'TCL',
    transport: 'Roku / Google TV / IR',
    status: 'Setup required',
    notes: 'The TV operating system must be selected before connecting.',
    ready: false,
    powerReady: true,
  ),
  _RemoteProfile(
    brand: 'Hisense',
    transport: 'VIDAA / Google TV / IR',
    status: 'Setup required',
    notes: 'The TV operating system and model determine the control adapter.',
    ready: false,
    powerReady: true,
  ),
  _RemoteProfile(
    brand: 'Vizio',
    transport: 'SmartCast / IR',
    status: 'Setup required',
    notes: 'Needs SmartCast pairing or an IR hub.',
    ready: false,
    powerReady: true,
  ),
  _RemoteProfile(
    brand: 'Panasonic',
    transport: 'IP / HDMI-CEC / IR',
    status: 'Setup required',
    notes: 'Power control depends on the exact regional TV model.',
    ready: false,
    powerReady: true,
  ),
  _RemoteProfile(
    brand: 'Philips',
    transport: 'Android TV / IP / IR',
    status: 'Setup required',
    notes: 'Needs the TV operating system and exact model series.',
    ready: false,
    powerReady: true,
  ),
];

class CommandsTab extends StatefulWidget {
  const CommandsTab({
    super.key,
    required this.apiClient,
    this.initialMode = CommandsMode.tv,
  });

  final ApiClient apiClient;
  final CommandsMode initialMode;

  @override
  State<CommandsTab> createState() => _CommandsTabState();
}

class _CommandsTabState extends State<CommandsTab> {
  bool _loading = true;
  String? _message;
  List<Map<String, dynamic>> _screens = const [];
  final TextEditingController _tvPairCodeController = TextEditingController();
  final TextEditingController _linkCodeController = TextEditingController();
  final TextEditingController _storeCodeController = TextEditingController();
  bool _sendingTvCodes = false;
  bool _sendingTvScreen = false;
  List<ScreenItem> _pairingScreens = const [];
  String? _selectedPairingScreenId;
  final Map<String, LatLng?> _resolvedMapPoints = {};
  late CommandsMode _commandsMode;
  String _remoteConnection = 'Wi-Fi';
  String _remoteBrand = 'Android / Google TV';
  String? _selectedRemoteDeviceId;
  final TvDiscoveryService _tvDiscoveryService = TvDiscoveryService();
  List<DiscoveredTv> _discoveredTvs = const [];
  bool _discoveringTvs = false;

  @override
  void initState() {
    super.initState();
    _commandsMode = widget.initialMode;
    _loadDevices();
    _loadLinkCode();
  }

  @override
  void dispose() {
    _tvPairCodeController.dispose();
    _linkCodeController.dispose();
    _storeCodeController.dispose();
    super.dispose();
  }

  Future<void> _loadLinkCode() async {
    try {
      final profile = await widget.apiClient.getMe();
      if (!mounted || _linkCodeController.text.trim().isNotEmpty) {
        return;
      }
      _linkCodeController.text = (profile.linkCode ?? '').trim();
    } catch (_) {
      // The link code can still be entered manually.
    }
  }

  Future<void> _sendTvPairingCodes() async {
    final tvPairCode = _tvPairCodeController.text.trim();
    final linkCode = _linkCodeController.text.trim();
    final storeCode = _storeCodeController.text.trim();
    if (!RegExp(r'^\d{6}$').hasMatch(tvPairCode)) {
      setState(() {
        _message = 'Enter the 6-digit TV code shown on the TV.';
      });
      return;
    }
    if (!RegExp(r'^\d{4}$').hasMatch(linkCode) || storeCode.isEmpty) {
      setState(() {
        _message = 'Enter your 4-digit link code and store code.';
      });
      return;
    }

    setState(() {
      _sendingTvCodes = true;
      _message = null;
    });
    try {
      final connected = await widget.apiClient.sendTvPairingCodes(
        tvPairCode: tvPairCode,
        linkCode: linkCode,
        storeCode: storeCode,
      );
      List<ScreenItem> pairingScreens = const [];
      String? screenLoadError;
      try {
        pairingScreens = await widget.apiClient.getScreens(storeCode);
      } catch (e) {
        screenLoadError = e.toString().replaceFirst('Exception: ', '');
      }
      if (!mounted) {
        return;
      }
      setState(() {
        _pairingScreens = pairingScreens;
        _selectedPairingScreenId =
            pairingScreens.length == 1 ? pairingScreens.first.id : null;
        _message = screenLoadError ??
            (connected
                ? (pairingScreens.isEmpty
                    ? 'Codes sent. No screens were found for this store.'
                    : 'Codes sent. Choose a screen below.')
                : 'Codes queued. Keep the TV pairing screen open and try again if it does not update.');
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
          _sendingTvCodes = false;
        });
      }
    }
  }

  Future<void> _sendTvScreenSelection() async {
    final tvPairCode = _tvPairCodeController.text.trim();
    final storeCode = _storeCodeController.text.trim();
    final screenId = _selectedPairingScreenId;
    if (!RegExp(r'^\d{6}$').hasMatch(tvPairCode) ||
        storeCode.isEmpty ||
        screenId == null ||
        screenId.isEmpty) {
      setState(() {
        _message = 'Choose a screen before sending it to the TV.';
      });
      return;
    }

    setState(() {
      _sendingTvScreen = true;
      _message = null;
    });
    try {
      final connected = await widget.apiClient.sendTvScreenSelection(
        tvPairCode: tvPairCode,
        storeCode: storeCode,
        screenId: screenId,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _message = connected
            ? 'Screen $screenId sent to the TV.'
            : 'Screen selection queued. Keep the TV pairing flow open.';
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
          _sendingTvScreen = false;
        });
      }
    }
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

  Future<void> _scanNearbyTvs() async {
    if (_discoveringTvs) {
      return;
    }
    setState(() {
      _discoveringTvs = true;
      _message = null;
    });
    try {
      final devices = await _tvDiscoveryService.scan();
      if (!mounted) {
        return;
      }
      setState(() {
        _discoveredTvs = devices;
        _message = devices.isEmpty
            ? 'No compatible TV services were found on this Wi-Fi network.'
            : 'Found ${devices.length} nearby TV service${devices.length == 1 ? '' : 's'}.';
      });
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _message =
            'TV scan failed: ${e.toString().replaceFirst('Exception: ', '')}';
      });
    } finally {
      if (mounted) {
        setState(() {
          _discoveringTvs = false;
        });
      }
    }
  }

  Map<String, dynamic>? _registeredScreenForTv(DiscoveredTv tv) {
    for (final screen in _screens) {
      final deviceId = (screen['device_id'] ?? '').toString().trim();
      final ip = (screen['ip'] ?? '').toString().trim();
      if (deviceId.isNotEmpty &&
          deviceId != 'Not Assigned' &&
          ip == tv.address.address) {
        return screen;
      }
    }
    return null;
  }

  void _useDiscoveredTv(DiscoveredTv tv) {
    final registeredScreen = _registeredScreenForTv(tv);
    final profile = _remoteProfiles.where((item) => item.brand == tv.brand);
    setState(() {
      if (profile.isNotEmpty) {
        _remoteBrand = profile.first.brand;
      }
      if (registeredScreen == null) {
        _selectedRemoteDeviceId = null;
        _message =
            '${tv.name} was found at ${tv.address.address}, but it is not registered as an EverydayAdvertise TV yet. Open the TV app and complete pairing first.';
        return;
      }
      _selectedRemoteDeviceId = registeredScreen['device_id']?.toString();
      _message =
          '${tv.name} selected. The remote will use the registered TV connection.';
    });
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

  Future<void> _sendRemoteCommand(String command) async {
    final deviceId = _selectedRemoteDeviceId;
    if (deviceId == null || deviceId.isEmpty) {
      setState(() {
        _message = 'Choose an online TV before using the remote.';
      });
      return;
    }

    Map<String, dynamic>? device;
    for (final screen in _screens) {
      if (screen['device_id']?.toString() == deviceId) {
        device = screen;
        break;
      }
    }
    final status = (device?['status'] ?? 'offline').toString().toLowerCase();
    if (status != 'online') {
      setState(() {
        _message = 'This TV is offline. Connect it before using the remote.';
      });
      return;
    }

    try {
      await widget.apiClient.sendAndroidTvCommand(
        deviceId: deviceId,
        command: 'remote_$command',
      );
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

  Future<_CommandMapPin?> _resolvePinForScreen(
      Map<String, dynamic> screen) async {
    final deviceId = (screen['device_id'] ?? '').toString().trim();
    if (deviceId.isEmpty || deviceId == 'Not Assigned') {
      return null;
    }

    final storeName =
        (screen['store_name'] ?? screen['store_id'] ?? '-').toString().trim();
    final screenName =
        (screen['screen_name'] ?? screen['screen_id'] ?? '-').toString().trim();
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
                    label: Text('Pins: ${pins.length}',
                        style: theme.textTheme.bodySmall),
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

  Widget _buildRemoteBody(ThemeData theme, ColorScheme scheme) {
    final profile = _remoteProfiles.firstWhere(
      (item) => item.brand == _remoteBrand,
    );
    final remoteDevices = _screens.where((screen) {
      final deviceId = (screen['device_id'] ?? '').toString().trim();
      return deviceId.isNotEmpty && deviceId != 'Not Assigned';
    }).toList();
    final selectedDeviceId = remoteDevices.any(
      (screen) => screen['device_id']?.toString() == _selectedRemoteDeviceId,
    )
        ? _selectedRemoteDeviceId
        : null;
    final selectedDevice = selectedDeviceId == null
        ? null
        : remoteDevices.firstWhere(
            (screen) => screen['device_id']?.toString() == selectedDeviceId,
          );
    final selectedOnline =
        (selectedDevice?['status'] ?? '').toString().toLowerCase() == 'online';
    final remoteEnabled =
        profile.ready && selectedDeviceId != null && selectedOnline;

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 20),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.settings_remote_rounded, color: scheme.primary),
                    const SizedBox(width: 8),
                    Text('Universal remote',
                        style: theme.textTheme.titleMedium),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  'Scan this Wi-Fi network for compatible TVs. Registered EverydayAdvertise TVs can be controlled here; other brands may still require their pairing app or IR hardware.',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: scheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 14),
                DropdownButtonFormField<String>(
                  value: _remoteBrand,
                  decoration: InputDecoration(
                    labelText: 'TV brand / platform',
                    prefixIcon: const Icon(Icons.tv_rounded),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  items: _remoteProfiles.map((item) {
                    return DropdownMenuItem<String>(
                      value: item.brand,
                      child: Text(item.brand),
                    );
                  }).toList(),
                  onChanged: (value) {
                    if (value == null) {
                      return;
                    }
                    setState(() {
                      _remoteBrand = value;
                      if (!_remoteProfiles
                          .firstWhere((item) => item.brand == value)
                          .ready) {
                        _message =
                            'This brand still needs its connection setup.';
                      }
                    });
                  },
                ),
                const SizedBox(height: 10),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: profile.ready
                        ? scheme.primaryContainer
                        : scheme.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(
                            profile.ready
                                ? Icons.check_circle_rounded
                                : Icons.info_outline_rounded,
                            size: 18,
                            color: profile.ready
                                ? scheme.onPrimaryContainer
                                : scheme.onSurfaceVariant,
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              '${profile.status} · ${profile.transport}',
                              style: theme.textTheme.titleSmall?.copyWith(
                                color: profile.ready
                                    ? scheme.onPrimaryContainer
                                    : scheme.onSurfaceVariant,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(
                        profile.notes,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: profile.ready
                              ? scheme.onPrimaryContainer
                              : scheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 14),
                SegmentedButton<String>(
                  segments: const [
                    ButtonSegment<String>(
                      value: 'Wi-Fi',
                      icon: Icon(Icons.wifi_rounded),
                      label: Text('Wi-Fi'),
                    ),
                    ButtonSegment<String>(
                      value: 'Bluetooth',
                      icon: Icon(Icons.bluetooth_rounded),
                      label: Text('Bluetooth'),
                    ),
                  ],
                  selected: {_remoteConnection},
                  onSelectionChanged: (selection) {
                    setState(() {
                      _remoteConnection = selection.first;
                      if (_remoteConnection == 'Bluetooth') {
                        _message =
                            'Bluetooth is available for supported TV accessories. Smart-TV discovery and commands use Wi-Fi.';
                      }
                    });
                  },
                ),
                const SizedBox(height: 14),
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        'Nearby TVs',
                        style: theme.textTheme.titleSmall,
                      ),
                    ),
                    FilledButton.tonalIcon(
                      onPressed: _discoveringTvs ? null : _scanNearbyTvs,
                      icon: _discoveringTvs
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.wifi_find_rounded),
                      label: Text(_discoveringTvs ? 'Scanning' : 'Scan Wi-Fi'),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                if (_discoveredTvs.isEmpty)
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: scheme.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      'Tap Scan Wi-Fi to find TVs without entering an IP address. Your phone and TV must be on the same network.',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                    ),
                  )
                else
                  ..._discoveredTvs.map((tv) {
                    final registered = _registeredScreenForTv(tv) != null;
                    return Card(
                      margin: const EdgeInsets.only(bottom: 6),
                      child: ListTile(
                        dense: true,
                        leading: const Icon(Icons.tv_rounded),
                        title: Text(tv.name),
                        subtitle: Text(
                          '${tv.brand} · ${tv.address.address}:${tv.port}',
                        ),
                        trailing: TextButton(
                          onPressed: () => _useDiscoveredTv(tv),
                          child: Text(registered ? 'Use' : 'Pair'),
                        ),
                      ),
                    );
                  }),
                const SizedBox(height: 8),
                if (_remoteConnection == 'Wi-Fi' && remoteDevices.isNotEmpty)
                  DropdownButtonFormField<String>(
                    value: selectedDeviceId,
                    decoration: InputDecoration(
                      labelText: 'Connected TV',
                      prefixIcon: const Icon(Icons.tv_rounded),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    hint: const Text('Choose a TV'),
                    items: remoteDevices.map((screen) {
                      final deviceId = screen['device_id'].toString();
                      final name =
                          (screen['screen_name'] ?? deviceId).toString();
                      final status = (screen['status'] ?? 'offline').toString();
                      return DropdownMenuItem<String>(
                        value: deviceId,
                        child: Text('$name · $status'),
                      );
                    }).toList(),
                    onChanged: (value) {
                      setState(() {
                        _selectedRemoteDeviceId = value;
                      });
                    },
                  )
                else
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: scheme.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      _remoteConnection == 'Bluetooth'
                          ? 'Bluetooth TV discovery is not configured yet. Use Wi-Fi with a connected screen for now.'
                          : 'No TV devices found. Pair a TV first, then refresh this page.',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                const SizedBox(height: 10),
                OutlinedButton.icon(
                  onPressed: _loading ? null : _loadDevices,
                  icon: const Icon(Icons.refresh_rounded),
                  label: const Text('Refresh TV list'),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        _buildRemoteControlSurface(
          theme,
          scheme,
          enabled: remoteEnabled,
          powerEnabled: remoteEnabled && profile.powerReady,
        ),
      ],
    );
  }

  Widget _buildRemoteControlSurface(
    ThemeData theme,
    ColorScheme scheme, {
    required bool enabled,
    required bool powerEnabled,
  }) {
    Widget action({
      required IconData icon,
      required String label,
      required String command,
      Color? color,
      bool? enabledOverride,
    }) {
      final actionEnabled = enabledOverride ?? enabled;
      return OutlinedButton(
        onPressed: actionEnabled ? () => _sendRemoteCommand(command) : null,
        style: OutlinedButton.styleFrom(
          foregroundColor: color,
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 22),
            const SizedBox(height: 4),
            Text(label, style: const TextStyle(fontSize: 11)),
          ],
        ),
      );
    }

    Widget direction({
      required IconData icon,
      required String command,
    }) {
      return IconButton.filledTonal(
        onPressed: enabled ? () => _sendRemoteCommand(command) : null,
        icon: Icon(icon),
        tooltip: command,
      );
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.gamepad_rounded, color: scheme.primary),
                const SizedBox(width: 8),
                Text('TV remote', style: theme.textTheme.titleMedium),
                const Spacer(),
                if (!enabled)
                  Text(
                    'Connect a TV first',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 14),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                action(
                  icon: Icons.power_settings_new_rounded,
                  label: 'Power',
                  command: 'power',
                  color: scheme.error,
                  enabledOverride: powerEnabled,
                ),
                action(
                  icon: Icons.input_rounded,
                  label: 'Input',
                  command: 'input',
                ),
                action(
                  icon: Icons.volume_off_rounded,
                  label: 'Mute',
                  command: 'mute',
                ),
              ],
            ),
            const SizedBox(height: 16),
            Center(
                child: direction(icon: Icons.keyboard_arrow_up, command: 'up')),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                direction(icon: Icons.keyboard_arrow_left, command: 'left'),
                const SizedBox(width: 24),
                FilledButton(
                  onPressed:
                      enabled ? () => _sendRemoteCommand('select') : null,
                  style: FilledButton.styleFrom(
                    shape: const CircleBorder(),
                    padding: const EdgeInsets.all(20),
                  ),
                  child: const Text('OK'),
                ),
                const SizedBox(width: 24),
                direction(icon: Icons.keyboard_arrow_right, command: 'right'),
              ],
            ),
            Center(
                child: direction(
                    icon: Icons.keyboard_arrow_down, command: 'down')),
            const SizedBox(height: 14),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                action(
                  icon: Icons.home_rounded,
                  label: 'Home',
                  command: 'home',
                ),
                action(
                  icon: Icons.arrow_back_rounded,
                  label: 'Back',
                  command: 'back',
                ),
                action(
                  icon: Icons.menu_rounded,
                  label: 'Menu',
                  command: 'menu',
                ),
              ],
            ),
            const SizedBox(height: 14),
            Row(
              children: [
                Expanded(
                  child: FilledButton.tonalIcon(
                    onPressed: enabled
                        ? () => _sendRemoteCommand('volume_down')
                        : null,
                    icon: const Icon(Icons.volume_down_rounded),
                    label: const Text('Volume −'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: FilledButton.tonalIcon(
                    onPressed:
                        enabled ? () => _sendRemoteCommand('volume_up') : null,
                    icon: const Icon(Icons.volume_up_rounded),
                    label: const Text('Volume +'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: FilledButton.tonalIcon(
                    onPressed: enabled
                        ? () => _sendRemoteCommand('channel_down')
                        : null,
                    icon: const Icon(Icons.keyboard_arrow_down_rounded),
                    label: const Text('Channel −'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: FilledButton.tonalIcon(
                    onPressed:
                        enabled ? () => _sendRemoteCommand('channel_up') : null,
                    icon: const Icon(Icons.keyboard_arrow_up_rounded),
                    label: const Text('Channel +'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            Text(
              'Remote buttons send brand-specific commands through the connected TV bridge. Wi-Fi and Bluetooth support must be enabled by the TV device integration.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: scheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
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
            _buildTvPairingSection(theme, scheme),
            const SizedBox(height: 12),
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

  Widget _buildTvPairingSection(ThemeData theme, ColorScheme scheme) {
    InputDecoration fieldDecoration(String label, String hint) {
      return InputDecoration(
        labelText: label,
        hintText: hint,
        filled: true,
        fillColor: scheme.surfaceContainerLowest,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
      );
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.link_rounded, color: scheme.primary),
                const SizedBox(width: 8),
                Text('Connect a TV', style: theme.textTheme.titleMedium),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              'Enter the unique TV code, then send your link code and store code to the pairing screen.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: scheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _tvPairCodeController,
              keyboardType: TextInputType.number,
              maxLength: 6,
              decoration: fieldDecoration('TV code', '6-digit code on TV'),
            ),
            const SizedBox(height: 4),
            TextField(
              controller: _linkCodeController,
              keyboardType: TextInputType.number,
              maxLength: 4,
              decoration: fieldDecoration('Your link code', '4-digit code'),
            ),
            const SizedBox(height: 4),
            TextField(
              controller: _storeCodeController,
              keyboardType: TextInputType.number,
              maxLength: 8,
              decoration: fieldDecoration('Store code', 'For example 1000'),
            ),
            const SizedBox(height: 4),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: _sendingTvCodes ? null : _sendTvPairingCodes,
                icon: _sendingTvCodes
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.send_rounded),
                label: Text(_sendingTvCodes ? 'Sending…' : 'Send to TV'),
              ),
            ),
            if (_pairingScreens.isNotEmpty) ...[
              const SizedBox(height: 14),
              Divider(color: scheme.outlineVariant),
              const SizedBox(height: 8),
              Text(
                'Choose a screen for this TV',
                style: theme.textTheme.titleSmall,
              ),
              const SizedBox(height: 4),
              ..._pairingScreens.map(
                (screen) => RadioListTile<String>(
                  contentPadding: EdgeInsets.zero,
                  value: screen.id,
                  groupValue: _selectedPairingScreenId,
                  onChanged: _sendingTvScreen
                      ? null
                      : (value) {
                          setState(() {
                            _selectedPairingScreenId = value;
                          });
                        },
                  title: Text(screen.name),
                  subtitle: Text(screen.id),
                ),
              ),
              const SizedBox(height: 4),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: _sendingTvScreen ? null : _sendTvScreenSelection,
                  icon: _sendingTvScreen
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.tv_rounded),
                  label: Text(
                    _sendingTvScreen ? 'Sending…' : 'Send selected screen',
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    Widget modeButton({
      required IconData icon,
      required String tooltip,
      required CommandsMode mode,
    }) {
      final selected = _commandsMode == mode;
      return IconButton(
        tooltip: tooltip,
        onPressed: () {
          setState(() {
            _commandsMode = mode;
          });
        },
        style: IconButton.styleFrom(
          backgroundColor:
              selected ? scheme.primaryContainer : scheme.surfaceContainer,
          foregroundColor:
              selected ? scheme.onPrimaryContainer : scheme.onSurfaceVariant,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
        icon: Icon(icon),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
          child: Row(
            children: [
              modeButton(
                icon: Icons.tv_rounded,
                tooltip: 'TV commands',
                mode: CommandsMode.tv,
              ),
              const SizedBox(width: 8),
              modeButton(
                icon: Icons.settings_remote_rounded,
                tooltip: 'Universal remote',
                mode: CommandsMode.remote,
              ),
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
          child: _commandsMode == CommandsMode.tv
              ? _buildCommandsBody(theme, scheme)
              : _buildRemoteBody(theme, scheme),
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

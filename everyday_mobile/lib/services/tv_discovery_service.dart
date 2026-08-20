import 'dart:convert';
import 'dart:async';
import 'dart:io';

import 'package:bonsoir/bonsoir.dart';

class DiscoveredTv {
  const DiscoveredTv({
    required this.id,
    required this.name,
    required this.brand,
    required this.address,
    required this.port,
    required this.serviceType,
    this.txt = const <String, String>{},
    this.hostname,
  });

  final String id;
  final String name;
  final String brand;
  final InternetAddress address;
  final int port;
  final String serviceType;

  /// mDNS TXT attributes. Our own TVs publish store_id, screen_id, device_id
  /// and pair_code here, which is how a discovered TV is matched to a screen
  /// already registered to the account rather than guessed at by name.
  final Map<String, String> txt;

  /// The name the service resolved to, e.g. "living-room.local". Kept because
  /// some platforms hand back a hostname rather than a numeric address, and
  /// dropping the TV in that case would be worse than showing it unaddressed.
  final String? hostname;

  /// True for a TV running our own app, as opposed to a third-party set.
  bool get isOwnApp =>
      serviceType == TvDiscoveryService.ownServiceType ||
      txt['app'] == 'everydayadvertise-tv';

  String? get storeId => _clean(txt['store_id']);
  String? get screenId => _clean(txt['screen_id']);
  String? get deviceId => _clean(txt['device_id']);

  static String? _clean(String? value) {
    final trimmed = (value ?? '').trim();
    return trimmed.isEmpty ? null : trimmed;
  }

  String get protocol => serviceType
      .replaceAll(RegExp(r'\.local\.?$'), '')
      .replaceFirst(RegExp(r'^_'), '')
      .replaceAll('._tcp', ' TCP')
      .replaceAll('._udp', ' UDP');
}

class TvDiscoveryService {
  /// Our own TVs first: the Android TV app registers this via NsdManager, and
  /// it is the only type guaranteed to identify a screen already on the account.
  /// Must also appear in ios/Runner/Info.plist NSBonjourServices - iOS silently
  /// refuses to query a type that is not declared there.
  static const ownServiceType = '_everydayadvertise._tcp.local';

  static const _knownServiceTypes = <String>{
    ownServiceType,
    '_airplay._tcp.local',
    '_androidtvremote2._tcp.local',
    '_googlecast._tcp.local',
    '_samsungmsf._tcp.local',
    '_webos-second-screen._tcp.local',
    '_roku-ecp._tcp.local',
    '_viziocast._tcp.local',
    '_sony-bravia._tcp.local',
  };

  /// Find TVs advertising over mDNS/Bonjour on the current Wi-Fi network.
  ///
  /// Uses the platform's own Bonjour stack (NSNetServiceBrowser on iOS,
  /// NsdManager on Android) rather than opening a multicast socket directly.
  /// That matters on iPhone: raw multicast requires the
  /// com.apple.developer.networking.multicast entitlement, which Apple grants
  /// only on request, so a socket-based scan silently returned nothing however
  /// correct Info.plist looked. Declaring each type in NSBonjourServices is
  /// enough for the native API - and it is also mandatory, since iOS refuses to
  /// browse a type that is not listed there.
  Future<List<DiscoveredTv>> scan({
    Duration timeout = const Duration(seconds: 6),
  }) async {
    final discovered = <String, DiscoveredTv>{};
    final deadline = DateTime.now().add(timeout);

    // All types at once: each browse is cheap and waiting on them in turn would
    // spend the whole budget on the first few.
    await Future.wait([
      for (final serviceType in _knownServiceTypes)
        _browse(serviceType, discovered, deadline),
    ]);

    final ssdpBudget = deadline.difference(DateTime.now());
    if (ssdpBudget > Duration.zero) {
      // Android only in practice - iOS blocks the raw multicast SSDP needs.
      for (final tv in await _scanSsdp(
        timeout: _boundedDuration(ssdpBudget, const Duration(seconds: 2)),
      )) {
        _addDiscovered(discovered, tv);
      }
    }

    final results = discovered.values.toList()
      ..sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
    return results;
  }

  /// Browse one service type until [deadline], resolving whatever turns up.
  ///
  /// One failing type must not abort the others - a platform that refuses a
  /// particular type should cost us that type, not the whole scan.
  Future<void> _browse(
    String serviceType,
    Map<String, DiscoveredTv> discovered,
    DateTime deadline,
  ) async {
    final remaining = deadline.difference(DateTime.now());
    if (remaining <= Duration.zero) {
      return;
    }
    // Bonsoir wants the bare type; our set carries the mDNS ".local" suffix.
    final bonsoirType = serviceType.replaceAll(RegExp(r'\.local\.?$'), '');
    BonsoirDiscovery? discovery;
    StreamSubscription<BonsoirDiscoveryEvent>? subscription;
    try {
      discovery = BonsoirDiscovery(type: bonsoirType, printLogs: false);
      await discovery.ready;
      final stream = discovery.eventStream;
      if (stream == null) {
        return;
      }
      final resolver = discovery.serviceResolver;
      subscription = stream.listen((event) {
        final service = event.service;
        if (service == null) {
          return;
        }
        if (event.type == BonsoirDiscoveryEventType.discoveryServiceFound) {
          // Found only gives a name; resolving is what yields host and TXT.
          unawaited(Future<void>.sync(() => service.resolve(resolver))
              .catchError((Object _) {}));
          return;
        }
        if (event.type == BonsoirDiscoveryEventType.discoveryServiceResolved &&
            service is ResolvedBonsoirService) {
          final tv = _fromResolved(service, serviceType);
          if (tv != null) {
            _addDiscovered(discovered, tv);
          }
        }
      });
      await discovery.start();
      await Future<void>.delayed(deadline.difference(DateTime.now()));
    } catch (_) {
      // See the doc comment - swallow and let the other types report.
    } finally {
      await subscription?.cancel();
      try {
        await discovery?.stop();
      } catch (_) {}
    }
  }

  /// Turn a resolved Bonjour service into a [DiscoveredTv], or null if it has
  /// no usable address.
  DiscoveredTv? _fromResolved(ResolvedBonsoirService service, String serviceType) {
    final host = (service.host ?? '').trim();
    if (host.isEmpty) {
      return null;
    }
    // Some platforms resolve to a hostname such as "living-room.local" rather
    // than a numeric address. Keep the TV in the list either way - hostname
    // above preserves what we were actually given.
    final address = InternetAddress.tryParse(host) ?? InternetAddress.anyIPv4;
    final attributes = <String, String>{
      for (final entry in service.attributes.entries)
        entry.key.toLowerCase(): entry.value,
    };
    return DiscoveredTv(
      id: '$serviceType/${service.name}',
      name: _displayName(service.name),
      brand: _brandFor(serviceType, service.name),
      address: address,
      port: service.port,
      serviceType: serviceType,
      txt: attributes,
      hostname: host,
    );
  }

  Future<List<DiscoveredTv>> _scanSsdp({required Duration timeout}) async {
    if (timeout <= Duration.zero) {
      return const [];
    }
    final socket = await RawDatagramSocket.bind(
      InternetAddress.anyIPv4,
      0,
      reuseAddress: true,
      ttl: 1,
    );
    final results = <String, DiscoveredTv>{};
    final target = InternetAddress('239.255.255.250');
    const request = 'M-SEARCH * HTTP/1.1\r\n'
        'HOST: 239.255.255.250:1900\r\n'
        'MAN: "ssdp:discover"\r\n'
        'MX: 2\r\n'
        'ST: ssdp:all\r\n\r\n';

    void receive() {
      Datagram? datagram;
      while ((datagram = socket.receive()) != null) {
        final response = utf8.decode(datagram!.data, allowMalformed: true);
        final headers = <String, String>{};
        for (final line in response.split(RegExp(r'\r?\n'))) {
          final separator = line.indexOf(':');
          if (separator <= 0) {
            continue;
          }
          headers[line.substring(0, separator).trim().toLowerCase()] =
              line.substring(separator + 1).trim();
        }
        final location = Uri.tryParse(headers['location'] ?? '');
        if (location == null || location.host.isEmpty) {
          continue;
        }
        final fingerprint = [
          headers['server'],
          headers['st'],
          headers['usn'],
          location.toString(),
        ].whereType<String>().join(' ').toLowerCase();
        if (!_looksLikeTv(fingerprint)) {
          continue;
        }
        final name = (headers['server'] ?? location.host).trim();
        _addDiscovered(
          results,
          DiscoveredTv(
            id: headers['usn'] ?? location.toString(),
            name: name,
            brand: _brandFor(fingerprint, name),
            address: InternetAddress(location.host),
            port: location.port == 0 ? 80 : location.port,
            serviceType: 'ssdp',
          ),
        );
      }
    }

    final subscription = socket.listen((event) {
      if (event == RawSocketEvent.read) {
        receive();
      }
    });
    socket.send(utf8.encode(request), target, 1900);
    await Future<void>.delayed(timeout);
    receive();
    await subscription.cancel();
    socket.close();
    return results.values.toList();
  }


  static String _displayName(String value) {
    final withoutLocal = value.replaceFirst(RegExp(r'\.local\.?$'), '');
    final separator = withoutLocal.indexOf('._');
    final name =
        separator > 0 ? withoutLocal.substring(0, separator) : withoutLocal;
    return name.replaceAll(RegExp(r'\\032'), ' ').trim();
  }

  static String _brandFor(String serviceType, String name) {
    if (serviceType == ownServiceType) {
      return 'EverydayAdvertise TV';
    }
    final value = '${serviceType}_$name'.toLowerCase();
    if (value.contains('samsung')) return 'Samsung';
    if (value.contains('webos') || value.contains('lg')) return 'LG';
    if (value.contains('bravia') || value.contains('sony')) return 'Sony';
    if (value.contains('roku')) return 'TCL / Roku';
    if (value.contains('vizio')) return 'Vizio';
    if (value.contains('hisense')) return 'Hisense';
    if (value.contains('panasonic')) return 'Panasonic';
    if (value.contains('philips')) return 'Philips';
    if (value.contains('googlecast') ||
        value.contains('androidtv') ||
        value.contains('chromecast')) {
      return 'Android / Google TV';
    }
    if (value.contains('airplay')) return 'AirPlay TV';
    return 'Network TV';
  }

  static bool _looksLikeTv(String value) {
    const tvTerms = [
      'androidtv',
      'bravia',
      'chromecast',
      'hisense',
      'lg webos',
      'roku',
      'samsung',
      'smart tv',
      'smart-tv',
      'sony',
      'tcl',
      'television',
      'vizio',
      'webos',
    ];
    return tvTerms.any(value.contains);
  }

  static void _addDiscovered(
    Map<String, DiscoveredTv> devices,
    DiscoveredTv device,
  ) {
    final key = device.address.address;
    final existing = devices[key];
    if (existing == null ||
        (existing.brand == 'Network TV' && device.brand != 'Network TV')) {
      devices[key] = device;
    }
  }

  static Duration _boundedDuration(Duration value, Duration maximum) {
    return value < maximum ? value : maximum;
  }

  /// TXT attributes for a service instance, as a plain key/value map.
}

import 'dart:convert';
import 'dart:async';
import 'dart:io';

import 'package:multicast_dns/multicast_dns.dart';

class DiscoveredTv {
  const DiscoveredTv({
    required this.id,
    required this.name,
    required this.brand,
    required this.address,
    required this.port,
    required this.serviceType,
    this.txt = const <String, String>{},
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

  Future<List<DiscoveredTv>> scan({
    Duration timeout = const Duration(seconds: 6),
  }) async {
    final client = MDnsClient();
    final discovered = <String, DiscoveredTv>{};
    final serviceTypes = <String>{..._knownServiceTypes};
    final deadline = DateTime.now().add(timeout);

    try {
      await client.start();
      final discoveredTypes = await _collect<PtrResourceRecord>(
        client.lookup<PtrResourceRecord>(
          ResourceRecordQuery.serverPointer('_services._dns-sd._udp.local'),
        ),
        const Duration(milliseconds: 1200),
      );
      for (final record in discoveredTypes) {
        final type = _normaliseServiceType(record.domainName);
        if (type != null) {
          serviceTypes.add(type);
        }
      }

      for (final serviceType in serviceTypes) {
        if (DateTime.now().isAfter(deadline)) {
          break;
        }
        final records = await _lookupService(
          client,
          serviceType,
          remaining: deadline.difference(DateTime.now()),
        );
        for (final tv in records) {
          _addDiscovered(discovered, tv);
        }
      }
      for (final tv in await _scanSsdp(timeout: const Duration(seconds: 2))) {
        _addDiscovered(discovered, tv);
      }
    } finally {
      client.stop();
    }

    final results = discovered.values.toList()
      ..sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
    return results;
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

  Future<List<DiscoveredTv>> _lookupService(
    MDnsClient client,
    String serviceType, {
    required Duration remaining,
  }) async {
    if (remaining <= Duration.zero) {
      return const [];
    }
    final pointers = await _collect<PtrResourceRecord>(
      client.lookup<PtrResourceRecord>(
        ResourceRecordQuery.serverPointer(serviceType),
      ),
      _boundedDuration(remaining, const Duration(milliseconds: 900)),
    );
    final results = <DiscoveredTv>[];
    for (final pointer in pointers) {
      final records = await _collect<SrvResourceRecord>(
        client.lookup<SrvResourceRecord>(
          ResourceRecordQuery.service(pointer.domainName),
        ),
        const Duration(milliseconds: 700),
      );
      final txt = await _collectTxt(client, pointer.domainName);
      for (final srv in records) {
        final addresses = await _collect<IPAddressResourceRecord>(
          client.lookup<IPAddressResourceRecord>(
            ResourceRecordQuery.addressIPv4(srv.target),
          ),
          const Duration(milliseconds: 700),
        );
        for (final address in addresses) {
          results.add(
            DiscoveredTv(
              id: pointer.domainName,
              name: _displayName(pointer.domainName),
              brand: _brandFor(serviceType, pointer.domainName),
              address: address.address,
              port: srv.port,
              serviceType: serviceType,
              txt: txt,
            ),
          );
        }
      }
    }
    return results;
  }

  static String? _normaliseServiceType(String value) {
    final lower = value.toLowerCase();
    if (!lower.startsWith('_') ||
        (!lower.contains('._tcp') && !lower.contains('._udp'))) {
      return null;
    }
    return lower.endsWith('.local') ? lower : '$lower.local';
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
  ///
  /// Failure is not fatal: a TV without readable TXT still shows in the list,
  /// it just cannot be matched to a registered screen automatically.
  static Future<Map<String, String>> _collectTxt(
    MDnsClient client,
    String domainName,
  ) async {
    final result = <String, String>{};
    try {
      final records = await _collect<TxtResourceRecord>(
        client.lookup<TxtResourceRecord>(
          ResourceRecordQuery.text(domainName),
        ),
        const Duration(milliseconds: 700),
      );
      for (final record in records) {
        for (final line in record.text.split(RegExp('[\r\n\u0000]+'))) {
          final index = line.indexOf('=');
          if (index <= 0) {
            continue;
          }
          result[line.substring(0, index).trim().toLowerCase()] =
              line.substring(index + 1).trim();
        }
      }
    } catch (_) {
      // Ignore - see the doc comment.
    }
    return result;
  }

  static Future<List<T>> _collect<T extends ResourceRecord>(
    Stream<T> stream,
    Duration timeout,
  ) async {
    final values = <T>[];
    if (timeout <= Duration.zero) {
      return values;
    }
    try {
      await for (final value in stream.timeout(timeout)) {
        values.add(value);
      }
    } on TimeoutException {
      return values;
    } on SocketException {
      return values;
    }
    return values;
  }
}

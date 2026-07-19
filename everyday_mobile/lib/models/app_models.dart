class UserProfile {
  UserProfile({
    required this.username,
    this.fullName,
    this.linkCode,
  });

  final String username;
  final String? fullName;
  final String? linkCode;

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      username: (json['username'] ?? '').toString(),
      fullName: json['full_name']?.toString(),
      linkCode: json['link_code']?.toString(),
    );
  }
}

class StoreItem {
  StoreItem({
    required this.id,
    required this.name,
    this.address = '',
    this.latitude,
    this.longitude,
  });

  final String id;
  final String name;
  final String address;
  final double? latitude;
  final double? longitude;

  factory StoreItem.fromJson(Map<String, dynamic> json) {
    return StoreItem(
      id: (json['id'] ?? '').toString(),
      name: (json['name'] ?? json['id'] ?? '').toString(),
      address: (json['address'] ?? '').toString().trim(),
      latitude: double.tryParse((json['latitude'] ?? '').toString()),
      longitude: double.tryParse((json['longitude'] ?? '').toString()),
    );
  }
}

class StoreGroup {
  StoreGroup({
    required this.id,
    required this.name,
    this.storeIds = const [],
  });

  final String id;
  final String name;
  final List<String> storeIds;

  factory StoreGroup.fromJson(Map<String, dynamic> json) {
    final rawIds = json['store_ids'];
    return StoreGroup(
      id: (json['id'] ?? '').toString(),
      name: (json['name'] ?? '').toString(),
      storeIds: rawIds is List
          ? rawIds.map((item) => item.toString()).toList()
          : const [],
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'store_ids': storeIds,
      };
}

class ScreenItem {
  ScreenItem({
    required this.id,
    required this.name,
    this.rotation = 0,
    this.protected = false,
    this.muted = false,
    this.address = '',
    this.vertical = false,
    this.horizontal = true,
    this.panelZone = const {},
  });

  final String id;
  final String name;
  final int rotation;
  final bool protected;
  final bool muted;
  final String address;
  final bool vertical;
  final bool horizontal;
  final Map<String, dynamic> panelZone;

  factory ScreenItem.fromJson(String id, Map<String, dynamic> json) {
    final rawRotation = int.tryParse('${json['rotation'] ?? 0}') ?? 0;
    final normalizedRotation =
        <int>{0, 90, 180, 270}.contains(rawRotation) ? rawRotation : 0;
    final rawPanelZone = json['panel_zone'];
    return ScreenItem(
      id: id,
      name: (json['name'] ?? id).toString(),
      rotation: normalizedRotation,
      protected: (json['protected'] ?? false) == true,
      muted: (json['muted'] ?? false) == true,
      address: (json['address'] ?? '').toString().trim(),
      vertical: (json['vertical'] ?? false) == true,
      horizontal: (json['horizontal'] ?? true) != false,
      panelZone: rawPanelZone is Map
          ? rawPanelZone.map(
              (key, value) => MapEntry(key.toString(), value),
            )
          : const {},
    );
  }
}

class AndroidTvDevice {
  AndroidTvDevice({
    required this.id,
    required this.status,
    required this.storeName,
    required this.screenName,
  });

  final String id;
  final String status;
  final String storeName;
  final String screenName;

  factory AndroidTvDevice.fromJson(Map<String, dynamic> json) {
    return AndroidTvDevice(
      id: (json['id'] ?? '').toString(),
      status: (json['status'] ?? 'offline').toString(),
      storeName: (json['store_name'] ?? '').toString(),
      screenName: (json['screen_name'] ?? '').toString(),
    );
  }
}

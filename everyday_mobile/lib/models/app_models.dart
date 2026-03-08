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
  StoreItem({required this.id, required this.name});

  final String id;
  final String name;

  factory StoreItem.fromJson(Map<String, dynamic> json) {
    return StoreItem(
      id: (json['id'] ?? '').toString(),
      name: (json['name'] ?? json['id'] ?? '').toString(),
    );
  }
}

class ScreenItem {
  ScreenItem({required this.id, required this.name});

  final String id;
  final String name;

  factory ScreenItem.fromJson(String id, Map<String, dynamic> json) {
    return ScreenItem(
      id: id,
      name: (json['name'] ?? id).toString(),
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

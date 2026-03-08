import 'dart:io';

import 'package:cookie_jar/cookie_jar.dart';
import 'package:dio/dio.dart';
import 'package:dio_cookie_manager/dio_cookie_manager.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/app_models.dart';

class ApiClient {
  ApiClient();

  static const String _baseUrlKey = 'api_base_url';
  static const String _defaultBaseUrl = 'https://api.everydayadvertise.com';

  late final Dio _dio;
  final CookieJar _cookieJar = CookieJar();

  String _baseUrl = _defaultBaseUrl;

  String get baseUrl => _baseUrl;

  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _baseUrl = (prefs.getString(_baseUrlKey) ?? _defaultBaseUrl).trim();

    _dio = Dio(
      BaseOptions(
        baseUrl: _baseUrl,
        connectTimeout: const Duration(seconds: 20),
        receiveTimeout: const Duration(seconds: 30),
        followRedirects: true,
        validateStatus: (status) => status != null && status < 500,
      ),
    );
    _dio.interceptors.add(CookieManager(_cookieJar));
  }

  Future<void> setBaseUrl(String url) async {
    final normalized = url.trim().replaceAll(RegExp(r'/$'), '');
    if (normalized.isEmpty) {
      throw Exception('Base URL cannot be empty');
    }
    _baseUrl = normalized;
    _dio.options.baseUrl = normalized;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_baseUrlKey, normalized);
  }

  Future<bool> checkSession() async {
    try {
      final me = await getMe();
      return me.username.isNotEmpty;
    } catch (_) {
      return false;
    }
  }

  Future<void> login({required String username, required String password}) async {
    final response = await _dio.post(
      '/login',
      data: FormData.fromMap({
        'username': username,
        'password': password,
      }),
      options: Options(
        contentType: Headers.formUrlEncodedContentType,
      ),
    );

    if (response.statusCode == null || response.statusCode! >= 400) {
      throw Exception('Login failed');
    }

    final ok = await checkSession();
    if (!ok) {
      throw Exception('Login failed: invalid credentials or access denied');
    }
  }

  Future<void> logout() async {
    try {
      await _dio.get('/logout');
    } catch (_) {
      // no-op
    }
    final uri = Uri.parse(_dio.options.baseUrl);
    _cookieJar.deleteAll();
    _cookieJar.delete(uri);
  }

  Future<UserProfile> getMe() async {
    final response = await _dio.get('/api/me');
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Unable to load profile').toString());
    }
    return UserProfile.fromJson(data);
  }

  Future<List<StoreItem>> getStores() async {
    final response = await _dio.get('/stores');
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Unable to load stores').toString());
    }
    final list = (data['stores'] as List? ?? const [])
        .map((item) => StoreItem.fromJson(_asMap(item)))
        .where((item) => item.id.isNotEmpty)
        .toList();
    return list;
  }

  Future<List<ScreenItem>> getScreens(String storeId) async {
    final response = await _dio.get('/screens/$storeId');
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Unable to load screens').toString());
    }

    final screensMap = _asMap(data['screens']);
    final out = <ScreenItem>[];
    for (final entry in screensMap.entries) {
      out.add(ScreenItem.fromJson(entry.key, _asMap(entry.value)));
    }
    return out;
  }

  Future<String> uploadMedia(File file) async {
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(file.path, filename: file.uri.pathSegments.last),
    });

    final response = await _dio.post('/upload_media', data: formData);
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Upload failed').toString());
    }
    final filename = (data['filename'] ?? '').toString();
    if (filename.isEmpty) {
      throw Exception('Upload failed: missing filename');
    }
    return filename;
  }

  Future<void> assignToScreen({
    required String storeId,
    required String screenId,
    required String filename,
  }) async {
    final response = await _dio.post(
      '/assign_to_screen',
      data: {
        'store_id': storeId,
        'screen_id': screenId,
        'filename': filename,
      },
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Assign failed').toString());
    }
  }

  Future<List<AndroidTvDevice>> getAndroidTvDevices() async {
    final response = await _dio.get('/api/android_tv_status');
    final data = _asMap(response.data);

    final devices = (data['devices'] as List? ?? const [])
        .map((item) => AndroidTvDevice.fromJson(_asMap(item)))
        .where((item) => item.id.isNotEmpty)
        .toList();
    return devices;
  }

  Future<void> sendAndroidTvCommand({
    required String deviceId,
    required String command,
  }) async {
    final response = await _dio.post(
      '/api/android_tv_command',
      data: {
        'device_id': deviceId,
        'command': command,
      },
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Command failed').toString());
    }
  }

  Future<void> updateProfileName(String fullName) async {
    final response = await _dio.post(
      '/api/profile/name',
      data: {'full_name': fullName},
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Name update failed').toString());
    }
  }

  Future<void> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    final response = await _dio.post(
      '/api/profile/password',
      data: {
        'current_password': currentPassword,
        'new_password': newPassword,
      },
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Password change failed').toString());
    }
  }

  Future<String> regenerateCode() async {
    final response = await _dio.post('/profile/regenerate_code');
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Failed to regenerate code').toString());
    }
    return (data['link_code'] ?? '').toString();
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
}

import 'dart:io';

import 'package:cookie_jar/cookie_jar.dart';
import 'package:dio/dio.dart';
import 'package:dio_cookie_manager/dio_cookie_manager.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/app_models.dart';

class ApiClient {
  ApiClient();

  static const String _baseUrlKey = 'api_base_url';
  static const String _mobileAuthTokenKey = 'mobile_auth_token';
  static const String _lastLoginUsernameKey = 'last_login_username';
  static const String _defaultBaseUrl = 'https://everydayadvertise.com';

  late final Dio _dio;
  final CookieJar _cookieJar = CookieJar();

  String _baseUrl = _defaultBaseUrl;
  String? _mobileAuthToken;
  String? _lastLoginUsername;

  String get baseUrl => _baseUrl;
  String? get mobileAuthToken => _mobileAuthToken;
  String? get lastLoginUsername => _lastLoginUsername;

  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _baseUrl = (prefs.getString(_baseUrlKey) ?? _defaultBaseUrl).trim();
    _mobileAuthToken = (prefs.getString(_mobileAuthTokenKey) ?? '').trim();
    if (_mobileAuthToken!.isEmpty) {
      _mobileAuthToken = null;
    }
    _lastLoginUsername =
        (prefs.getString(_lastLoginUsernameKey) ?? '').trim().toLowerCase();
    if (_lastLoginUsername!.isEmpty) {
      _lastLoginUsername = null;
    }

    final lower = _baseUrl.toLowerCase();
    if (lower.startsWith('https://api.everydayadvertise.com') ||
        lower.startsWith('http://api.everydayadvertise.com')) {
      _baseUrl = _baseUrl
          .replaceFirst(
              RegExp(r'^https://api\.everydayadvertise\.com',
                  caseSensitive: false),
              'https://everydayadvertise.com')
          .replaceFirst(
              RegExp(r'^http://api\.everydayadvertise\.com',
                  caseSensitive: false),
              'https://everydayadvertise.com');
      await prefs.setString(_baseUrlKey, _baseUrl);
    }

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
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          final token = _mobileAuthToken;
          if (token != null && token.isNotEmpty) {
            options.headers['X-Mobile-Auth'] = token;
          }
          handler.next(options);
        },
      ),
    );
  }

  Future<void> setMobileAuthToken(String token) async {
    final clean = token.trim();
    if (clean.isEmpty) {
      throw Exception('Invalid auth token');
    }
    _mobileAuthToken = clean;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_mobileAuthTokenKey, clean);
  }

  Future<void> clearMobileAuthToken() async {
    _mobileAuthToken = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_mobileAuthTokenKey);
  }

  Future<void> _rememberLoginUsername(String username) async {
    final clean = username.trim().toLowerCase();
    if (clean.isEmpty) {
      return;
    }
    _lastLoginUsername = clean;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_lastLoginUsernameKey, clean);
  }

  Future<String?> getRememberedLoginUsername() async {
    if ((_lastLoginUsername ?? '').trim().isNotEmpty) {
      return _lastLoginUsername;
    }
    final prefs = await SharedPreferences.getInstance();
    final cached = (prefs.getString(_lastLoginUsernameKey) ?? '').trim();
    return cached.isEmpty ? null : cached.toLowerCase();
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
      return me.username.trim().isNotEmpty;
    } catch (_) {
      return false;
    }
  }

  Future<void> login(
      {required String username, required String password}) async {
    final response = await _dio.post(
      '/api/auth/local-login',
      data: {
        'username': username,
        'password': password,
      },
    );

    final data = _asMap(response.data);

    if (response.statusCode == null || response.statusCode! >= 400) {
      throw Exception((data['error'] ?? 'Login failed').toString());
    }

    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Login failed').toString());
    }

    final mobileToken = (data['mobile_auth_token'] ?? '').toString().trim();
    if (mobileToken.isEmpty) {
      throw Exception('Login failed: missing mobile auth token');
    }
    await setMobileAuthToken(mobileToken);
    await _rememberLoginUsername(username);

    final ok = await checkSession();
    if (!ok) {
      throw Exception('Login failed: invalid credentials or access denied');
    }
  }

  Future<Map<String, dynamic>> signup({
    required String username,
    required String password,
    required String password2,
    String fullName = '',
  }) async {
    final response = await _dio.post(
      '/api/auth/signup',
      data: {
        'username': username,
        'password': password,
        'password2': password2,
        'full_name': fullName,
      },
    );

    final data = _asMap(response.data);

    if (response.statusCode == null || response.statusCode! >= 400) {
      throw Exception((data['error'] ?? 'Signup failed').toString());
    }

    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Signup failed').toString());
    }

    return data;
  }

  Future<String> requestPasswordReset({required String email}) async {
    final response = await _dio.post(
      '/api/auth/forgot-password',
      data: {'email': email.trim()},
    );

    final data = _asMap(response.data);
    if (response.statusCode == null || response.statusCode! >= 400) {
      throw Exception(
          (data['error'] ?? 'Could not process request.').toString());
    }
    if (data['success'] != true) {
      throw Exception(
          (data['error'] ?? 'Could not process request.').toString());
    }
    return (data['message'] ?? 'If that email exists, we sent a reset link.')
        .toString();
  }

  Future<String> resetPassword({
    required String token,
    required String password,
  }) async {
    final response = await _dio.post(
      '/api/auth/reset-password',
      data: {
        'token': token.trim(),
        'password': password,
      },
    );

    final data = _asMap(response.data);
    if (response.statusCode == null || response.statusCode! >= 400) {
      throw Exception(
          (data['error'] ?? 'Could not update password.').toString());
    }
    if (data['success'] != true) {
      throw Exception(
          (data['error'] ?? 'Could not update password.').toString());
    }
    return (data['message'] ?? 'Password updated. You can now sign in.')
        .toString();
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
    await clearMobileAuthToken();
    _lastLoginUsername = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_lastLoginUsernameKey);
  }

  Future<Map<String, bool>> getAuthProviders() async {
    final response = await _dio.get('/api/auth/providers');
    final data = _asMap(response.data);
    if (data['success'] != true) {
      return {'google': false, 'microsoft': false, 'apple': false};
    }
    final providers = _asMap(data['providers']);
    return {
      'google': providers['google'] == true,
      'microsoft': providers['microsoft'] == true,
      'apple': providers['apple'] == true,
    };
  }

  Future<Map<String, dynamic>> getAuthProviderConfig() async {
    final response = await _dio.get('/api/auth/providers');
    final data = _asMap(response.data);
    if (data['success'] != true) {
      return {
        'google': false,
        'microsoft': false,
        'apple': false,
        'google_client_id': '',
      };
    }
    final providers = _asMap(data['providers']);
    return {
      'google': providers['google'] == true,
      'microsoft': providers['microsoft'] == true,
      'apple': providers['apple'] == true,
      'google_client_id': (data['google_client_id'] ?? '').toString(),
    };
  }

  Future<String> loginWithGoogleNative({
    String? idToken,
    String? serverAuthCode,
  }) async {
    final token = (idToken ?? '').trim();
    final code = (serverAuthCode ?? '').trim();
    if (token.isEmpty && code.isEmpty) {
      throw Exception('Missing Google credentials');
    }
    final response = await _dio.post(
      '/api/auth/google/native',
      data: {
        if (token.isNotEmpty) 'id_token': token,
        if (code.isNotEmpty) 'server_auth_code': code,
      },
      options: Options(contentType: Headers.formUrlEncodedContentType),
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Google login failed').toString());
    }
    final mobileToken = (data['mobile_auth_token'] ?? '').toString().trim();
    if (mobileToken.isEmpty) {
      throw Exception('Google login failed: missing mobile token');
    }
    await setMobileAuthToken(mobileToken);
    try {
      final me = await getMe();
      if (me.username.trim().isNotEmpty) {
        await _rememberLoginUsername(me.username);
      }
    } catch (_) {
      // best-effort only
    }
    return mobileToken;
  }

  Uri buildMobileSocialStartUri({
    required String provider,
    String redirectUri = 'everydaymobile://oauth-callback',
  }) {
    final p = provider.trim().toLowerCase();
    final base = _dio.options.baseUrl.replaceAll(RegExp(r'/$'), '');
    return Uri.parse('$base/auth/mobile/start/$p')
        .replace(queryParameters: {'redirect_uri': redirectUri});
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

  Future<String?> getMasterStoreId() async {
    final response = await _dio.get('/stores');
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Unable to load stores').toString());
    }
    final raw = data['master_store_id'];
    final value = raw?.toString().trim() ?? '';
    if (value.isNotEmpty) {
      return value;
    }

    final stores = (data['stores'] as List? ?? const [])
        .map((item) => _asMap(item))
        .toList();
    if (stores.isEmpty) {
      return null;
    }

    final fallback = (stores.first['id'] ?? '').toString().trim();
    return fallback.isEmpty ? null : fallback;
  }

  Future<void> addStore({
    required String storeId,
    required String storeName,
  }) async {
    final response = await _dio.post(
      '/add_store',
      data: {
        'store_id': storeId.trim(),
        'store_name': storeName.trim(),
      },
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Unable to add store').toString());
    }
  }

  Future<void> deleteStore(String storeId) async {
    final response = await _dio.post(
      '/delete_store',
      data: {'store_id': storeId},
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Unable to delete store').toString());
    }
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

  Future<Map<String, dynamic>> getSubscriptionSummary() async {
    final response = await _dio.get('/api/subscription/summary');
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception(
          (data['error'] ?? 'Unable to load subscription summary').toString());
    }
    return data;
  }

  Future<String> createBillingCheckoutSession() async {
    final response = await _dio.post('/api/billing/checkout-session');
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception(
          (data['error'] ?? 'Unable to create checkout session').toString());
    }
    final checkoutUrl = (data['checkout_url'] ?? '').toString().trim();
    if (checkoutUrl.isEmpty) {
      throw Exception('Checkout URL missing from server response');
    }
    return checkoutUrl;
  }

  Future<String> addScreen({
    required String storeId,
    String screenType = 'screen',
  }) async {
    final response = await _dio.post(
      '/add_screen',
      data: {
        'store_id': storeId,
        'screen_type': screenType,
      },
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Unable to add screen').toString());
    }
    return (data['screen_id'] ?? '').toString();
  }

  Future<void> deleteScreen({
    required String storeId,
    required String screenId,
  }) async {
    final response = await _dio.post(
      '/delete_screen',
      data: {
        'store_id': storeId,
        'screen_id': screenId,
      },
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Unable to delete screen').toString());
    }
  }

  Future<void> renameScreen({
    required String storeId,
    required String screenId,
    required String name,
  }) async {
    final response = await _dio.post(
      '/update_screen_name',
      data: {
        'store_id': storeId,
        'screen_id': screenId,
        'name': name,
      },
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Unable to rename screen').toString());
    }
  }

  Future<Map<String, String>> getScreenStatus(String storeId) async {
    final response = await _dio.get('/api/screen_status/$storeId');
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Unable to load status').toString());
    }

    final statusRaw = _asMap(data['status']);
    final out = <String, String>{};
    for (final entry in statusRaw.entries) {
      out[entry.key] = (entry.value ?? 'offline').toString().toLowerCase();
    }
    return out;
  }

  Future<String> uploadMedia(File file) async {
    final data = await uploadMediaDetailed(file);
    final filename = (data['filename'] ?? '').toString();
    if (filename.isEmpty) {
      throw Exception('Upload failed: missing filename');
    }
    return filename;
  }

  Future<Map<String, dynamic>> uploadMediaDetailed(File file) async {
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(file.path,
          filename: file.uri.pathSegments.last),
    });

    final response = await _dio.post('/upload_media', data: formData);
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Upload failed').toString());
    }
    return data;
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

  Future<List<Map<String, dynamic>>> getPlaylist({
    required String storeId,
    required String screenId,
  }) async {
    final response = await _dio.get(
      '/playlist/$storeId/$screenId',
      queryParameters: {
        'skip_schedule_filter': '1',
      },
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Unable to load playlist').toString());
    }

    final playlist = data['playlist'];
    if (playlist is! List) {
      return const [];
    }
    return playlist.map((item) => _asMap(item)).toList();
  }

  Future<Map<String, dynamic>> listLibrary({String? prefix}) async {
    final cleanPrefix = prefix?.trim() ?? '';
    final response = await _dio.get(
      '/library',
      queryParameters:
          cleanPrefix.isEmpty ? null : <String, dynamic>{'prefix': cleanPrefix},
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Unable to load library').toString());
    }
    return data;
  }

  Future<List<Map<String, dynamic>>> getAllScreensStatus() async {
    final response = await _dio.get('/api/all_screens_status');
    final data = _asMap(response.data);
    final screensRaw = data['screens'];
    if (screensRaw is! List) {
      throw Exception(
          (data['error'] ?? 'Unable to load device manager').toString());
    }
    return screensRaw.map((item) => _asMap(item)).toList();
  }

  Future<Map<String, Map<String, dynamic>>> getPiStatusMap() async {
    final response = await _dio.get('/api/pi_status');
    final data = _asMap(response.data);
    if (data.containsKey('error')) {
      throw Exception((data['error'] ?? 'Unable to load Pi status').toString());
    }
    final out = <String, Map<String, dynamic>>{};
    for (final entry in data.entries) {
      out[entry.key] = _asMap(entry.value);
    }
    return out;
  }

  Future<void> addPiDeviceAssignment({
    required String piId,
    required String ipAddress,
    required String storeId,
    required String screenId,
  }) async {
    final response = await _dio.post(
      '/api/add-pi-device',
      data: {
        'pi_id': piId,
        'ip_address': ipAddress,
        'store_id': storeId,
        'screen_id': screenId,
      },
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception(
          (data['message'] ?? data['error'] ?? 'Failed to assign Pi')
              .toString());
    }
  }

  Future<void> configurePiWebsocket({
    required String piId,
    required String pairCode,
    required String storeId,
    required String screenId,
    bool autoStart = true,
  }) async {
    final response = await _dio.post(
      '/api/configure-pi-ws',
      data: {
        'pi_id': piId,
        'pair_code': pairCode,
        'store_id': storeId,
        'screen_id': screenId,
        'auto_start': autoStart,
      },
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception(
          (data['message'] ?? data['error'] ?? 'Failed to configure Pi')
              .toString());
    }
  }

  Future<void> restartPiDevice(String piId) async {
    final response = await _dio.post(
      '/api/pi-restart',
      data: {'pi_id': piId},
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception(
          (data['message'] ?? data['error'] ?? 'Failed to restart Pi')
              .toString());
    }
  }

  Future<void> deletePiDevice(String piId) async {
    final response = await _dio.post(
      '/api/pi-delete',
      data: {'pi_id': piId},
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception(
          (data['message'] ?? data['error'] ?? 'Failed to delete Pi')
              .toString());
    }
  }

  Future<Map<String, dynamic>> getPiLocation(String piId) async {
    final response = await _dio.get(
      '/api/get-pi-location',
      queryParameters: {'pi_id': piId},
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception(
          (data['message'] ?? data['error'] ?? 'Failed to load Pi location')
              .toString());
    }
    return data;
  }

  Future<void> updatePiLocationName({
    required String piId,
    required String locationName,
  }) async {
    final response = await _dio.post(
      '/api/update-pi-location',
      data: {
        'pi_id': piId,
        'location_name': locationName,
      },
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception(
          (data['message'] ?? data['error'] ?? 'Failed to update location')
              .toString());
    }
  }

  Future<void> updatePlaylistItem({
    required String storeId,
    required String screenId,
    required String itemId,
    String? file,
    String? start,
    String? end,
    bool? enabled,
    bool? repeat,
    int? duration,
    List<String>? days,
    int? effectId,
    String? effect,
  }) async {
    final payload = <String, dynamic>{};
    if (file != null && file.isNotEmpty) {
      payload['file'] = file;
    }
    if (start != null) {
      payload['start'] = _normalizeScheduleDateTime(start);
    }
    if (end != null) {
      payload['end'] = _normalizeScheduleDateTime(end);
    }
    if (enabled != null) {
      payload['enabled'] = enabled;
    }
    if (repeat != null) {
      payload['repeat'] = repeat;
    }
    if (duration != null) {
      payload['duration'] = duration;
    }
    if (days != null) {
      payload['days'] = days;
    }
    if (effectId != null) {
      payload['effect_id'] = effectId;
    } else if (effect != null && effect.trim().isNotEmpty) {
      payload['effect'] = effect.trim();
    }
    if (payload.isEmpty) {
      return;
    }

    final response = await _dio.post(
      '/playlist/item/$storeId/$screenId/$itemId/update',
      data: payload,
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception(
          (data['error'] ?? 'Failed to update playlist item').toString());
    }
  }

  Future<void> deletePlaylistItem({
    required String storeId,
    required String screenId,
    required String itemId,
  }) async {
    final response = await _dio.post(
      '/playlist/item/$storeId/$screenId/$itemId/delete',
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception(
          (data['error'] ?? 'Failed to delete playlist item').toString());
    }
  }

  Future<Map<String, dynamic>> addScheduleWindow({
    required String storeId,
    required String screenId,
    required String itemId,
    required String? start,
    required String? end,
    required List<String> days,
    required bool enabled,
  }) async {
    final response = await _dio.post(
      '/playlist/item/$storeId/$screenId/$itemId/schedule',
      data: {
        'start': _normalizeScheduleDateTime(start),
        'end': _normalizeScheduleDateTime(end),
        'days': days,
        'enabled': enabled,
      },
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Failed to add schedule').toString());
    }
    return data;
  }

  Future<void> updateScheduleWindow({
    required String storeId,
    required String screenId,
    required String itemId,
    required int index,
    String? start,
    String? end,
    List<String>? days,
    bool? enabled,
  }) async {
    final payload = <String, dynamic>{};
    if (start != null) {
      payload['start'] = _normalizeScheduleDateTime(start);
    }
    if (end != null) {
      payload['end'] = _normalizeScheduleDateTime(end);
    }
    if (days != null) {
      payload['days'] = days;
    }
    if (enabled != null) {
      payload['enabled'] = enabled;
    }

    final response = await _dio.post(
      '/playlist/item/$storeId/$screenId/$itemId/schedule/$index/update',
      data: payload,
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception(
          (data['error'] ?? 'Failed to update schedule').toString());
    }
  }

  Future<void> deleteScheduleWindow({
    required String storeId,
    required String screenId,
    required String itemId,
    required int index,
  }) async {
    final response = await _dio.post(
      '/playlist/item/$storeId/$screenId/$itemId/schedule/$index/delete',
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception(
          (data['error'] ?? 'Failed to delete schedule').toString());
    }
  }

  Future<Map<String, String>> getAuthHeadersForUrl(String url) async {
    final trimmed = url.trim();
    if (trimmed.isEmpty) {
      return const {};
    }

    Uri uri;
    try {
      uri = Uri.parse(trimmed);
      if (!uri.hasScheme || uri.host.isEmpty) {
        uri = Uri.parse(_dio.options.baseUrl +
            (trimmed.startsWith('/') ? trimmed : '/$trimmed'));
      }
    } catch (_) {
      return const {};
    }

    final cookies = await _cookieJar.loadForRequest(uri);
    if (cookies.isEmpty) {
      return const {};
    }

    cookies.sort((a, b) => a.name.compareTo(b.name));
    final cookieHeader = cookies.map((c) => '${c.name}=${c.value}').join('; ');
    if (cookieHeader.isEmpty) {
      return const {};
    }
    return {'Cookie': cookieHeader};
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

  Future<int> updateScreenRotation({
    required String storeId,
    required String screenId,
    required int rotation,
  }) async {
    final response = await _dio.post(
      '/update_rotation',
      data: {
        'store_id': storeId,
        'screen_id': screenId,
        'rotation': rotation,
      },
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Failed to rotate screen').toString());
    }
    return int.tryParse('${data['rotation'] ?? rotation}') ?? rotation;
  }

  Future<Map<String, dynamic>> getSliceJobStatus(String jobId) async {
    final response = await _dio.get('/slice_job_status/$jobId');
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception(
          (data['error'] ?? 'Failed to check slice job').toString());
    }
    return data;
  }

  Future<List<Map<String, dynamic>>> listSliceJobs() async {
    final response = await _dio.get('/api/list_slice_jobs');
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception(
          (data['error'] ?? 'Failed to load slice jobs').toString());
    }
    final jobsRaw = data['jobs'];
    if (jobsRaw is! List) {
      return const [];
    }
    return jobsRaw.map((job) => _asMap(job)).toList();
  }

  Future<Map<String, dynamic>> autoCreateSyncScreens({
    required String storeId,
    required String layout,
    required List<Map<String, dynamic>> slicedFiles,
  }) async {
    final response = await _dio.post(
      '/auto_create_sync_screens',
      data: {
        'store_id': storeId,
        'layout': layout,
        'sliced_files': slicedFiles,
      },
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception(
          (data['error'] ?? 'Failed to auto-create sync screens').toString());
    }
    return data;
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

  Future<Map<String, dynamic>> getAccountOverview() async {
    final response = await _dio.get('/api/account/overview');
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception(
          (data['error'] ?? 'Failed to load account overview').toString());
    }
    return data;
  }

  Future<String> createBillingPortalSession() async {
    final response = await _dio.post('/api/billing/portal-session');
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception(
          (data['error'] ?? 'Failed to open billing portal').toString());
    }
    final url = (data['portal_url'] ?? '').toString().trim();
    if (url.isEmpty) {
      throw Exception('Billing portal URL missing from response');
    }
    return url;
  }

  Future<String> cancelSubscription() async {
    final response = await _dio.post('/api/billing/cancel');
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception(
          (data['error'] ?? 'Failed to cancel subscription').toString());
    }
    return (data['message'] ?? 'Subscription will be cancelled at period end')
        .toString();
  }

  Future<String> reactivateSubscription() async {
    final response = await _dio.post('/api/billing/reactivate');
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception(
          (data['error'] ?? 'Failed to reactivate subscription').toString());
    }
    return (data['message'] ?? 'Subscription reactivated').toString();
  }

  Future<String> updateAccountPhone(String phoneNumber) async {
    final response = await _dio.post(
      '/api/account/phone',
      data: {'phone_number': phoneNumber},
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception(
          (data['error'] ?? 'Failed to update phone number').toString());
    }
    return (data['message'] ?? 'Phone number updated successfully').toString();
  }

  Future<String> sendPhoneVerificationCode() async {
    final response = await _dio.post('/api/account/phone/send-code');
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception(
          (data['error'] ?? 'Failed to send verification code').toString());
    }
    return (data['message'] ?? 'Verification code sent via SMS').toString();
  }

  Future<String> verifyPhoneCode(String code) async {
    final response = await _dio.post(
      '/api/account/phone/verify',
      data: {'code': code.trim()},
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception((data['error'] ?? 'Failed to verify phone').toString());
    }
    return (data['message'] ?? 'Phone number verified successfully!')
        .toString();
  }

  Future<String> resendVerificationEmail({String? email}) async {
    final cleanEmail = (email ?? '').trim();
    if (cleanEmail.isEmpty) {
      throw Exception('Email is required');
    }

    // Match website behavior exactly: submit the same form endpoint used by
    // the web UI and treat a successful round-trip as "verification email sent".
    final response = await _dio.post(
      '/resend-verification',
      data: {'email': cleanEmail},
      options: Options(contentType: Headers.formUrlEncodedContentType),
    );

    final statusCode = response.statusCode ?? 0;
    if (statusCode >= 500) {
      throw Exception('Failed to resend verification email');
    }

    return 'Verification email sent! Please check your inbox and click the link to verify your email.';
  }

  Future<Map<String, dynamic>> cancelScreenSubscription({
    required int screenSubscriptionId,
    String reason = 'No reason provided',
    String feedback = '',
  }) async {
    final response = await _dio.post(
      '/remove_screen',
      data: {
        'screen_subscription_id': screenSubscriptionId,
        'reason': reason,
        'feedback': feedback,
      },
    );
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception(
          (data['error'] ?? 'Failed to cancel screen subscription').toString());
    }
    return data;
  }

  Future<Map<String, dynamic>> cancelAllScreenSubscriptions() async {
    final response = await _dio.post('/remove_all_screens');
    final data = _asMap(response.data);
    if (data['success'] != true) {
      throw Exception(
          (data['error'] ?? 'Failed to cancel all screens').toString());
    }
    return data;
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
      throw Exception(
          (data['error'] ?? 'Failed to regenerate code').toString());
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

  String? _normalizeScheduleDateTime(String? value) {
    if (value == null) {
      return null;
    }
    final text = value.trim();
    if (text.isEmpty) {
      return null;
    }

    String twoDigits(String input) {
      final parsed = int.tryParse(input) ?? 0;
      return parsed.toString().padLeft(2, '0');
    }

    final dateOnly = RegExp(r'^(\d{4}-\d{2}-\d{2})$').firstMatch(text);
    if (dateOnly != null) {
      return '${dateOnly.group(1)}T00:00:00';
    }

    final dateTime = RegExp(
      r'^(\d{4}-\d{2}-\d{2})[ T](\d{1,2}):(\d{2})(?::(\d{2}))?',
    ).firstMatch(text);
    if (dateTime != null) {
      final date = dateTime.group(1)!;
      final hh = twoDigits(dateTime.group(2) ?? '0');
      final mm = twoDigits(dateTime.group(3) ?? '0');
      final ss = twoDigits(dateTime.group(4) ?? '0');
      return '$date' 'T$hh:$mm:$ss';
    }

    final timeOnly =
        RegExp(r'^(\d{1,2}):(\d{2})(?::(\d{2}))?$').firstMatch(text);
    if (timeOnly != null) {
      final hh = twoDigits(timeOnly.group(1) ?? '0');
      final mm = twoDigits(timeOnly.group(2) ?? '0');
      final ss = twoDigits(timeOnly.group(3) ?? '0');
      return '$hh:$mm:$ss';
    }

    return text;
  }
}

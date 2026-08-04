import 'dart:async';

import 'package:app_links/app_links.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:sign_in_with_apple/sign_in_with_apple.dart';
import 'package:url_launcher/url_launcher.dart';

import 'password_reset_screen.dart';
import '../services/api_client.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({
    super.key,
    required this.apiClient,
    required this.onLoginSuccess,
    this.enableSocialAuthBootstrap = true,
  });

  final ApiClient apiClient;
  final Future<void> Function() onLoginSuccess;
  final bool enableSocialAuthBootstrap;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen>
    with SingleTickerProviderStateMixin {
  static const List<List<Color>> _bgGradientPalettes = [
    [Color(0xFF2563EB), Color(0xFF7C3AED), Color(0xFFEC4899)],
    [Color(0xFF0EA5E9), Color(0xFF6366F1), Color(0xFFD946EF)],
    [Color(0xFF3B82F6), Color(0xFF8B5CF6), Color(0xFFF43F5E)],
    [Color(0xFF06B6D4), Color(0xFF4F46E5), Color(0xFFEC4899)],
    [Color(0xFF38BDF8), Color(0xFF7C3AED), Color(0xFFF97316)],
  ];

  final _formKey = GlobalKey<FormState>();
  final _fullNameController = TextEditingController();
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();

  bool _loading = false;
  bool _socialLoading = false;
  bool _checkingProviders = true;
  bool _isSignupMode = false;
  bool _googleEnabled = false;
  bool _microsoftEnabled = false;
  bool _appleEnabled = false;
  String _googleServerClientId = '';
  String _googleAndroidClientId = '';
  String _googleIosClientId = '';
  bool _obscurePassword = true;
  bool _obscureConfirmPassword = true;
  String? _error;
  late final AnimationController _bgController;
  late final int _backgroundSeedIndex;
  final AppLinks _appLinks = AppLinks();
  StreamSubscription<Uri>? _linkSub;

  bool get _shouldShowAppleSignIn {
    if (_appleEnabled) {
      return true;
    }
    final platform = defaultTargetPlatform;
    return platform == TargetPlatform.iOS || platform == TargetPlatform.macOS;
  }

  bool get _shouldShowGoogleSignIn {
    if (_googleEnabled || _googleServerClientId.trim().isNotEmpty) {
      return true;
    }
    final platform = defaultTargetPlatform;
    return platform == TargetPlatform.android ||
        platform == TargetPlatform.iOS ||
        platform == TargetPlatform.macOS;
  }

  @override
  void initState() {
    super.initState();
    _backgroundSeedIndex =
        DateTime.now().microsecondsSinceEpoch % _bgGradientPalettes.length;
    _bgController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 18),
    )..repeat();

    if (widget.enableSocialAuthBootstrap) {
      _initSocialAuth();
    } else {
      _checkingProviders = false;
    }
  }

  @override
  void dispose() {
    _linkSub?.cancel();
    _fullNameController.dispose();
    _usernameController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    _bgController.dispose();
    super.dispose();
  }

  Future<void> _initSocialAuth() async {
    try {
      final providers = await widget.apiClient.getAuthProviderConfig();
      if (!mounted) {
        return;
      }
      setState(() {
        _googleEnabled = providers['google'] == true;
        _microsoftEnabled = providers['microsoft'] == true;
        _appleEnabled = providers['apple'] == true;
        _googleServerClientId =
            (providers['google_client_id'] ?? '').toString();
        _googleAndroidClientId =
            (providers['google_android_client_id'] ?? '').toString();
        _googleIosClientId =
            (providers['google_ios_client_id'] ?? '').toString();
        _checkingProviders = false;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _checkingProviders = false;
      });
    }

    try {
      final initialUri = await _appLinks.getInitialLink();
      if (initialUri != null) {
        await _handleIncomingAuthLink(initialUri);
      }
    } catch (_) {
      // no-op
    }

    _linkSub = _appLinks.uriLinkStream.listen((uri) async {
      await _handleIncomingAuthLink(uri);
    });
  }

  Future<void> _handleIncomingAuthLink(Uri uri) async {
    if (uri.scheme.toLowerCase() != 'everydaymobile') {
      return;
    }

    final host = uri.host.toLowerCase();
    if (host == 'reset-password') {
      final token = (uri.queryParameters['token'] ?? '').trim();
      if (token.isEmpty || !mounted) {
        return;
      }
      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => PasswordResetScreen(
            apiClient: widget.apiClient,
            resetToken: token,
            initialEmail: _usernameController.text.trim(),
          ),
        ),
      );
      return;
    }

    final status = (uri.queryParameters['status'] ?? '').toLowerCase();
    if (status != 'success') {
      if (!mounted) {
        return;
      }
      setState(() {
        _socialLoading = false;
        _error = 'Social login failed. Please try again.';
      });
      return;
    }

    final token = (uri.queryParameters['token'] ?? '').trim();
    if (token.isEmpty) {
      if (!mounted) {
        return;
      }
      setState(() {
        _socialLoading = false;
        _error = 'Social login failed: missing token.';
      });
      return;
    }

    try {
      await widget.apiClient.setMobileAuthToken(token);
      final ok = await widget.apiClient.checkSession();
      if (!mounted) {
        return;
      }
      if (ok) {
        await widget.onLoginSuccess();
        return;
      }
      setState(() {
        _socialLoading = false;
        _error = 'Social login did not create a valid session.';
      });
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _socialLoading = false;
        _error = e.toString().replaceFirst('Exception: ', '');
      });
    }
  }

  Future<void> _startSocialLogin(String provider) async {
    setState(() {
      _error = null;
      _socialLoading = true;
    });

    try {
      final uri =
          widget.apiClient.buildMobileSocialStartUri(provider: provider);
      final ok = await launchUrl(uri, mode: LaunchMode.externalApplication);
      if (!ok && mounted) {
        setState(() {
          _socialLoading = false;
          _error = 'Could not open browser for social login.';
        });
      }
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _socialLoading = false;
        _error = e.toString().replaceFirst('Exception: ', '');
      });
    }
  }

  Uri _publicUri(String path) {
    final base = widget.apiClient.baseUrl.replaceAll(RegExp(r'/$'), '');
    final cleanPath = path.startsWith('/') ? path : '/$path';
    return Uri.parse('$base$cleanPath');
  }

  Future<void> _openPublicPage(String path) async {
    final ok = await launchUrl(
      _publicUri(path),
      mode: LaunchMode.externalApplication,
    );
    if (!ok && mounted) {
      setState(() {
        _error = 'Could not open browser.';
      });
    }
  }

  Future<void> _openPasswordReset() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => PasswordResetScreen(
          apiClient: widget.apiClient,
          initialEmail: _usernameController.text.trim(),
        ),
      ),
    );
  }

  Future<void> _startGoogleLoginNativeFirst() async {
    setState(() {
      _error = null;
      _socialLoading = true;
    });

    try {
      final serverClientId = _googleServerClientId.trim();
      final nativeClientId = switch (defaultTargetPlatform) {
        TargetPlatform.android => _googleAndroidClientId.trim(),
        TargetPlatform.iOS || TargetPlatform.macOS => _googleIosClientId.trim(),
        _ => '',
      };
      final signIn = GoogleSignIn(
        scopes: const ['email', 'profile'],
        clientId: nativeClientId.isEmpty ? null : nativeClientId,
        serverClientId: serverClientId.isEmpty ? null : serverClientId,
      );

      await signIn.signOut();
      final account = await signIn.signIn();
      if (account == null) {
        if (!mounted) {
          return;
        }
        setState(() {
          _socialLoading = false;
          _error = 'Google sign-in cancelled.';
        });
        return;
      }

      final auth = await account.authentication;
      final idToken = (auth.idToken ?? '').trim();
      final serverAuthCode = (account.serverAuthCode ?? '').trim();
      if (idToken.isEmpty && serverAuthCode.isEmpty) {
        // Some emulators can open Google sign-in but cannot issue a native
        // token until a Google account and matching OAuth client are present.
        // Keep the user moving with the browser OAuth flow instead.
        await _startSocialLogin('google');
        return;
      }

      await widget.apiClient.loginWithGoogleNative(
        idToken: idToken,
        serverAuthCode: serverAuthCode,
      );
      final ok = await widget.apiClient.checkSession();
      if (!mounted) {
        return;
      }
      if (ok) {
        await widget.onLoginSuccess();
        return;
      }

      setState(() {
        _socialLoading = false;
        _error = 'Google sign-in did not create a valid session.';
      });
    } catch (e) {
      final rawError = e.toString().replaceFirst('Exception: ', '');
      final lower = rawError.toLowerCase();
      final isDeveloperConfigError = lower.contains('apiexception: 10') ||
          lower.contains('api10') ||
          lower.contains('developer_error') ||
          lower.contains('gidclientid') ||
          lower.contains('no active configuration') ||
          (e is PlatformException && e.code == 'sign_in_failed');

      if (isDeveloperConfigError) {
        // Native Google sign-in is often unavailable on misconfigured emulator builds;
        // fall back to browser OAuth so users can still authenticate.
        await _startSocialLogin('google');
        return;
      }

      if (!mounted) {
        return;
      }
      setState(() {
        _socialLoading = false;
        _error = rawError;
      });
    }
  }

  List<Color> _animatedBackgroundPalette(double t) {
    final paletteCount = _bgGradientPalettes.length;
    final scaled = t * paletteCount;
    final fromIndex = (_backgroundSeedIndex + scaled.floor()) % paletteCount;
    final toIndex = (fromIndex + 1) % paletteCount;
    final blend = Curves.easeInOut.transform(scaled - scaled.floorToDouble());
    final from = _bgGradientPalettes[fromIndex];
    final to = _bgGradientPalettes[toIndex];
    return List<Color>.generate(
      from.length,
      (index) => Color.lerp(from[index], to[index], blend) ?? from[index],
    );
  }

  Future<void> _startAppleLoginNativeFirst() async {
    final platform = defaultTargetPlatform;
    final supportsNativeApple =
        platform == TargetPlatform.iOS || platform == TargetPlatform.macOS;
    if (!supportsNativeApple) {
      await _startSocialLogin('apple');
      return;
    }

    setState(() {
      _error = null;
      _socialLoading = true;
    });

    try {
      final available = await SignInWithApple.isAvailable();
      if (!available) {
        await _startSocialLogin('apple');
        return;
      }

      final credential = await SignInWithApple.getAppleIDCredential(
        scopes: const [
          AppleIDAuthorizationScopes.email,
          AppleIDAuthorizationScopes.fullName,
        ],
      );

      final identityToken = (credential.identityToken ?? '').trim();
      if (identityToken.isEmpty) {
        if (!mounted) {
          return;
        }
        setState(() {
          _socialLoading = false;
          _error = 'Apple sign-in did not return an identity token.';
        });
        return;
      }

      await widget.apiClient.loginWithAppleNative(
        identityToken: identityToken,
        authorizationCode: credential.authorizationCode,
        givenName: credential.givenName,
        familyName: credential.familyName,
        email: credential.email,
      );
      final ok = await widget.apiClient.checkSession();
      if (!mounted) {
        return;
      }
      if (ok) {
        await widget.onLoginSuccess();
        return;
      }

      setState(() {
        _socialLoading = false;
        _error = 'Apple sign-in did not create a valid session.';
      });
    } on SignInWithAppleAuthorizationException catch (e) {
      if (e.code == AuthorizationErrorCode.canceled) {
        if (!mounted) {
          return;
        }
        setState(() {
          _socialLoading = false;
          _error = 'Apple sign-in cancelled.';
        });
        return;
      }

      await _startSocialLogin('apple');
    } catch (e) {
      final rawError = e.toString().replaceFirst('Exception: ', '');
      final lower = rawError.toLowerCase();
      final shouldFallbackToWeb = lower.contains('akauthenticationerror') ||
          lower.contains('authorizationerror') ||
          lower.contains('code=1000') ||
          lower.contains('code=1001') ||
          lower.contains('code=-7003') ||
          lower.contains('code=-7034') ||
          (e is PlatformException &&
              (e.code == 'authorization-error' ||
                  e.code == 'sign_in_with_apple_error'));

      if (shouldFallbackToWeb) {
        await _startSocialLogin('apple');
        return;
      }

      if (!mounted) {
        return;
      }
      setState(() {
        _socialLoading = false;
        _error = rawError;
      });
    }
  }

  Widget _buildSocialButtonLogo(String assetPath, {double size = 18}) {
    return Image.asset(
      assetPath,
      width: size,
      height: size,
      fit: BoxFit.contain,
      errorBuilder: (context, error, stackTrace) => SizedBox(
        width: size,
        height: size,
      ),
    );
  }

  Widget _buildAnimatedWordBackground() {
    return AnimatedBuilder(
      animation: _bgController,
      builder: (context, _) {
        final t = _bgController.value;
        final colorA = HSVColor.fromAHSV(1, (220 + (t * 140)) % 360, 0.66, 1)
            .toColor()
            .withAlpha(60);
        final colorB = HSVColor.fromAHSV(1, (300 + (t * 140)) % 360, 0.58, 1)
            .toColor()
            .withAlpha(48);
        final shift = (t * 340) - 170;

        TextStyle styleA = TextStyle(
          fontSize: 34,
          fontWeight: FontWeight.w800,
          letterSpacing: 1.2,
          color: colorA,
        );
        TextStyle styleB = TextStyle(
          fontSize: 26,
          fontWeight: FontWeight.w700,
          letterSpacing: 1.0,
          color: colorB,
        );

        return IgnorePointer(
          child: ClipRect(
            child: Stack(
              children: [
                Positioned(
                  top: -20,
                  left: -260 + shift,
                  child: Transform.rotate(
                    angle: -0.16,
                    child: Text(
                      'EVERYDAY ADVERTISE   EVERYDAY ADVERTISE   EVERYDAY ADVERTISE',
                      style: styleA,
                    ),
                  ),
                ),
                Positioned(
                  top: 120,
                  left: -420 - shift,
                  child: Transform.rotate(
                    angle: -0.14,
                    child: Text(
                      'EVERYDAY ADVERTISE   EVERYDAY ADVERTISE   EVERYDAY ADVERTISE   EVERYDAY ADVERTISE',
                      style: styleB,
                    ),
                  ),
                ),
                Positioned(
                  top: 270,
                  left: -320 + (shift * 0.8),
                  child: Transform.rotate(
                    angle: -0.18,
                    child: Text(
                      'EVERYDAY ADVERTISE   EVERYDAY ADVERTISE   EVERYDAY ADVERTISE',
                      style: styleA.copyWith(fontSize: 30),
                    ),
                  ),
                ),
                Positioned(
                  bottom: 120,
                  left: -440 - (shift * 0.65),
                  child: Transform.rotate(
                    angle: -0.13,
                    child: Text(
                      'EVERYDAY ADVERTISE   EVERYDAY ADVERTISE   EVERYDAY ADVERTISE   EVERYDAY ADVERTISE',
                      style: styleB,
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildAdvertisingScene() {
    Widget bannerCard({
      required String title,
      required IconData icon,
      required List<Color> colors,
      required double width,
      required double height,
    }) {
      return Container(
        width: width,
        height: height,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          gradient: LinearGradient(colors: colors),
          border: Border.all(color: Colors.white.withAlpha(40)),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withAlpha(35),
              blurRadius: 18,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: Row(
          children: [
            Expanded(
              child: Text(
                title,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: Colors.white.withAlpha(230),
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.8,
                ),
              ),
            ),
            const SizedBox(width: 10),
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(
                color: Colors.black.withAlpha(55),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, color: Colors.white, size: 18),
            ),
          ],
        ),
      );
    }

    return AnimatedBuilder(
      animation: _bgController,
      builder: (context, _) {
        final t = _bgController.value;
        final width = MediaQuery.sizeOf(context).width;
        final laneSpan = width + 260;
        final lane1X = -(t * laneSpan);
        final lane2X = -(((t + 0.45) % 1) * laneSpan);
        final lane3X = -(((t + 0.18) % 1) * laneSpan);

        return IgnorePointer(
          child: ClipRect(
            child: Stack(
              children: [
                Positioned(
                  top: 70,
                  left: lane1X,
                  child: Row(
                    children: [
                      bannerCard(
                        title: 'DIGITAL TV CAMPAIGN',
                        icon: Icons.tv,
                        width: 236,
                        height: 94,
                        colors: const [Color(0x66FFFFFF), Color(0x6693C5FD)],
                      ),
                      const SizedBox(width: 14),
                      bannerCard(
                        title: 'PROMO LOOP',
                        icon: Icons.movie_creation_outlined,
                        width: 212,
                        height: 94,
                        colors: const [Color(0x66F9A8D4), Color(0x66C4B5FD)],
                      ),
                      const SizedBox(width: 14),
                      bannerCard(
                        title: 'SCREEN ADS',
                        icon: Icons.slideshow,
                        width: 216,
                        height: 94,
                        colors: const [Color(0x66BFDBFE), Color(0x66A5B4FC)],
                      ),
                    ],
                  ),
                ),
                Positioned(
                  top: 186,
                  left: lane2X,
                  child: Row(
                    children: [
                      bannerCard(
                        title: 'BANNER NETWORK',
                        icon: Icons.campaign,
                        width: 220,
                        height: 86,
                        colors: const [Color(0x66FBCFE8), Color(0x66C4B5FD)],
                      ),
                      const SizedBox(width: 12),
                      bannerCard(
                        title: 'IN-STORE OFFER',
                        icon: Icons.local_offer_outlined,
                        width: 208,
                        height: 86,
                        colors: const [Color(0x66FDE68A), Color(0x66FDBA74)],
                      ),
                      const SizedBox(width: 12),
                      bannerCard(
                        title: 'LIVE DISPLAY',
                        icon: Icons.cast_connected,
                        width: 204,
                        height: 86,
                        colors: const [Color(0x6686EFAC), Color(0x6699F6E4)],
                      ),
                    ],
                  ),
                ),
                Positioned(
                  top: 292,
                  left: lane3X,
                  child: Row(
                    children: [
                      bannerCard(
                        title: 'ADS UPDATE EVERY 5s',
                        icon: Icons.update,
                        width: 248,
                        height: 80,
                        colors: const [Color(0x66BFDBFE), Color(0x66A5B4FC)],
                      ),
                      const SizedBox(width: 12),
                      bannerCard(
                        title: 'MULTI-SCREEN READY',
                        icon: Icons.grid_view_rounded,
                        width: 228,
                        height: 80,
                        colors: const [Color(0x66DDD6FE), Color(0x66F9A8D4)],
                      ),
                      const SizedBox(width: 12),
                      bannerCard(
                        title: 'TV + MOBILE CONTROL',
                        icon: Icons.phone_android,
                        width: 232,
                        height: 80,
                        colors: const [Color(0x66BAE6FD), Color(0x6699F6E4)],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Future<void> _login() async {
    debugPrint(
      'LOGIN: tapped, username="${_usernameController.text.trim()}", passwordLength=${_passwordController.text.length}',
    );
    if (!_formKey.currentState!.validate()) {
      debugPrint('LOGIN: form validation failed');
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      debugPrint('LOGIN: form valid, calling apiClient.login()');
      await widget.apiClient.login(
        username: _usernameController.text.trim(),
        password: _passwordController.text,
      );
      debugPrint('LOGIN: apiClient.login() succeeded');
      await widget.onLoginSuccess();
    } catch (e) {
      debugPrint('LOGIN: failed with error: $e');
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

  Future<void> _signup() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final result = await widget.apiClient.signup(
        fullName: _fullNameController.text.trim(),
        username: _usernameController.text.trim(),
        password: _passwordController.text,
        password2: _confirmPasswordController.text,
      );

      if (!mounted) {
        return;
      }

      final message =
          (result['message'] ?? 'Account created successfully').toString();
      setState(() {
        _isSignupMode = false;
        _passwordController.clear();
        _confirmPasswordController.clear();
        _error = null;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(message)),
      );
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
    final scheme = Theme.of(context).colorScheme;

    return Scaffold(
      body: Stack(
        children: [
          AnimatedBuilder(
            animation: _bgController,
            builder: (context, _) {
              final animatedPalette =
                  _animatedBackgroundPalette(_bgController.value);
              return Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: animatedPalette,
                  ),
                ),
              );
            },
          ),
          Container(
            decoration: const BoxDecoration(
              gradient: RadialGradient(
                center: Alignment(-0.65, -0.7),
                radius: 1.1,
                colors: [Color(0x55FFFFFF), Color(0x00FFFFFF)],
              ),
            ),
          ),
          _buildAnimatedWordBackground(),
          _buildAdvertisingScene(),
          Container(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0x08000000), Color(0x22000000)],
              ),
            ),
          ),
          SafeArea(
            child: LayoutBuilder(
              builder: (context, constraints) {
                return SingleChildScrollView(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                  child: ConstrainedBox(
                    constraints:
                        BoxConstraints(minHeight: constraints.maxHeight - 20),
                    child: Center(
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 440),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            const SizedBox(height: 10),
                            Container(
                              decoration: BoxDecoration(
                                color: Colors.white.withValues(alpha: 0.95),
                                borderRadius: BorderRadius.circular(28),
                                boxShadow: const [
                                  BoxShadow(
                                    color: Color(0x22000000),
                                    blurRadius: 24,
                                    offset: Offset(0, 10),
                                  ),
                                ],
                              ),
                              child: Padding(
                                padding:
                                    const EdgeInsets.fromLTRB(18, 20, 18, 18),
                                child: Form(
                                  key: _formKey,
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        _isSignupMode
                                            ? 'Create your account'
                                            : 'Sign in',
                                        style: Theme.of(context)
                                            .textTheme
                                            .headlineSmall
                                            ?.copyWith(
                                              fontWeight: FontWeight.w700,
                                            ),
                                      ),
                                      const SizedBox(height: 6),
                                      if (_isSignupMode)
                                        RichText(
                                          text: TextSpan(
                                            style: Theme.of(context)
                                                .textTheme
                                                .bodySmall
                                                ?.copyWith(
                                                  color:
                                                      scheme.onSurfaceVariant,
                                                ),
                                            children: [
                                              const TextSpan(
                                                text:
                                                    'By continuing, you agree to our ',
                                              ),
                                              WidgetSpan(
                                                alignment:
                                                    PlaceholderAlignment.middle,
                                                child: GestureDetector(
                                                  onTap: () =>
                                                      _openPublicPage('/terms'),
                                                  child: Text(
                                                    'Terms of Service',
                                                    style: TextStyle(
                                                      color: scheme.primary,
                                                    ),
                                                  ),
                                                ),
                                              ),
                                              const TextSpan(text: ' and '),
                                              WidgetSpan(
                                                alignment:
                                                    PlaceholderAlignment.middle,
                                                child: GestureDetector(
                                                  onTap: () => _openPublicPage(
                                                      '/privacy-policy'),
                                                  child: Text(
                                                    'Privacy Policy',
                                                    style: TextStyle(
                                                      color: scheme.primary,
                                                    ),
                                                  ),
                                                ),
                                              ),
                                              const TextSpan(
                                                text:
                                                    '. We’ll send a verification email after signup.',
                                              ),
                                            ],
                                          ),
                                        )
                                      else
                                        Text(
                                          'Use your dashboard account credentials.',
                                          style: Theme.of(context)
                                              .textTheme
                                              .bodyMedium
                                              ?.copyWith(
                                                color: scheme.onSurfaceVariant,
                                              ),
                                        ),
                                      const SizedBox(height: 16),
                                      if (_isSignupMode) ...[
                                        TextFormField(
                                          controller: _fullNameController,
                                          textInputAction: TextInputAction.next,
                                          decoration: const InputDecoration(
                                            hintText: 'Full name',
                                            prefixIcon:
                                                Icon(Icons.badge_outlined),
                                          ),
                                        ),
                                        const SizedBox(height: 12),
                                      ],
                                      TextFormField(
                                        controller: _usernameController,
                                        keyboardType:
                                            TextInputType.emailAddress,
                                        textInputAction: TextInputAction.next,
                                        decoration: InputDecoration(
                                          hintText: _isSignupMode
                                              ? 'Email address'
                                              : 'Username or email',
                                          prefixIcon:
                                              const Icon(Icons.person_outline),
                                        ),
                                        validator: (value) {
                                          final text = (value ?? '').trim();
                                          if (text.isEmpty) {
                                            return 'Required';
                                          }
                                          if (_isSignupMode &&
                                              (!text.contains('@') ||
                                                  !text
                                                      .split('@')
                                                      .last
                                                      .contains('.'))) {
                                            return 'Please use a valid email address';
                                          }
                                          return null;
                                        },
                                      ),
                                      const SizedBox(height: 12),
                                      TextFormField(
                                        controller: _passwordController,
                                        textInputAction: _isSignupMode
                                            ? TextInputAction.next
                                            : TextInputAction.done,
                                        obscureText: _obscurePassword,
                                        onFieldSubmitted: (_) {
                                          if (!_loading && !_isSignupMode) {
                                            _login();
                                          }
                                        },
                                        decoration: InputDecoration(
                                          hintText: 'Password',
                                          prefixIcon:
                                              const Icon(Icons.lock_outline),
                                          suffixIcon: IconButton(
                                            tooltip: _obscurePassword
                                                ? 'Show password'
                                                : 'Hide password',
                                            icon: Icon(
                                              _obscurePassword
                                                  ? Icons.visibility_off
                                                  : Icons.visibility,
                                            ),
                                            onPressed: () {
                                              setState(() {
                                                _obscurePassword =
                                                    !_obscurePassword;
                                              });
                                            },
                                          ),
                                        ),
                                        validator: (value) {
                                          if (value == null || value.isEmpty) {
                                            return 'Required';
                                          }
                                          if (_isSignupMode &&
                                              value.length < 6) {
                                            return 'Password must be at least 6 characters';
                                          }
                                          return null;
                                        },
                                      ),
                                      if (_isSignupMode) ...[
                                        const SizedBox(height: 12),
                                        TextFormField(
                                          controller:
                                              _confirmPasswordController,
                                          textInputAction: TextInputAction.done,
                                          obscureText: _obscureConfirmPassword,
                                          onFieldSubmitted: (_) {
                                            if (!_loading) {
                                              _signup();
                                            }
                                          },
                                          decoration: InputDecoration(
                                            hintText: 'Confirm password',
                                            prefixIcon:
                                                const Icon(Icons.lock_reset),
                                            suffixIcon: IconButton(
                                              tooltip: _obscureConfirmPassword
                                                  ? 'Show password'
                                                  : 'Hide password',
                                              icon: Icon(
                                                _obscureConfirmPassword
                                                    ? Icons.visibility_off
                                                    : Icons.visibility,
                                              ),
                                              onPressed: () {
                                                setState(() {
                                                  _obscureConfirmPassword =
                                                      !_obscureConfirmPassword;
                                                });
                                              },
                                            ),
                                          ),
                                          validator: (value) {
                                            if (!_isSignupMode) {
                                              return null;
                                            }
                                            if ((value ?? '').isEmpty) {
                                              return 'Required';
                                            }
                                            if (value !=
                                                _passwordController.text) {
                                              return 'Passwords do not match';
                                            }
                                            return null;
                                          },
                                        ),
                                      ],
                                      const SizedBox(height: 14),
                                      if (_error != null)
                                        Container(
                                          width: double.infinity,
                                          margin:
                                              const EdgeInsets.only(bottom: 10),
                                          padding: const EdgeInsets.all(10),
                                          decoration: BoxDecoration(
                                            color: scheme.errorContainer,
                                            borderRadius:
                                                BorderRadius.circular(14),
                                          ),
                                          child: Text(
                                            _error!,
                                            style: TextStyle(
                                              color: scheme.onErrorContainer,
                                            ),
                                          ),
                                        ),
                                      SizedBox(
                                        width: double.infinity,
                                        child: FilledButton(
                                          onPressed:
                                              (_loading || _socialLoading)
                                                  ? null
                                                  : (_isSignupMode
                                                      ? _signup
                                                      : _login),
                                          style: FilledButton.styleFrom(
                                            minimumSize:
                                                const Size.fromHeight(54),
                                            shape: RoundedRectangleBorder(
                                              borderRadius:
                                                  BorderRadius.circular(18),
                                            ),
                                          ),
                                          child: Text(_loading
                                              ? (_isSignupMode
                                                  ? 'Creating account...'
                                                  : 'Signing in...')
                                              : (_isSignupMode
                                                  ? 'Create account'
                                                  : 'Sign in')),
                                        ),
                                      ),
                                      const SizedBox(height: 12),
                                      if (_checkingProviders)
                                        const LinearProgressIndicator(
                                            minHeight: 2)
                                      else ...[
                                        if (_shouldShowGoogleSignIn)
                                          SizedBox(
                                            width: double.infinity,
                                            child: OutlinedButton.icon(
                                              onPressed: (_loading ||
                                                      _socialLoading)
                                                  ? null
                                                  : _startGoogleLoginNativeFirst,
                                              style: OutlinedButton.styleFrom(
                                                minimumSize:
                                                    const Size.fromHeight(54),
                                                shape: RoundedRectangleBorder(
                                                  borderRadius:
                                                      BorderRadius.circular(18),
                                                ),
                                              ),
                                              icon: _buildSocialButtonLogo(
                                                'assets/images/google.png',
                                              ),
                                              label: Text(_socialLoading
                                                  ? 'Signing in with Google...'
                                                  : 'Continue with Google'),
                                            ),
                                          ),
                                        if (_shouldShowGoogleSignIn ||
                                            _microsoftEnabled)
                                          const SizedBox(height: 8),
                                        if (_microsoftEnabled)
                                          SizedBox(
                                            width: double.infinity,
                                            child: OutlinedButton(
                                              onPressed:
                                                  (_loading || _socialLoading)
                                                      ? null
                                                      : () => _startSocialLogin(
                                                          'microsoft'),
                                              style: OutlinedButton.styleFrom(
                                                minimumSize:
                                                    const Size.fromHeight(54),
                                                shape: RoundedRectangleBorder(
                                                  borderRadius:
                                                      BorderRadius.circular(18),
                                                ),
                                              ),
                                              child: const Text(
                                                  'Continue with Microsoft'),
                                            ),
                                          ),
                                        if (_shouldShowAppleSignIn) ...[
                                          if (_shouldShowGoogleSignIn ||
                                              _microsoftEnabled)
                                            const SizedBox(height: 8),
                                          SizedBox(
                                            width: double.infinity,
                                            child: OutlinedButton.icon(
                                              onPressed: (_loading ||
                                                      _socialLoading)
                                                  ? null
                                                  : _startAppleLoginNativeFirst,
                                              style: OutlinedButton.styleFrom(
                                                minimumSize:
                                                    const Size.fromHeight(54),
                                                shape: RoundedRectangleBorder(
                                                  borderRadius:
                                                      BorderRadius.circular(18),
                                                ),
                                              ),
                                              icon: _buildSocialButtonLogo(
                                                'assets/images/apple.png',
                                              ),
                                              label: const Text(
                                                  'Continue with Apple'),
                                            ),
                                          ),
                                        ],
                                        const SizedBox(height: 12),
                                        Center(
                                          child: Wrap(
                                            alignment: WrapAlignment.center,
                                            spacing: 6,
                                            runSpacing: 6,
                                            children: [
                                              TextButton(
                                                onPressed:
                                                    (_loading || _socialLoading)
                                                        ? null
                                                        : () {
                                                            setState(() {
                                                              _isSignupMode =
                                                                  !_isSignupMode;
                                                              _error = null;
                                                            });
                                                          },
                                                child: Text(_isSignupMode
                                                    ? 'Already have an account? Log in'
                                                    : 'Create an account'),
                                              ),
                                              if (!_isSignupMode) ...[
                                                const Text('·'),
                                                TextButton(
                                                  onPressed: (_loading ||
                                                          _socialLoading)
                                                      ? null
                                                      : _openPasswordReset,
                                                  child: const Text(
                                                      'Forgot password?'),
                                                ),
                                                const Text('·'),
                                                TextButton(
                                                  onPressed: (_loading ||
                                                          _socialLoading)
                                                      ? null
                                                      : () => _openPublicPage(
                                                          '/resend-verification'),
                                                  child: const Text(
                                                      'Resend verification'),
                                                ),
                                              ],
                                            ],
                                          ),
                                        ),
                                      ],
                                    ],
                                  ),
                                ),
                              ),
                            ),
                            const SizedBox(height: 10),
                          ],
                        ),
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

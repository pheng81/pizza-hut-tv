import 'dart:async';

import 'package:app_links/app_links.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_sign_in/google_sign_in.dart';
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
  final _formKey = GlobalKey<FormState>();
  final _fullNameController = TextEditingController();
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();
  final _baseUrlController = TextEditingController();

  bool _loading = false;
  bool _socialLoading = false;
  bool _checkingProviders = true;
  bool _isSignupMode = false;
  bool _googleEnabled = false;
  bool _microsoftEnabled = false;
  bool _appleEnabled = false;
  String _googleClientId = '';
  bool _obscurePassword = true;
  bool _obscureConfirmPassword = true;
  String? _error;
  late final AnimationController _bgController;
  final AppLinks _appLinks = AppLinks();
  StreamSubscription<Uri>? _linkSub;

  @override
  void initState() {
    super.initState();
    _baseUrlController.text = widget.apiClient.baseUrl;
    _bgController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 12),
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
    _baseUrlController.dispose();
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
        _googleClientId = (providers['google_client_id'] ?? '').toString();
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
      final serverClientId = _googleClientId.trim();
      final signIn = GoogleSignIn(
        scopes: const ['email', 'profile'],
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
        if (!mounted) {
          return;
        }
        setState(() {
          _socialLoading = false;
          _error =
              'Native Google token not returned. Please check Google Play Services/account on this device.';
        });
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
                        colors: const [Color(0x664DD0E1), Color(0x663B82F6)],
                      ),
                      const SizedBox(width: 14),
                      bannerCard(
                        title: 'PROMO LOOP',
                        icon: Icons.movie_creation_outlined,
                        width: 212,
                        height: 94,
                        colors: const [Color(0x665F7CFA), Color(0x664338CA)],
                      ),
                      const SizedBox(width: 14),
                      bannerCard(
                        title: 'SCREEN ADS',
                        icon: Icons.slideshow,
                        width: 216,
                        height: 94,
                        colors: const [Color(0x6667E8F9), Color(0x662563EB)],
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
                        colors: const [Color(0x66EC4899), Color(0x667C3AED)],
                      ),
                      const SizedBox(width: 12),
                      bannerCard(
                        title: 'IN-STORE OFFER',
                        icon: Icons.local_offer_outlined,
                        width: 208,
                        height: 86,
                        colors: const [Color(0x66F59E0B), Color(0x66EA580C)],
                      ),
                      const SizedBox(width: 12),
                      bannerCard(
                        title: 'LIVE DISPLAY',
                        icon: Icons.cast_connected,
                        width: 204,
                        height: 86,
                        colors: const [Color(0x6622C55E), Color(0x66059669)],
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
                        colors: const [Color(0x663B82F6), Color(0x661D4ED8)],
                      ),
                      const SizedBox(width: 12),
                      bannerCard(
                        title: 'MULTI-SCREEN READY',
                        icon: Icons.grid_view_rounded,
                        width: 228,
                        height: 80,
                        colors: const [Color(0x668B5CF6), Color(0x664C1D95)],
                      ),
                      const SizedBox(width: 12),
                      bannerCard(
                        title: 'TV + MOBILE CONTROL',
                        icon: Icons.phone_android,
                        width: 232,
                        height: 80,
                        colors: const [Color(0x660EA5E9), Color(0x660369A1)],
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
    if (!_formKey.currentState!.validate()) {
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      await widget.apiClient.login(
        username: _usernameController.text.trim(),
        password: _passwordController.text,
      );
      await widget.onLoginSuccess();
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

  Future<void> _saveBaseUrl() async {
    try {
      await widget.apiClient.setBaseUrl(_baseUrlController.text);
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Base URL updated')),
      );
    } catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.toString().replaceFirst('Exception: ', ''))),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    return Scaffold(
      body: Stack(
        children: [
          Container(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  Color(0xFF111A33),
                  Color(0xFF1C2A4A),
                ],
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
                colors: [Color(0x22000000), Color(0x77000000)],
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
                            Card(
                              elevation: 0,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(18),
                                side: BorderSide(color: scheme.outlineVariant),
                              ),
                              child: Padding(
                                padding: const EdgeInsets.all(18),
                                child: Form(
                                  key: _formKey,
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        _isSignupMode
                                            ? 'Sign Up for Free'
                                            : 'Sign in',
                                        style: Theme.of(context)
                                            .textTheme
                                            .headlineSmall,
                                      ),
                                      const SizedBox(height: 4),
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
                                                    'By clicking Continue, you agree to our ',
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
                                              const TextSpan(text: ' and our '),
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
                                                    '. You\'ll receive a verification email to confirm your account.',
                                              ),
                                            ],
                                          ),
                                        )
                                      else
                                        Text(
                                          'Use your dashboard account credentials.',
                                          style: Theme.of(context)
                                              .textTheme
                                              .bodySmall
                                              ?.copyWith(
                                                color: scheme.onSurfaceVariant,
                                              ),
                                        ),
                                      const SizedBox(height: 14),
                                      TextFormField(
                                        controller: _baseUrlController,
                                        keyboardType: TextInputType.url,
                                        textInputAction: TextInputAction.next,
                                        decoration: InputDecoration(
                                          labelText: 'API Base URL',
                                          prefixIcon: const Icon(Icons.link),
                                          suffixIcon: IconButton(
                                            tooltip: 'Save URL',
                                            icon:
                                                const Icon(Icons.save_outlined),
                                            onPressed: _saveBaseUrl,
                                          ),
                                        ),
                                        validator: (value) {
                                          if (value == null ||
                                              value.trim().isEmpty) {
                                            return 'Required';
                                          }
                                          return null;
                                        },
                                      ),
                                      const SizedBox(height: 12),
                                      if (_isSignupMode) ...[
                                        TextFormField(
                                          controller: _fullNameController,
                                          textInputAction: TextInputAction.next,
                                          decoration: const InputDecoration(
                                            labelText: 'Full Name',
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
                                          labelText: _isSignupMode
                                              ? 'Email Address'
                                              : 'Username',
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
                                          labelText: 'Password',
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
                                            labelText: 'Confirm Password',
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
                                                BorderRadius.circular(10),
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
                                        child: FilledButton.icon(
                                          onPressed:
                                              (_loading || _socialLoading)
                                                  ? null
                                                  : (_isSignupMode
                                                      ? _signup
                                                      : _login),
                                          icon: _loading
                                              ? const SizedBox(
                                                  height: 16,
                                                  width: 16,
                                                  child:
                                                      CircularProgressIndicator(
                                                    strokeWidth: 2,
                                                  ),
                                                )
                                              : Icon(_isSignupMode
                                                  ? Icons.person_add_alt_1
                                                  : Icons.login),
                                          label: Text(_loading
                                              ? (_isSignupMode
                                                  ? 'Creating account...'
                                                  : 'Signing in...')
                                              : (_isSignupMode
                                                  ? 'Create Account'
                                                  : 'Sign in')),
                                        ),
                                      ),
                                      const SizedBox(height: 12),
                                      if (_checkingProviders)
                                        const LinearProgressIndicator(
                                            minHeight: 2)
                                      else ...[
                                        if (_googleEnabled)
                                          SizedBox(
                                            width: double.infinity,
                                            child: OutlinedButton.icon(
                                              onPressed: (_loading ||
                                                      _socialLoading)
                                                  ? null
                                                  : _startGoogleLoginNativeFirst,
                                              icon: const Icon(
                                                  Icons.g_mobiledata),
                                              label: Text(_socialLoading
                                                  ? 'Signing in with Google...'
                                                  : 'Continue with Google'),
                                            ),
                                          ),
                                        if (_googleEnabled || _microsoftEnabled)
                                          const SizedBox(height: 8),
                                        if (_microsoftEnabled)
                                          SizedBox(
                                            width: double.infinity,
                                            child: OutlinedButton.icon(
                                              onPressed:
                                                  (_loading || _socialLoading)
                                                      ? null
                                                      : () => _startSocialLogin(
                                                          'microsoft'),
                                              icon: const Icon(
                                                  Icons.window_rounded),
                                              label: const Text(
                                                  'Continue with Microsoft'),
                                            ),
                                          ),
                                        if (_appleEnabled) ...[
                                          if (_googleEnabled ||
                                              _microsoftEnabled)
                                            const SizedBox(height: 8),
                                          SizedBox(
                                            width: double.infinity,
                                            child: OutlinedButton.icon(
                                              onPressed:
                                                  (_loading || _socialLoading)
                                                      ? null
                                                      : () => _startSocialLogin(
                                                          'apple'),
                                              icon: const Icon(Icons.apple),
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

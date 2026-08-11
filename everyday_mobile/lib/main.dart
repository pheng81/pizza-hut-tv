import 'dart:math' as math;

import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';

import 'screens/login_screen.dart';
import 'screens/main_shell.dart';
import 'services/api_client.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const EverydayMobileApp());
}

class EverydayMobileApp extends StatefulWidget {
  const EverydayMobileApp({super.key});

  @override
  State<EverydayMobileApp> createState() => _EverydayMobileAppState();
}

class _EverydayMobileAppState extends State<EverydayMobileApp> {
  late final ApiClient _apiClient;
  bool _authenticated = false;
  bool _introVisible = true;
  bool _introFadingOut = false;
  bool _introLogoEntered = false;
  bool _bootstrapped = false;

  @override
  void initState() {
    super.initState();
    _apiClient = ApiClient();
    _startIntroSequence();
    _bootstrap();
  }

  Future<void> _startIntroSequence() async {
    if (!mounted) {
      return;
    }
    setState(() {
      _introVisible = true;
      _introFadingOut = false;
      _introLogoEntered = false;
    });

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _introLogoEntered = true;
      });
    });

    await Future.delayed(const Duration(milliseconds: 1600));
    if (!mounted) {
      return;
    }
    setState(() {
      _introFadingOut = true;
    });
    await Future.delayed(const Duration(milliseconds: 400));
    if (!mounted) {
      return;
    }
    setState(() {
      _introVisible = false;
    });
  }

  Future<void> _bootstrap() async {
    await _apiClient.init();
    final ok = await _apiClient.checkSession();
    if (!mounted) {
      return;
    }
    setState(() {
      _authenticated = ok;
      _bootstrapped = true;
    });
  }

  Future<void> _onLoginSuccess() async {
    if (!mounted) {
      return;
    }
    setState(() {
      _authenticated = true;
    });
  }

  Future<void> _onLogout() async {
    await _apiClient.logout();
    if (!mounted) {
      return;
    }
    setState(() {
      _authenticated = false;
    });
    await _startIntroSequence();
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = ColorScheme.fromSeed(
      seedColor: CupertinoColors.activeBlue,
      brightness: Brightness.light,
    );
    return MaterialApp(
      title: 'Everyday Mobile',
      theme: ThemeData(
        colorScheme: colorScheme,
        useMaterial3: true,
        scaffoldBackgroundColor: CupertinoColors.systemGroupedBackground,
        appBarTheme: AppBarTheme(
          backgroundColor: colorScheme.primary,
          foregroundColor: Colors.white,
          centerTitle: false,
          elevation: 0,
        ),
        cardTheme: CardThemeData(
          elevation: 0,
          color: Colors.white,
          margin: EdgeInsets.zero,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
        ),
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
            minimumSize: const Size(0, 46),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
        ),
        outlinedButtonTheme: OutlinedButtonThemeData(
          style: OutlinedButton.styleFrom(
            minimumSize: const Size(0, 42),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: const Color(0xFFF8FAFC),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide(color: colorScheme.outlineVariant),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide(color: colorScheme.outlineVariant),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide(color: colorScheme.primary, width: 1.4),
          ),
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        ),
      ),
      debugShowCheckedModeBanner: false,
      home: !_bootstrapped || _introVisible
          ? _IntroSplash(
              fadingOut: _introFadingOut,
              logoEntered: _introLogoEntered,
            )
          : (_authenticated
              ? MainShell(
                  apiClient: _apiClient,
                  onLogout: _onLogout,
                )
              : LoginScreen(
                  apiClient: _apiClient,
                  onLoginSuccess: _onLoginSuccess,
                )),
    );
  }
}

class _IntroSplash extends StatefulWidget {
  const _IntroSplash({
    required this.fadingOut,
    required this.logoEntered,
  });

  final bool fadingOut;
  final bool logoEntered;

  @override
  State<_IntroSplash> createState() => _IntroSplashState();
}

class _IntroSplashState extends State<_IntroSplash>
    with SingleTickerProviderStateMixin {
  late final AnimationController _gradient;

  @override
  void initState() {
    super.initState();
    _gradient = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2800),
    )..repeat();
  }

  @override
  void dispose() {
    _gradient.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final logoWidth = MediaQuery.sizeOf(context).width * 0.84;
    return Scaffold(
      backgroundColor: const Color(0xFF0B0F16),
      body: SafeArea(
        child: Center(
          child: AnimatedBuilder(
            animation: _gradient,
            child: SizedBox(
              width: logoWidth,
              child: FittedBox(
                fit: BoxFit.scaleDown,
                child: Text(
                  'Everyday\nAdvertise',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 160,
                    fontWeight: FontWeight.w800,
                    height: 0.82,
                    letterSpacing: -2,
                    shadows: [
                      Shadow(
                        color: Color(0x66000000),
                        blurRadius: 14,
                        offset: Offset(0, 4),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            builder: (context, logo) {
              final shift = math.sin(_gradient.value * math.pi * 2) * 0.35;
              return AnimatedOpacity(
                opacity: widget.fadingOut ? 0 : 1,
                duration: const Duration(milliseconds: 350),
                child: AnimatedScale(
                  scale: widget.logoEntered ? 1 : 0.9,
                  duration: const Duration(milliseconds: 700),
                  curve: Curves.easeOutCubic,
                  child: ShaderMask(
                    blendMode: BlendMode.srcIn,
                    shaderCallback: (bounds) => LinearGradient(
                      begin: Alignment(-1.2 + shift, -0.15),
                      end: Alignment(1.2 + shift, 0.15),
                      colors: const [
                        Color(0xFFFF2D84),
                        Color(0xFFB544FF),
                        Color(0xFF3C6CFF),
                      ],
                    ).createShader(bounds),
                    child: logo,
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}

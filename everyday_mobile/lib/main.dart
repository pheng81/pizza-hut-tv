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
  bool _introVisible = false;
  bool _introFadingOut = false;
  bool _introLogoEntered = false;
  bool _bootstrapped = false;

  @override
  void initState() {
    super.initState();
    _apiClient = ApiClient();
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

    await Future.delayed(const Duration(milliseconds: 3500));
    if (!mounted) {
      return;
    }
    setState(() {
      _introFadingOut = true;
    });
    await Future.delayed(const Duration(milliseconds: 700));
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
    if (!ok) {
      await _startIntroSequence();
    }
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
      seedColor: const Color(0xFF1D4ED8),
      brightness: Brightness.light,
    );
    return MaterialApp(
      title: 'Everyday Mobile',
      theme: ThemeData(
        colorScheme: colorScheme,
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFFF4F6FA),
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
            borderRadius: BorderRadius.circular(14),
            side: BorderSide(color: colorScheme.outlineVariant.withAlpha(140)),
          ),
        ),
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
            minimumSize: const Size.fromHeight(46),
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
      builder: (context, child) {
        if (child == null) {
          return const SizedBox.shrink();
        }
        return Stack(
          children: [
            child,
            if (_introVisible)
              Positioned.fill(
                child: IgnorePointer(
                  child: AnimatedOpacity(
                    opacity: _introFadingOut ? 0 : 1,
                    duration: const Duration(milliseconds: 600),
                    curve: Curves.easeOut,
                    child: ColoredBox(
                      color: const Color(0xFF0B0B0F),
                      child: Center(
                        child: AnimatedScale(
                          scale: _introLogoEntered ? 1.0 : 0.9,
                          duration: const Duration(milliseconds: 1000),
                          curve: Curves.easeOut,
                          child: AnimatedOpacity(
                            opacity: _introLogoEntered ? 1 : 0,
                            duration: const Duration(milliseconds: 1000),
                            curve: Curves.easeOut,
                            child: const _IntroWordmark(),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
          ],
        );
      },
      home: !_bootstrapped
          ? const Scaffold(body: SizedBox.expand())
          : (_authenticated
              ? MainShell(
                  apiClient: _apiClient,
                  onLogout: _onLogout,
                )
              : (_introVisible
                  ? const Scaffold(body: SizedBox.expand())
                  : LoginScreen(
                      apiClient: _apiClient,
                      onLoginSuccess: _onLoginSuccess,
                    ))),
    );
  }
}

class _IntroWordmark extends StatelessWidget {
  const _IntroWordmark();

  @override
  Widget build(BuildContext context) {
    final base = Theme.of(context).textTheme.displayMedium?.copyWith(
      fontWeight: FontWeight.w900,
      color: const Color(0xFFFF6A00),
      height: 0.95,
      letterSpacing: -1.0,
      shadows: const [
        Shadow(
          color: Color(0x66000000),
          blurRadius: 14,
          offset: Offset(0, 2),
        ),
      ],
    );

    return FittedBox(
      fit: BoxFit.scaleDown,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24),
        child: Text(
          'Everyday\nAdvertise',
          textAlign: TextAlign.center,
          style: base,
        ),
      ),
    );
  }
}

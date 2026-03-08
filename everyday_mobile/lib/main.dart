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

  @override
  void initState() {
    super.initState();
    _apiClient = ApiClient();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    await _apiClient.init();
    final ok = await _apiClient.checkSession();
    if (!mounted) {
      return;
    }
    setState(() {
      _authenticated = ok;
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
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Everyday Mobile',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.red),
        useMaterial3: true,
      ),
      home: _authenticated
          ? MainShell(
              apiClient: _apiClient,
              onLogout: _onLogout,
            )
          : LoginScreen(
              apiClient: _apiClient,
              onLoginSuccess: _onLoginSuccess,
            ),
    );
  }
}

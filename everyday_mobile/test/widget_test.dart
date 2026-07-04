// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:everyday_mobile/screens/login_screen.dart';
import 'package:everyday_mobile/services/api_client.dart';

void main() {
  testWidgets('Login screen renders', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});
    final apiClient = ApiClient();
    await apiClient.init();

    await tester.pumpWidget(
      MaterialApp(
        home: LoginScreen(
          apiClient: apiClient,
          onLoginSuccess: () async {},
          enableSocialAuthBootstrap: false,
        ),
      ),
    );

    expect(find.text('Sign in'), findsWidgets);
    expect(find.text('Use your dashboard account credentials.'), findsOneWidget);
    expect(find.text('API Base URL'), findsOneWidget);
    expect(find.byType(TextFormField), findsWidgets);
  });
}

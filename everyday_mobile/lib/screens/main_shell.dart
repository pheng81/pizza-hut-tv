import 'package:flutter/material.dart';

import '../services/api_client.dart';
import 'tabs/commands_tab.dart';
import 'tabs/profile_tab.dart';
import 'tabs/stores_tab.dart';
import 'tabs/upload_tab.dart';

class MainShell extends StatefulWidget {
  const MainShell({
    super.key,
    required this.apiClient,
    required this.onLogout,
  });

  final ApiClient apiClient;
  final Future<void> Function() onLogout;

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _index = 0;
  String? _selectedStoreId;
  String? _selectedScreenId;

  @override
  Widget build(BuildContext context) {
    final tabs = [
      StoresTab(
        apiClient: widget.apiClient,
        selectedStoreId: _selectedStoreId,
        selectedScreenId: _selectedScreenId,
        onSelectionChanged: (storeId, screenId) {
          setState(() {
            _selectedStoreId = storeId;
            _selectedScreenId = screenId;
          });
        },
      ),
      UploadTab(
        apiClient: widget.apiClient,
        selectedStoreId: _selectedStoreId,
        selectedScreenId: _selectedScreenId,
      ),
      CommandsTab(apiClient: widget.apiClient),
      ProfileTab(
        apiClient: widget.apiClient,
        onLogout: widget.onLogout,
      ),
    ];

    return Scaffold(
      body: SafeArea(child: tabs[_index]),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (value) {
          setState(() {
            _index = value;
          });
        },
        destinations: const [
          NavigationDestination(icon: Icon(Icons.store), label: 'Stores'),
          NavigationDestination(icon: Icon(Icons.upload_file), label: 'Upload'),
          NavigationDestination(icon: Icon(Icons.tv), label: 'Commands'),
          NavigationDestination(icon: Icon(Icons.person), label: 'Profile'),
        ],
      ),
    );
  }
}

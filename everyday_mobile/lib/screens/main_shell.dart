import 'package:flutter/material.dart';

import '../services/api_client.dart';
import 'tabs/commands_tab.dart';
import 'tabs/device_manager_tab.dart';
import 'tabs/profile_tab.dart';
import 'tabs/stores_tab.dart';

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
    final scheme = Theme.of(context).colorScheme;
    final titles = [
      'Stores & Screens',
      'Device Manager',
      'TV Commands',
      'Profile'
    ];
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
      DeviceManagerTab(apiClient: widget.apiClient),
      CommandsTab(apiClient: widget.apiClient),
      ProfileTab(
        apiClient: widget.apiClient,
        onLogout: widget.onLogout,
      ),
    ];

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(titles[_index]),
            Text(
              'Everyday Advertise',
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: Colors.white.withAlpha(220),
                  ),
            ),
          ],
        ),
      ),
      body: SafeArea(child: tabs[_index]),
      bottomNavigationBar: NavigationBar(
        height: 72,
        backgroundColor: Colors.white,
        indicatorColor: scheme.primaryContainer,
        selectedIndex: _index,
        onDestinationSelected: (value) {
          setState(() {
            _index = value;
          });
        },
        destinations: const [
          NavigationDestination(icon: Icon(Icons.storefront), label: 'Stores'),
          NavigationDestination(icon: Icon(Icons.devices), label: 'Devices'),
          NavigationDestination(icon: Icon(Icons.tv), label: 'Commands'),
          NavigationDestination(icon: Icon(Icons.person), label: 'Profile'),
        ],
      ),
    );
  }
}

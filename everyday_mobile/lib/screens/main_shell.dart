import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';

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

class _MainShellState extends State<MainShell>
    with SingleTickerProviderStateMixin {
  int _index = 0;
  String? _selectedStoreId;
  String? _selectedScreenId;
  String? _profileAvatarUrl;
  late final AnimationController _chrome;

  @override
  void initState() {
    super.initState();
    _chrome = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 220),
      value: 1,
    );
    _loadProfileAvatar();
  }

  @override
  void dispose() {
    _chrome.dispose();
    super.dispose();
  }

  bool _handleContentScroll(ScrollNotification notification) {
    if (notification.metrics.axis != Axis.vertical) {
      return false;
    }
    if (notification.metrics.pixels <=
        notification.metrics.minScrollExtent + 4) {
      _chrome.forward();
      return false;
    }
    if (notification is UserScrollNotification) {
      if (notification.direction == ScrollDirection.reverse) {
        _chrome.reverse();
      } else if (notification.direction == ScrollDirection.forward) {
        _chrome.forward();
      }
    }
    return false;
  }

  Future<void> _loadProfileAvatar() async {
    try {
      final profile = await widget.apiClient.getMe();
      if (!mounted) {
        return;
      }
      setState(() {
        final nextUrl = (profile.avatarUrl ?? '').trim();
        _profileAvatarUrl = nextUrl.isEmpty ? null : nextUrl;
      });
    } catch (_) {
      // keep default icon
    }
  }

  Widget _buildCurrentTab() {
    switch (_index) {
      case 0:
        return StoresTab(
          apiClient: widget.apiClient,
          selectedStoreId: _selectedStoreId,
          selectedScreenId: _selectedScreenId,
          onSelectionChanged: (storeId, screenId) {
            setState(() {
              _selectedStoreId = storeId;
              _selectedScreenId = screenId;
            });
          },
        );
      case 1:
        return DeviceManagerTab(apiClient: widget.apiClient);
      case 2:
        return CommandsTab(apiClient: widget.apiClient);
      case 3:
        return ProfileTab(
          apiClient: widget.apiClient,
          onLogout: widget.onLogout,
          onProfileChanged: _loadProfileAvatar,
        );
      default:
        return const SizedBox.shrink();
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final titles = [
      'Stores & Screens',
      'Device Manager',
      'TV Commands',
      'Profile'
    ];
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.dark,
        statusBarBrightness: Brightness.light,
        systemNavigationBarColor: Colors.white,
        systemNavigationBarIconBrightness: Brightness.dark,
      ),
      child: Scaffold(
        backgroundColor: Colors.white,
        body: Stack(
          children: [
            Positioned(
              top: 0,
              left: 0,
              right: 0,
              height: 360,
              child: const ColoredBox(color: Colors.white),
            ),
            SafeArea(
              bottom: false,
              child: Column(
                children: [
                SizeTransition(
                  axisAlignment: -1,
                  sizeFactor: _chrome,
                  child: _SimpleHeader(
                    title: titles[_index],
                    subtitle: 'Everyday Advertise',
                  ),
                ),
                Expanded(
                  child: NotificationListener<ScrollNotification>(
                    onNotification: _handleContentScroll,
                    child: _buildCurrentTab(),
                  ),
                ),
                SafeArea(
                  top: false,
                  child: Container(
                    width: double.infinity,
                    color: Colors.white,
                    padding: const EdgeInsets.fromLTRB(8, 4, 8, 6),
                    child: Row(
                      children: [
                      _NavIconButton(
                        icon: Icons.storefront,
                        selected: _index == 0,
                        colorScheme: scheme,
                        onTap: () => setState(() => _index = 0),
                      ),
                      _NavIconButton(
                        icon: Icons.devices,
                        selected: _index == 1,
                        colorScheme: scheme,
                        onTap: () => setState(() => _index = 1),
                      ),
                      _NavIconButton(
                        icon: Icons.tv,
                        selected: _index == 2,
                        colorScheme: scheme,
                        onTap: () => setState(() => _index = 2),
                      ),
                        _NavIconButton(
                          icon: Icons.person,
                          selected: _index == 3,
                          colorScheme: scheme,
                          avatarUrl: _profileAvatarUrl,
                          apiClient: widget.apiClient,
                          onTap: () {
                            setState(() => _index = 3);
                            _loadProfileAvatar();
                          },
                        ),
                      ],
                    ),
                  ),
                ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _NavIconButton extends StatelessWidget {
  const _NavIconButton({
    required this.icon,
    required this.selected,
    required this.colorScheme,
    required this.onTap,
    this.avatarUrl,
    this.apiClient,
  });

  final IconData icon;
  final bool selected;
  final ColorScheme colorScheme;
  final VoidCallback onTap;
  final String? avatarUrl;
  final ApiClient? apiClient;

  @override
  Widget build(BuildContext context) {
    final hasAvatar = (avatarUrl ?? '').trim().isNotEmpty;
    ImageProvider? avatarProvider;
    if (hasAvatar) {
      final raw = avatarUrl!.trim();
      if (raw.startsWith('http://') || raw.startsWith('https://')) {
        avatarProvider = NetworkImage(raw);
      } else if (apiClient != null) {
        final normalizedBase = apiClient!.baseUrl.replaceAll(RegExp(r'/$'), '');
        final normalizedPath = raw.startsWith('/') ? raw : '/$raw';
        avatarProvider = NetworkImage('$normalizedBase$normalizedPath');
      }
    }
    return Expanded(
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: hasAvatar
              ? Center(
                  child: Container(
                    width: 26,
                    height: 26,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: selected
                          ? colorScheme.primaryContainer
                          : colorScheme.surfaceContainerHighest,
                      border: Border.all(
                        color: selected
                            ? colorScheme.primary
                            : colorScheme.outlineVariant,
                        width: selected ? 1.8 : 1,
                      ),
                      image: avatarProvider == null
                          ? null
                          : DecorationImage(
                              image: avatarProvider,
                              fit: BoxFit.cover,
                            ),
                    ),
                  ),
                )
              : Icon(
                  icon,
                  size: 24,
                  color: selected
                      ? colorScheme.primary
                      : colorScheme.onSurfaceVariant,
                ),
        ),
      ),
    );
  }
}

class _SimpleHeader extends StatelessWidget {
  const _SimpleHeader({required this.title, required this.subtitle});

  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      decoration: const BoxDecoration(color: Colors.transparent),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  color: const Color(0xFF1F2937),
                  fontWeight: FontWeight.w700,
                ),
          ),
          const SizedBox(height: 2),
          Text(
            subtitle,
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
                  color: const Color(0xFF6B7280),
                ),
          ),
        ],
      ),
    );
  }
}

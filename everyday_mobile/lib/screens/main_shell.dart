import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_svg/flutter_svg.dart';

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
  String? _profileLinkCode;
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
        final nextCode = (profile.linkCode ?? '').trim();
        _profileLinkCode = nextCode.isEmpty ? null : nextCode;
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
        return CommandsTab(
          key: const ValueKey('tv-commands'),
          apiClient: widget.apiClient,
          initialMode: CommandsMode.tv,
        );
      case 3:
        return CommandsTab(
          key: const ValueKey('remote-control'),
          apiClient: widget.apiClient,
          initialMode: CommandsMode.remote,
        );
      case 4:
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
      'Remote Control',
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
                      linkCode: _profileLinkCode,
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
                    child: CupertinoTabBar(
                      currentIndex: _index,
                      onTap: (index) {
                        setState(() => _index = index);
                        if (index == 4) {
                          _loadProfileAvatar();
                        }
                      },
                      activeColor: scheme.primary,
                      inactiveColor: const Color(0xFF6B7280),
                      backgroundColor: Colors.white,
                      border: const Border(
                        top: BorderSide(color: Color(0xFFE5E5EA)),
                      ),
                      items: [
                        const BottomNavigationBarItem(
                          icon: Icon(CupertinoIcons.building_2_fill),
                        ),
                        const BottomNavigationBarItem(
                          icon: _DeviceTabIcon(),
                        ),
                        const BottomNavigationBarItem(
                          icon: Icon(CupertinoIcons.tv),
                        ),
                        const BottomNavigationBarItem(
                          icon: Icon(CupertinoIcons.game_controller_solid),
                        ),
                        BottomNavigationBarItem(
                          icon: _ProfileTabIcon(
                            avatarUrl: _profileAvatarUrl,
                            apiClient: widget.apiClient,
                            selected: _index == 4,
                          ),
                        ),
                      ],
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

class _ProfileTabIcon extends StatelessWidget {
  const _ProfileTabIcon({
    required this.avatarUrl,
    required this.apiClient,
    required this.selected,
  });

  final String? avatarUrl;
  final ApiClient apiClient;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    final hasAvatar = (avatarUrl ?? '').trim().isNotEmpty;
    ImageProvider? avatarProvider;
    if (hasAvatar) {
      final raw = avatarUrl!.trim();
      if (raw.startsWith('http://') || raw.startsWith('https://')) {
        avatarProvider = NetworkImage(raw);
      } else {
        final normalizedBase = apiClient.baseUrl.replaceAll(RegExp(r'/$'), '');
        final normalizedPath = raw.startsWith('/') ? raw : '/$raw';
        avatarProvider = NetworkImage('$normalizedBase$normalizedPath');
      }
    }
    return Container(
      width: 28,
      height: 28,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: CupertinoColors.systemGrey5,
        border: Border.all(
          color: selected
              ? CupertinoColors.activeBlue
              : CupertinoColors.systemGrey4,
          width: selected ? 1.8 : 1,
        ),
        image: avatarProvider == null
            ? null
            : DecorationImage(image: avatarProvider, fit: BoxFit.cover),
      ),
      child: avatarProvider == null
          ? const Icon(CupertinoIcons.person_fill, size: 16)
          : null,
    );
  }
}

class _DeviceTabIcon extends StatelessWidget {
  const _DeviceTabIcon();

  @override
  Widget build(BuildContext context) {
    return SvgPicture.asset(
      'assets/images/everyday_box.svg',
      width: 29,
      height: 29,
      fit: BoxFit.contain,
    );
  }
}

class _SimpleHeader extends StatelessWidget {
  const _SimpleHeader({
    required this.title,
    required this.subtitle,
    required this.linkCode,
  });

  final String title;
  final String subtitle;
  final String? linkCode;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      decoration: const BoxDecoration(color: Colors.transparent),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Expanded(
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
          ),
          if ((linkCode ?? '').isNotEmpty) _StoreNumber(linkCode: linkCode!),
        ],
      ),
    );
  }
}

class _StoreNumber extends StatelessWidget {
  const _StoreNumber({required this.linkCode});

  final String linkCode;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 104,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.end,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Text(
            'STORE NUMBER',
            style: TextStyle(
              color: Color(0xFF6B7280),
              fontSize: 8,
              fontWeight: FontWeight.w800,
              letterSpacing: 0.6,
            ),
          ),
          Text(
            linkCode,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: Colors.black,
              fontSize: 26,
              fontWeight: FontWeight.w900,
              height: 0.98,
              letterSpacing: 1.1,
            ),
          ),
        ],
      ),
    );
  }
}

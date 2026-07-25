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

  // Drives the header + bottom bar: 1.0 = fully shown, 0.0 = collapsed.
  late final AnimationController _chrome;

  @override
  void initState() {
    super.initState();
    _chrome = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 220),
      value: 1,
    );
  }

  @override
  void dispose() {
    _chrome.dispose();
    super.dispose();
  }

  bool _onScroll(ScrollNotification notification) {
    if (notification.metrics.axis != Axis.vertical) {
      return false;
    }
    // Always show the chrome when the list is at (or near) the top.
    if (notification.metrics.pixels <=
        notification.metrics.minScrollExtent + 4) {
      _chrome.forward();
      return false;
    }
    if (notification is UserScrollNotification) {
      switch (notification.direction) {
        case ScrollDirection.reverse:
          _chrome.reverse(); // scrolling down -> hide chrome
          break;
        case ScrollDirection.forward:
          _chrome.forward(); // scrolling up -> reveal chrome
          break;
        case ScrollDirection.idle:
          break;
      }
    }
    return false;
  }

  void _revealChrome() {
    if (_chrome.status != AnimationStatus.completed) {
      _chrome.forward();
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

    return AnimatedBuilder(
      animation: _chrome,
      builder: (context, _) {
        // Light status-bar icons while the dark header shows, dark icons once
        // it has collapsed over the light content beneath.
        final headerShown = _chrome.value > 0.5;
        return AnnotatedRegion<SystemUiOverlayStyle>(
          value: headerShown
              ? SystemUiOverlayStyle.light
              : SystemUiOverlayStyle.dark,
          child: Scaffold(
            body: Column(
              children: [
                SizeTransition(
                  axisAlignment: -1,
                  sizeFactor: _chrome,
                  child: _StoreHeader(
                    title: titles[_index],
                    subtitle: 'Everyday Advertise',
                  ),
                ),
                Expanded(
                  child: NotificationListener<ScrollNotification>(
                    onNotification: _onScroll,
                    child: tabs[_index],
                  ),
                ),
              ],
            ),
            bottomNavigationBar: SizeTransition(
              axisAlignment: 1,
              sizeFactor: _chrome,
              child: Container(
                color: Colors.white,
                padding: EdgeInsets.only(
                  left: 8,
                  right: 8,
                  top: 4,
                  bottom: MediaQuery.of(context).padding.bottom > 0 ? 8 : 6,
                ),
                child: Row(
                  children: [
                    _NavIconButton(
                      icon: Icons.storefront,
                      selected: _index == 0,
                      colorScheme: scheme,
                      onTap: () {
                        setState(() {
                          _index = 0;
                        });
                        _revealChrome();
                      },
                    ),
                    _NavIconButton(
                      icon: Icons.devices,
                      selected: _index == 1,
                      colorScheme: scheme,
                      onTap: () {
                        setState(() {
                          _index = 1;
                        });
                        _revealChrome();
                      },
                    ),
                    _NavIconButton(
                      icon: Icons.tv,
                      selected: _index == 2,
                      colorScheme: scheme,
                      onTap: () {
                        setState(() {
                          _index = 2;
                        });
                        _revealChrome();
                      },
                    ),
                    _NavIconButton(
                      icon: Icons.person,
                      selected: _index == 3,
                      colorScheme: scheme,
                      onTap: () {
                        setState(() {
                          _index = 3;
                        });
                        _revealChrome();
                      },
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

class _NavIconButton extends StatelessWidget {
  const _NavIconButton({
    required this.icon,
    required this.selected,
    required this.colorScheme,
    required this.onTap,
  });

  final IconData icon;
  final bool selected;
  final ColorScheme colorScheme;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Icon(
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

class _StoreHeader extends StatelessWidget {
  const _StoreHeader({required this.title, required this.subtitle});

  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final topInset = MediaQuery.of(context).padding.top;
    return SizedBox(
      height: topInset + 96,
      child: Stack(
        fit: StackFit.expand,
        children: [
          DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  scheme.primary,
                  Color.alphaBlend(Colors.black.withAlpha(70), scheme.primary),
                ],
              ),
            ),
          ),
          Positioned.fill(
            child: SvgPicture.asset(
              'assets/images/store_header.svg',
              fit: BoxFit.cover,
              alignment: Alignment.bottomCenter,
            ),
          ),
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0x1A000000), Color(0x5C000000)],
              ),
            ),
          ),
          Padding(
            padding: EdgeInsets.only(
              top: topInset,
              left: 20,
              right: 20,
              bottom: 12,
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Expanded(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: Theme.of(context).textTheme.titleLarge?.copyWith(
                              color: Colors.white,
                              fontWeight: FontWeight.w700,
                            ),
                      ),
                      Text(
                        subtitle,
                        style: Theme.of(context).textTheme.labelMedium?.copyWith(
                              color: Colors.white.withAlpha(220),
                            ),
                      ),
                    ],
                  ),
                ),
                Container(
                  width: 42,
                  height: 42,
                  decoration: BoxDecoration(
                    color: Colors.white.withAlpha(32),
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: Colors.white.withAlpha(46),
                    ),
                  ),
                  child: const Icon(
                    Icons.person_rounded,
                    color: Colors.white,
                    size: 22,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

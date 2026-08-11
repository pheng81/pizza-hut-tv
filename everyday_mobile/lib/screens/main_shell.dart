import 'package:flutter/cupertino.dart';
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
          key: const ValueKey('remote-control'),
          apiClient: widget.apiClient,
          initialMode: CommandsMode.remote,
        );
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
    final titles = ['Stores & Screens', 'Device Manager', 'Remote', 'Profile'];
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
                        if (index == 3) {
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
                        BottomNavigationBarItem(
                          icon: _RaspberryPiTabIcon(selected: _index == 1),
                        ),
                        BottomNavigationBarItem(
                          icon: _RemoteTabIcon(selected: _index == 2),
                          label: 'Remote',
                        ),
                        BottomNavigationBarItem(
                          icon: _ProfileTabIcon(
                            avatarUrl: _profileAvatarUrl,
                            apiClient: widget.apiClient,
                            selected: _index == 3,
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

class _RemoteTabIcon extends StatelessWidget {
  const _RemoteTabIcon({required this.selected});

  final bool selected;

  @override
  Widget build(BuildContext context) {
    final color =
        selected ? CupertinoColors.systemPurple : CupertinoColors.systemGrey;
    return TweenAnimationBuilder<double>(
      key: ValueKey(selected),
      tween: Tween(begin: 1, end: selected ? 1.14 : 1),
      duration: const Duration(milliseconds: 280),
      curve: Curves.elasticOut,
      builder: (context, scale, child) => Transform.scale(
        scale: scale,
        child: Icon(
          CupertinoIcons.game_controller_solid,
          size: 22,
          color: color,
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

class _RaspberryPiTabIcon extends StatefulWidget {
  const _RaspberryPiTabIcon({required this.selected});

  final bool selected;

  @override
  State<_RaspberryPiTabIcon> createState() => _RaspberryPiTabIconState();
}

class _RaspberryPiTabIconState extends State<_RaspberryPiTabIcon>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _scale;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 420),
    );
    _scale = TweenSequence<double>([
      TweenSequenceItem(tween: Tween(begin: 1, end: 1.13), weight: 38),
      TweenSequenceItem(tween: Tween(begin: 1.13, end: 1), weight: 62),
    ]).animate(CurvedAnimation(parent: _controller, curve: Curves.easeOut));
    if (widget.selected) {
      _controller.forward();
    }
  }

  @override
  void didUpdateWidget(covariant _RaspberryPiTabIcon oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.selected && !oldWidget.selected) {
      _controller.forward(from: 0);
    } else if (!widget.selected && oldWidget.selected) {
      _controller.stop();
      _controller.value = 0;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) => Transform.translate(
        offset: Offset(0, widget.selected ? -2 * _controller.value : 0),
        child: Transform.scale(
          scale: widget.selected ? _scale.value : 1,
          child: CustomPaint(
            size: const Size(32, 32),
            painter: _RaspberryPiPainter(
              selected: widget.selected,
              activity: _controller.value,
            ),
          ),
        ),
      ),
    );
  }
}

class _RaspberryPiPainter extends CustomPainter {
  const _RaspberryPiPainter({required this.selected, required this.activity});

  final bool selected;
  final double activity;

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    canvas.save();
    canvas.translate(center.dx - 16, center.dy - 16);

    final boardPaint = Paint()
      ..color = selected ? const Color(0xFF409E57) : const Color(0xFF8E8E93);
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        const Rect.fromLTWH(2.5, 7, 27, 19),
        const Radius.circular(4),
      ),
      boardPaint,
    );

    final pinPaint = Paint()
      ..color = selected ? const Color(0xFFFFD54F) : const Color(0xFFD8B94A);
    for (var index = 0; index < 7; index++) {
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(8 + index * 2.5, 1, 1.5, 5),
          const Radius.circular(0.5),
        ),
        pinPaint,
      );
    }

    final processorPaint = Paint()..color = const Color(0xC7000000);
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        const Rect.fromLTWH(8, 13, 9, 9),
        const Radius.circular(2),
      ),
      processorPaint,
    );

    final portPaint = Paint()..color = const Color(0xFFB8B8B4);
    for (var index = 0; index < 2; index++) {
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(23, 12 + index * 6, 5, 4),
          const Radius.circular(1),
        ),
        portPaint,
      );
    }
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        const Rect.fromLTWH(13, 25, 8, 4),
        const Radius.circular(1.3),
      ),
      portPaint,
    );

    final ledPaint = Paint()
      ..color = const Color(0xFF34C759)
      ..maskFilter = selected && activity > 0
          ? const MaskFilter.blur(BlurStyle.normal, 2.5)
          : null;
    canvas.drawCircle(const Offset(23, 22), 1.75, ledPaint);
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant _RaspberryPiPainter oldDelegate) {
    return oldDelegate.selected != selected || oldDelegate.activity != activity;
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

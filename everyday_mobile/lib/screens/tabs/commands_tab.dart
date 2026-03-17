import 'package:flutter/material.dart';

import '../../models/app_models.dart';
import '../../services/api_client.dart';

class CommandsTab extends StatefulWidget {
  const CommandsTab({super.key, required this.apiClient});

  final ApiClient apiClient;

  @override
  State<CommandsTab> createState() => _CommandsTabState();
}

class _CommandsTabState extends State<CommandsTab> {
  bool _loading = true;
  String? _message;
  List<AndroidTvDevice> _devices = const [];

  @override
  void initState() {
    super.initState();
    _loadDevices();
  }

  Future<void> _loadDevices() async {
    setState(() {
      _loading = true;
      _message = null;
    });
    try {
      final devices = await widget.apiClient.getAndroidTvDevices();
      if (!mounted) {
        return;
      }
      setState(() {
        _devices = devices;
      });
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _message = e.toString().replaceFirst('Exception: ', '');
      });
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
        });
      }
    }
  }

  Future<void> _send(String deviceId, String command) async {
    setState(() {
      _message = null;
    });
    try {
      await widget.apiClient
          .sendAndroidTvCommand(deviceId: deviceId, command: command);
      if (!mounted) {
        return;
      }
      setState(() {
        _message = 'Sent $command to $deviceId';
      });
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _message = e.toString().replaceFirst('Exception: ', '');
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
          child: Row(
            children: [
              Container(
                height: 34,
                width: 34,
                decoration: BoxDecoration(
                  color: scheme.primaryContainer,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(
                  Icons.cast_connected,
                  color: scheme.onPrimaryContainer,
                  size: 18,
                ),
              ),
              const SizedBox(width: 10),
              Text('Connected TVs', style: theme.textTheme.titleLarge),
              const Spacer(),
              IconButton(
                onPressed: _loading ? null : _loadDevices,
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
        ),
        if (_message != null)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: scheme.surfaceContainer,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(_message!),
            ),
          ),
        const SizedBox(height: 8),
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : ListView.builder(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                  itemCount: _devices.length,
                  itemBuilder: (context, index) {
                    final d = _devices[index];
                    final online = d.status.toLowerCase() == 'online';

                    return Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Card(
                        child: Padding(
                          padding: const EdgeInsets.all(14),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  const Icon(Icons.tv),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Text(d.id,
                                        style: theme.textTheme.titleMedium),
                                  ),
                                  Container(
                                    padding: const EdgeInsets.symmetric(
                                        horizontal: 10, vertical: 4),
                                    decoration: BoxDecoration(
                                      color: online
                                          ? scheme.primaryContainer
                                          : scheme.surfaceContainerHighest,
                                      borderRadius: BorderRadius.circular(999),
                                    ),
                                    child: Text(
                                      d.status,
                                      style: TextStyle(
                                        color: online
                                            ? scheme.onPrimaryContainer
                                            : scheme.onSurfaceVariant,
                                        fontSize: 12,
                                        fontWeight: FontWeight.w600,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 6),
                              Text(
                                '${d.storeName} • ${d.screenName}',
                                style: theme.textTheme.bodyMedium?.copyWith(
                                  color: scheme.onSurfaceVariant,
                                ),
                              ),
                              const SizedBox(height: 10),
                              Wrap(
                                spacing: 8,
                                runSpacing: 8,
                                children: [
                                  FilledButton(
                                    style: FilledButton.styleFrom(
                                      backgroundColor: const Color(0xFF2563EB),
                                      foregroundColor: Colors.white,
                                    ),
                                    onPressed: () =>
                                        _send(d.id, 'refresh_screen'),
                                    child: const Text('Refresh'),
                                  ),
                                  FilledButton(
                                    style: FilledButton.styleFrom(
                                      backgroundColor: const Color(0xFF16A34A),
                                      foregroundColor: Colors.white,
                                    ),
                                    onPressed: () =>
                                        _send(d.id, 'reload_playlist'),
                                    child: const Text('Reload'),
                                  ),
                                  OutlinedButton(
                                    style: OutlinedButton.styleFrom(
                                      foregroundColor: const Color(0xFF7C3AED),
                                      side: const BorderSide(
                                        color: Color(0xFF7C3AED),
                                      ),
                                    ),
                                    onPressed: () => _send(d.id, 'restart_app'),
                                    child: const Text('Restart App'),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }
}

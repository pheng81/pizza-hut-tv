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
      await widget.apiClient.sendAndroidTvCommand(deviceId: deviceId, command: command);
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
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('TV Commands', style: Theme.of(context).textTheme.titleLarge),
              IconButton(
                onPressed: _loading ? null : _loadDevices,
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          if (_message != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text(_message!),
            ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : ListView.builder(
                    itemCount: _devices.length,
                    itemBuilder: (context, index) {
                      final d = _devices[index];
                      return Card(
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(d.id, style: Theme.of(context).textTheme.titleMedium),
                              Text('${d.storeName} / ${d.screenName}'),
                              Text('Status: ${d.status}'),
                              const SizedBox(height: 8),
                              Wrap(
                                spacing: 8,
                                children: [
                                  OutlinedButton(
                                    onPressed: () => _send(d.id, 'refresh_screen'),
                                    child: const Text('Refresh'),
                                  ),
                                  OutlinedButton(
                                    onPressed: () => _send(d.id, 'reload_playlist'),
                                    child: const Text('Reload'),
                                  ),
                                  OutlinedButton(
                                    onPressed: () => _send(d.id, 'restart_app'),
                                    child: const Text('Restart App'),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

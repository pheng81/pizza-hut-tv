import 'package:flutter/material.dart';

import '../../models/app_models.dart';
import '../../services/api_client.dart';

class ProfileTab extends StatefulWidget {
  const ProfileTab({
    super.key,
    required this.apiClient,
    required this.onLogout,
  });

  final ApiClient apiClient;
  final Future<void> Function() onLogout;

  @override
  State<ProfileTab> createState() => _ProfileTabState();
}

class _ProfileTabState extends State<ProfileTab> {
  final _nameController = TextEditingController();
  final _currentPasswordController = TextEditingController();
  final _newPasswordController = TextEditingController();

  UserProfile? _profile;
  bool _loading = true;
  String? _message;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _nameController.dispose();
    _currentPasswordController.dispose();
    _newPasswordController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _message = null;
    });
    try {
      final profile = await widget.apiClient.getMe();
      if (!mounted) {
        return;
      }
      setState(() {
        _profile = profile;
        _nameController.text = profile.fullName ?? '';
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

  Future<void> _updateName() async {
    try {
      await widget.apiClient.updateProfileName(_nameController.text.trim());
      if (!mounted) {
        return;
      }
      setState(() {
        _message = 'Name updated';
      });
      await _load();
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _message = e.toString().replaceFirst('Exception: ', '');
      });
    }
  }

  Future<void> _changePassword() async {
    try {
      await widget.apiClient.changePassword(
        currentPassword: _currentPasswordController.text,
        newPassword: _newPasswordController.text,
      );
      if (!mounted) {
        return;
      }
      _currentPasswordController.clear();
      _newPasswordController.clear();
      setState(() {
        _message = 'Password updated';
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

  Future<void> _regenerateCode() async {
    try {
      final code = await widget.apiClient.regenerateCode();
      if (!mounted) {
        return;
      }
      setState(() {
        _message = 'New link code: $code';
      });
      await _load();
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
      child: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              children: [
                Text('Profile', style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 8),
                if (_profile != null) ...[
                  Text('Username: ${_profile!.username}'),
                  Text('Link code: ${_profile!.linkCode ?? '-'}'),
                ],
                if (_message != null)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Text(_message!),
                  ),
                TextField(
                  controller: _nameController,
                  decoration: const InputDecoration(labelText: 'Full name'),
                ),
                const SizedBox(height: 8),
                FilledButton(
                  onPressed: _updateName,
                  child: const Text('Update Name'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _currentPasswordController,
                  obscureText: true,
                  decoration: const InputDecoration(labelText: 'Current password'),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: _newPasswordController,
                  obscureText: true,
                  decoration: const InputDecoration(labelText: 'New password'),
                ),
                const SizedBox(height: 8),
                FilledButton(
                  onPressed: _changePassword,
                  child: const Text('Change Password'),
                ),
                const SizedBox(height: 8),
                OutlinedButton(
                  onPressed: _regenerateCode,
                  child: const Text('Regenerate Link Code'),
                ),
                const SizedBox(height: 8),
                OutlinedButton(
                  onPressed: () async {
                    await widget.onLogout();
                  },
                  child: const Text('Logout'),
                ),
              ],
            ),
    );
  }
}

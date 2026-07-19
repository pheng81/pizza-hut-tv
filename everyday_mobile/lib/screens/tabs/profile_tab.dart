import 'package:flutter/material.dart';

import '../account_page.dart';
import '../store_groups_page.dart';
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
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Padding(
      padding: const EdgeInsets.all(16),
      child: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              children: [
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Container(
                              height: 34,
                              width: 34,
                              decoration: BoxDecoration(
                                color: scheme.primaryContainer,
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: Icon(
                                Icons.person,
                                color: scheme.onPrimaryContainer,
                                size: 18,
                              ),
                            ),
                            const SizedBox(width: 10),
                            Text('Account', style: theme.textTheme.titleMedium),
                          ],
                        ),
                        const SizedBox(height: 8),
                        if (_profile != null) ...[
                          Text('Username: ${_profile!.username}'),
                          const SizedBox(height: 4),
                          Text('Link code: ${_profile!.linkCode ?? '-'}'),
                        ],
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 10),
                FilledButton.icon(
                  onPressed: () {
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => AccountPage(
                          apiClient: widget.apiClient,
                          initialUsername: _profile?.username,
                        ),
                      ),
                    );
                  },
                  icon: const Icon(Icons.account_balance_wallet_outlined),
                  label: const Text('Open Account Center'),
                ),
                const SizedBox(height: 10),
                Card(
                  child: ListTile(
                    leading: Container(
                      height: 36,
                      width: 36,
                      decoration: BoxDecoration(
                        color: scheme.secondaryContainer,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Icon(
                        Icons.groups_outlined,
                        color: scheme.onSecondaryContainer,
                      ),
                    ),
                    title: const Text('Store Groups'),
                    subtitle: const Text('Create groups and select stores'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () {
                      Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => StoreGroupsPage(
                            apiClient: widget.apiClient,
                          ),
                        ),
                      );
                    },
                  ),
                ),
                if (_message != null) ...[
                  const SizedBox(height: 10),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: scheme.surfaceContainer,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(_message!),
                  ),
                ],
                const SizedBox(height: 10),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Update Name', style: theme.textTheme.titleMedium),
                        const SizedBox(height: 10),
                        TextField(
                          controller: _nameController,
                          decoration:
                              const InputDecoration(labelText: 'Full name'),
                        ),
                        const SizedBox(height: 10),
                        FilledButton(
                          style: FilledButton.styleFrom(
                            backgroundColor: const Color(0xFF2563EB),
                            foregroundColor: Colors.white,
                          ),
                          onPressed: _updateName,
                          child: const Text('Save Name'),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 10),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Change Password',
                            style: theme.textTheme.titleMedium),
                        const SizedBox(height: 10),
                        TextField(
                          controller: _currentPasswordController,
                          obscureText: true,
                          decoration: const InputDecoration(
                              labelText: 'Current password'),
                        ),
                        const SizedBox(height: 8),
                        TextField(
                          controller: _newPasswordController,
                          obscureText: true,
                          decoration:
                              const InputDecoration(labelText: 'New password'),
                        ),
                        const SizedBox(height: 10),
                        FilledButton(
                          style: FilledButton.styleFrom(
                            backgroundColor: const Color(0xFF16A34A),
                            foregroundColor: Colors.white,
                          ),
                          onPressed: _changePassword,
                          child: const Text('Update Password'),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 10),
                OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: const Color(0xFF7C3AED),
                    side: const BorderSide(color: Color(0xFF7C3AED)),
                  ),
                  onPressed: _regenerateCode,
                  icon: const Icon(Icons.pin_outlined),
                  label: const Text('Regenerate Link Code'),
                ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: scheme.error,
                    side: BorderSide(color: scheme.error),
                  ),
                  onPressed: () async {
                    await widget.onLogout();
                  },
                  icon: const Icon(Icons.logout),
                  label: const Text('Logout'),
                ),
              ],
            ),
    );
  }
}

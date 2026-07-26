import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../account_page.dart';
import '../store_groups_page.dart';
import '../../models/app_models.dart';
import '../../services/api_client.dart';

class ProfileTab extends StatefulWidget {
  const ProfileTab({
    super.key,
    required this.apiClient,
    required this.onLogout,
    this.onProfileChanged,
  });

  final ApiClient apiClient;
  final Future<void> Function() onLogout;
  final VoidCallback? onProfileChanged;

  @override
  State<ProfileTab> createState() => _ProfileTabState();
}

class _ProfileTabState extends State<ProfileTab> {
  final _nameController = TextEditingController();
  final _currentPasswordController = TextEditingController();
  final _newPasswordController = TextEditingController();
  final ImagePicker _imagePicker = ImagePicker();

  UserProfile? _profile;
  bool _loading = true;
  bool _uploadingAvatar = false;
  String? _message;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _pickAndUploadAvatar() async {
    try {
      final picked = await _imagePicker.pickImage(
        source: ImageSource.gallery,
        maxWidth: 1200,
        maxHeight: 1200,
        imageQuality: 90,
      );
      if (picked == null || !mounted) {
        return;
      }
      setState(() {
        _uploadingAvatar = true;
        _message = null;
      });
      await widget.apiClient.uploadProfileAvatar(picked.path);
      if (!mounted) {
        return;
      }
      setState(() {
        _message = 'Profile photo updated';
      });
      await _load();
      widget.onProfileChanged?.call();
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
          _uploadingAvatar = false;
        });
      }
    }
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
      widget.onProfileChanged?.call();
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

    InputDecoration flatInput(String label) {
      return InputDecoration(
        hintText: label,
        filled: true,
        fillColor: scheme.surfaceContainerHigh,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      );
    }

    Widget flatSection({
      required Widget child,
      EdgeInsets padding = const EdgeInsets.all(18),
    }) {
      return Container(
        padding: padding,
        decoration: BoxDecoration(
          color: scheme.surface,
          borderRadius: BorderRadius.circular(24),
        ),
        child: child,
      );
    }

    ImageProvider? profileImageProvider() {
      final url = (_profile?.avatarUrl ?? '').trim();
      if (url.isEmpty) {
        return null;
      }
      if (url.startsWith('http://') || url.startsWith('https://')) {
        return NetworkImage(url);
      }
      final normalizedBase =
          widget.apiClient.baseUrl.replaceAll(RegExp(r'/$'), '');
      final normalizedPath = url.startsWith('/') ? url : '/$url';
      return NetworkImage('$normalizedBase$normalizedPath');
    }

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 2, 16, 16),
      child: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              children: [
                flatSection(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          GestureDetector(
                            onTap: _uploadingAvatar ? null : _pickAndUploadAvatar,
                            child: Stack(
                              alignment: Alignment.center,
                              children: [
                                Container(
                                  width: 76,
                                  height: 76,
                                  decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    color: const Color(0xFFEDEFFD),
                                    image: profileImageProvider() == null
                                        ? null
                                        : DecorationImage(
                                            image: profileImageProvider()!,
                                            fit: BoxFit.cover,
                                          ),
                                  ),
                                  child: profileImageProvider() != null
                                      ? null
                                      : Icon(
                                          Icons.person_rounded,
                                          size: 34,
                                          color: scheme.primary,
                                        ),
                                ),
                                if (_uploadingAvatar)
                                  Container(
                                    width: 76,
                                    height: 76,
                                    decoration: const BoxDecoration(
                                      shape: BoxShape.circle,
                                      color: Color(0x66000000),
                                    ),
                                    child: const Padding(
                                      padding: EdgeInsets.all(22),
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2.4,
                                        color: Colors.white,
                                      ),
                                    ),
                                  ),
                              ],
                            ),
                          ),
                          const SizedBox(width: 14),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'Account',
                                  style: theme.textTheme.titleMedium?.copyWith(
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                                const SizedBox(height: 6),
                                Text(
                                  _profile?.username ?? '',
                                  style: theme.textTheme.bodyLarge?.copyWith(
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  'Link code: ${_profile?.linkCode ?? '-'}',
                                  style: theme.textTheme.bodyMedium?.copyWith(
                                    color: scheme.onSurfaceVariant,
                                  ),
                                ),
                                const SizedBox(height: 6),
                                Text(
                                  'Tap photo to change',
                                  style: theme.textTheme.bodySmall?.copyWith(
                                    color: scheme.primary,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 10),
                flatSection(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Update Name',
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 10),
                      TextField(
                        controller: _nameController,
                        decoration: flatInput('Full name'),
                      ),
                      const SizedBox(height: 12),
                      FilledButton(
                        style: FilledButton.styleFrom(
                          elevation: 0,
                          backgroundColor: const Color(0xFF2563EB),
                          foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(16),
                          ),
                          padding: const EdgeInsets.symmetric(
                            horizontal: 20,
                            vertical: 16,
                          ),
                        ),
                        onPressed: _updateName,
                        child: const Text('Save Name'),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 10),
                flatSection(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 10,
                  ),
                  child: Material(
                    color: Colors.transparent,
                    child: InkWell(
                      borderRadius: BorderRadius.circular(18),
                      onTap: () {
                        Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) => AccountPage(
                              apiClient: widget.apiClient,
                              initialUsername: _profile?.username,
                            ),
                          ),
                        );
                      },
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 2,
                          vertical: 4,
                        ),
                        child: Row(
                          children: [
                            Container(
                              height: 42,
                              width: 42,
                              decoration: BoxDecoration(
                                color: scheme.primaryContainer,
                                borderRadius: BorderRadius.circular(14),
                              ),
                              child: Icon(
                                Icons.account_balance_wallet_outlined,
                                color: scheme.onPrimaryContainer,
                              ),
                            ),
                            const SizedBox(width: 14),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'Open Account Center',
                                    style:
                                        theme.textTheme.titleSmall?.copyWith(
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                  const SizedBox(height: 2),
                                  Text(
                                    'Billing, subscription, and account details',
                                    style: theme.textTheme.bodySmall?.copyWith(
                                      color: scheme.onSurfaceVariant,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            Icon(
                              Icons.chevron_right,
                              color: scheme.onSurfaceVariant,
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 10),
                flatSection(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 10,
                  ),
                  child: ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: Container(
                      height: 42,
                      width: 42,
                      decoration: BoxDecoration(
                        color: scheme.secondaryContainer,
                        borderRadius: BorderRadius.circular(14),
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
                      color: scheme.surfaceContainerHigh,
                      borderRadius: BorderRadius.circular(18),
                    ),
                    child: Text(_message!),
                  ),
                ],
                const SizedBox(height: 10),
                flatSection(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Change Password',
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 10),
                      TextField(
                        controller: _currentPasswordController,
                        obscureText: true,
                        decoration: flatInput('Current password'),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: _newPasswordController,
                        obscureText: true,
                        decoration: flatInput('New password'),
                      ),
                      const SizedBox(height: 12),
                      FilledButton(
                        style: FilledButton.styleFrom(
                          elevation: 0,
                          backgroundColor: const Color(0xFF16A34A),
                          foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(16),
                          ),
                          padding: const EdgeInsets.symmetric(
                            horizontal: 20,
                            vertical: 16,
                          ),
                        ),
                        onPressed: _changePassword,
                        child: const Text('Update Password'),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 10),
                FilledButton.tonalIcon(
                  style: FilledButton.styleFrom(
                    elevation: 0,
                    backgroundColor: const Color(0xFFF3EEFF),
                    foregroundColor: const Color(0xFF7C3AED),
                    minimumSize: const Size.fromHeight(52),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(18),
                    ),
                  ),
                  onPressed: _regenerateCode,
                  icon: const Icon(Icons.pin_outlined),
                  label: const Text('Regenerate Link Code'),
                ),
                const SizedBox(height: 8),
                FilledButton.tonalIcon(
                  style: FilledButton.styleFrom(
                    elevation: 0,
                    backgroundColor: const Color(0xFFFFECEB),
                    foregroundColor: scheme.error,
                    minimumSize: const Size.fromHeight(52),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(18),
                    ),
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

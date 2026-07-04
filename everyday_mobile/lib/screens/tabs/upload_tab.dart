import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../../services/api_client.dart';

class UploadTab extends StatefulWidget {
  const UploadTab({
    super.key,
    required this.apiClient,
    required this.selectedStoreId,
    required this.selectedScreenId,
  });

  final ApiClient apiClient;
  final String? selectedStoreId;
  final String? selectedScreenId;

  @override
  State<UploadTab> createState() => _UploadTabState();
}

class _UploadTabState extends State<UploadTab> {
  File? _file;
  String? _fileSourceLabel;
  String? _selectedLibraryFile;
  String? _message;
  bool _busy = false;
  final ImagePicker _imagePicker = ImagePicker();

  Future<void> _pickFile() async {
    final result = await FilePicker.platform.pickFiles(withData: false);
    if (result == null || result.files.isEmpty) {
      return;
    }
    final path = result.files.single.path;
    if (path == null) {
      return;
    }
    setState(() {
      _file = File(path);
      _fileSourceLabel = null;
      _selectedLibraryFile = null;
      _message = null;
    });
  }

  Future<void> _pickFromGoogleDrive() async {
    final result = await FilePicker.platform.pickFiles(
      dialogTitle: 'Choose from Google Drive',
      type: FileType.custom,
      allowedExtensions: const [
        'jpg',
        'jpeg',
        'png',
        'webp',
        'gif',
        'bmp',
        'mp4',
        'mov',
        'm4v',
        'webm',
        'mkv',
        'avi',
      ],
      withData: false,
    );
    if (result == null || result.files.isEmpty) {
      setState(() {
        _message =
            'No Drive file selected. If Google Drive is not listed, install the Google Drive app, sign in, or download the file and choose it from Downloads.';
      });
      return;
    }
    final path = result.files.single.path;
    if (path == null || path.trim().isEmpty) {
      setState(() {
        _message =
            'Android did not return a readable Drive file. Download it locally from Drive and try again.';
      });
      return;
    }
    setState(() {
      _file = File(path);
      _fileSourceLabel = 'Google Drive';
      _selectedLibraryFile = null;
      _message = null;
    });
  }

  Future<void> _pickFromCamera() async {
    try {
      final picked = await _imagePicker.pickImage(
        source: ImageSource.camera,
        imageQuality: 92,
      );
      if (picked == null) {
        return;
      }
      setState(() {
        _file = File(picked.path);
        _fileSourceLabel = 'Camera';
        _selectedLibraryFile = null;
        _message = null;
      });
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _message =
            'Camera is unavailable: ${e.toString().replaceFirst('Exception: ', '')}';
      });
    }
  }

  Future<void> _pickFromServerLibrary() async {
    final selected = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (_) => FractionallySizedBox(
        heightFactor: 0.9,
        child: _UploadLibraryPickerSheet(apiClient: widget.apiClient),
      ),
    );

    if (!mounted || selected == null || selected.trim().isEmpty) {
      return;
    }

    setState(() {
      _selectedLibraryFile = selected.trim();
      _file = null;
      _fileSourceLabel = null;
      _message = null;
    });
  }

  Future<void> _uploadAndAssign() async {
    final selectedLibrary = (_selectedLibraryFile ?? '').trim();
    if (_file == null && selectedLibrary.isEmpty) {
      setState(() {
        _message = 'Select a local file or choose from server library first.';
      });
      return;
    }
    if (widget.selectedStoreId == null || widget.selectedScreenId == null) {
      setState(() {
        _message = 'Select store and screen in Stores tab first.';
      });
      return;
    }

    setState(() {
      _busy = true;
      _message = null;
    });

    try {
      String filename;
      // Prefer local file/camera selection when available.
      if (_file != null) {
        filename = await widget.apiClient.uploadMedia(_file!);
      } else {
        filename = selectedLibrary;
      }
      await widget.apiClient.assignToScreen(
        storeId: widget.selectedStoreId!,
        screenId: widget.selectedScreenId!,
        filename: filename,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _message = _file != null
            ? 'Photo/file uploaded and assigned successfully. Check Stores tab Current Media.'
            : 'Assigned media from server library successfully. Check Stores tab Current Media.';
        _file = null;
        _fileSourceLabel = null;
        _selectedLibraryFile = null;
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
          _busy = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return ListView(
      padding: const EdgeInsets.all(16),
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
                        Icons.my_location,
                        color: scheme.onPrimaryContainer,
                        size: 18,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Text('Target Screen', style: theme.textTheme.titleMedium),
                  ],
                ),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    Chip(
                      backgroundColor: const Color(0xFFDBEAFE),
                      avatar: const Icon(Icons.storefront, size: 16),
                      label: Text(
                          'Store: ${widget.selectedStoreId ?? 'Not selected'}'),
                    ),
                    Chip(
                      backgroundColor: const Color(0xFFE0F2FE),
                      avatar: const Icon(Icons.tv, size: 16),
                      label: Text(
                          'Screen: ${widget.selectedScreenId ?? 'Not selected'}'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Choose Media', style: theme.textTheme.titleMedium),
                const SizedBox(height: 4),
                Text(
                  'Upload image or video and assign immediately.',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: scheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: _busy ? null : _pickFile,
                        icon: const Icon(Icons.folder_open),
                        label: const Text('Choose from Device'),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: _busy ? null : _pickFromCamera,
                        icon: const Icon(Icons.photo_camera),
                        label: const Text('Take Photo'),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: _busy ? null : _pickFromGoogleDrive,
                    icon: const Icon(Icons.add_to_drive),
                    label: const Text('Choose from Google Drive'),
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  'If Recent opens, use the menu to choose Drive. If Drive is missing, install Google Drive and sign in first.',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: scheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 8),
                Container(
                  width: double.infinity,
                  padding:
                      const EdgeInsets.symmetric(vertical: 14, horizontal: 12),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: scheme.outlineVariant),
                    color: scheme.surfaceContainerLow,
                  ),
                  child: Text(
                    _file == null
                        ? 'No local file selected'
                        : 'Selected ${_fileSourceLabel ?? 'local file'}: ${_file!.uri.pathSegments.last}',
                    textAlign: TextAlign.center,
                    style: theme.textTheme.bodyMedium,
                  ),
                ),
                if (_file != null) ...[
                  const SizedBox(height: 8),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(10),
                    child: Image.file(
                      _file!,
                      height: 120,
                      width: double.infinity,
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => Container(
                        height: 120,
                        width: double.infinity,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: scheme.outlineVariant),
                        ),
                        child:
                            const Text('Preview unavailable for selected file'),
                      ),
                    ),
                  ),
                ],
                const SizedBox(height: 10),
                OutlinedButton.icon(
                  onPressed: _busy ? null : _pickFromServerLibrary,
                  icon: const Icon(Icons.collections),
                  label: const Text('Choose Existing from Server Library'),
                ),
                if (_selectedLibraryFile != null &&
                    _selectedLibraryFile!.trim().isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text(
                    'Selected library media: ${_selectedLibraryFile!}',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: theme.textTheme.bodySmall,
                  ),
                ],
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        FilledButton.icon(
          style: FilledButton.styleFrom(
            backgroundColor: const Color(0xFF16A34A),
            foregroundColor: Colors.white,
          ),
          onPressed: _busy ? null : _uploadAndAssign,
          icon: _busy
              ? const SizedBox(
                  height: 16,
                  width: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.cloud_upload),
          label: Text(_busy ? 'Uploading...' : 'Upload to Selected Screen'),
        ),
        if (_message != null) ...[
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: scheme.surfaceContainer,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: scheme.outlineVariant),
            ),
            child: Text(_message!),
          ),
        ],
      ],
    );
  }
}

class _UploadLibraryPickerSheet extends StatefulWidget {
  const _UploadLibraryPickerSheet({required this.apiClient});

  final ApiClient apiClient;

  @override
  State<_UploadLibraryPickerSheet> createState() =>
      _UploadLibraryPickerSheetState();
}

class _UploadLibraryPickerSheetState extends State<_UploadLibraryPickerSheet> {
  bool _loading = true;
  String? _error;
  String _prefix = '';
  String _filter = 'all';
  Map<String, String> _authHeaders = const {};
  List<Map<String, dynamic>> _dirs = const [];
  List<Map<String, dynamic>> _files = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await widget.apiClient
          .listLibrary(prefix: _prefix.isEmpty ? null : _prefix);
      if (!mounted) {
        return;
      }

      final dirs = data['dirs'] is List ? (data['dirs'] as List) : const [];
      final files = data['files'] is List ? (data['files'] as List) : const [];
      setState(() {
        _dirs = dirs
            .map((item) => item is Map
                ? item.map((k, v) => MapEntry(k.toString(), v))
                : <String, dynamic>{})
            .where((item) => item.isNotEmpty)
            .toList();
        _files = files
            .map((item) => item is Map
                ? item.map((k, v) => MapEntry(k.toString(), v))
                : <String, dynamic>{})
            .where((item) => item.isNotEmpty)
            .toList();
      });

      final sampleUrl = _files
          .map((f) => (f['url'] ?? '').toString().trim())
          .firstWhere((u) => u.isNotEmpty,
              orElse: () => widget.apiClient.baseUrl);
      final headers = await widget.apiClient.getAuthHeadersForUrl(sampleUrl);
      if (!mounted) {
        return;
      }
      setState(() {
        _authHeaders = headers;
      });
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = e.toString().replaceFirst('Exception: ', '');
      });
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
        });
      }
    }
  }

  List<Map<String, dynamic>> _filteredFiles() {
    if (_filter == 'all') {
      return _files;
    }
    return _files.where((file) {
      final mediaType = (file['media_type'] ?? '').toString().toLowerCase();
      if (_filter == 'images') {
        return mediaType == 'image' || mediaType == 'animated';
      }
      if (_filter == 'videos') {
        return mediaType == 'video';
      }
      return true;
    }).toList();
  }

  String _basename(String path) {
    final cleaned = path.trim();
    if (cleaned.isEmpty) {
      return cleaned;
    }
    final parts = cleaned.split('/');
    return parts.isEmpty ? cleaned : parts.last;
  }

  String _encodePathForRoute(String value) {
    return value
        .split('/')
        .where((segment) => segment.trim().isNotEmpty)
        .map(Uri.encodeComponent)
        .join('/');
  }

  String _previewUrlForFile(Map<String, dynamic> file) {
    final name = (file['name'] ?? '').toString().trim();
    final rawUrl = (file['url'] ?? '').toString().trim();
    if (name.isEmpty) {
      return rawUrl;
    }

    final mediaType = (file['media_type'] ?? '').toString().toLowerCase();
    final base = widget.apiClient.baseUrl.replaceAll(RegExp(r'/$'), '');
    final encodedName = _encodePathForRoute(name);
    if (mediaType == 'video') {
      return '$base/vthumb/96/$encodedName';
    }
    return '$base/thumb/96/$encodedName';
  }

  Widget _fileLeading(Map<String, dynamic> file) {
    final mediaType = (file['media_type'] ?? '').toString().toLowerCase();
    final url = _previewUrlForFile(file);
    if (url.isNotEmpty) {
      return ClipRRect(
        borderRadius: BorderRadius.circular(6),
        child: Image.network(
          url,
          headers: _authHeaders,
          width: 44,
          height: 44,
          fit: BoxFit.cover,
          errorBuilder: (_, __, ___) => const SizedBox(
            width: 44,
            height: 44,
            child: Icon(Icons.broken_image),
          ),
        ),
      );
    }
    return Icon(mediaType == 'video' ? Icons.movie : Icons.image);
  }

  void _goUp() {
    if (_prefix.isEmpty) {
      return;
    }
    final idx = _prefix.lastIndexOf('/');
    setState(() {
      _prefix = idx <= 0 ? '' : _prefix.substring(0, idx);
    });
    _load();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final files = _filteredFiles();

    return SafeArea(
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 10, 8, 8),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    'Choose Existing Media',
                    style: theme.textTheme.titleMedium,
                  ),
                ),
                IconButton(
                  onPressed: () => Navigator.of(context).pop(),
                  icon: const Icon(Icons.close),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
            child: Row(
              children: [
                OutlinedButton.icon(
                  onPressed: _prefix.isEmpty || _loading ? null : _goUp,
                  icon: const Icon(Icons.arrow_upward),
                  label: const Text('Up'),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _prefix.isEmpty ? 'Library root' : _prefix,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: theme.textTheme.bodySmall,
                  ),
                ),
                IconButton(
                  onPressed: _loading ? null : _load,
                  icon: const Icon(Icons.refresh),
                  tooltip: 'Refresh',
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: SegmentedButton<String>(
              segments: const [
                ButtonSegment<String>(value: 'all', label: Text('All')),
                ButtonSegment<String>(value: 'images', label: Text('Images')),
                ButtonSegment<String>(value: 'videos', label: Text('Videos')),
              ],
              selected: <String>{_filter},
              onSelectionChanged: (selection) {
                final next = selection.isEmpty ? 'all' : selection.first;
                setState(() {
                  _filter = next;
                });
              },
            ),
          ),
          const SizedBox(height: 8),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Text(
                            _error!,
                            style: theme.textTheme.bodyMedium?.copyWith(
                              color: theme.colorScheme.error,
                            ),
                            textAlign: TextAlign.center,
                          ),
                        ),
                      )
                    : ListView(
                        padding: const EdgeInsets.fromLTRB(8, 0, 8, 12),
                        children: [
                          if (_dirs.isNotEmpty) ...[
                            Padding(
                              padding: const EdgeInsets.fromLTRB(8, 6, 8, 4),
                              child: Text('Folders',
                                  style: theme.textTheme.titleSmall),
                            ),
                            ..._dirs.map((dir) {
                              final dirName = (dir['name'] ?? '').toString();
                              final dirPrefix =
                                  (dir['prefix'] ?? '').toString().trim();
                              return ListTile(
                                leading: const Icon(Icons.folder),
                                title: Text(
                                    dirName.isEmpty ? '(Folder)' : dirName),
                                trailing: const Icon(Icons.chevron_right),
                                onTap: dirPrefix.isEmpty
                                    ? null
                                    : () {
                                        setState(() {
                                          _prefix = dirPrefix;
                                        });
                                        _load();
                                      },
                              );
                            }),
                          ],
                          Padding(
                            padding: const EdgeInsets.fromLTRB(8, 6, 8, 4),
                            child: Text('Files',
                                style: theme.textTheme.titleSmall),
                          ),
                          if (files.isEmpty)
                            Padding(
                              padding: const EdgeInsets.all(12),
                              child: Text(
                                'No files found.',
                                style: theme.textTheme.bodySmall,
                              ),
                            )
                          else
                            ...files.map((file) {
                              final name = (file['name'] ?? '').toString();
                              final label = _basename(name);
                              return ListTile(
                                leading: _fileLeading(file),
                                title: Text(
                                  label.isEmpty ? name : label,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                                subtitle: Text(
                                  name,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                                onTap: name.trim().isEmpty
                                    ? null
                                    : () => Navigator.of(context).pop(name),
                              );
                            }),
                        ],
                      ),
          ),
        ],
      ),
    );
  }
}

import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

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
  String? _message;
  bool _busy = false;

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
      _message = null;
    });
  }

  Future<void> _uploadAndAssign() async {
    if (_file == null) {
      setState(() {
        _message = 'Select a file first.';
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
      final filename = await widget.apiClient.uploadMedia(_file!);
      await widget.apiClient.assignToScreen(
        storeId: widget.selectedStoreId!,
        screenId: widget.selectedScreenId!,
        filename: filename,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _message = 'Uploaded and assigned successfully.';
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
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Upload Media', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          Text('Store: ${widget.selectedStoreId ?? '-'}'),
          Text('Screen: ${widget.selectedScreenId ?? '-'}'),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: _busy ? null : _pickFile,
            icon: const Icon(Icons.attach_file),
            label: const Text('Choose File'),
          ),
          if (_file != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text('Selected: ${_file!.uri.pathSegments.last}'),
            ),
          const SizedBox(height: 12),
          FilledButton.icon(
            onPressed: _busy ? null : _uploadAndAssign,
            icon: const Icon(Icons.cloud_upload),
            label: _busy
                ? const SizedBox(
                    height: 16,
                    width: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Upload to Selected Screen'),
          ),
          if (_message != null)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Text(_message!),
            ),
        ],
      ),
    );
  }
}

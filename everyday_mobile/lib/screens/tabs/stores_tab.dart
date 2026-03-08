import 'package:flutter/material.dart';

import '../../models/app_models.dart';
import '../../services/api_client.dart';

class StoresTab extends StatefulWidget {
  const StoresTab({
    super.key,
    required this.apiClient,
    required this.selectedStoreId,
    required this.selectedScreenId,
    required this.onSelectionChanged,
  });

  final ApiClient apiClient;
  final String? selectedStoreId;
  final String? selectedScreenId;
  final void Function(String? storeId, String? screenId) onSelectionChanged;

  @override
  State<StoresTab> createState() => _StoresTabState();
}

class _StoresTabState extends State<StoresTab> {
  bool _loading = true;
  String? _error;
  List<StoreItem> _stores = const [];
  List<ScreenItem> _screens = const [];

  @override
  void initState() {
    super.initState();
    _loadStores();
  }

  Future<void> _loadStores() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final stores = await widget.apiClient.getStores();
      String? storeId = widget.selectedStoreId;
      if (storeId == null || stores.every((s) => s.id != storeId)) {
        storeId = stores.isNotEmpty ? stores.first.id : null;
      }

      List<ScreenItem> screens = const [];
      String? screenId = widget.selectedScreenId;
      if (storeId != null) {
        screens = await widget.apiClient.getScreens(storeId);
        if (screenId == null || screens.every((s) => s.id != screenId)) {
          screenId = screens.isNotEmpty ? screens.first.id : null;
        }
      } else {
        screenId = null;
      }

      if (!mounted) {
        return;
      }
      setState(() {
        _stores = stores;
        _screens = screens;
      });
      widget.onSelectionChanged(storeId, screenId);
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

  Future<void> _onSelectStore(String? storeId) async {
    if (storeId == null) {
      widget.onSelectionChanged(null, null);
      setState(() {
        _screens = const [];
      });
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final screens = await widget.apiClient.getScreens(storeId);
      final screenId = screens.isNotEmpty ? screens.first.id : null;
      if (!mounted) {
        return;
      }
      setState(() {
        _screens = screens;
      });
      widget.onSelectionChanged(storeId, screenId);
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
              Text('Stores & Screens', style: Theme.of(context).textTheme.titleLarge),
              IconButton(
                onPressed: _loading ? null : _loadStores,
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(_error!, style: const TextStyle(color: Colors.red)),
            ),
          DropdownButtonFormField<String>(
            value: widget.selectedStoreId,
            items: _stores
                .map((store) => DropdownMenuItem(
                      value: store.id,
                      child: Text('${store.id} - ${store.name}'),
                    ))
                .toList(),
            onChanged: _loading ? null : _onSelectStore,
            decoration: const InputDecoration(labelText: 'Store'),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            value: widget.selectedScreenId,
            items: _screens
                .map((screen) => DropdownMenuItem(
                      value: screen.id,
                      child: Text('${screen.id} - ${screen.name}'),
                    ))
                .toList(),
            onChanged: _loading
                ? null
                : (value) {
                    widget.onSelectionChanged(widget.selectedStoreId, value);
                  },
            decoration: const InputDecoration(labelText: 'Screen'),
          ),
          const SizedBox(height: 16),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : ListView(
                    children: [
                      Text('Available stores: ${_stores.length}'),
                      Text('Screens in selected store: ${_screens.length}'),
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}

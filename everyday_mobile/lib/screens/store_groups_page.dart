import 'package:flutter/material.dart';

import '../models/app_models.dart';
import '../services/api_client.dart';

class StoreGroupsPage extends StatefulWidget {
  const StoreGroupsPage({super.key, required this.apiClient});

  final ApiClient apiClient;

  @override
  State<StoreGroupsPage> createState() => _StoreGroupsPageState();
}

class _StoreGroupsPageState extends State<StoreGroupsPage> {
  List<StoreItem> _stores = const [];
  List<StoreGroup> _groups = const [];
  final Map<String, String> _queries = {};
  bool _loading = true;
  bool _saving = false;
  String? _error;

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
      final results = await Future.wait([
        widget.apiClient.getStores(),
        widget.apiClient.getStoreGroups(),
      ]);
      if (!mounted) return;
      setState(() {
        _stores = results[0] as List<StoreItem>;
        _groups = results[1] as List<StoreGroup>;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = error.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _save(List<StoreGroup> groups) async {
    setState(() => _saving = true);
    try {
      await widget.apiClient.saveStoreGroups(groups);
      if (!mounted) return;
      setState(() => _groups = groups);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Store groups saved')),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
            content: Text(error.toString().replaceFirst('Exception: ', ''))),
      );
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _createGroup() async {
    final controller = TextEditingController();
    final name = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Create store group'),
        content: TextField(
          controller: controller,
          autofocus: true,
          textInputAction: TextInputAction.done,
          onSubmitted: (value) => Navigator.pop(context, value.trim()),
          decoration: const InputDecoration(
            labelText: 'Group name',
            hintText: 'e.g. Sydney stores',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text.trim()),
            child: const Text('Create'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (name == null || name.isEmpty) return;
    final group = StoreGroup(
      id: 'group_${DateTime.now().millisecondsSinceEpoch}',
      name: name,
    );
    await _save([..._groups, group]);
  }

  Future<void> _deleteGroup(StoreGroup group) async {
    final confirmed = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
              title: Text('Delete ${group.name}?'),
              content:
                  const Text('Stores will not be deleted from your account.'),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context, false),
                  child: const Text('Cancel'),
                ),
                FilledButton.tonal(
                  onPressed: () => Navigator.pop(context, true),
                  child: const Text('Delete'),
                ),
              ],
            ));
    if (confirmed == true) {
      await _save(_groups.where((item) => item.id != group.id).toList());
    }
  }

  Future<void> _updateGroupSelection(
    StoreGroup group,
    Iterable<String> storeIds,
    bool selected,
  ) async {
    final ids = group.storeIds.toSet();
    if (selected) {
      ids.addAll(storeIds);
    } else {
      ids.removeAll(storeIds);
    }
    final updated = StoreGroup(
      id: group.id,
      name: group.name,
      storeIds: ids.toList()..sort(),
    );
    final groups =
        _groups.map((item) => item.id == group.id ? updated : item).toList();
    await _save(groups);
  }

  List<StoreItem> _visibleStores(StoreGroup group) {
    final query = (_queries[group.id] ?? '').trim().toLowerCase();
    if (query.isEmpty) return _stores;
    return _stores
        .where((store) =>
            '${store.name} ${store.id}'.toLowerCase().contains(query))
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Store Groups')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _saving ? null : _createGroup,
        icon: const Icon(Icons.add),
        label: const Text('New group'),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(mainAxisSize: MainAxisSize.min, children: [
                      Text(_error!, textAlign: TextAlign.center),
                      const SizedBox(height: 12),
                      FilledButton(
                          onPressed: _load, child: const Text('Try again')),
                    ]),
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
                    children: [
                      Card(
                        color: theme.colorScheme.primaryContainer,
                        child: const Padding(
                          padding: EdgeInsets.all(16),
                          child: Row(children: [
                            Icon(Icons.groups_outlined),
                            SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                'Create groups for faster bulk store actions. Search before selecting when you have many stores.',
                              ),
                            ),
                          ]),
                        ),
                      ),
                      const SizedBox(height: 10),
                      if (_groups.isEmpty)
                        const Card(
                          child: Padding(
                            padding: EdgeInsets.all(24),
                            child: Text(
                                'No groups yet. Use New group to create one.'),
                          ),
                        ),
                      for (final group in _groups) _buildGroupCard(group),
                    ],
                  ),
                ),
    );
  }

  Widget _buildGroupCard(StoreGroup group) {
    final theme = Theme.of(context);
    final visibleStores = _visibleStores(group);
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ExpansionTile(
        leading: Icon(Icons.folder_shared_outlined,
            color: theme.colorScheme.primary),
        title: Text(group.name),
        subtitle: Text('${group.storeIds.length} stores selected'),
        trailing: IconButton(
          tooltip: 'Delete group',
          onPressed: _saving ? null : () => _deleteGroup(group),
          icon: const Icon(Icons.delete_outline),
        ),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        children: [
          TextField(
            onChanged: (value) => setState(() => _queries[group.id] = value),
            decoration: const InputDecoration(
              prefixIcon: Icon(Icons.search),
              hintText: 'Search stores by name or ID',
            ),
          ),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(
              child: OutlinedButton(
                onPressed: _saving || visibleStores.isEmpty
                    ? null
                    : () => _updateGroupSelection(
                        group, visibleStores.map((store) => store.id), true),
                child: const Text('Select visible'),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: OutlinedButton(
                onPressed: _saving || visibleStores.isEmpty
                    ? null
                    : () => _updateGroupSelection(
                        group, visibleStores.map((store) => store.id), false),
                child: const Text('Clear visible'),
              ),
            ),
          ]),
          const SizedBox(height: 4),
          if (visibleStores.isEmpty)
            const Padding(
              padding: EdgeInsets.all(20),
              child: Text('No matching stores.'),
            )
          else
            ...visibleStores.map((store) => CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  dense: true,
                  value: group.storeIds.contains(store.id),
                  title: Text(store.name),
                  subtitle: Text('Store ID: ${store.id}'),
                  onChanged: _saving
                      ? null
                      : (selected) => _updateGroupSelection(
                          group, [store.id], selected ?? false),
                )),
        ],
      ),
    );
  }
}

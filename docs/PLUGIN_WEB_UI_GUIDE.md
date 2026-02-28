# Plugin Management Web UI

## Overview

The Wasla admin portal now includes a comprehensive web-based interface for managing plugins, registrations, permission scopes, and event subscriptions. This web UI provides superuser admins with intuitive visual controls for all aspects of plugin lifecycle management.

## Features

### 1. Plugin Management Dashboard
- **URL**: `/admin/plugins/`
- **Route Name**: `admin_portal:plugins_dashboard`
- **Access**: Superuser only
- **Features**:
  - Overview cards showing total plugins, registrations, and active installs
  - Quick access buttons to all plugin management sections
  - Recent registrations list
  - Recent installs list
  - Navigation to detailed management sections

### 2. Plugin Registry Management
The plugin registry is the core interface for registering, verifying, and configuring plugins.

#### Registry List View
- **URL**: `/admin/plugins/registry/`
- **Route Name**: `admin_portal:plugin_registry_list`
- **Features**:
  - Search by plugin name, key, or entrypoint
  - Filter by verification status (Verified/Unverified)
  - Display of scopes and subscription counts
  - Quick action link to manage individual registrations

#### Register New Plugin
- **URL**: `/admin/plugins/registry/create/`
- **Route Name**: `admin_portal:plugin_registry_create`
- **Fields**:
  - Plugin selection (dropdown of unregistered plugins)
  - Plugin key (auto-populated, editable)
  - Entrypoint (module path)
  - Min/Max Core Version (version compatibility)
  - Isolation Mode (Standard/Isolated/Privileged)
- **Behavior**:
  - Prevents duplicate registrations
  - Creates registration in unverified state
  - Redirects to detail page after creation

#### Registry Detail View
- **URL**: `/admin/plugins/registry/<registration_id>/`
- **Route Name**: `admin_portal:plugin_registry_detail`
- **Sections**:
  1. **Registration Details** (read-only):
     - Plugin ID, Key, Entrypoint
     - Isolation Mode badge
     - Core version compatibility
     - Creation and verification timestamps
  
  2. **Verification Card**:
     - Visual status (Verified/Unverified)
     - One-click verify button (if unverified)
     - One-click unverify button (if verified)
  
  3. **Update Configuration Form**:
     - Editable min/max core versions
     - Editable isolation mode
     - Save button to apply changes
  
  4. **Permission Scopes Card**:
     - Shows configured scopes
     - Scope count badge
     - Link to manage scopes
  
  5. **Event Subscriptions Card**:
     - Shows subscription count
     - Link to view active subscriptions
  
  6. **Danger Zone**:
     - Delete registration button (with confirmation)
     - Requires explicit user confirmation

### 3. Permission Scopes Management
Define and manage what resources each plugin can access.

#### Scopes View
- **URL**: `/admin/plugins/registry/<registration_id>/scopes/`
- **Route Name**: `admin_portal:plugin_scopes`
- **Left Panel - Add Scope**:
  - Scope code input (hierarchical notation)
  - Description textarea
  - Quick-select buttons for common scopes
  - Common scope presets:
    - `plugin.lifecycle.enable`
    - `plugin.lifecycle.disable`
    - `plugin.lifecycle.uninstall`
    - `plugin.webhooks.manage`
    - `plugin.events.subscribe`
    - `plugin.data.read`
    - `plugin.data.write`

- **Right Panel - Configured Scopes**:
  - List of all scopes for this plugin
  - Each scope shows code, description, and creation date
  - Delete button for each scope
  - Empty state with hint to add scopes

### 4. Event Subscriptions Management
Monitor tenant-level event subscriptions to plugins.

#### Subscriptions List
- **URL**: `/admin/plugins/subscriptions/`
- **Route Name**: `admin_portal:plugin_subscriptions`
- **Filtering**:
  - Filter by plugin/registration
  - Filter by tenant
  - Filter by store
- **Columns**:
  - Plugin name
  - Tenant name
  - Store name (or "Tenant-wide")
  - Event keys (with "+N more" indicator)
  - Active status badge
  - Creation date

### 5. Event Deliveries Monitor
Track event delivery history and status.

#### Deliveries List
- **URL**: `/admin/plugins/deliveries/`
- **Route Name**: `admin_portal:plugin_event_deliveries`
- **Filtering**:
  - Filter by delivery status (Queued/Delivered/Skipped/Failed)
  - Filter by event key
- **Pagination**:
  - 50 items per page
  - First/Previous/Next/Last navigation
- **Columns**:
  - Event key (monospace code)
  - Plugin name
  - Tenant name
  - Status badge with color coding:
    - **Queued** (info/blue)
    - **Delivered** (success/green)
    - **Skipped** (warning/yellow)
    - **Failed** (danger/red)
  - Created and updated timestamps

### 6. Installed Plugins Viewer
See all plugin installations across stores.

#### Installed Plugins List
- **URL**: `/admin/plugins/installed/`
- **Route Name**: `admin_portal:installed_plugins`
- **Filtering**:
  - Filter by store
  - Filter by status (Enabled/Disabled)
- **Columns**:
  - Plugin name with description
  - Store name
  - Version code
  - Enabled/Disabled status badge
  - Installation date
  - Enabled since date (if enabled)

## Navigation

The plugin management section is accessed via the admin portal sidebar:
- A **Plugins** link appears in the sidebar with a puzzle icon
- It's highlighted as active when viewing any plugin management page
- Links in the management interfaces provide cross-navigation

```
Admin Portal Sidebar
├── Dashboard
├── Tenants
├── Stores
├── Payments
├── Manual Payments
├── Subscriptions
├── Settlements
├── Invoices
├── Webhooks
├── Performance
├── ──────────────── (separator)
└── Plugins ← NEW
    ├── Dashboard
    ├── Registry List
    ├── Registry Detail
    ├── Scopes Management
    ├── Subscriptions
    ├── Deliveries
    └── Installed
```

## Security

All plugin management views enforce superuser-only access through the `@admin_required` decorator:

```python
@login_required
@admin_required
def plugins_dashboard_view(request):
    # View is only accessible to authenticated superusers
    ...
```

## URL Routes

All routes are namespaced under `admin_portal`:

| Endpoint | URL | View | Name |
|----------|-----|------|------|
| Dashboard | `/admin/plugins/` | `plugins_dashboard_view` | `plugins_dashboard` |
| Registry List | `/admin/plugins/registry/` | `plugin_registry_list_view` | `plugin_registry_list` |
| Register Plugin | `/admin/plugins/registry/create/` | `plugin_registry_create_view` | `plugin_registry_create` |
| Registry Detail | `/admin/plugins/registry/<id>/` | `plugin_registry_detail_view` | `plugin_registry_detail` |
| Manage Scopes | `/admin/plugins/registry/<id>/scopes/` | `plugin_scopes_view` | `plugin_scopes` |
| Subscriptions | `/admin/plugins/subscriptions/` | `plugin_subscriptions_view` | `plugin_subscriptions` |
| Deliveries | `/admin/plugins/deliveries/` | `plugin_event_deliveries_view` | `plugin_event_deliveries` |
| Installed | `/admin/plugins/installed/` | `installed_plugins_view` | `installed_plugins` |

## Template Structure

Templates are located in `/wasla/templates/admin_portal/plugins/`:

```
templates/admin_portal/plugins/
├── dashboard.html              # Main plugin dashboard
├── registry_list.html          # List all registrations
├── registry_create.html        # Create new registration
├── registry_detail.html        # View & edit single registration
├── scopes.html                 # Manage permission scopes
├── subscriptions.html          # View event subscriptions
├── event_deliveries.html       # View event delivery history
└── installed.html              # View installed plugins across stores
```

All templates inherit from `admin_portal/base_portal.html` which provides:
- Sidebar navigation
- Admin header
- Bootstrap 5.3 styling
- Wasla theme colors (primary: #1F4FD8, accent: #F7941D)

## Form Submissions

Plugin management uses Django form submissions with POST for state-changing operations:

### Registry Detail Actions
```
POST /admin/plugins/registry/<id>/
Parameters: action=[verify|reject|update|delete]
```

### Scopes Management
```
POST /admin/plugins/registry/<id>/scopes/
Parameters: action=[add_scope|delete_scope], scope_code, description, scope_id
```

## Typical Workflows

### 1. Register a New Plugin
1. Navigate to `/admin/plugins/registry/`
2. Click "Register Plugin" button
3. Select plugin from dropdown
4. Confirm/edit plugin key and entrypoint
5. Set version compatibility
6. Click "Register Plugin"
7. Redirected to detail view (unverified state)

### 2. Verify and Configure
1. In registry detail view, click "Verify Registration"
2. Status changes to verified
3. Click "Manage Scopes" tab
4. Add needed scopes for plugin access
5. Plugin is now ready for installation

### 3. Monitor Subscriptions
1. Navigate to `/admin/plugins/subscriptions/`
2. Use filters to find specific plugin/tenant subscriptions
3. View active event subscriptions
4. Navigate to `/admin/plugins/deliveries/` to see event history

### 4. Audit Installations
1. Navigate to `/admin/plugins/installed/`
2. Filter by store or enabled status
3. See when plugins were installed/enabled
4. Track versions across stores

## File Structure Changes

```
wasla/
├── apps/plugins/
│   ├── views/
│   │   ├── __init__.py          # Updated: exports web views
│   │   ├── api.py               # Existing: API endpoints
│   │   └── web.py               # NEW: Template-based views
│   └── urls.py                  # Existing: API routes unchanged
├── apps/admin_portal/
│   └── urls.py                  # Updated: Added plugin routes
└── templates/admin_portal/
    ├── base_portal.html         # Updated: Added plugins sidebar link
    └── plugins/                 # NEW: Plugin management templates
        ├── dashboard.html
        ├── registry_list.html
        ├── registry_create.html
        ├── registry_detail.html
        ├── scopes.html
        ├── subscriptions.html
        ├── event_deliveries.html
        └── installed.html
```

## Testing

All existing plugin tests pass without modification:

```bash
pytest apps/plugins/tests.py -v
# ===== 5 passed in 21.37s =====
```

Web views have been validated with:
- Django system checks (0 issues)
- URL routing verification
- Template syntax validation
- View import tests

## Integration Notes

- Web views use the same plugin models as the API
- Authorization via the existing `@admin_required` decorator
- Form handling via standard Django POST
- No additional dependencies required
- Compatible with existing plugin lifecycle system

## Future Enhancements

Possible future additions to the web UI:

1. **Inline Plugin Configuration**
   - Accept custom configuration JSON per plugin
   - Store in PluginRegistration or new PluginConfig model
   - Display config editor in registry detail view

2. **Scope Approval Workflow**
   - Require security team approval before scope grant
   - Add approval status to PluginPermissionScope
   - Display approval history

3. **Plugin Marketplace**
   - Browse available plugins from registry
   - One-click install to specific stores
   - Plugin ratings and reviews

4. **Event Subscription UI**
   - Drag-and-drop event subscription builder
   - Visual event taxonomy explorer
   - Batch subscription management

5. **Improved Monitoring Dashboard**
   - Real-time event delivery chart
   - Plugin health indicators
   - Performance metrics per plugin

---

**Last Updated**: February 27, 2026
**Version**: 1.0
**Status**: Complete & Production Ready

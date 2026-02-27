# Wasla RBAC Enforcement Examples

## 1. Catalog: Product Create (Owner/Admin/Staff)
**Permission:** `catalog.create_product`  
**Endpoint:** `POST /api/catalog/products/`  
**Enforcement:** [apps/catalog/api.py](apps/catalog/api.py#L142)

```python
class ProductUpsertAPI(APIView):
    @method_decorator(require_permission("catalog.create_product"))
    def post(self, request):
        # Only users with `catalog.create_product` can create products
        store = require_store(request)
        serializer = ProductWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = ProductConfigurationService.upsert_product_with_variants(...)
        return Response(ProductDetailSerializer(product).data, status=201)
```

**Result:**
- **Owner/Admin/Staff**: Create succeeds (200/201)
- **Read-only**: `403 Forbidden`
- **Unauthenticated**: `403 Forbidden`

---

## 2. Orders: Sales Report View (Owner/Admin/Staff/Read-only)
**Permission:** `orders.view_reports`  
**Endpoint:** `GET /api/merchants/sales/report/`  
**Enforcement:** [apps/orders/views/api.py](apps/orders/views/api.py#L84)

```python
class SalesReportAPI(APIView):
    @method_decorator(require_permission("orders.view_reports"))
    def get(self, request):
        # Only members with `orders.view_reports` can see analytics
        store = require_store(request)
        orders_qs = Order.objects.filter(store_id=store.id, status="paid")
        return Response({...})
```

**Result:**
- **Owner/Admin/Staff/Read-only**: Report returned (200)
- **No membership**: `403 Forbidden`

---

## 3. Wallet: Withdrawal Management (Admin only)
**Permission:** `wallet.manage_withdrawals`  
**Endpoint:** `POST /api/admin/wallet/withdrawals/{id}/approve/`  
**Enforcement:** [apps/wallet/views/api.py](apps/wallet/views/api.py#L176)

```python
class AdminApproveWithdrawalAPI(APIView):
    permission_classes = [IsAdminUser]

    @method_decorator(require_permission("wallet.manage_withdrawals"))
    def post(self, request, withdrawal_id: int):
        # Only admin role can approve/reject/pay withdrawals
        withdrawal = WalletService.approve_withdrawal(withdrawal_id, request.user.id)
        return api_response(success=True, data=...)
```

**Result:**
- **Owner/Admin**: Approval succeeds (200)
- **Staff/Read-only**: `403 Forbidden`

---

## 4. Settlements: Mark Paid (Admin only)
**Permission:** `settlements.manage_settlements`  
**Endpoint:** `POST /api/settlements/admin/settlements/{id}/mark-paid`  
**Enforcement:** [apps/settlements/interfaces/api/views.py](apps/settlements/interfaces/api/views.py#L238)

```python
class AdminMarkSettlementPaidAPI(APIView):
    permission_classes = [IsAdminUser]

    @method_decorator(require_permission("settlements.manage_settlements"))
    def post(self, request, settlement_id: int):
        settlement = MarkSettlementPaidUseCase.execute(...)
        return api_response(success=True, data=...)
```

**Result:**
- **Owner/Admin**: Mark paid succeeds (200)
- **Staff/Read-only**: `403 Forbidden`

---

## 5. Plugins: Install Plugin (Owner/Admin/Staff)
**Permission:** `plugins.install_plugin`  
**Endpoint:** `POST /stores/{store_id}/plugins/install/`  
**Enforcement:** [apps/plugins/views/api.py](apps/plugins/views/api.py#L24)

```python
class PluginInstallAPI(APIView):
    @method_decorator(require_permission("plugins.install_plugin"))
    def post(self, request, store_id):
        store = require_store(request)
        plugin = Plugin.objects.filter(id=request.data.get("plugin_id")).first()
        installed = PluginInstallationService.install_plugin(store.id, plugin, ...)
        return Response(InstalledPluginSerializer(installed).data, status=201)
```

**Result:**
- **Owner/Admin/Staff**: Installation succeeds (201)
- **Read-only**: `403 Forbidden`

---

## 6. Domains: Queue Provision (Admin only)
**Permission:** `domains.queue_provision`  
**Endpoint:** `POST /api/admin/domains/queue`  
**Enforcement:** [apps/domains/interfaces/api_views.py](apps/domains/interfaces/api_views.py#L13)

```python
class DomainProvisionQueueAPI(APIView):
    permission_classes = [IsAdminUser]

    @method_decorator(require_permission("domains.queue_provision"))
    def post(self, request):
        domain_id = int(request.data.get("domain_id") or 0)
        domain = StoreDomain.objects.filter(id=domain_id).first()
        domain.status = StoreDomain.STATUS_PENDING_VERIFICATION
        domain.save()
        return api_response(success=True, data={...})
```

**Result:**
- **Owner/Admin**: Queue succeeds (200)
- **Staff/Read-only**: `403 Forbidden`

---

## Testing RBAC

### Unit Tests
Run the full RBAC suite:
```bash
python manage.py test apps.tenants.tests_rbac -v 2
```

**Coverage:**
- Permission resolver with request-level caching
- Decorator enforcement (`@require_permission`)
- Session-based tenant resolution fallback
- Seed command creates all 20 permissions + 58 role mappings

### Manual Verification
1. Seed permissions:
   ```bash
   python manage.py seed_permissions
   ```
2. Create memberships with different roles (owner/admin/staff/read_only).
3. Authenticate as each role and attempt protected endpoints.
4. Observe `403 Forbidden` when permission is missing.

---

## Permission Matrix

| Permission Code                      | Owner | Admin | Staff | Read-only |
|--------------------------------------|-------|-------|-------|-----------|
| `catalog.create_product`             | ✅    | ✅    | ✅    | ❌        |
| `catalog.update_product`             | ✅    | ✅    | ✅    | ❌        |
| `orders.create_order`                | ✅    | ✅    | ✅    | ❌        |
| `orders.view_reports`                | ✅    | ✅    | ✅    | ✅        |
| `wallet.view_wallet`                 | ✅    | ✅    | ✅    | ✅        |
| `wallet.create_withdrawal`           | ✅    | ✅    | ✅    | ❌        |
| `wallet.manage_withdrawals`          | ✅    | ✅    | ❌    | ❌        |
| `settlements.view_balance`           | ✅    | ✅    | ✅    | ✅        |
| `settlements.manage_settlements`     | ✅    | ✅    | ❌    | ❌        |
| `plugins.install_plugin`             | ✅    | ✅    | ✅    | ❌        |
| `plugins.uninstall_plugin`           | ✅    | ✅    | ❌    | ❌        |
| `domains.queue_provision`            | ✅    | ✅    | ❌    | ❌        |

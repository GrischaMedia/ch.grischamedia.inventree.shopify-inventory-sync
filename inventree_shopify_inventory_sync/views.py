from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from django.utils.timezone import now

from plugin.registry import registry

from .sync import run_full_sync, report_missing_skus
from .shopify_client import ShopifyClient

SLUG = "shopify-inventory-sync"
_last_sync_result = None
_last_sync_at = None

def _plugin():
    return registry.get_plugin(SLUG)

def _allowed(u):
    try:
        return bool(u.is_superuser or u.has_perm("stock.change_stockitem"))
    except Exception:
        return False

@login_required
def settings_view(request):
    p = _plugin()
    if p is None:
        return HttpResponseForbidden("Plugin nicht geladen")

    # „Sync jetzt starten“ via Button (GET) – bewusst idempotent gehalten
    flash = None
    if request.GET.get("run") == "1":
        if not _allowed(request.user):
            return HttpResponseForbidden("Keine Berechtigung")
        global _last_sync_at, _last_sync_result
        _last_sync_result = run_full_sync(p, request.user)
        _last_sync_at = now()
        flash = "Sync ausgeführt."

    ctx = {
        "plugin": p,
        "slug": SLUG,
        "version": getattr(p, "VERSION", "n/a"),
        "last_sync_at": _last_sync_at,
        "last_sync_summary": _summarize(_last_sync_result) if _last_sync_result else None,
        "last_sync_json": _last_sync_result,
        "flash": flash,
    }
    return render(request, "inventree_shopify_inventory_sync/settings.html", ctx)

def _summarize(res):
    if not res:
        return None
    ok = res.get("ok")
    matched = res.get("sku_matched", 0)
    changed = res.get("changed", 0)
    processed = res.get("processed", res.get("total_parts", 0))
    return f"ok={ok} matched={matched} changed={changed} processed={processed}"

@login_required
@user_passes_test(_allowed)
def sync_now_open(request):
    p = _plugin()
    if p is None:
        return HttpResponseForbidden("Plugin nicht geladen")

    global _last_sync_at, _last_sync_result
    _last_sync_result = run_full_sync(p, request.user)
    _last_sync_at = now()
    return JsonResponse(_last_sync_result)

@login_required
@user_passes_test(_allowed)
def report_missing(request):
    p = _plugin()
    if p is None:
        return HttpResponseForbidden("Plugin nicht geladen")
    return JsonResponse(report_missing_skus(p))

@login_required
@user_passes_test(_allowed)
def debug_sku(request):
    p = _plugin()
    if p is None:
        return HttpResponseForbidden("Plugin nicht geladen")
    sku = (request.GET.get("sku") or "").strip()
    if not sku:
        return JsonResponse({"ok": False, "error": "missing sku"})
    client = ShopifyClient(
        domain=p.get_setting("shop_domain"),
        token=p.get_setting("admin_token"),
        use_graphql=p.get_setting("use_graphql"),
        only_location_name=p.get_setting("only_location_name"),
    )
    try:
        variant = client.find_variant_by_sku(sku)
        if not variant:
            return JsonResponse({"ok": False, "sku": sku, "error": "variant_not_found"})
        sum_available, levels = client.get_inventory_levels(variant["inventory_item_id"])
        return JsonResponse({"ok": True, "sku": sku, "variant": variant, "sum_available": sum_available, "levels": levels})
    except Exception as e:
        return JsonResponse({"ok": False, "sku": sku, "error": str(e)})

@login_required
def sync_json(request):
    """Hilfs-Endpoint: letztes Ergebnis als JSON"""
    if _last_sync_result is None:
        return JsonResponse({"ok": False, "error": "no_last_run"})
    return JsonResponse(_last_sync_result)
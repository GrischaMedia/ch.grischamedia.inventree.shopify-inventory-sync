from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.timezone import now
from django.shortcuts import render

# nichts Schweres top-level importieren
from plugin.registry import registry

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


def _summarize(result: dict) -> str:
    """Kurze, menschenlesbare Zusammenfassung für die UI."""
    if not result or not isinstance(result, dict):
        return "–"
    parts = []
    if "dry_run" in result:
        parts.append("Dry-Run" if result["dry_run"] else "Live")
    for k in ("total_parts", "processed", "sku_matched", "changed", "skipped_delta_guard"):
        if k in result:
            parts.append(f"{k.replace('_',' ')}: {result[k]}")
    return " | ".join(parts) or "–"


@login_required
@user_passes_test(_allowed)
def sync_now_open(request):
    """
    Bewährter Endpoint:
    - Standard: JSON
    - Mit ?ui=1: hübsches Panel (ohne Routing-Änderung)
    """
    p = _plugin()
    if p is None:
        return HttpResponseForbidden("Plugin nicht geladen")

    want_ui = request.GET.get("ui") == "1"

    # Falls UI gewünscht: optional sofort laufen lassen, wenn run=1
    if want_ui and request.GET.get("run") == "1":
        from .sync import run_full_sync  # lazy import
        global _last_sync_at, _last_sync_result
        _last_sync_result = run_full_sync(p, request.user)
        _last_sync_at = now()

    if want_ui:
        ctx = {
            "slug": SLUG,
            "version": getattr(p, "VERSION", "n/a"),
            "last_sync_at": _last_sync_at,
            "last_sync_json": _last_sync_result or {},
            "last_sync_summary": _summarize(_last_sync_result),
            "settings": {
                "shop_domain": p.get_setting("shop_domain"),
                "use_graphql": p.get_setting("use_graphql"),
                "only_location_name": p.get_setting("only_location_name"),
                "target_location_id": p.get_setting("target_location_id"),
                "delta_guard": p.get_setting("delta_guard"),
                "dry_run": p.get_setting("dry_run"),
                "max_parts_per_run": p.get_setting("max_parts_per_run"),
                "throttle_ms": p.get_setting("throttle_ms"),
            },
        }
        return render(request, "inventree_shopify_inventory_sync/panel.html", ctx)

    # JSON (Default)
    from .sync import run_full_sync  # lazy import
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
    from .sync import report_missing_skus  # lazy import
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

    from .shopify_client import ShopifyClient  # lazy import

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
    if _last_sync_result is None:
        return JsonResponse({"ok": False, "error": "no_last_run"})
    return JsonResponse(_last_sync_result)
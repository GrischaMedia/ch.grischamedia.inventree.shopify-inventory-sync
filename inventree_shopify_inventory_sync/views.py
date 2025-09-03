from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt

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


def _coerce(value, validator):
    if validator == "bool":
        if isinstance(value, bool):
            return value
        v = str(value or "").strip().lower()
        return v in ("1", "true", "yes", "on", "y")
    if validator == "int":
        try:
            return int(str(value).strip() or "0")
        except Exception:
            return 0
    return "" if value is None else str(value)


@login_required
@user_passes_test(_allowed)
def sync_now_open(request):
    """
    Startet einen Sync und gibt JSON zurück.
    (Bewährter, funktionierender Endpoint)
    """
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
    """
    Listet IPNs, die in Shopify per SKU nicht gefunden wurden (JSON).
    """
    p = _plugin()
    if p is None:
        return HttpResponseForbidden("Plugin nicht geladen")
    return JsonResponse(report_missing_skus(p))


@login_required
@user_passes_test(_allowed)
def debug_sku(request):
    """
    Prüft eine einzelne SKU gegen Shopify und gibt Verfügbarkeiten zurück (JSON).
    """
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


@csrf_exempt
@login_required
@user_passes_test(_allowed)
def save_settings(request):
    """
    Speichert Plugin-Settings (JSON POST).
    Keine UI-Route, keine Template-Ansicht – nur JSON.
    """
    p = _plugin()
    if p is None:
        return HttpResponseForbidden("Plugin nicht geladen")
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST required"})
    try:
        import json
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        payload = {}
    defs = p.SETTINGS
    for key, meta in defs.items():
        raw = payload.get(key, "")
        vdef = meta.get("validator")
        coerced = _coerce(raw, vdef)
        p.set_setting(key, coerced, user=request.user)
    return JsonResponse({"ok": True})


@login_required
def sync_json(request):
    """
    Gibt das JSON des letzten Laufs zurück.
    (Kein UI; wenn _last_sync_result leer ist -> Fehlermeldung)
    """
    if _last_sync_result is None:
        return JsonResponse({"ok": False, "error": "no_last_run"})
    return JsonResponse(_last_sync_result)
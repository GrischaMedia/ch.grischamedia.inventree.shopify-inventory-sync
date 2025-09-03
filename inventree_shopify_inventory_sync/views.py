# inventree_shopify_inventory_sync/views.py

from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.utils.html import escape
from django.shortcuts import redirect
import requests

from plugin.registry import registry
from .sync import run_full_sync

SLUG = "shopify-inventory-sync"


def _allowed(u):
    try:
        return bool(u.is_superuser or u.has_perm("stock.change_stockitem"))
    except Exception:
        return False


def _plugin():
    return registry.get_plugin(SLUG)


def ping(request):
    p = _plugin()
    return JsonResponse({
        "ok": True,
        "plugin_loaded": bool(p),
        "user_authenticated": bool(getattr(request, "user", None) and request.user.is_authenticated),
    })


@login_required
def index(request):
    p = _plugin()
    if p is None:
        return HttpResponseForbidden("plugin not loaded")

    base = request.path.rstrip("/")
    data = {
        "plugin": SLUG,
        "version": getattr(p, "VERSION", "n/a"),
        "endpoints": {
            "open": request.build_absolute_uri(f"{base}/sync-now-open/"),
            "guarded": request.build_absolute_uri(f"{base}/sync-now/"),
            "ping": request.build_absolute_uri(f"{base}/ping/"),
            "config": request.build_absolute_uri(f"{base}/config/"),
            "debug_sku": request.build_absolute_uri(f"{base}/debug-sku/?sku=MB-TEST"),
            "report_missing": request.build_absolute_uri(f"{base}/report-missing/"),
        },
        "perms_ok": _allowed(request.user),
    }
    return JsonResponse(data)


@login_required
@user_passes_test(_allowed)
def sync_now(request):
    p = _plugin()
    if p is None:
        return HttpResponseForbidden("plugin not loaded")
    return JsonResponse(run_full_sync(p, request.user))


@login_required
def sync_now_open(request):
    if not _allowed(request.user):
        return HttpResponseForbidden("insufficient permissions")
    p = _plugin()
    if p is None:
        return HttpResponseForbidden("plugin not loaded")
    return JsonResponse(run_full_sync(p, request.user))


@csrf_exempt
@login_required
def settings_form(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("superuser required")

    p = _plugin()
    if p is None:
        return HttpResponseForbidden("plugin not loaded")

    keys = [
        "shop_domain",
        "admin_api_token",
        "use_graphql",
        "inv_target_location",
        "restrict_location_name",
        "auto_schedule_minutes",
        "delta_guard",
        "dry_run",
        "note_text",
        "filter_category_ids",
    ]

    if request.method == "POST":
        for k in keys:
            val = request.POST.get(k, "")
            if k in {"use_graphql", "dry_run"}:
                val = str(val).lower() in {"1", "true", "on", "yes"}
            elif k in {"auto_schedule_minutes", "delta_guard"}:
                try:
                    val = int(val)
                except Exception:
                    val = 0
            p.set_setting(k, val, user=request.user)
        return redirect(request.path)

    values = {k: p.get_setting(k) for k in keys}

    html = [
        "<html><head><meta charset='utf-8'><title>Shopify Sync Settings</title></head><body>",
        "<h1>Shopify Sync – Einstellungen</h1>",
        f"<p><strong>Plugin:</strong> {escape(SLUG)} &nbsp; "
        f"<strong>Version:</strong> {escape(getattr(p, 'VERSION', 'n/a'))}</p>",
        "<form method='post'>",
        "<table border='0' cellpadding='6' cellspacing='0' style='max-width:800px;'>",
    ]

    def row(label, name, value, input_type="text"):
        v = "" if value is None else str(value)
        return (
            "<tr>"
            f"<td style='white-space:nowrap;vertical-align:top;'>{escape(label)}</td>"
            f"<td><input type='{input_type}' name='{escape(name)}' "
            f"value='{escape(v)}' style='width:420px;'></td>"
            "</tr>"
        )

    html.append(row("Shopify Shop Domain", "shop_domain", values.get("shop_domain", "")))
    html.append(row("Admin API Token", "admin_api_token", values.get("admin_api_token", ""), "password"))
    html.append(row("GraphQL verwenden (true/false)", "use_graphql", values.get("use_graphql", False)))
    html.append(row("InvenTree Ziel-Lagerort (ID)", "inv_target_location", values.get("inv_target_location", "")))
    html.append(row("Nur Standort (Name)", "restrict_location_name", values.get("restrict_location_name", "")))
    html.append(row("Auto-Sync Intervall Minuten", "auto_schedule_minutes", values.get("auto_schedule_minutes", 30)))
    html.append(row("Delta-Guard", "delta_guard", values.get("delta_guard", 500)))
    html.append(row("Dry-Run (true/false)", "dry_run", values.get("dry_run", True)))
    html.append(row("Buchungsnotiz", "note_text", values.get("note_text", "Korrektur durch Onlineshop")))
    html.append(row("Nur Kategorien (IDs, komma-getrennt)", "filter_category_ids", values.get("filter_category_ids", "")))

    html += [
        "</table>",
        "<p><button type='submit'>Speichern</button> &nbsp; "
        "<a href='../'>Zurück</a></p>",
        "</form>",
        "</body></html>",
    ]
    return HttpResponse("\n".join(html))


@login_required
def debug_sku(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("superuser required")

    p = _plugin()
    if p is None:
        return HttpResponseForbidden("plugin not loaded")

    sku = (request.GET.get("sku") or "").strip()
    if not sku:
        return JsonResponse({"ok": False, "error": "param ?sku=... fehlt"})

    domain = (p.get_setting("shop_domain") or "").strip().lower()
    domain = domain.replace("https://", "").replace("http://", "").strip("/")
    token = p.get_setting("admin_api_token")
    api_ver = "2024-10"

    sess = requests.Session()
    sess.headers.update({
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json",
    })

    base = f"https://{domain}/admin/api/{api_ver}"

    vres = sess.get(f"{base}/variants.json", params={"sku": sku}, timeout=20)
    try:
        vres.raise_for_status()
    except Exception as e:
        return JsonResponse({"ok": False, "sku": sku, "error": f"variants_http_error: {e}", "status": vres.status_code})

    variants = (vres.json() or {}).get("variants", []) or []
    variant = None
    for v in variants:
        if (v.get("sku") or "").strip() == sku:
            variant = {
                "id": v.get("id"),
                "sku": v.get("sku"),
                "inventory_item_id": v.get("inventory_item_id"),
                "product_id": v.get("product_id"),
                "title": v.get("title"),
            }
            break

    if not variant:
        return JsonResponse({"ok": False, "sku": sku, "error": "variant_not_found_rest", "raw_count": len(variants)})

    inv_item_id = variant["inventory_item_id"]

    locres = sess.get(f"{base}/locations.json", timeout=20)
    try:
        locres.raise_for_status()
    except Exception as e:
        return JsonResponse({"ok": False, "sku": sku, "variant": variant, "error": f"locations_http_error: {e}", "status": locres.status_code})

    locations = (locres.json() or {}).get("locations", []) or []

    only_name = (p.get_setting("restrict_location_name") or "").strip()
    if only_name:
        locations = [l for l in locations if (l.get("name") or "").strip() == only_name]

    levels = []
    total = 0
    loc_ids = ",".join(str(l.get("id")) for l in locations if l.get("id"))
    if loc_ids:
        lres = sess.get(
            f"{base}/inventory_levels.json",
            params={"inventory_item_ids": inv_item_id, "location_ids": loc_ids},
            timeout=20,
        )
        if lres.status_code == 200:
            j = lres.json() or {}
            for lvl in (j.get("inventory_levels") or []):
                avail = lvl.get("available")
                # name lookup
                lname = next((x.get("name") for x in locations if x.get("id") == lvl.get("location_id")), None)
                levels.append({"location_id": lvl.get("location_id"), "location_name": lname, "available": avail})
                if avail is not None:
                    total += int(avail)

    return JsonResponse({
        "ok": True,
        "sku": sku,
        "variant": variant,
        "sum_available": total,
        "levels": levels,
    })


@login_required
def missing_report(request):
    """Liste aller Parts innerhalb des Filters, deren SKU in Shopify nicht gefunden wird."""
    if not request.user.is_superuser:
        return HttpResponseForbidden("superuser required")
    p = _plugin()
    if p is None:
        return HttpResponseForbidden("plugin not loaded")

    from .shopify_client import ShopifyClient
    client = ShopifyClient(
        (p.get_setting("shop_domain") or ""),
        (p.get_setting("admin_api_token") or ""),
        use_graphql=False,
    )

    from .sync import _iter_parts
    missing, present = [], []
    for part in _iter_parts(p):
        ipn = (part.IPN or "").strip()
        if not ipn:
            continue
        v = client.find_variant_by_sku(ipn)
        (missing if not v else present).append({"part": part.pk, "ipn": ipn})

    return JsonResponse({"ok": True, "missing": missing, "present": present})
# inventree_shopify_inventory_sync/views.py

from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.utils.html import escape
from django.shortcuts import redirect

from plugin.registry import registry
from .sync import run_full_sync

SLUG = "shopify-inventory-sync"


def _allowed(u):
    """
    Erlaubt Superuser immer; alternativ reicht das Recht, StockItems zu ändern.
    """
    try:
        return bool(u.is_superuser or u.has_perm("stock.change_stockitem"))
    except Exception:
        return False


def _plugin():
    """
    Laufende Plugin-Instanz sicher aus der Registry holen.
    (Robuster als request.plugin, das nicht in allen Builds gesetzt ist.)
    """
    return registry.get_plugin(SLUG)


# --- Public health endpoint: zeigt, ob URLs gemountet und Plugin geladen sind ---
def ping(request):
    p = _plugin()
    return JsonResponse({
        "ok": True,
        "plugin_loaded": bool(p),
        "user_authenticated": bool(getattr(request, "user", None) and request.user.is_authenticated),
    })


@login_required
def index(request):
    """
    Liefert Basisinfos + direkte Links auf die anderen Endpoints.
    """
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
            "settings": request.build_absolute_uri(f"{base}/settings/"),
        },
        "perms_ok": _allowed(request.user),
    }
    return JsonResponse(data)


@login_required
@user_passes_test(_allowed)
def sync_now(request):
    """
    Guarded Sync (Login + Permission).
    """
    p = _plugin()
    if p is None:
        return HttpResponseForbidden("plugin not loaded")
    return JsonResponse(run_full_sync(p, request.user))


@login_required
def sync_now_open(request):
    """
    „Offener“ Sync für eingeloggte User mit klaren 403 statt Redirects.
    Nutzt dieselbe Permission-Logik wie sync_now, prüft sie aber manuell.
    """
    if not _allowed(request.user):
        return HttpResponseForbidden("insufficient permissions")

    p = _plugin()
    if p is None:
        return HttpResponseForbidden("plugin not loaded")

    return JsonResponse(run_full_sync(p, request.user))


# --- Einfache Settings-Seite im Plugin (Superuser-only) ---
@csrf_exempt  # nur für Superuser zugänglich; CSRF optional später ergänzbar
@login_required
def settings_form(request):
    """
    Minimalistische Einstellungsseite, die direkt die Plugin-Settings in InvenTree speichert.
    So umgehst du die bockige Core-Modal-UI vollständig.
    """
    if not request.user.is_superuser:
        return HttpResponseForbidden("superuser required")

    p = _plugin()
    if p is None:
        return HttpResponseForbidden("plugin not loaded")

    # Keys müssen zu SETTINGS in plugin.py passen
    keys = [
        "shop_domain",
        "admin_api_token",
        "use_graphql",
        "inv_target_location",
        "auto_schedule_minutes",
        "delta_guard",
        "dry_run",
        "note_text",
        "filter_category_ids",
    ]

    if request.method == "POST":
        # Werte übernehmen und typgerecht konvertieren
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

        # PRG-Pattern: nach POST neu laden
        return redirect(request.path)

    # Aktuelle Werte lesen
    values = {k: p.get_setting(k) for k in keys}

    # Kleinste mögliche HTML-Seite, kein Template nötig
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
    html.append(row("GraphQL verwenden (true/false)", "use_graphql", values.get("use_graphql", True)))
    html.append(row("InvenTree Ziel-Lagerort (ID)", "inv_target_location", values.get("inv_target_location", "")))
    html.append(row("Auto-Sync Intervall Minuten", "auto_schedule_minutes", values.get("auto_schedule_minutes", 30)))
    html.append(row("Delta-Guard", "delta_guard", values.get("delta_guard", 0)))
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

#SKU TEST
@login_required
def debug_sku(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("superuser required")
    p = _plugin()
    if p is None:
        return HttpResponseForbidden("plugin not loaded")

    sku = request.GET.get("sku", "").strip()
    if not sku:
        return JsonResponse({"ok": False, "error": "param ?sku=... fehlt"})

    # Shopify-Client wie im Sync
    from .shopify_client import ShopifyClient
    domain = p.get_setting("shop_domain")
    token = p.get_setting("admin_api_token")
    use_graphql = bool(p.get_setting("use_graphql"))
    client = ShopifyClient(domain, token, use_graphql=False)  # fürs Debug REST nutzen

    # 1) Variante finden
    variant = client.find_variant_by_sku(sku)
    if not variant:
        return JsonResponse({"ok": False, "sku": sku, "error": "variant_not_found"})

    inv_item_id = variant.get("inventoryItemId")

    # 2) Alle Locations & Levels holen (roh), um zu sehen, was Shopify liefert
    try:
        locs = client._rest_get(f"/admin/api/2024-10/locations.json").get("locations", [])
    except Exception as e:
        return JsonResponse({"ok": False, "sku": sku, "variant": variant, "error": f"locations_error: {e}"})

    levels = []
    total = 0
    for loc in locs:
        lid = loc.get("id")
        try:
            j = client._rest_get(
                f"/admin/api/2024-10/inventory_levels.json",
                params={"inventory_item_ids": inv_item_id, "location_ids": lid},
            )
            for lvl in j.get("inventory_levels", []) or []:
                avail = lvl.get("available")
                levels.append({
                    "location_id": lid,
                    "location_name": loc.get("name"),
                    "available": avail,
                })
                if avail is not None:
                    total += int(avail)
        except Exception as e:
            levels.append({"location_id": lid, "location_name": loc.get("name"), "error": str(e)})

    return JsonResponse({
        "ok": True,
        "sku": sku,
        "variant": variant,
        "sum_available": total,
        "levels": levels,
    })
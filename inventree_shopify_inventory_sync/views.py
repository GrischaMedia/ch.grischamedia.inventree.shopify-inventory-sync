# inventree_shopify_inventory_sync/views.py

from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.utils.html import escape
from django.shortcuts import redirect

from plugin.registry import registry
from .sync import run_full_sync, _iter_parts
from .shopify_client import ShopifyClient

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
            "open": f"{base}/sync-now-open/",
            "guarded": f"{base}/sync-now/",
            "ping": f"{base}/ping/",
            "config": f"{base}/config/",
            "debug_sku": f"{base}/debug-sku/?sku=MB-TEST",
            "report_missing": f"{base}/report-missing/",
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
        "shop_domain", "admin_api_token", "use_graphql", "inv_target_location",
        "restrict_location_name", "auto_schedule_minutes", "delta_guard",
        "dry_run", "note_text", "filter_category_ids", "throttle_ms",
        "max_parts_per_run",
    ]
    info_keys = ["last_sync_at", "last_sync_result"]

    saved_msg = ""
    sync_result = None

    if request.method == "POST":
        if "__run_sync__" in request.POST:
            res = run_full_sync(p, request.user)
            sync_result = res
            from datetime import datetime
            p.set_setting("last_sync_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user=request.user)
            short = f"ok={res.get('ok')} matched={res.get('sku_matched')} changed={res.get('changed')} processed={res.get('processed')}"
            p.set_setting("last_sync_result", short, user=request.user)
            saved_msg = "Sync ausgeführt."
        else:
            for k in keys:
                val = request.POST.get(k, "")
                if k in {"use_graphql", "dry_run"}:
                    val = str(val).lower() in {"1", "true", "on", "yes"}
                elif k in {"auto_schedule_minutes", "delta_guard", "throttle_ms", "max_parts_per_run"}:
                    try:
                        val = int(val)
                    except Exception:
                        val = 0
                p.set_setting(k, val, user=request.user)
            saved_msg = "Gespeichert."

    values = {k: p.get_setting(k) for k in keys}
    infos = {k: p.get_setting(k) for k in info_keys}

    css = """
    <style>
      body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; padding: 24px; }
      h1 { margin-bottom: 10px; }
      .card { max-width: 860px; background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 18px 20px; box-shadow: 0 2px 10px rgba(0,0,0,.04); }
      .grid { display: grid; grid-template-columns: 280px 1fr; gap: 12px 18px; align-items: center; }
      .muted { color:#6b7280; font-size: 13px; }
      input[type=text], input[type=password], input[type=number] { width: 100%; padding:10px; border:1px solid #d1d5db; border-radius:8px; }
      .row { margin: 12px 0; }
      .btn { display:inline-block; padding:10px 14px; border-radius:8px; border:1px solid #d1d5db; background:#f9fafb; cursor:pointer; }
      .btn.primary { background:#2563eb; color:#fff; border-color:#2563eb; }
      .toolbar { display:flex; gap:10px; align-items:center; }
      .notice { margin-top:12px; color:#065f46; background:#ecfdf5; border:1px solid #a7f3d0; padding:8px 10px; border-radius:8px; display:inline-block; }
      .hr { height:1px; background:#e5e7eb; margin:16px 0; }
      .kv { display:flex; gap:12px; font-size:14px; }
      .kv dt { color:#6b7280; min-width:150px; }
      pre { background:#f8fafc; padding:10px; border-radius:8px; border:1px solid #e5e7eb; overflow:auto; }
      a.link { text-decoration:none; color:#2563eb; }
    </style>
    """

    def input_row(label, name, value, typ="text", placeholder=""):
        v = "" if value is None else str(value)
        return f"""
          <div class='row grid'>
            <div><div><strong>{escape(label)}</strong><div class='muted'>{escape(name)}</div></div></div>
            <div><input type='{escape(typ)}' name='{escape(name)}' value='{escape(v)}' placeholder='{escape(placeholder)}'></div>
          </div>
        """

    html = [ "<html><head><meta charset='utf-8'><title>Shopify Sync – Einstellungen</title>", css, "</head><body>" ]
    html.append("<h1>Shopify Sync – Einstellungen</h1>")

    # Info-Card + Buttons
    html.append("<div class='card' style='margin-bottom:16px'>")
    base = request.path.rstrip("/")
    html.append("<div class='toolbar'>")
    html.append(f"<form method='post' style='display:inline'><button class='btn primary' name='__run_sync__' value='1'>Sync jetzt starten</button></form>")
    html.append(f"<a class='btn' href='{escape(base)}/../sync-now-open/'>als JSON öffnen</a>")
    html.append(f"<a class='btn' href='{escape(base)}/../report-missing/'>fehlende SKUs</a>")
    html.append("</div>")

    if saved_msg:
        html.append(f"<div class='notice'>{escape(saved_msg)}</div>")

    last_at = infos.get("last_sync_at") or "—"
    last_res = infos.get("last_sync_result") or "—"
    html += [
        "<div class='hr'></div>",
        "<div class='kv'><dt>Letzter Sync</dt><dd>" + escape(last_at) + "</dd></div>",
        "<div class='kv'><dt>Ergebnis</dt><dd>" + escape(last_res) + "</dd></div>",
    ]
    if sync_result is not None:
        import json
        html += ["<div class='hr'></div>", "<div><strong>Live-Ergebnis</strong></div>",
                 "<pre>" + escape(json.dumps(sync_result, ensure_ascii=False, indent=2)) + "</pre>"]
    html.append("</div>")

    # Settings-Form
    html.append("<form class='card' method='post'>")
    html.append(input_row("Shopify Shop Domain", "shop_domain", values.get("shop_domain", ""), "text", "myshop.myshopify.com"))
    html.append(input_row("Admin API Token", "admin_api_token", values.get("admin_api_token", ""), "password", "*****"))
    html.append(input_row("GraphQL verwenden (true/false)", "use_graphql", values.get("use_graphql", True), "text", "True/False"))
    html.append(input_row("InvenTree Ziel-Lagerort (ID)", "inv_target_location", values.get("inv_target_location", ""), "text", "z. B. 143"))
    html.append(input_row("Nur Standort (Name)", "restrict_location_name", values.get("restrict_location_name", ""), "text", "Domleschgerstrasse 22"))
    html.append(input_row("Auto-Sync Intervall Minuten", "auto_schedule_minutes", values.get("auto_schedule_minutes", 5), "number"))
    html.append(input_row("Delta-Guard", "delta_guard", values.get("delta_guard", 500), "number"))
    html.append(input_row("Dry-Run (true/false)", "dry_run", values.get("dry_run", True), "text", "True/False"))
    html.append(input_row("Buchungsnotiz", "note_text", values.get("note_text", "Korrektur durch Onlineshop")))
    html.append(input_row("Nur Kategorien (IDs, komma-getrennt)", "filter_category_ids", values.get("filter_category_ids", "")))
    html.append(input_row("Throttle pro Artikel (ms)", "throttle_ms", values.get("throttle_ms", 600), "number"))
    html.append(input_row("Max. Artikel pro Lauf", "max_parts_per_run", values.get("max_parts_per_run", 40), "number"))

    html.append("<div class='row'><button class='btn primary' type='submit'>Speichern</button> <a class='btn' href='../'>Zurück</a></div>")
    html.append("</form>")

    html.append("</body></html>")
    return HttpResponse("".join(html))


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

    client = ShopifyClient(
        (p.get_setting("shop_domain") or ""),
        (p.get_setting("admin_api_token") or ""),
        use_graphql=True,
    )

    variant = client.find_variant_by_sku(sku)
    if not variant:
        return JsonResponse({"ok": False, "sku": sku, "error": "variant_not_found"})

    only_name = (p.get_setting("restrict_location_name") or "").strip() or None
    total = client.inventory_available_sum(variant.get("inventory_item_id"), only_location_name=only_name)

    return JsonResponse({
        "ok": True,
        "sku": sku,
        "variant": variant,
        "sum_available": total,
    })


@login_required
def missing_report(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("superuser required")
    p = _plugin()
    if p is None:
        return HttpResponseForbidden("plugin not loaded")

    client = ShopifyClient(
        (p.get_setting("shop_domain") or ""),
        (p.get_setting("admin_api_token") or ""),
        use_graphql=True,
    )

    missing, present = [], []
    for part in _iter_parts(p):
        ipn = (part.IPN or "").strip()
        if not ipn:
            continue
        v = client.find_variant_by_sku(ipn)
        (missing if not v else present).append({"part": part.pk, "ipn": ipn})

    return JsonResponse({"ok": True, "missing": missing, "present": present})
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
def settings_view_inline(request):
    """
    Komplette Konfigurationsseite als Inline-HTML unter /plugin/<slug>/panel/
    GET ?run=1 führt einen Sync aus und zeigt rechts das Live-JSON.
    """
    p = _plugin()
    if p is None:
        return HttpResponseForbidden("Plugin nicht geladen")

    global _last_sync_at, _last_sync_result

    flash = ""
    if request.GET.get("run") == "1":
        if not _allowed(request.user):
            return HttpResponseForbidden("Keine Berechtigung")
        _last_sync_result = run_full_sync(p, request.user)
        _last_sync_at = now()
        flash = "Sync ausgeführt."

    # Settings einsammeln
    defs_ui = []
    current = p.get_settings()
    for key, meta in p.SETTINGS.items():
        defs_ui.append({
            "key": key,
            "name": meta.get("name", key),
            "description": meta.get("description", ""),
            "value": current.get(key).value if key in current else meta.get("default", ""),
            "validator": meta.get("validator", ""),
        })

    def _summarize(res):
        if not res:
            return ""
        ok = res.get("ok")
        matched = res.get("sku_matched", 0)
        changed = res.get("changed", 0)
        processed = res.get("processed", res.get("total_parts", 0))
        return f"ok={ok} matched={matched} changed={changed} processed={processed}"

    summary = _summarize(_last_sync_result)
    last_sync_at_str = _last_sync_at.strftime("%Y-%m-%d %H:%M:%S") if _last_sync_at else "–"

    # Inline-HTML
    html_top = f"""<!doctype html>
<html lang="de"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Shopify Sync – Einstellungen</title>
<style>
:root{{--bg:#0b1020;--panel:#101833;--muted:#8ea3c3;--text:#e8eefb;--accent:#4da3ff;--accent-2:#7bd389;--danger:#ff5c6b;--border:#1d2747}}
*{{box-sizing:border-box}} body{{margin:0;font:14px/1.5 system-ui,-apple-system,Segoe UI,Roboto,Ubuntu;background:var(--bg);color:var(--text)}}
a{{color:var(--accent);text-decoration:none}} .wrap{{max-width:1200px;margin:24px auto;padding:0 16px}}
h1{{margin:0 0 16px 0;font-size:28px}} .grid{{display:grid;grid-template-columns:480px 1fr;gap:20px}}
@media (max-width:980px){{.grid{{grid-template-columns:1fr}}}} .card{{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:16px}}
.row{{display:flex;gap:8px;flex-wrap:wrap;align-items:center}}
.btn{{border:1px solid var(--border);background:#162149;color:var(--text);padding:10px 14px;border-radius:10px;font-weight:600;cursor:pointer}}
.btn:hover{{background:#1a2760}} .btn.alt{{background:#162b24}} .btn.alt:hover{{background:#1b3a30}} .btn.ghost{{background:transparent}}
.tag{{display:inline-block;padding:3px 8px;border-radius:999px;border:1px solid var(--border);color:var(--muted)}}
.flash{{background:#102a17;border:1px solid #184a2a;color:#b8ffd0;padding:10px 12px;border-radius:10px;margin:10px 0}}
.muted{{color:var(--muted)}} .small{{font-size:12px}} pre{{white-space:pre-wrap;word-break:break-word;background:#0d142b;border:1px solid var(--border);border-radius:10px;padding:12px;max-height:60vh;overflow:auto}}
.form dl{{display:grid;grid-template-columns:240px 1fr;gap:10px 12px}} @media (max-width:720px){{.form dl{{grid-template-columns:1fr}}}}
.form dt{{color:var(--muted);align-self:center}} .form dd{{margin:0}} .in{{width:100%;padding:10px 12px;border-radius:10px;border:1px solid var(--border);background:#0f1733;color:var(--text)}}
.sum-line{{display:flex;gap:18px;flex-wrap:wrap}} .sum-line div{{background:#0d1530;border:1px solid var(--border);padding:8px 10px;border-radius:10px}}
.sticky{{position:sticky;top:16px}} .toolbar{{display:flex;gap:8px;flex-wrap:wrap}}
</style></head><body>
<div class="wrap">
  <h1>Shopify Sync – Einstellungen</h1>
  {"<div class='flash'>" + "Sync ausgeführt." + "</div>" if (flash) else ""}
  <div class="grid">
    <div class="card">
      <div class="toolbar" style="margin-bottom:10px">
        <a class="btn" href="?run=1">Sync jetzt starten</a>
        <a class="btn ghost" href="/plugin/{SLUG}/sync-json/" target="_blank">als JSON öffnen</a>
        <a class="btn ghost" href="/plugin/{SLUG}/report-missing/" target="_blank">fehlende SKUs</a>
        <span class="tag">Version 0.0.32</span>
      </div>
      <form id="cfg" class="form">
        <dl>"""

    # Felder
    import html as _html
    fields_html = []
    for s in defs_ui:
        val = _html.escape(str(s["value"]) if s["value"] is not None else "")
        desc = f"<div class='small muted'>{_html.escape(s['description'])}</div>" if s["description"] else ""
        fields_html.append(
            f"<dt>{_html.escape(s['name'])}</dt>"
            f"<dd><input class='in' name='{_html.escape(s['key'])}' value=\"{val}\">{desc}</dd>"
        )

    # Rechte Spalte
    def _json_pretty(data):
        import json
        return json.dumps(data, ensure_ascii=False, indent=2)

    json_pretty = _json_pretty(_last_sync_result or {"info": "Noch kein Ergebnis vorhanden."})
    sum_html = (
        "<div class='sum-line'>" + "".join([f"<div>{_html.escape(t)}</div>" for t in (summary.split(" ") if summary else [])]) + "</div>"
        if summary else "<span class='muted'>Noch kein Lauf gespeichert.</span>"
    )

    html_bottom = f"""</dl>
        <div style="margin-top:12px" class="row">
          <button class="btn alt" type="submit">Speichern</button>
          <span class="muted small">Plugin: {SLUG}</span>
        </div>
      </form>
    </div>

    <div class="card sticky">
      <div class="row" style="justify-content:space-between;align-items:center;margin-bottom:8px">
        <div class="muted small">Letzter Sync</div>
        <div class="tag">{last_sync_at_str}</div>
      </div>
      <div style="margin:6px 0 12px 0">{sum_html}</div>

      <div class="muted small" style="margin-bottom:6px">Live-Ergebnis</div>
      <pre id="live-pre">{_html.escape(json_pretty)}</pre>

      <div class="row" style="margin-top:8px">
        <button id="runBtn" class="btn">Sync jetzt starten</button>
        <a class="btn ghost" href="/plugin/{SLUG}/sync-json/" target="_blank">als JSON öffnen</a>
      </div>
    </div>
  </div>
</div>

<script>
const btn = document.getElementById('runBtn');
const pre = document.getElementById('live-pre');
const form = document.getElementById('cfg');

if (btn) {{
  btn.addEventListener('click', async (e) => {{
    e.preventDefault();
    btn.disabled = true; const label = btn.textContent; btn.textContent = 'Sync läuft …';
    try {{
      const r = await fetch('/plugin/{SLUG}/sync-now-open/');
      const j = await r.json();
      pre.textContent = JSON.stringify(j, null, 2);
    }} catch (err) {{
      pre.textContent = 'Fehler: ' + err;
    }} finally {{
      btn.textContent = label; btn.disabled = false;
    }}
  }});
}}

if (form) {{
  form.addEventListener('submit', async (e) => {{
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    try {{
      const r = await fetch('/plugin/{SLUG}/save-settings/', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(data)
      }});
      const j = await r.json();
      alert(j.ok ? 'Gespeichert.' : ('Fehler: ' + (j.error || 'unbekannt')));
    }} catch (err) {{
      alert('Fehler: ' + err);
    }}
  }});
}}
</script>
</body></html>"""

    return HttpResponse(html_top + "".join(fields_html) + html_bottom)


@csrf_exempt
@login_required
@user_passes_test(_allowed)
def save_settings(request):
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
    if _last_sync_result is None:
        return JsonResponse({"ok": False, "error": "no_last_run"})
    return JsonResponse(_last_sync_result)
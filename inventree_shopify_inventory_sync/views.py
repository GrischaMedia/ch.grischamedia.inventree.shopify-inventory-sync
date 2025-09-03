from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required, user_passes_test
from plugin.registry import registry
from .sync import run_full_sync

SLUG = "shopify-inventory-sync"

def _allowed(u):
    try:
        return bool(u.is_superuser or u.has_perm("stock.change_stockitem"))
    except Exception:
        return False

def _plugin():
    # Sicher die Plugin-Instanz aus der Registry holen
    return registry.get_plugin(SLUG)

# --- Public health endpoint: hilft sofort zu sehen, ob URLs gemountet sind ---
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
    data = {
        "plugin": SLUG,
        "version": getattr(p, "VERSION", "n/a"),
        "endpoints": {
            "open":  request.build_absolute_uri(request.path.rstrip("/") + "/sync-now-open/"),
            "guarded": request.build_absolute_uri(request.path.rstrip("/") + "/sync-now/"),
            "ping": request.build_absolute_uri(request.path.rstrip("/") + "/ping/"),
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
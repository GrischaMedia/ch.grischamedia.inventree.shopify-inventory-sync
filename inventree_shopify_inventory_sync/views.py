# inventree_shopify_inventory_sync/views.py
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required, user_passes_test

from plugin.registry import registry  # <— offizielle Registry
from .sync import run_full_sync

SLUG = "shopify-inventory-sync"

def _allowed(u):
    return bool(u.is_superuser or u.has_perm("stock.change_stockitem"))

def _plugin():
    # Sichere Auflösung der Plugin-Instanz – unabhängig davon, wie die View aufgerufen wird
    return registry.get_plugin(SLUG)

@login_required
def index(request):
    p = _plugin()
    if p is None:
        return HttpResponseForbidden("plugin not loaded")
    data = {
        "plugin": SLUG,
        "endpoints": {
            "open":  request.build_absolute_uri(request.path.rstrip("/") + "/sync-now-open/"),
            "guarded": request.build_absolute_uri(request.path.rstrip("/") + "/sync-now/"),
        },
        "perms_ok": _allowed(request.user),
        "version": getattr(p, "VERSION", "n/a"),
        "title": getattr(p, "TITLE", ""),
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
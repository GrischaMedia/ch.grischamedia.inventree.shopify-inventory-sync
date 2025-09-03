from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required, user_passes_test
from .sync import run_full_sync

def _allowed(u):
    return bool(u.is_superuser or u.has_perm("stock.change_stockitem"))

@login_required
def index(request):
    data = {
        "plugin": "shopify-inventory-sync",
        "endpoints": {
            "open":  request.build_absolute_uri(request.path.rstrip("/") + "/sync-now-open/"),
            "guarded": request.build_absolute_uri(request.path.rstrip("/") + "/sync-now/"),
        },
        "perms_ok": _allowed(request.user),
    }
    return JsonResponse(data)

@login_required
@user_passes_test(_allowed)
def sync_now(request):
    return JsonResponse(run_full_sync(request.plugin, request.user))  # InvenTree injiziert .plugin in die View

@login_required
def sync_now_open(request):
    if not _allowed(request.user):
        return HttpResponseForbidden("insufficient permissions")
    return JsonResponse(run_full_sync(request.plugin, request.user))
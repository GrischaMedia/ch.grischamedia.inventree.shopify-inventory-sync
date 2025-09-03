# inventree/shopify_inventory_sync/plugin.py
from plugin import InvenTreePlugin
from plugin.mixins import SettingsMixin, AppMixin
from django.urls import path, reverse
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required, user_passes_test

from .sync import run_full_sync


def _is_allowed(user):
    """Superuser immer; sonst reicht stock.change_stockitem."""
    return bool(user.is_superuser or user.has_perm("stock.change_stockitem"))


class ShopifyInventorySyncPlugin(SettingsMixin, AppMixin, InvenTreePlugin):
    NAME = "ShopifyInventorySync"
    SLUG = "shopify-inventory-sync"  # wichtig: dieser Wert bestimmt die URL-Namespace
    TITLE = "Shopify → InvenTree Inventory Sync (SKU == IPN)"
    DESCRIPTION = "Liest Bestände aus Shopify (per SKU) und bucht Bestandskorrekturen in InvenTree (IPN-Match)."
    VERSION = "0.0.5"
    AUTHOR = "GrischaMedia / Grischabock (Sandro Geyer)"

    SETTINGS = {
        "shop_domain": {"name": "Shopify Shop Domain", "description": "z. B. my-shop.myshopify.com (ENV: SHOPIFY_SHOP_DOMAIN)", "default": ""},
        "admin_api_token": {"name": "Admin API Token", "description": "Shopify Admin API Access Token (ENV: SHOPIFY_ADMIN_API_TOKEN)", "default": "", "protected": True},
        "use_graphql": {"name": "GraphQL verwenden", "description": "Für performantere SKU-Suchen", "default": True},
        "inv_target_location": {"name": "InvenTree Ziel-Lagerort (ID)", "description": "ID des Lagerorts 'Onlineshop' (ENV: INVENTREE_TARGET_LOCATION_ID)", "default": ""},
        "auto_schedule_minutes": {"name": "Auto-Sync Intervall (Minuten)", "description": "0 = aus (extern via Cron o.ä.)", "default": 30},
        "delta_guard": {"name": "Delta-Limit pro Artikel", "description": "Max. absolute Anpassung pro Sync (z. B. 500). 0 = aus.", "default": 0},
        "dry_run": {"name": "Dry-Run", "description": "Nur lesen, keine Buchungen ausführen", "default": True},
        "note_text": {"name": "Buchungsnotiz", "description": "Notiz für Stock-Adjustments", "default": "Korrektur durch Onlineshop"},
        "filter_category_ids": {"name": "Nur Kategorien (IDs, komma-getrennt)", "description": "Optional: nur Parts in diesen Kategorien syncen (leer = alle aktiven Parts).", "default": ""},
    }

    # ---- Menüeintrag: InvenTree baut die korrekte URL selbst ----
    def get_menu_items(self, request):
        items = []
        if request.user.is_authenticated and _is_allowed(request.user):
            items.append({
                "name": "Shopify Sync jetzt (open)",
                "link": reverse(f"plugin:{self.SLUG}-sync-now-open"),
                "icon": "fa-sync",
            })
            items.append({
                "name": "Shopify Sync jetzt",
                "link": reverse(f"plugin:{self.SLUG}-sync-now"),
                "icon": "fa-sync",
            })
        return items

    # ---- Routing ----
    def get_urls(self):
        # WICHTIG: Kurz-Namen ohne Unterstrich verwenden!
        return [
            path("sync-now/", self._wrap(self.sync_now_view), name="sync-now"),
            path("sync-now-open/", self.sync_now_open_view, name="sync-now-open"),
        ]

    def _wrap(self, view):
        @login_required
        @user_passes_test(_is_allowed)
        def wrapped(request, *args, **kwargs):
            return view(request, *args, **kwargs)
        return wrapped

    # ---- Views ----
    def sync_now_view(self, request):
        result = run_full_sync(self, request.user)
        return JsonResponse(result)

    def sync_now_open_view(self, request):
        # keine Decorators -> liefert 403/200 statt Redirect
        if not request.user.is_authenticated:
            return HttpResponseForbidden("not authenticated")
        if not _is_allowed(request.user):
            return HttpResponseForbidden("insufficient permissions")
        result = run_full_sync(self, request.user)
        return JsonResponse(result)

    def setup(self, *args, **kwargs):
        # Auto-Sync extern triggern (Cron/Task)
        pass
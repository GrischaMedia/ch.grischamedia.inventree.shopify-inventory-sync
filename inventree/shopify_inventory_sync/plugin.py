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
    SLUG = "shopify-inventory-sync"
    TITLE = "Shopify → InvenTree Inventory Sync (SKU == IPN)"
    DESCRIPTION = "Liest Bestände aus Shopify (per SKU) und bucht Bestandskorrekturen in InvenTree (IPN-Match)."
    VERSION = "0.0.7"
    AUTHOR = "GrischaMedia / Grischabock (Sandro Geyer)"

    # --- EXPLIZITE TYPEN -> Settings-Form rendert zuverlässig ---
    SETTINGS = {
        "shop_domain": {
            "name": "Shopify Shop Domain",
            "description": "z. B. my-shop.myshopify.com (ENV: SHOPIFY_SHOP_DOMAIN)",
            "default": "",
            "type": "string",
        },
        "admin_api_token": {
            "name": "Admin API Token",
            "description": "Shopify Admin API Access Token (ENV: SHOPIFY_ADMIN_API_TOKEN)",
            "default": "",
            "protected": True,
            "type": "string",
        },
        "use_graphql": {
            "name": "GraphQL verwenden",
            "description": "Für performantere SKU-Suchen",
            "default": True,
            "type": "boolean",
        },
        "inv_target_location": {
            "name": "InvenTree Ziel-Lagerort (ID)",
            "description": "ID des Lagerorts 'Onlineshop' (ENV: INVENTREE_TARGET_LOCATION_ID)",
            "default": "",
            "type": "string",
        },
        "auto_schedule_minutes": {
            "name": "Auto-Sync Intervall (Minuten)",
            "description": "0 = aus (extern via Cron o.ä.)",
            "default": 30,
            "type": "integer",
        },
        "delta_guard": {
            "name": "Delta-Limit pro Artikel",
            "description": "Max. absolute Anpassung pro Sync (z. B. 500). 0 = aus.",
            "default": 0,
            "type": "integer",
        },
        "dry_run": {
            "name": "Dry-Run",
            "description": "Nur lesen, keine Buchungen ausführen",
            "default": True,
            "type": "boolean",
        },
        "note_text": {
            "name": "Buchungsnotiz",
            "description": "Notiz für Stock-Adjustments",
            "default": "Korrektur durch Onlineshop",
            "type": "string",
        },
        "filter_category_ids": {
            "name": "Nur Kategorien (IDs, komma-getrennt)",
            "description": "Optional: nur Parts in diesen Kategorien syncen (leer = alle aktiven Parts).",
            "default": "",
            "type": "string",
        },
    }

    # ---- Menüeintrag (falls deine UI ihn anzeigt) ----
    def get_menu_items(self, request):
        items = []
        if request.user.is_authenticated and _is_allowed(request.user):
            items.append({
                "name": "Shopify Sync – Übersicht",
                "link": reverse(f"plugin:{self.SLUG}-index"),
                "icon": "fa-external-link-alt",
            })
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
        # Kurznamen → finaler Name wird "plugin:<SLUG>-<name>"
        return [
            path("", self.index_view, name="index"),
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
    def index_view(self, request):
        """
        Immer erreichbar (mit Login), liefert klare Hinweise + Links als JSON.
        Nutze das, wenn du irgendwelche Weiterleitungen siehst.
        """
        if not request.user.is_authenticated:
            return HttpResponseForbidden("not authenticated")

        data = {
            "plugin": self.SLUG,
            "endpoints": {
                "open": reverse(f"plugin:{self.SLUG}-sync-now-open"),
                "guarded": reverse(f"plugin:{self.SLUG}-sync-now"),
            },
            "perms_ok": _is_allowed(request.user),
        }
        return JsonResponse(data)

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
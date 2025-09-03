# ch.grischamedia.inventree.shopify-inventory-sync/plugin.py
from plugin import InvenTreePlugin
from plugin.mixins import SettingsMixin, AppMixin
from django.urls import path
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required, permission_required

from .sync import run_full_sync

class ShopifyInventorySyncPlugin(SettingsMixin, AppMixin, InvenTreePlugin):
    """
    Shopify -> InvenTree Bestandsabgleich (SKU == IPN)
    """
    NAME = "ShopifyInventorySync"
    SLUG = "shopify-inventory-sync"
    TITLE = "Shopify → InvenTree Inventory Sync (SKU == IPN)"
    DESCRIPTION = "Liest Bestände aus Shopify (per SKU) und bucht Bestandskorrekturen in InvenTree (IPN-Match)."
    VERSION = "0.0.1"
    AUTHOR = "GrischaMedia / Grischabock (Sandro Geyer)"

    SETTINGS = {
        "shop_domain": {
            "name": "Shopify Shop Domain",
            "description": "z. B. my-shop.myshopify.com",
            "default": "",
        },
        "admin_api_token": {
            "name": "Admin API Token",
            "description": "Shopify Admin API Access Token (Custom App)",
            "default": "",
            "protected": True,
        },
        "use_graphql": {
            "name": "GraphQL verwenden",
            "description": "Für performantere SKU-Suchen",
            "default": True,
        },
        "inv_target_location": {
            "name": "InvenTree Ziel-Lagerort (ID)",
            "description": "ID des Lagerorts 'Onlineshop' (dorthin wird gespiegelt)",
            "default": "",
        },
        "auto_schedule_minutes": {
            "name": "Auto-Sync Intervall (Minuten)",
            "description": "0 = aus (extern via Cron o.ä.)",
            "default": 30,
        },
        "delta_guard": {
            "name": "Delta-Limit pro Artikel",
            "description": "Max. absolute Anpassung pro Sync (z. B. 500). 0 = aus.",
            "default": 0,
        },
        "dry_run": {
            "name": "Dry-Run",
            "description": "Nur lesen, keine Buchungen ausführen",
            "default": True,
        },
        "note_text": {
            "name": "Buchungsnotiz",
            "description": "Notiz für Stock-Adjustments",
            "default": "Korrektur durch Onlineshop",
        },
        "filter_category_ids": {
            "name": "Nur Kategorien (IDs, komma-getrennt)",
            "description": "Optional: nur Parts in diesen Kategorien syncen (leer = alle aktiven Parts).",
            "default": "",
        },
    }

    # Manuelle Trigger-Route (Button/URL)
    def get_urls(self):
        return [
            path("sync-now/", self._wrap(self.sync_now_view), name="shopify_inventory_sync_now"),
        ]

    def _wrap(self, view):
        @login_required
        @permission_required("stock.change_stockitem", raise_exception=True)
        def wrapped(request, *args, **kwargs):
            return view(request, *args, **kwargs)
        return wrapped

    def sync_now_view(self, request):
        if not request.user.is_authenticated:
            return HttpResponseForbidden()
        result = run_full_sync(self, request.user)
        return JsonResponse(result)

    def setup(self, *args, **kwargs):
        """
        Hinweis: Auto-Sync bitte extern triggern (z. B. Cron, der die obige URL aufruft),
        oder über einen Periodic Task, der run_full_sync(self, system_user) ausführt.
        Das ist stabiler und einfacher zu kontrollieren.
        """
        pass
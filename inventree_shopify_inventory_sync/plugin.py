# inventree_shopify_inventory_sync/plugin.py

from plugin import InvenTreePlugin
from plugin.mixins import SettingsMixin, UrlsMixin
from django.urls import path, reverse
from . import views


class ShopifyInventorySyncPlugin(SettingsMixin, UrlsMixin, InvenTreePlugin):
    """
    Shopify → InvenTree Bestandsabgleich (SKU == IPN)
    """
    NAME = "ShopifyInventorySync"
    SLUG = "shopify-inventory-sync"
    TITLE = "Shopify → InvenTree Inventory Sync (SKU == IPN)"
    DESCRIPTION = "Liest Bestände aus Shopify (per SKU) und bucht Bestandskorrekturen in InvenTree (IPN-Match)."
    VERSION = "0.0.51"
    AUTHOR = "GrischaMedia / Grischabock (Sandro Geyer)"

    URLS = [
        path("", views.index, name="index"),
        path("ping/", views.ping, name="ping"),
        path("sync-now/", views.sync_now, name="sync-now"),
        path("sync-now-open/", views.sync_now_open, name="sync-now-open"),
        path("config/", views.settings_form, name="config"),
        path("debug-sku/", views.debug_sku, name="debug-sku"),
        path("report-missing/", views.missing_report, name="report-missing"),
    ]

    def get_menu_items(self, request):
        try:
            allowed = request.user.is_authenticated and (
                request.user.is_superuser or request.user.has_perm("stock.change_stockitem")
            )
        except Exception:
            allowed = False

        if not allowed:
            return []

        ns = f"plugin:{self.SLUG}"
        return [
            {"name": "Shopify Sync – Übersicht", "link": reverse(f"{ns}-index"), "icon": "fa-external-link-alt"},
            {"name": "Shopify Sync – Config", "link": reverse(f"{ns}-config"), "icon": "fa-cog"},
            {"name": "Shopify Sync jetzt (open)", "link": reverse(f"{ns}-sync-now-open"), "icon": "fa-sync"},
            {"name": "Shopify Sync jetzt", "link": reverse(f"{ns}-sync-now"), "icon": "fa-sync"},
            {"name": "Debug SKU", "link": reverse(f"{ns}-debug-sku") + "?sku=MB-TEST", "icon": "fa-bug"},
            {"name": "Report fehlende SKUs", "link": reverse(f"{ns}-report-missing"), "icon": "fa-list"},
            {"name": "Ping", "link": reverse(f"{ns}-ping"), "icon": "fa-circle"},
        ]

    SETTINGS = {
        "shop_domain": {
            "name": "Shopify Shop Domain",
            "description": "z. B. my-shop.myshopify.com (ohne https://)",
            "default": "",
            "type": "string",
        },
        "admin_api_token": {
            "name": "Admin API Token",
            "description": "Shopify Admin API Access Token",
            "default": "",
            "protected": True,
            "type": "string",
        },
        "use_graphql": {
            "name": "GraphQL verwenden",
            "description": "REST + GraphQL-Fallback für Variantensuche",
            "default": True,
            "type": "boolean",
        },
        "inv_target_location": {
            "name": "InvenTree Ziel-Lagerort (ID)",
            "description": "Nicht-struktureller Lagerort für Online-Bestand",
            "default": "",
            "type": "string",
        },
        "restrict_location_name": {
            "name": "Nur Standort (Name)",
            "description": "Nur dieser Shopify-Standort wird summiert (optional)",
            "default": "",
            "type": "string",
        },
        "auto_schedule_minutes": {
            "name": "Auto-Sync Intervall (Minuten)",
            "description": "0 = aus",
            "default": 5,
            "type": "integer",
        },
        "delta_guard": {
            "name": "Delta-Limit pro Artikel",
            "description": "0 = aus",
            "default": 500,
            "type": "integer",
        },
        "dry_run": {
            "name": "Dry-Run",
            "description": "Nur lesen, keine Buchungen",
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
            "description": "Leerlassen = alle aktiven Teile",
            "default": "",
            "type": "string",
        },
        "throttle_ms": {
            "name": "Throttle pro Artikel (ms)",
            "description": "kleine Pause zwischen Artikeln",
            "default": 600,
            "type": "integer",
        },
        "max_parts_per_run": {
            "name": "Max. Artikel pro Lauf",
            "description": "0 = unlimitiert",
            "default": 40,
            "type": "integer",
        },
        # Anzeige-Felder (werden von views gepflegt)
        "last_sync_at": {
            "name": "Letzter Sync (Zeit)",
            "description": "Nur Anzeige",
            "default": "",
            "type": "string",
        },
        "last_sync_result": {
            "name": "Letzter Sync (Kurzinfo)",
            "description": "Nur Anzeige",
            "default": "",
            "type": "string",
        },
    }
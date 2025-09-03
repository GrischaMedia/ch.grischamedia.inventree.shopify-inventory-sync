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
    SLUG = "shopify-inventory-sync"  # URL-Basis: /plugin/shopify-inventory-sync/
    TITLE = "Shopify → InvenTree Inventory Sync (SKU == IPN)"
    DESCRIPTION = "Liest Bestände aus Shopify (per SKU) und bucht Bestandskorrekturen in InvenTree (IPN-Match)."
    VERSION = "0.0.12"
    AUTHOR = "GrischaMedia / Grischabock (Sandro Geyer)"

    # Routen (wie beim funktionierenden In/Out-Plugin über URLS)
    URLS = [
        path("", views.index, name="index"),
        path("ping/", views.ping, name="ping"),
        path("sync-now/", views.sync_now, name="sync-now"),
        path("sync-now-open/", views.sync_now_open, name="sync-now-open"),
        path("config/", views.settings_form, name="config"),          # eigene, simple Config-Seite
        path("debug-sku/", views.debug_sku, name="debug-sku"),        # gezieltes SKU-Debug gegen Shopify
    ]

    # Menü
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
            {"name": "Ping", "link": reverse(f"{ns}-ping"), "icon": "fa-circle"},
        ]

    # Settings (explizite Typen, damit auch die Core-UI korrekt wäre)
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
            "description": "Für performantere SKU-Suchen (REST ist stabiler für exakte SKU-Matches)",
            "default": False,
            "type": "boolean",
        },
        "inv_target_location": {
            "name": "InvenTree Ziel-Lagerort (ID)",
            "description": "ID des (nicht-strukturellen) Lagerorts für Online-Bestand",
            "default": "",
            "type": "string",
        },
        "auto_schedule_minutes": {
            "name": "Auto-Sync Intervall (Minuten)",
            "description": "0 = aus (extern via Cron)",
            "default": 30,
            "type": "integer",
        },
        "delta_guard": {
            "name": "Delta-Limit pro Artikel",
            "description": "Max. absolute Anpassung pro Sync (0=aus)",
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
            "description": "Leerlassen = alle aktiven Parts. Unterkategorien werden automatisch mitgefiltert.",
            "default": "",
            "type": "string",
        },
    }
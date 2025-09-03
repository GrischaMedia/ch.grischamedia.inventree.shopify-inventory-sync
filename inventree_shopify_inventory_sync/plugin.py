from plugin import InvenTreePlugin
from plugin.mixins import SettingsMixin


class ShopifyInventorySyncPlugin(InvenTreePlugin, SettingsMixin):
    """
    Shopify → InvenTree Bestandsabgleich (SKU == IPN)
    """
    NAME = "ShopifyInventorySync"
    SLUG = "shopify-inventory-sync"  # <== WICHTIG: Mount-Pfad /plugin/shopify-inventory-sync/
    TITLE = "Shopify Inventory Sync"
    DESCRIPTION = "Liest Bestände aus Shopify (per SKU) und bucht Bestandskorrekturen in InvenTree (IPN-Match)."
    VERSION = "0.0.41"
    AUTHOR = "GrischaMedia / Grischabock (Sandro Geyer)"
    WEBSITE = ""

    SETTINGS = {
        "shop_domain": {
            "name": "Shopify Shop Domain",
            "description": "*.myshopify.com (ohne https://)",
            "default": "",
        },
        "admin_token": {
            "name": "Admin API Token",
            "description": "Shopify Admin API Access Token",
            "validator": "string",
            "default": "",
        },
        "use_graphql": {
            "name": "GraphQL verwenden (true/false)",
            "description": "Wenn true, GraphQL statt REST.",
            "validator": "bool",
            "default": False,
        },
        "target_location_id": {
            "name": "InvenTree Ziel-Lagerort (ID)",
            "description": "Nicht-struktureller Lagerort für Shop-Bestände (z.B. 143).",
            "validator": "int",
            "default": 0,
        },
        "only_location_name": {
            "name": "Nur Standort (Name)",
            "description": "Nur diese Shopify-Location zählen (leer = alle).",
            "default": "",
        },
        "auto_sync_minutes": {
            "name": "Auto-Sync Intervall Minuten",
            "description": "0 = aus.",
            "validator": "int",
            "default": 0,
        },
        "delta_guard": {
            "name": "Delta-Guard",
            "description": "Max. Differenz pro Artikel. 0 = aus.",
            "validator": "int",
            "default": 500,
        },
        "dry_run": {
            "name": "Dry-Run (true/false)",
            "description": "Wenn true, keine Buchungen.",
            "validator": "bool",
            "default": True,
        },
        "booking_note": {
            "name": "Buchungsnotiz",
            "description": "Text für Stock Adjustments.",
            "default": "Korrektur durch Onlineshop",
        },
        "only_categories": {
            "name": "Nur Kategorien (IDs, komma-getrennt)",
            "description": "Nur diese Teil-Kategorien (inkl. Unterkategorien).",
            "default": "",
        },
        "throttle_ms": {
            "name": "Throttle pro Artikel (ms)",
            "description": "Wartezeit zwischen Shopify-Requests (429 vermeiden).",
            "validator": "int",
            "default": 600,
        },
        "max_parts_per_run": {
            "name": "Max. Artikel pro Lauf",
            "description": "Begrenzt die Anzahl je Sync-Run.",
            "validator": "int",
            "default": 60,
        },
    }

    # === WICHTIG ===
    # Routen werden DIREKT hier registriert. KEINE urls.py im Paket!
    def setup_urls(self):
        from django.urls import path
        from . import views

        return [
            path("sync-now-open/", views.sync_now_open, name="shopify_sync_now"),
            path("report-missing/", views.report_missing, name="shopify_sync_missing"),
            path("debug-sku/", views.debug_sku, name="shopify_debug_sku"),
            path("sync-json/", views.sync_json, name="shopify_sync_json"),
            path("save-settings/", views.save_settings, name="shopify_sync_save"),
        ]

    # Kompatibilität für ältere InvenTree-Versionen
    def get_urls(self):
        return self.setup_urls()

    # Öffnen-Link im Plugin-Menü: auf bewährten JSON-Endpoint zeigen (kein /settings/, kein /panel/)
    def get_plugin_url(self):
        return f"/plugin/{self.SLUG}/sync-now-open/"
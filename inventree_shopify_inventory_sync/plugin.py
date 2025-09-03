from plugin import InvenTreePlugin
from plugin.mixins import SettingsMixin


class ShopifyInventorySyncPlugin(InvenTreePlugin, SettingsMixin):
    NAME = "ShopifyInventorySync"
    SLUG = "shopify-inventory-sync"
    TITLE = "Shopify Inventory Sync"
    DESCRIPTION = "Shopify → InvenTree Bestandsabgleich (SKU == IPN)."
    VERSION = "0.0.31"
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

    def setup_urls(self):
        from . import urls
        return urls.urlpatterns

    def get_urls(self):
        return self.setup_urls()

    def get_plugin_url(self):
        # Zeige im Plugin-Dialog direkt auf den Root-Pfad des Plugins
        return f"/plugin/{self.SLUG}/"
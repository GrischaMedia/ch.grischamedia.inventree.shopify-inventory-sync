from plugin import InvenTreePlugin
from plugin.mixins import SettingsMixin, AppMixin
from django.urls import reverse

class ShopifyInventorySyncPlugin(SettingsMixin, AppMixin, InvenTreePlugin):
    NAME = "ShopifyInventorySync"
    SLUG = "shopify-inventory-sync"  # bestimmt den URL-Namespace: plugin:<SLUG>-<route-name>
    TITLE = "Shopify → InvenTree Inventory Sync (SKU == IPN)"
    DESCRIPTION = "Liest Bestände aus Shopify (per SKU) und bucht Bestandskorrekturen in InvenTree (IPN-Match)."
    VERSION = "0.0.12"
    AUTHOR = "GrischaMedia / Grischabock (Sandro Geyer)"

    # zeigt Einträge im Plugin-Menü
    def get_menu_items(self, request):
        if not (request.user.is_authenticated and request.user.is_superuser or request.user.has_perm("stock.change_stockitem")):
            return []
        ns = f"plugin:{self.SLUG}"
        return [
            {"name": "Shopify Sync – Übersicht", "link": reverse(f"{ns}-index"), "icon": "fa-external-link-alt"},
            {"name": "Shopify Sync jetzt (open)", "link": reverse(f"{ns}-sync-now-open"), "icon": "fa-sync"},
            {"name": "Shopify Sync jetzt", "link": reverse(f"{ns}-sync-now"), "icon": "fa-sync"},
        ]

    # bindet unsere urls.py ein (wie beim alten Plugin)
    def get_urls(self):
        from .urls import urlpatterns
        return urlpatterns

    # **explizite Typen**, damit die Settings-Form sicher rendert
    SETTINGS = {
        "shop_domain": {"name": "Shopify Shop Domain", "description": "z. B. my-shop.myshopify.com", "default": "", "type": "string"},
        "admin_api_token": {"name": "Admin API Token", "description": "Shopify Admin API Access Token", "default": "", "protected": True, "type": "string"},
        "use_graphql": {"name": "GraphQL verwenden", "description": "Für performantere SKU-Suchen", "default": True, "type": "boolean"},
        "inv_target_location": {"name": "InvenTree Ziel-Lagerort (ID)", "description": "ID des Lagerorts 'Onlineshop'", "default": "", "type": "string"},
        "auto_schedule_minutes": {"name": "Auto-Sync Intervall (Minuten)", "description": "0 = aus (extern via Cron)", "default": 30, "type": "integer"},
        "delta_guard": {"name": "Delta-Limit pro Artikel", "description": "Max. absolute Anpassung pro Sync (0=aus)", "default": 0, "type": "integer"},
        "dry_run": {"name": "Dry-Run", "description": "Nur lesen, keine Buchungen", "default": True, "type": "boolean"},
        "note_text": {"name": "Buchungsnotiz", "description": "Notiz für Stock-Adjustments", "default": "Korrektur durch Onlineshop", "type": "string"},
        "filter_category_ids": {"name": "Nur Kategorien (IDs, komma-getrennt)", "description": "Leer = alle aktiven Parts", "default": "", "type": "string"},
    }
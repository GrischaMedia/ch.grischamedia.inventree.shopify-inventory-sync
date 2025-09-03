from django.urls import path
from . import views

urlpatterns = [
    # Root des Plugins -> sicher auf /settings/ weiterleiten
    path("", views.index_redirect, name="shopify_sync_root"),

    # Einstellungsseite (mit Styling & Live-Panel)
    path("settings/", views.settings_view, name="shopify_sync_settings"),

    # Aktionen / Tools
    path("sync-now-open/", views.sync_now_open, name="shopify_sync_now"),
    path("report-missing/", views.report_missing, name="shopify_sync_missing"),
    path("debug-sku/", views.debug_sku, name="shopify_debug_sku"),
    path("sync-json/", views.sync_json, name="shopify_sync_json"),
]
from django.urls import path
from . import views

urlpatterns = [
    # Root des Plugins -> unsere Inline-HTML-Config-Seite (kein Redirect, kein Template)
    path("", views.settings_view_inline, name="shopify_sync_index"),

    # Aktionen / Tools (wie gehabt)
    path("sync-now-open/", views.sync_now_open, name="shopify_sync_now"),
    path("report-missing/", views.report_missing, name="shopify_sync_missing"),
    path("debug-sku/", views.debug_sku, name="shopify_debug_sku"),
    path("sync-json/", views.sync_json, name="shopify_sync_json"),

    # Speichern der Settings via POST-Fetch (CSRF-exempt eigener Endpunkt, damit nichts blockiert)
    path("save-settings/", views.save_settings, name="shopify_sync_save"),
]
from django.urls import path
from . import views

urlpatterns = [
    # Kein Root-Mount – die Config/UI liegt bewusst unter /panel/
    path("panel/", views.settings_view_inline, name="shopify_sync_index"),

    # Aktionen / Tools (wie gehabt)
    path("sync-now-open/", views.sync_now_open, name="shopify_sync_now"),
    path("report-missing/", views.report_missing, name="shopify_sync_missing"),
    path("debug-sku/", views.debug_sku, name="shopify_debug_sku"),
    path("sync-json/", views.sync_json, name="shopify_sync_json"),

    # Speichern der Settings (JSON-POST, CSRF-exempt)
    path("save-settings/", views.save_settings, name="shopify_sync_save"),
]
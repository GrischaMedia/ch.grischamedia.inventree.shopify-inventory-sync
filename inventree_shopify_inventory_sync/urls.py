from django.urls import path
from . import views

urlpatterns = [
    # Root des Plugins -> direkt unsere Panel-View (kein Redirect!)
    path("", views.open_panel, name="shopify_sync_root"),

    # Eigener, konfliktfreier Pfad für das UI
    path("panel/", views.open_panel, name="shopify_sync_panel"),

    # Aktionen / Tools
    path("sync-now-open/", views.sync_now_open, name="shopify_sync_now"),
    path("report-missing/", views.report_missing, name="shopify_sync_missing"),
    path("debug-sku/", views.debug_sku, name="shopify_debug_sku"),
    path("sync-json/", views.sync_json, name="shopify_sync_json"),
]
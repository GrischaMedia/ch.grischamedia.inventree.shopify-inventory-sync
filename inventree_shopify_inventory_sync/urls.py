from django.urls import path
from . import views

urlpatterns = [
    # Root des Plugins -> direkt unsere Panel/Settings-View (KEIN Redirect)
    path("", views.settings_view, name="shopify_sync_index"),

    # Tools / Aktionen (diese liefen bei dir bereits stabil)
    path("sync-now-open/", views.sync_now_open, name="shopify_sync_now"),
    path("report-missing/", views.report_missing, name="shopify_sync_missing"),
    path("debug-sku/", views.debug_sku, name="shopify_debug_sku"),
    path("sync-json/", views.sync_json, name="shopify_sync_json"),
]
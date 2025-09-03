from django.urls import path
from . import views

# Die Namen hier werden zu plugin:<SLUG>-<name> -> also z. B. plugin:shopify-inventory-sync-index
urlpatterns = [
    path("", views.index, name="index"),
    path("sync-now/", views.sync_now, name="sync-now"),
    path("sync-now-open/", views.sync_now_open, name="sync-now-open"),
]
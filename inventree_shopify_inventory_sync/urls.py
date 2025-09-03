from django.urls import path
from . import views

# Namen werden zu: plugin:<SLUG>-<name>  → z. B. plugin:shopify-inventory-sync-index
urlpatterns = [
    path("", views.index, name="index"),
    path("ping/", views.ping, name="ping"),               # öffentlich (kein Login) zum schnellen Test
    path("sync-now/", views.sync_now, name="sync-now"),
    path("sync-now-open/", views.sync_now_open, name="sync-now-open"),
]
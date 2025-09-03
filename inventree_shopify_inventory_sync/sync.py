# inventree_shopify_inventory_sync/sync.py
from typing import Iterable

from django.db import transaction

from part.models import Part, PartCategory
from stock.models import StockItem, StockLocation

from .shopify_client import ShopifyClient


def _as_bool(val) -> bool:
    return str(val).strip().lower() in {"1", "true", "on", "yes"}


def _ensure_target_location(loc_id: str | int) -> StockLocation | None:
    if not loc_id:
        return None
    try:
        loc = StockLocation.objects.get(pk=int(loc_id))
    except Exception:
        return None

    if getattr(loc, "structural", False):
        child = StockLocation.objects.filter(parent=loc, structural=False).first()
        if child:
            return child
        return None

    return loc


def _get_or_create_mirror_item(part: Part, location: StockLocation) -> StockItem:
    item = (
        StockItem.objects
        .filter(part=part, location=location, is_building=False)
        .order_by("id")
        .first()
    )
    if item:
        return item
    return StockItem.objects.create(part=part, location=location, quantity=0)


def _iter_parts(plugin) -> Iterable[Part]:
    qs = Part.objects.filter(active=True)

    cat_ids_str = (plugin.get_setting("filter_category_ids") or "").strip()
    if cat_ids_str:
        base_ids = [int(x) for x in cat_ids_str.split(",") if x.strip().isdigit()]
        if base_ids:
            all_ids = set()
            for cid in base_ids:
                try:
                    c = PartCategory.objects.get(pk=cid)
                    for node in c.get_descendants(include_self=True):
                        all_ids.add(node.pk)
                except PartCategory.DoesNotExist:
                    continue
            if all_ids:
                qs = qs.filter(category_id__in=all_ids)

    return qs.iterator()


def run_full_sync(plugin, user):
    domain = plugin.get_setting("shop_domain")
    token = plugin.get_setting("admin_api_token")
    use_graphql = _as_bool(plugin.get_setting("use_graphql"))
    loc_id = plugin.get_setting("inv_target_location")
    dry_run = _as_bool(plugin.get_setting("dry_run"))
    delta_guard = int(plugin.get_setting("delta_guard") or 0)
    note = plugin.get_setting("note_text") or "Korrektur durch Onlineshop"
    only_loc_name = (plugin.get_setting("restrict_location_name") or "").strip() or None

    if not domain or not token or not loc_id:
        return {"ok": False, "error": "Einstellungen unvollständig (Domain/Token/Ziel-Lagerort)."}

    target_location = _ensure_target_location(loc_id)
    if not target_location:
        return {"ok": False, "error": "Ziel-Lagerort ungültig (strukturell oder nicht gefunden)."}

    client = ShopifyClient(domain, token, use_graphql=use_graphql)

    total_parts = 0
    matched = 0
    changed = 0
    skipped_guard = 0
    preview = []

    for part in _iter_parts(plugin):
        total_parts += 1
        ipn = (part.IPN or "").strip()
        if not ipn:
            continue

        variant = client.find_variant_by_sku(ipn)
        if not variant:
            preview.append({"part": part.pk, "ipn": ipn, "status": "shopify_variant_not_found"})
            continue

        matched += 1
        inv_item_id = variant.get("inventory_item_id") or variant.get("inventoryItemId")
        target = client.inventory_available_sum(inv_item_id, only_location_name=only_loc_name)
        if target is None:
            preview.append({"part": part.pk, "ipn": ipn, "status": "shopify_inventory_error"})
            continue

        mirror = _get_or_create_mirror_item(part, target_location)
        current = int(mirror.quantity or 0)
        delta = int(target) - current

        if delta_guard and abs(delta) > delta_guard:
            skipped_guard += 1
            preview.append({
                "part": part.pk, "ipn": ipn, "current": current, "target": int(target),
                "delta": delta, "status": "skipped_delta_guard"
            })
            continue

        if dry_run or delta == 0:
            preview.append({
                "part": part.pk, "ipn": ipn, "current": current, "target": int(target),
                "delta": delta, "status": "dry_run" if dry_run else "no_change"
            })
        else:
            with transaction.atomic():
                try:
                    mirror.adjustStock(delta, user=user, notes=note)  # type: ignore[attr-defined]
                except Exception:
                    mirror.quantity = int(target)
                    mirror.save()
            changed += 1
            preview.append({
                "part": part.pk, "ipn": ipn, "current": current, "target": int(target),
                "delta": delta, "status": "adjusted"
            })

    return {
        "ok": True,
        "dry_run": dry_run,
        "total_parts": total_parts,
        "sku_matched": matched,
        "changed": changed,
        "skipped_delta_guard": skipped_guard,
        "details_preview": preview[:100],
    }
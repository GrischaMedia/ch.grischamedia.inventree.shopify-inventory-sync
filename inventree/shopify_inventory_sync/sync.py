# inventree/shopify_inventory_sync/sync.py
from typing import Dict, Any, Iterable
from django.db import transaction
import os

from .shopify_client import ShopifyClient


def _get_models():
    from part.models import Part
    from stock.models import StockItem, StockLocation
    return Part, StockItem, StockLocation


def _iter_parts(plugin) -> Iterable:
    Part, _, _ = _get_models()
    qs = Part.objects.filter(active=True)
    cat_ids_str = (plugin.get_setting("filter_category_ids") or "").strip()
    if cat_ids_str:
        cat_ids = [int(x) for x in cat_ids_str.split(",") if x.strip().isdigit()]
        if cat_ids:
            qs = qs.filter(category_id__in=cat_ids)
    return qs.iterator()


def _ensure_target_location(loc_id: str):
    _, _, StockLocation = _get_models()
    try:
        if not loc_id:
            return None
        return StockLocation.objects.get(pk=int(loc_id))
    except Exception:
        return None


def _get_or_create_mirror_item(part, location):
    _, StockItem, _ = _get_models()
    item = StockItem.objects.filter(part=part, location=location, serial=None).first()
    if item:
        return item
    return StockItem.objects.create(part=part, location=location, quantity=0)


def _stocktake_with_note(item, user, new_qty: int, note: str) -> Dict[str, Any]:
    try:
        res = item.stocktake(user, new_qty, notes=note)  # type: ignore[attr-defined]
        return {"changed": True, "method": "stocktake", "result": str(res)}
    except Exception:
        try:
            old = int(item.quantity)
            delta = int(new_qty) - old
            if delta == 0:
                return {"changed": False, "method": "noop"}
            if delta > 0:
                item.add_stock(user, delta, notes=note)  # type: ignore[attr-defined]
                return {"changed": True, "method": "add_stock", "delta": delta}
            else:
                item.remove_stock(user, -delta, notes=note)  # type: ignore[attr-defined]
                return {"changed": True, "method": "remove_stock", "delta": delta}
        except Exception:
            old = int(item.quantity)
            if old == new_qty:
                return {"changed": False, "method": "fallback_noop"}
            item.quantity = new_qty
            item.save()
            return {"changed": True, "method": "hard_set"}


def run_full_sync(plugin, user) -> Dict[str, Any]:
    shop_domain = plugin.get_setting("shop_domain") or os.getenv("SHOPIFY_SHOP_DOMAIN", "")
    token = plugin.get_setting("admin_api_token") or os.getenv("SHOPIFY_ADMIN_API_TOKEN", "")
    use_graphql = bool(plugin.get_setting("use_graphql"))
    inv_loc_id = plugin.get_setting("inv_target_location") or os.getenv("INVENTREE_TARGET_LOCATION_ID", "")
    delta_guard = int(plugin.get_setting("delta_guard") or 0)
    dry_run = bool(plugin.get_setting("dry_run"))
    note_text = plugin.get_setting("note_text") or os.getenv("SYNC_NOTE_TEXT", "Korrektur durch Onlineshop")

    target_location = _ensure_target_location(inv_loc_id)
    if not (shop_domain and token and target_location):
        return {"ok": False, "error": "Einstellungen unvollständig (Domain/Token/Ziel-Lagerort)."}

    client = ShopifyClient(shop_domain, token, use_graphql)

    total = matched = changed = skipped = 0
    details = []

    for part in _iter_parts(plugin):
        total += 1
        sku = (part.IPN or "").strip() or None
        if not sku:
            details.append({"part": part.pk, "status": "no_ipn"})
            continue

        variant = client.find_variant_by_sku(sku)
        if not variant:
            details.append({"part": part.pk, "ipn": sku, "status": "shopify_variant_not_found"})
            continue

        matched += 1
        avail = client.inventory_available(variant["inventoryItemId"])
        if avail is None:
            details.append({"part": part.pk, "ipn": sku, "status": "no_inventory_data"})
            continue

        mirror = _get_or_create_mirror_item(part, target_location)
        current_qty = int(mirror.quantity)
        target_qty = int(avail)
        delta = target_qty - current_qty

        if delta_guard and abs(delta) > delta_guard:
            skipped += 1
            details.append({
                "part": part.pk, "ipn": sku,
                "current": current_qty, "target": target_qty,
                "status": "skipped_delta_guard", "delta": delta
            })
            continue

        if dry_run or delta == 0:
            details.append({
                "part": part.pk, "ipn": sku,
                "current": current_qty, "target": target_qty,
                "status": "dry_run" if dry_run else "no_change",
                "delta": delta
            })
            continue

        with transaction.atomic():
            res = _stocktake_with_note(mirror, user, target_qty, note_text)
            if res.get("changed"):
                changed += 1
            details.append({
                "part": part.pk, "ipn": sku,
                "current": current_qty, "target": target_qty,
                "delta": delta,
                "result": res
            })

    return {
        "ok": True,
        "dry_run": dry_run,
        "total_parts": total,
        "sku_matched": matched,
        "changed": changed,
        "skipped_delta_guard": skipped,
        "details_preview": details[:50],
    }
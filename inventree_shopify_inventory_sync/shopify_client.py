# inventree_shopify_inventory_sync/shopify_client.py
import requests


API_VERSION = "2024-10"


class ShopifyClient:
    def __init__(self, domain: str, token: str, use_graphql: bool = False):
        self.domain = domain.strip().lower().replace("https://", "").replace("http://", "").strip("/")
        self.token = token.strip()
        self.use_graphql = use_graphql
        self.session = requests.Session()
        self.session.headers.update({
            "X-Shopify-Access-Token": self.token,
            "Content-Type": "application/json",
        })

    def _rest_get(self, path: str, params=None) -> dict:
        url = f"https://{self.domain}{path}"
        r = self.session.get(url, params=params, timeout=20)
        r.raise_for_status()
        return r.json() or {}

    def find_variant_by_sku(self, sku: str) -> dict | None:
        """Exakte Suche nach Variante per SKU (REST)."""
        j = self._rest_get(f"/admin/api/{API_VERSION}/variants.json", params={"sku": sku})
        for v in j.get("variants", []) or []:
            if (v.get("sku") or "").strip() == sku.strip():
                return {
                    "id": v.get("id"),
                    "sku": v.get("sku"),
                    "inventory_item_id": v.get("inventory_item_id"),
                    "product_id": v.get("product_id"),
                    "title": v.get("title"),
                }
        return None

    def inventory_available_sum(self, inventory_item_id: int | str) -> int | None:
        """Summiert available über alle Locations."""
        try:
            locs = self._rest_get(f"/admin/api/{API_VERSION}/locations.json").get("locations", [])
        except Exception:
            return None

        total = 0
        found = False
        for loc in locs:
            lid = loc.get("id")
            j = self._rest_get(
                f"/admin/api/{API_VERSION}/inventory_levels.json",
                params={"inventory_item_ids": inventory_item_id, "location_ids": lid},
            )
            for lvl in (j.get("inventory_levels") or []):
                avail = lvl.get("available")
                if avail is not None:
                    total += int(avail)
                    found = True
        return total if found else None
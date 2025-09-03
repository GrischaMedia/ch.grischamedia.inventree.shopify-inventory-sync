# inventree_shopify_inventory_sync/shopify_client.py
import re
import requests

API_VERSION = "2024-10"


class ShopifyClient:
    def __init__(self, shop_domain: str, token: str, use_graphql: bool = False):
        dom = (shop_domain or "").strip()
        dom = re.sub(r"^\s*https?://", "", dom, flags=re.I).strip().strip("/")
        self.shop_domain = dom

        self.token = token
        self.use_graphql = bool(use_graphql)

        self.session = requests.Session()
        self.session.headers.update({
            "X-Shopify-Access-Token": self.token,
            "Content-Type": "application/json",
        })

    @property
    def base_rest(self) -> str:
        return f"https://{self.shop_domain}/admin/api/{API_VERSION}"

    @property
    def base_graphql(self) -> str:
        return f"https://{self.shop_domain}/admin/api/{API_VERSION}/graphql.json"

    # -------- REST helpers --------
    def _rest_get(self, path: str, params: dict | None = None) -> dict:
        url = f"https://{self.shop_domain}{path}" if path.startswith("/") else f"{self.base_rest}/{path}"
        r = self.session.get(url, params=params or {}, timeout=20)
        r.raise_for_status()
        return r.json()

    def _rest_post(self, path: str, payload: dict) -> dict:
        url = f"https://{self.shop_domain}{path}" if path.startswith("/") else f"{self.base_rest}/{path}"
        r = self.session.post(url, json=payload or {}, timeout=20)
        r.raise_for_status()
        return r.json()

    # -------- GraphQL helper --------
    def _graphql(self, query: str, variables: dict | None = None) -> dict:
        r = self.session.post(self.base_graphql, json={"query": query, "variables": variables or {}}, timeout=20)
        r.raise_for_status()
        return r.json()

    # -------- Public API --------
    def find_variant_by_sku(self, sku: str) -> dict | None:
        """
        Liefert {"id": <variantId>, "inventoryItemId": <invItemId>, "sku": "..."} oder None.
        Nutzt primär REST für exakte Übereinstimmung. (GraphQL kann fuzzy sein.)
        """
        try:
            j = self._rest_get(f"/admin/api/{API_VERSION}/variants.json", params={"sku": sku})
            for v in j.get("variants", []) or []:
                if (v.get("sku") or "").strip() == sku.strip():
                    return {
                        "id": v.get("id"),
                        "inventoryItemId": v.get("inventory_item_id"),
                        "sku": v.get("sku"),
                    }
        except requests.HTTPError as e:
            # REST-Fehler? versuchs optional über GraphQL
            if self.use_graphql:
                try:
                    q = """
                    query($sku:String!){
                      productVariants(first:10, query:$sku){
                        edges{
                          node{
                            id
                            sku
                            inventoryItem{ id }
                          }
                        }
                      }
                    }
                    """
                    data = self._graphql(q, {"sku": f"sku:{sku}"})
                    edges = (data.get("data", {}).get("productVariants", {}) or {}).get("edges", []) or []
                    for e in edges:
                        n = e.get("node") or {}
                        if (n.get("sku") or "").strip() == sku.strip():
                            return {"id": n.get("id"), "inventoryItemId": (n.get("inventoryItem") or {}).get("id"), "sku": n.get("sku")}
                except Exception:
                    pass
            else:
                raise e
        return None

    def inventory_available_sum(self, inventory_item_id) -> int | None:
        """
        Summe der verfügbaren Stückzahlen (über alle Locations).
        Nutzt REST (funktioniert mit numeric IDs).
        """
        # Locations holen
        try:
            locs = self._rest_get(f"/admin/api/{API_VERSION}/locations.json").get("locations", []) or []
        except Exception:
            return None

        total = 0
        for loc in locs:
            lid = loc.get("id")
            try:
                j = self._rest_get(
                    f"/admin/api/{API_VERSION}/inventory_levels.json",
                    params={"inventory_item_ids": inventory_item_id, "location_ids": lid},
                )
                for lvl in j.get("inventory_levels", []) or []:
                    avail = lvl.get("available")
                    if avail is not None:
                        total += int(avail)
            except Exception:
                continue
        return total
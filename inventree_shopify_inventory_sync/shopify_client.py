# ch.grischamedia.inventree.shopify-inventory-sync/shopify_client.py
import requests

class ShopifyClient:
    def __init__(self, shop_domain: str, token: str, use_graphql: bool = True):
        self.shop_domain = shop_domain.strip()
        self.token = token.strip()
        self.use_graphql = use_graphql

    def _headers(self):
        return {
            "X-Shopify-Access-Token": self.token,
            "Content-Type": "application/json",
        }

    def find_variant_by_sku(self, sku: str):
        """
        Liefert {variantId, sku, inventoryItemId} oder None.
        Erwartet eindeutige SKU (eine Variante).
        """
        if not sku:
            return None

        if self.use_graphql:
            q = """
            query ($query:String!) {
              productVariants(first: 1, query: $query) {
                edges {
                  node {
                    id
                    sku
                    inventoryItem { id }
                  }
                }
              }
            }
            """
            variables = {"query": f"sku:{sku}"}
            r = requests.post(
                f"https://{self.shop_domain}/admin/api/2024-10/graphql.json",
                headers=self._headers(),
                json={"query": q, "variables": variables},
                timeout=20,
            )
            r.raise_for_status()
            data = r.json()
            edges = data.get("data", {}).get("productVariants", {}).get("edges", [])
            if not edges:
                return None
            node = edges[0]["node"]
            return {
                "variantId": node["id"],
                "sku": node["sku"],
                "inventoryItemId": node["inventoryItem"]["id"],
            }
        else:
            # REST-Fallback
            r = requests.get(
                f"https://{self.shop_domain}/admin/api/2024-10/variants.json",
                headers=self._headers(),
                params={"sku": sku, "limit": 1},
                timeout=20,
            )
            r.raise_for_status()
            js = r.json()
            if not js.get("variants"):
                return None
            v = js["variants"][0]
            return {
                "variantId": f"gid://shopify/ProductVariant/{v['id']}",
                "sku": v["sku"],
                "inventoryItemId": f"gid://shopify/InventoryItem/{v['inventory_item_id']}",
            }

    def inventory_available(self, inventory_item_gid: str) -> int | None:
        """
        Summiert 'available' über alle Shopify-Standorte (du hast derzeit nur einen).
        """
        q = """
        query($inventoryItemId:ID!) {
          inventoryItem(id: $inventoryItemId) {
            inventoryLevels(first: 10) {
              edges {
                node {
                  available
                  location { id name }
                }
              }
            }
          }
        }
        """
        r = requests.post(
            f"https://{self.shop_domain}/admin/api/2024-10/graphql.json",
            headers=self._headers(),
            json={"query": q, "variables": {"inventoryItemId": inventory_item_gid}},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        edges = (data.get("data", {})
                    .get("inventoryItem", {})
                    .get("inventoryLevels", {})
                    .get("edges", []))
        total = 0
        for e in edges:
            n = e["node"]
            total += int(n.get("available") or 0)
        return total
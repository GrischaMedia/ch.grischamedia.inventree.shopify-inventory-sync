# inventree_shopify_inventory_sync/shopify_client.py
import time
import unicodedata
import requests

API_VERSION = "2024-10"

_API_BUCKET_HIGH_WATERMARK = 35
_API_GENTLE_SLEEP = 0.6
_API_MAX_BACKOFF = 5.0


def _norm(s: str) -> str:
    """Robuste Normalisierung für SKU-Vergleiche: trim, NFKC, casefold."""
    if s is None:
        return ""
    return unicodedata.normalize("NFKC", str(s)).strip().casefold()


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

        self._locations_cache = None

    # --------- Rate-limit aware request ----------
    def _request(self, method: str, url: str, *, params=None, json=None, timeout=20, max_retries=5) -> requests.Response:
        backoff = 1.0
        last_exc = None
        for _ in range(max_retries):
            try:
                r = self.session.request(method=method.upper(), url=url, params=params, json=json, timeout=timeout)

                bucket = r.headers.get("X-Shopify-Shop-Api-Call-Limit")
                if bucket:
                    try:
                        used, cap = [int(x) for x in bucket.split("/", 1)]
                        if used >= _API_BUCKET_HIGH_WATERMARK:
                            time.sleep(_API_GENTLE_SLEEP)
                    except Exception:
                        pass

                if 200 <= r.status_code < 300:
                    return r

                if r.status_code == 429:
                    ra = r.headers.get("Retry-After")
                    pause = float(ra) if (ra and ra.isdigit()) else backoff
                    time.sleep(min(pause, _API_MAX_BACKOFF))
                    backoff = min(_API_MAX_BACKOFF, backoff * 2)
                    last_exc = requests.HTTPError(f"429 Too Many Requests: {url}", response=r)
                    continue

                if 500 <= r.status_code < 600:
                    time.sleep(min(backoff, _API_MAX_BACKOFF))
                    backoff = min(_API_MAX_BACKOFF, backoff * 2)
                    last_exc = requests.HTTPError(f"{r.status_code} Server Error: {url}", response=r)
                    continue

                r.raise_for_status()
                return r

            except (requests.ConnectionError, requests.Timeout) as e:
                last_exc = e
                time.sleep(min(backoff, _API_MAX_BACKOFF))
                backoff = min(_API_MAX_BACKOFF, backoff * 2)

        if isinstance(last_exc, requests.HTTPError):
            raise last_exc
        raise requests.HTTPError(f"Shopify request failed after retries: {url}")

    def _rest_get(self, path: str, params=None) -> dict:
        url = f"https://{self.domain}{path}"
        r = self._request("GET", url, params=params)
        return r.json() or {}

    def _graphql(self, query: str, variables: dict | None = None) -> dict:
        url = f"https://{self.domain}/admin/api/{API_VERSION}/graphql.json"
        r = self._request("POST", url, json={"query": query, "variables": variables or {}}, timeout=25)
        return r.json() or {}

    # --------- Public: Variant by SKU ----------
    def find_variant_by_sku(self, sku: str) -> dict | None:
        """
        Findet eine Variante anhand der SKU.
        1) REST /variants.json?sku=…
        2) Normalisierte, case-insensitive Prüfung
        3) Optionaler GraphQL-Fallback (query: sku:<SKU>)
        """
        target = _norm(sku)

        # REST
        j = self._rest_get(f"/admin/api/{API_VERSION}/variants.json", params={"sku": sku})
        variants = j.get("variants", []) or []
        for v in variants:
            if _norm(v.get("sku")) == target:
                return {
                    "id": v.get("id"),
                    "sku": v.get("sku"),
                    "inventory_item_id": v.get("inventory_item_id"),
                    "product_id": v.get("product_id"),
                    "title": v.get("title"),
                }

        # GraphQL Fallback (optional)
        if self.use_graphql:
            q = """
            query($q:String!){
              productVariants(first:25, query:$q){
                edges{
                  node{
                    id
                    sku
                    title
                    product { id }
                    inventoryItem { id }
                  }
                }
              }
            }
            """
            data = self._graphql(q, {"q": f"sku:{sku}"})
            edges = (((data.get("data") or {}).get("productVariants") or {}).get("edges") or [])
            for e in edges:
                n = e.get("node") or {}
                if _norm(n.get("sku")) == target:
                    # GraphQL-IDs sind GIDs -> inventoryItem.id ist z. B. "gid://shopify/InventoryItem/123"
                    inv_gid = (n.get("inventoryItem") or {}).get("id")
                    inv_id = inv_gid.rsplit("/", 1)[-1] if inv_gid else None
                    return {
                        "id": n.get("id"),
                        "sku": n.get("sku"),
                        "inventory_item_id": inv_id,
                        "product_id": (n.get("product") or {}).get("id"),
                        "title": n.get("title"),
                    }

        return None

    # --------- Locations / Inventory ----------
    def _get_all_locations(self) -> list[dict]:
        if self._locations_cache is not None:
            return self._locations_cache
        j = self._rest_get(f"/admin/api/{API_VERSION}/locations.json")
        locs = j.get("locations", []) or []
        self._locations_cache = locs
        return locs

    def inventory_available_sum(self, inventory_item_id: int | str, only_location_name: str | None = None) -> int | None:
        locs = self._get_all_locations()
        if not locs:
            return None

        if only_location_name:
            locs = [l for l in locs if _norm(l.get("name")) == _norm(only_location_name)]
            if not locs:
                return 0

        loc_ids = ",".join(str(l.get("id")) for l in locs if l.get("id"))
        if not loc_ids:
            return None

        j = self._rest_get(
            f"/admin/api/{API_VERSION}/inventory_levels.json",
            params={"inventory_item_ids": inventory_item_id, "location_ids": loc_ids},
        )
        levels = j.get("inventory_levels", []) or []
        if not levels:
            return 0

        total = 0
        for lvl in levels:
            a = lvl.get("available")
            if a is not None:
                total += int(a)
        return total
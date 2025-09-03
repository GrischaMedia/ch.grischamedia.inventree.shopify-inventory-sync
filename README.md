# Shopify → InvenTree Inventory Sync (SKU == IPN)

**Paket:** `ch.grischamedia.inventree.shopify-inventory-sync`  
**Version:** 0.0.17  
**Autor:** GrischaMedia / Grischabock (Sandro Geyer)

Synct Bestände **einseitig** von **Shopify** nach **InvenTree**:
- **Match:** Shopify **SKU** ↔ InvenTree **IPN**
- Bucht **Bestandskorrekturen** am Ziel-Lagerort (z. B. „Onlineshop“)
- Notiz je Buchung: **„Korrektur durch Onlineshop“**
- **Auto** (z. B. Cron) **und** **manuell** (URL/Button)

## Installation
1. Ordner in `<inventree_root>/plugins/ch.grischamedia.inventree.shopify-inventory-sync/` kopieren.
2. InvenTree neu starten.
3. Admin → Plugins → *Shopify → InvenTree Inventory Sync* → **aktivieren**.

## Einstellungen
- **Shopify Shop Domain**: `deinshop.myshopify.com`
- **Admin API Token**: aus Shopify *Custom App*
- **InvenTree Ziel-Lagerort (ID)**: ID von `Onlineshop`
- **GraphQL verwenden**: ✓
- **Auto-Sync Intervall (Minuten)**: 0 = aus (extern triggern)
- **Delta-Limit pro Artikel**: z. B. 500 (0 = aus)
- **Dry-Run**: zuerst **True** (Test)
- **Buchungsnotiz**: `Korrektur durch Onlineshop`
- **Nur Kategorien (IDs)**: optional, kommasepariert (z. B. nur „Shop“)

## Manuell auslösen
Aufrufen (eingeloggt, Recht `stock.change_stockitem`):
from odoo import api, models


class ProductLocationValue(models.AbstractModel):
    _name = "product.location.value"
    _description = "Production Location Value"

    @api.model
    def get_products(self, product_ids=None):
        """Return products with stock moves summary based on selected products"""
        domain = []
        if product_ids:
            domain.append(('id', 'in', product_ids))

        products = self.env['product.product'].sudo().search(domain)
        move_lines = self.env['stock.move.line'].sudo().search([])

        result = []
        for prod in products:
            summary = {
                "id": prod.id,
                "name": prod.display_name,
                "default_code": prod.default_code or "",
                "qty_available": prod.qty_available,
                "mo": 0,
                "so": 0,
                "po": 0,
                "internal": 0,
                "scrap": 0,
                "recs": [],
            }

            for move in move_lines.filtered(lambda m: m.product_id.id == prod.id):
                loc = move.location_id.usage if move.location_id else ''
                dest_loc = move.location_dest_id.usage if move.location_dest_id else ''

                if loc == "internal" and dest_loc == "production":
                    summary["mo"] += move.quantity
                elif loc == "internal" and dest_loc == "customer":
                    summary["so"] += move.quantity
                elif loc == "supplier" and dest_loc == "internal":
                    summary["po"] += move.quantity
                elif loc == "internal" and dest_loc == "internal":
                    summary["internal"] += move.quantity
                elif loc == "internal" and dest_loc == "inventory":
                    summary["scrap"] += move.quantity

                summary["recs"].append({
                    "id": move.id,
                    "reference": move.reference,
                    "picking_type": move.picking_type_id.display_name,
                    "location_from": move.location_id.display_name if move.location_id else '',
                    "location_to": move.location_dest_id.display_name if move.location_dest_id else '',
                    "quantity": move.quantity,
                    "state": move.state,
                    "date": move.date.strftime("%Y-%m-%d"),
                })

            result.append(summary)

        return result

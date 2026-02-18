try:
    from odoo import models, fields, api
except ImportError:
    pass

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    outward_value = fields.Float(string='Total Outward Value', compute='_compute_outward_value')

    def _compute_outward_value(self):
        for picking in self:
            value = 0.0
            for move in picking.move_ids_without_package:
                if move.state == 'done':
                    value += move.product_uom_qty * move.product_id.standard_price
            picking.outward_value = value

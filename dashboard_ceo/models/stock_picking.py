try:
    from odoo import models, fields, api
except ImportError:
    pass

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    outward_value = fields.Monetary(string='Amount', compute='_compute_outward_value', store=True, currency_field='currency_id')

    @api.depends('move_ids.state', 'move_ids.product_uom_qty', 'move_ids.product_id.standard_price')
    def _compute_outward_value(self):
        for picking in self:
            value = 0.0
            for move in picking.move_ids:
                if move.state == 'done':
                    value += move.product_uom_qty * move.product_id.standard_price
            picking.outward_value = value

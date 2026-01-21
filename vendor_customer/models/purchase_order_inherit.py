from odoo import models, fields, api, _

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.onchange('partner_id')
    def _onchange_partner_id(self):

        if self.partner_id and self.partner_id.product_id:
            lines = []
            for product in self.partner_id.product_id:
                lines.append((0, 0, {
                    'product_id': product.id,
                    'product_qty': 1.0,
                }))
            self.order_line = [(5, 0, 0)] + lines
        elif not self.partner_id:
            self.order_line = [(5, 0, 0)]

from odoo import models, fields, api, _


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    purchase_or_spare = fields.Selection([
        ('purchase', 'Purchase'),
        ('spare', 'Spares')
    ], string="Orders")

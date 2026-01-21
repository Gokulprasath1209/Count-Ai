from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    purchase_or_spare = fields.Selection([
        ('purchase', 'Purchase'),
        ('spare', 'Spares')
    ], string="Orders")

    # Removed redundant get_product_lines methods as they are handled in vendor_customer

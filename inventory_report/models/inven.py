from odoo import models, fields, api, _

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    shipment_type = fields.Selection([
        ('inward stock', 'incoming stock'),
        ('internal tranfer', 'internal tranfer'),
    ], string="Product shipment")
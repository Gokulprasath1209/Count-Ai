from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    sale_or_spare = fields.Selection([('sale', 'Sales'),
                                     ('spare', 'Spares')], string="Orders")
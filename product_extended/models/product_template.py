from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    default_code = fields.Char(
        string="ERP Code",
        index=True
    )

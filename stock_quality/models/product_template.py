from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    quality_check = fields.Boolean(
        string="Quality Check", 
        help="Indicates whether the product requires quality checking."
    )
    warranty = fields.Boolean(string="Warranty")

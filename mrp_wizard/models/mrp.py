from odoo import models, fields, api, _

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    production_type = fields.Selection([
        ('normal', 'Regular Production'),
        ('spare', 'Spare Production'),
    ], string="Production Type", default='normal')

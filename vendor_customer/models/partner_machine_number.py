from odoo import models, fields, api


class PartnerMachineNumber(models.Model):
    _name = 'partner.machine.number'
    _description = 'Machine Number'
    _order = 'name'

    name = fields.Char(string="Machine Number", required=True, help="Unique machine number identifier")
    active = fields.Boolean(default=True, help="Set to false to hide without deleting")
    partner_ids = fields.Many2many('res.partner', string='Customers', help="Customers associated with this machine number")
    
    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Machine Number must be unique!')
    ]
    
    def name_get(self):
        """Display machine number in selection fields"""
        result = []
        for record in self:
            result.append((record.id, record.name))
        return result

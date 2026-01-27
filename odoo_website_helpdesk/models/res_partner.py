from odoo import fields, models

class ResPartner(models.Model):
    _inherit = 'res.partner'

    ticket_type_id = fields.Many2one('helpdesk.type', string='Machine name', help='Ticket Type')
    on_time_rate = fields.Float(string='On Time Rate', help='On-time delivery or service rate percentage')

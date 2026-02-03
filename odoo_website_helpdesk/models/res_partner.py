from odoo import fields, models

class ResPartner(models.Model):
    _inherit = 'res.partner'

    ticket_type_id = fields.Many2one('helpdesk.type', string='Machine name', help='Ticket Type')
    machine_number = fields.Char(string='Machine Number', help='Machine Number')
    on_time_rate = fields.Float(string='On Time Rate', help='On-time delivery or service rate percentage')

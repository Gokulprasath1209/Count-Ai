from odoo import fields, models


class ProjectTask(models.Model):
    """Inheriting the project task"""
    _inherit = 'project.task'

    ticket_id = fields.Many2one('ticket.helpdesk', string='Ticket',
                                help='ID of the ticket .')
    ticket_billed = fields.Boolean('Billed', default=False,
                                   help='Billed Tickets')

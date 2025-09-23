from odoo import models, fields, api

class ResPartnerInherit(models.Model):
    _inherit = 'res.partner'

    vendor_rating = fields.Selection(
        [
            ('good', 'Good'),
            ('bad', 'Blocked')
        ],
        string='Vendor Rating'
    )
    accept_reject_status = fields.Selection(
        [
            ('accepted', 'Accepted'),
            ('rejected', 'Rejected'),
        ],
        string='Accept/Reject Status',
    )
    date = fields.Datetime('Date')
    partner_seq = fields.Char("Seq")
    department_of_vendor = fields.Many2one('hr.department','Department')
    res_users = fields.Many2one('res.users','Enquiry Person')
    nature_of_business = fields.Many2one('res.partner.industry','Nature Of Business')

    def action_accept(self):
        self.write({'accept_reject_status':'accepted'})

    def action_reject(self):
        self.write({'accept_reject_status': 'rejected'})



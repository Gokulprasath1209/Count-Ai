from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ResPartnerInherit(models.Model):
    _inherit = 'res.partner'

    product_id = fields.Many2many('product.product', 'Products', tracking=True, )

    # def action_accept(self):
    #     self.write({'accept_reject_status':'accepted'})
    #
    # def action_reject(self):
    #     self.write({'accept_reject_status': 'rejected'})



from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError



class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    purchase_or_spare = fields.Selection([
        ('purchase', 'Purchase'),
        ('spare', 'Spares')
    ], string="Orders")

    def action_rfq_send(self):
        if self.partner_id == self.env.ref('material_request.test_vendor'):
            raise UserError(
                _(F"Hello {self.env.user.name} Kindly Please check Vendor Name [{self.partner_id.name}] Using for Developer Purpose Select Correct Vendor"))
        else:
            res = super(PurchaseOrder, self).action_rfq_send()
        return res

    def button_confirm(self):
        if self.partner_id == self.env.ref('material_request.test_vendor'):
            raise UserError(
                _(F"Hello {self.env.user.name} Kindly Please check Vendor Name [{self.partner_id.name}] Using for Developer Purpose Select Correct Vendor"))
        else:
            res = super(PurchaseOrder, self).button_confirm()
        return res
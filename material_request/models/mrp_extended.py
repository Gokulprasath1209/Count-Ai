from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class SaleOrder(models.Model):
    _inherit = 'mrp.production'

    request_for_material = fields.Selection([('approve', 'Approve'),('hold','Hold'),
                                     ('reject', 'Reject')], string="Material Request")

    def action_request(self):
        products = []
        for i in self.move_raw_ids:
            val = (0,0,{'product_id':i.product_id.product_tmpl_id.id,'demand_qty':i.product_uom_qty})
            products.append(val)
        data = {'main_mrp_id':self.id,'user_id':self.env.user.id,'request_line_ids':products}
        self.env['material.request'].create(data)


    # def button_mark_done(self):
    #     if self.request_for_material == 'approve':
    #         return super().button_mark_done()
    #     else:
    #         raise UserError(
    #                 _(F"Hello {self.env.user.name} Kindly Please First Get a Material Request Status "))

    def action_start(self):
        if self.request_for_material == 'approve':
            return super().action_start()
        else:
            raise UserError(
                    _(F"Hello {self.env.user.name} Kindly Please First Get a Material Request Status "))

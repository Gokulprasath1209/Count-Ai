from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from reportlab.lib.pdfencrypt import computeO


class SaleOrder(models.Model):
    _inherit = 'mrp.production'

    request_for_material = fields.Selection(
        [('waiting_for_purchase', 'Waiting for Purchase'), ('onhand_approve', 'OnHand Approve'),
         ('full_approve', 'Full Approve')], string="Material Request")
    material_request_count =fields.Integer('Material Request Count',compute='get_material_request_count')
    material_request = fields.Selection(
        [('send', 'Send'), ('not_send', 'Not Send')],default='not_send', string="Material Request")

    def get_material_request_count(self):
        self.material_request_count = self.env['material.request'].search_count([('main_mrp_id', '=', self.id)])

    def action_open_material_request(self):
        self.ensure_one()
        material_request = self.env['material.request'].search([('main_mrp_id', '=', self.id)])
        return {
            'name': _('Quality Tests'),
            'type': 'ir.actions.act_window',
            'res_model': 'material.request',
            'view_mode': 'list,form',
            'domain': [('id', 'in', material_request.ids)],
            'context': {'create': False, 'edit': False}
            }

    def action_request(self):
        products = []
        for i in self.move_raw_ids:
            val = (0, 0, {'product_id': i.product_id.product_tmpl_id.id, 'demand_qty': i.product_uom_qty})
            products.append(val)
        data = {'main_mrp_id': self.id, 'user_id': self.env.user.id, 'request_line_ids': products}
        self.env['material.request'].create(data)
        self.write({'material_request':'send'})


    def action_start(self):
        if self.request_for_material in ['onhand_approve', 'full_approve']:
            pass
            return super().action_start()
        else:
            raise UserError(
                _(F"Hello {self.env.user.name} Kindly Please First Get a Material Request Status "))

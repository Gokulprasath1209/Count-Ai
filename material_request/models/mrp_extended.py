from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from reportlab.lib.pdfencrypt import computeO


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    product_type = fields.Selection(
        [('RnD', 'R&D'), ('moving', 'Moving'), ('non_moving', 'Non Moving')], default='RnD', string="Type")


class SaleOrder(models.Model):
    _inherit = 'mrp.production'
    _order = 'priority desc, date_start asc,id'

    def action_quality_request(self):
        lines = [
            (0, 0, {'product_id': self.product_id.id, 'product_qty': self.product_qty,
                    'product_uom': self.product_uom_id.id})]

        data = {'ref': self.name, 'type': 'fg', 'date_order': fields.datetime.now(), 'date_planned': self.date_finished,
                'test_line_ids': lines
                }
        self.env['quality.test'].create(data)

    request_for_material = fields.Selection(
        [('waiting_for_purchase', 'Waiting for Purchase'), ('onhand_approve', 'OnHand Approve'),
         ('full_approve', 'Full Approve')], string="Material Request")
    material_request_count = fields.Integer('Material Request Count', compute='get_material_request_count')
    material_request = fields.Selection(
        [('send', 'Send'), ('not_send', 'Not Send')], default='not_send', string="Material Requests")
    material_request_ids = fields.Many2many('material.request',string='Material Request Ids')
    mrp_unique_ref = fields.Char(string="Code")

    quality_test_count = fields.Integer('Quality Test Count', compute='get_quality_test_count')

    def get_quality_test_count(self):
        self.quality_test_count = self.env['quality.test'].search_count([('ref', '=', self.name)])

    def action_open_quality_request(self):
        self.ensure_one()
        quality = self.env['quality.test'].search([('ref', '=', self.name)])
        return {
            'name': _('Quality Request'),
            'type': 'ir.actions.act_window',
            'res_model': 'quality.test',
            'view_mode': 'list,form',
            'domain': [('id', 'in', quality.ids)],
            'context': {'create': False, 'edit': False}
        }

    def action_again_request(self):
        ctx = {'default_main_mrp_id': self.id}
        return {
            'type': 'ir.actions.act_window',
            'name': 'Material Request',
            'res_model': 'again.material.request',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': self.env['again.material.request'].id,
            'view_id': self.env.ref('material_request.view_again_material_request', False).id,
            'target': 'new',
            'context': ctx

        }

    def get_material_request_count(self):
        self.material_request_count = self.env['material.request'].search_count([('main_mrp_id', '=', self.id)])

    def action_open_material_request(self):
        self.ensure_one()
        material_request = self.env['material.request'].search([('main_mrp_id', '=', self.id)])
        return {
            'name': _('Material Request'),
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
        material_request = self.env['material.request'].create(data)
        self.material_request_ids = [(4, material_request.id)]
        self.write({'material_request': 'send'})

    def action_start(self):
        if self.request_for_material in ['onhand_approve', 'full_approve'] and self.material_request_ids[
            -1].product_accept_bool:
            return super().action_start()
        else:
            raise UserError(
                _(F"Hello {self.env.user.name} Kindly Please check Material Request Status or Please Acknowledged Receive Your Department"))

    def button_mark_done(self):
        quality = self.env['quality.test'].search([('ref', '=', self.name)])
        if quality.state == 'accept':
            return super().button_mark_done()
        else:
            raise UserError(
                _(F"Hello {self.env.user.name} Kindly Please check Quality Status ITs Done Then This FG move to Store"))
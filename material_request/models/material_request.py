from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class MaterialRequest(models.Model):
    _name = 'material.request'
    _description = 'Material Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name')
    main_mrp_id = fields.Many2one('mrp.production', string='Production')
    user_id = fields.Many2one('res.users', string='Request user')
    date = fields.Datetime(string='Date', default=fields.Datetime.now())
    procurement_ids = fields.Many2many('mrp.production', string='Production Child')
    state = fields.Selection([('waiting_for_purchase', 'Waiting for Purchase'), ('onhand_approve', 'OnHand Approve'),
                              ('full_approve', 'Full Approve')], string="Material Request")
    request_line_ids = fields.One2many('material.request.product.line', 'request_id')
    purchase_request_count = fields.Integer(string='Purchase Request',compute="get_purchase_request_count")

    def get_purchase_request_count(self):
        self.purchase_request_count = self.env['purchase.requisition'].search_count([('reference','=',self.name)])

    def action_open_purchase_request(self):
        self.ensure_one()
        purchase_requisition = self.env['purchase.requisition'].search([('reference','=',self.name)])
        return {
            'name': _('Purchase Request'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.requisition',
            'view_mode': 'list,kanban,form',
            'domain': [('id', 'in', purchase_requisition.ids)],
            'context': {'create': False,'edit':False}
        }

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('material.request.sequence')
        return super(MaterialRequest, self).create(vals)

    def action_approve(self):
        self.main_mrp_id.request_for_material = 'full_approve'
        self.write({'state': 'full_approve'})

    def action_purchase_request(self):
        view_id = self.env['purchase.request.wizard']
        products =[]
        for i in self.request_line_ids:
            val = (0, 0, {'product_id': i.product_id.product_variant_id.id, 'purchase_qty': i.demand_qty})
            products.append(val)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Request',
            'res_model': 'purchase.request.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': view_id.id,
            'view_id': self.env.ref('material_request.view_purchase_request', False).id,
            'target':'new',
            'context':{'default_material_request_id':self.id,'default_products_lines':products}
        }


class MaterialRequestProductLines(models.Model):
    _name = 'material.request.product.line'
    _description = 'Material Request Product Lines'

    product_id = fields.Many2one('product.template', string='Raw Material')
    demand_qty = fields.Float(string=' Demand Qty')
    approve_qty = fields.Float(string='Approve OnHand Qty')
    request_id = fields.Many2one('material.request')
    product_forecast_qty = fields.Float(string='Forecast Qty', related='product_id.virtual_available')

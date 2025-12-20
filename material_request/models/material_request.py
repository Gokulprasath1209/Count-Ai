from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class MaterialRequest(models.Model):
    _name = 'material.request'
    _description = 'Material Request'
    _order = 'id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name')
    main_mrp_id = fields.Many2one('mrp.production', string='Source')
    user_id = fields.Many2one('res.users', string='Request user')
    date = fields.Datetime(string='Date', default=fields.Datetime.now())
    procurement_ids = fields.Many2many('mrp.production', string='Production Child')
    state = fields.Selection(
        [('draft', 'Draft'), ('waiting_for_purchase', 'Waiting for Purchase'), ('onhand_approve', 'OnHand Approve'),
         ('full_approve', 'Full Approve')], string="Material Request", default='draft')
    request_line_ids = fields.One2many('material.request.product.line', 'request_id')
    purchase_request_count = fields.Integer(string='Purchase Request', compute="get_purchase_request_count")
    backorder_name = fields.Char(string='Backorder Ref')
    order_type = fields.Selection([('default_order', 'Default Order'), ('backorder', 'Back Order')],
                                  default='default_order', string="Material Requests")
    backorder_count = fields.Integer(string='Back Order count', compute="get_back_orders")
    product_accept_bool = fields.Boolean('Product Accept Bool')
    note = fields.Char(string='Note')
    ref = fields.Char(string='Ref')

    def action_receive_product(self):
        if self.state in ['waiting_for_purchase'] or self.state not in ['waiting_for_purchase', 'onhand_approve',
                                                                        'full_approve']:
            raise UserError(
                _(F"Hello {self.env.user.name} Kindly Please First Get a Material Request Approve "))
        self.write({'product_accept_bool': True})

    def get_back_orders(self):
        self.backorder_count = self.env['material.request'].search_count([('backorder_name', '=', self.name)])

    def action_material_request_backorder(self):
        self.ensure_one()
        purchase_requisition = self.env['purchase.requisition'].search([('reference', '=', self.name)])
        return {
            'name': _('Material Request Back orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'material.request',
            'view_mode': 'list,kanban,form',
            'domain': [('backorder_name', '=', self.name)],
        }

    def get_purchase_request_count(self):
        self.purchase_request_count = self.env['purchase.requisition'].search_count([('reference', '=', self.name)])

    def action_open_purchase_request(self):

        self.ensure_one()
        purchase_requisition = self.env['purchase.requisition'].search([('reference', '=', self.name)])
        return {
            'name': _('Purchase Request'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.requisition',
            'view_mode': 'list,kanban,form',
            'domain': [('id', 'in', purchase_requisition.ids)],
            'context': {'create': False, 'edit': False}
        }

    @api.model_create_multi
    def create(self, values):
        for vals in values:
            vals['name'] = self.env['ir.sequence'].next_by_code('material.request.sequence')
        return super(MaterialRequest, self).create(values)

    def action_approve(self):
        backorders_lines = []

        for i in self.request_line_ids:
            if i.demand_qty != i.approve_qty:
                backorders_lines.append(
                    (0, 0, {
                        'product_id': i.product_id.id,
                        'demand_qty': i.demand_qty - i.approve_qty
                    })
                )

        if not backorders_lines:
            self.main_mrp_id.write({'request_for_material': 'full_approve'})
            self.write({'state': 'full_approve'})
            return

        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Back Order',
            'res_model': 'material.request.backorder.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': self.env['material.request.backorder.wizard'].id,
            'view_id': self.env.ref('material_request.view_material_request_backorder', False).id,
            'target': 'new',
            'context': {
                'default_material_request_id': self.id,
                'default_products_lines': backorders_lines
            }
        }

    def action_purchase_request(self):
        view_id = self.env['purchase.request.wizard']
        products = []
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
            'target': 'new',
            'context': {'default_material_request_id': self.id, 'default_products_lines': products}
        }


class MaterialRequestProductLine(models.Model):
    _name = 'material.request.product.line'
    _description = 'Material Request Product Line'

    request_id = fields.Many2one('material.request')

    product_id = fields.Many2one(
        'product.product',
        string='Raw Material',
        required=True,
        ondelete='restrict'
    )

    demand_qty = fields.Float(
        string='Demand Qty',
        default=0.0
    )

    approve_qty = fields.Float(
        string='Approve OnHand Qty',
        default=0.0
    )

    total_stock = fields.Float(
        string="Total Stock",
        compute="_compute_total_stock",
        store=False
    )

    @api.depends('product_id')
    def _compute_total_stock(self):
        for line in self:
            line.total_stock = line.product_id.qty_available if line.product_id else 0.0

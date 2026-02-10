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
    date = fields.Date(string='Date', default=fields.Date.context_today)
    display_date = fields.Char(string='Date', compute='_compute_display_date')

    @api.depends('date')
    def _compute_display_date(self):
        for rec in self:
            rec.display_date = rec.date.strftime('%d-%m-%Y') if rec.date else ''
    procurement_ids = fields.Many2many('mrp.production', string='Production Child')
    state = fields.Selection([
        ('draft', 'Waiting For Approval'),
        ('waiting_for_purchase', 'Waiting for Purchase'),
        ('onhand_approve', 'OnHand Approve'),
        ('full_approve', 'Full Approve'),
        ('received', 'Received by Employee'),
        ('cancel', 'Cancel By a employee'),
    ], string="Material Request", default='draft', tracking=True)
    request_line_ids = fields.One2many('material.request.product.line', 'request_id')
    purchase_request_count = fields.Integer(string='Purchase Request', compute="get_purchase_request_count")
    backorder_name = fields.Char(string='Backorder Ref')
    order_type = fields.Selection([('default_order', 'Default Order'), ('backorder', 'Back Order')],
                                  default='default_order', string="Material Requests")
    backorder_count = fields.Integer(string='Back Order count', compute="get_back_orders")
    product_accept_bool = fields.Boolean('Product Accept Bool')
    user_product_accept_bool = fields.Boolean('Product Accept Bool')
    note = fields.Char(string='Note')
    ref = fields.Char(string='Ref')
    request_type = fields.Selection([('user', 'User'), ('mrp', 'MRP')], string='Request Type')

    approve_type = fields.Selection([('draft', 'Draft'), ('ceo', 'CEO'), ('ceo_reject', 'CEO Reject')], default='draft')

    dest_loc_id = fields.Many2one('stock.location', string='Destination')


    stock_picking_count = fields.Integer(string='Stock Picking Count', compute="get_stock_picking_count")
    same_user_bool = fields.Boolean(string='Same User',compute='get_same_user_bool')

    def get_same_user_bool(self):
        self.same_user_bool = True if self.user_id.id == self.env.user.id else False

    def get_stock_picking_count(self):
        self.stock_picking_count = self.env['stock.picking'].search_count([('origin', '=', self.name)])

    def action_open_stock_picking(self):
        self.ensure_one()
        return {
            'name': _('Stock Picking'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'list,kanban,form',
            'domain': [('origin', '=', self.name)],
        }

    def action_ceo_approve(self):
        self.write({'approve_type': 'ceo'})

    def action_ceo_reject(self):
        self.write({'approve_type': 'ceo_reject'})

    def action_user_receive_product(self):
        if self.state in ['full_approve', 'onhand_approve']:
            self.user_product_accept_bool = True
        else:
            raise UserError(
                _(F"Hello {self.env.user.name} Kindly Please First Get a Material Request Approve "))

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
        if self.request_type == 'mrp':
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
        if self.request_type == 'user':
            if self.approve_type == 'ceo':
                lines = []
                for i in self.request_line_ids:
                    data = {
                        'name': i.product_id.name,
                        'product_id': i.product_id.id,
                        'product_uom_qty': i.demand_qty,
                        'quantity': i.approve_qty,
                    }
                    lines.append((0, 0, data))
                stock_move = {'partner_id': self.user_id.partner_id.id,
                              'picking_type_id': self.env.ref('stock.picking_type_internal').id,
                              'location_id': self.env.ref('stock.stock_location_stock').id,
                              'location_dest_id': self.dest_loc_id.id,
                              'scheduled_date': fields.datetime.now(), 'origin': self.name, 'move_ids': lines
                              }
                self.env['stock.picking'].create(stock_move)

                self.write({'state': 'full_approve'})

                if self.ref:
                    user_request = self.env['user.material.request'].search([('name', '=', self.ref)], limit=1)
                    if user_request:
                         user_request.action_receive()
            else:
                raise UserError(
                    _(F"Hello {self.env.user.name} Kindly Get A CEO Approve"))

    def action_purchase_request(self):
        view_id = self.env['purchase.request.wizard']
        products = []
        for i in self.request_line_ids:
            val = (0, 0, {'product_id': i.product_id.product_variant_id.id, 'purchase_qty': i.demand_qty})
            products.append(val)
        if self.request_type == 'user':
            if self.approve_type == 'ceo':
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
            else:
                raise UserError(
                    _(F"Hello {self.env.user.name} Kindly Get A CEO Approve"))
        if self.request_type == 'mrp':
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
    product_id = fields.Many2one('product.product',string='Raw Material',required=True,ondelete='restrict')
    demand_qty = fields.Float(string='Demand Qty',default=0.0)
    approve_qty = fields.Float( string='Approve OnHand Qty',default=0.0)
    total_stock = fields.Float(string="Total Stock",compute="_compute_total_stock",store=False)
    note = fields.Char(string='Note')
    @api.depends('product_id')
    def _compute_total_stock(self):
        for line in self:
            line.total_stock = line.product_id.qty_available if line.product_id else 0.0

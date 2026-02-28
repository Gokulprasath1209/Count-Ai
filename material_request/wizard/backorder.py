from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class MaterialRequestBackorder(models.TransientModel):
    _name = 'material.request.backorder.wizard'
    _description = "Material Request Backorder Wizard"

    material_request_id = fields.Many2one('material.request')
    products_lines = fields.One2many('material.request.backorder.lines', 'backorder_id')

    def create_back_order(self):
        lines = [(0, 0, {'product_id': i.product_id.id, 'demand_qty': i.demand_qty}) for i in self.products_lines]
        data = {'main_mrp_id': self.material_request_id.main_mrp_id.id,
                'user_id': self.env.user.id,
                'backorder_name': self.material_request_id.name,
                'order_type': 'backorder',
                'date': fields.datetime.now(),
                'request_line_ids': lines,
                'request_type': self.material_request_id.request_type,
                'Project_id': self.material_request_id.Project_id,
                }
        self.env['material.request'].create(data)
        self.material_request_id.main_mrp_id.write({'request_for_material': 'onhand_approve'})
        self.material_request_id.write({'state': 'onhand_approve'})
        self.material_request_id.create_stock_picking()


class MaterialRequestBackorderLines(models.TransientModel):
    _name = 'material.request.backorder.lines'
    _description = "Material Request Backorder Lines Wizard"

    product_id = fields.Many2one('product.product', string='Raw Material')
    demand_qty = fields.Float(string=' Demand Qty')
    backorder_id = fields.Many2one('material.request.backorder.wizard')


class AgainMaterialRequest(models.TransientModel):
    _name = 'again.material.request'
    _description = 'Again Material Request'

    main_mrp_id = fields.Many2one('mrp.production', string='Production')
    user_id = fields.Many2one('res.users', string='Request user', default=lambda self: self.env.user.id)
    date = fields.Date(string='Date', default=fields.Date.context_today)
    display_date = fields.Char(string='Date', compute='_compute_display_date')

    @api.depends('date')
    def _compute_display_date(self):
        for rec in self:
            rec.display_date = rec.date.strftime('%d-%m-%Y') if rec.date else ''
    products_lines = fields.One2many('again.material.request.lines', 'request_id')

    def create_again_material_request(self):
        products = []
        for i in self.products_lines:
            val = (0, 0, {'product_id': i.product_id.id, 'demand_qty': i.demand_qty})
            products.append(val)
        data = {'main_mrp_id': self.main_mrp_id.id, 'user_id': self.env.user.id, 'request_line_ids': products,'request_type': 'mrp'}
        material_request = self.env['material.request'].create(data)



class AgainMaterialRequestLines(models.TransientModel):
    _name = 'again.material.request.lines'
    _description = "Again Material Request Lines Wizard"

    product_id = fields.Many2one('product.product', string='Raw Material')
    demand_qty = fields.Float(string=' Demand Qty')
    request_id = fields.Many2one('again.material.request')

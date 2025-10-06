from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class MaterialRequestBackorder(models.TransientModel):
    _name = 'material.request.backorder.wizard'
    _description = "Material Request Backorder Wizard"

    material_request_id = fields.Many2one('material.request')
    products_lines =fields.One2many('material.request.backorder.lines','backorder_id')

    def create_back_order(self):
        lines = [(0, 0, {'product_id': i.product_id.id, 'demand_qty': i.demand_qty}) for i in self.products_lines]
        data = {'main_mrp_id':self.material_request_id.main_mrp_id.id,
                'user_id':self.env.user.id,
                'backorder_name':self.material_request_id.name,
                'order_type':'backorder',
                'date':fields.datetime.now(),
                'request_line_ids':lines
                }
        self.env['material.request'].create(data)
        self.material_request_id.main_mrp_id.write({'request_for_material': 'onhand_approve'})
        self.material_request_id.write({'state': 'onhand_approve'})

class MaterialRequestBackorderLines(models.TransientModel):
    _name = 'material.request.backorder.lines'
    _description = "Material Request Backorder Lines Wizard"

    product_id = fields.Many2one('product.template', string='Raw Material')
    demand_qty = fields.Float(string=' Demand Qty')
    backorder_id = fields.Many2one('material.request.backorder.wizard')
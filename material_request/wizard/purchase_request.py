from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseRequestWizard(models.TransientModel):
    _name = 'purchase.request.wizard'
    _description = "Purchase Request Wizard"

    material_request_id = fields.Many2one('material.request')
    partner_id = fields.Many2one('res.partner',string='Vendor', default=lambda self: self.env.ref('material_request.test_vendor'),)
    products_lines = fields.One2many('purchase.request.wizard.lines','purchase_request_wizard_id')


    def save_button(self):
        lines = [(0,0,{'product_id':i.product_id.id,'product_qty':i.purchase_qty}) for i in self.products_lines]
        self.env['purchase.requisition'].create({'vendor_id':self.partner_id.id,'reference':self.material_request_id.name,
                                                 'line_ids':lines})
        self.material_request_id.write({'state':'waiting_for_purchase'})
        self.material_request_id.main_mrp_id.write({'request_for_material':'waiting_for_purchase'})


class PurchaseRequestWizardLines(models.TransientModel):
    _name = 'purchase.request.wizard.lines'
    _description = "Purchase Request Wizard Lines"

    product_id = fields.Many2one('product.product',string='Product')
    purchase_qty = fields.Float(string='Purchase Qty')
    purchase_request_wizard_id = fields.Many2one('purchase.request.wizard')
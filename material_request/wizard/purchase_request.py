from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseRequest(models.Model):
    _inherit = 'purchase.requisition'

    sug_partner_ids = fields.Many2many('res.partner', string='Suggested Vendors')

    def action_confirm(self):
        if self.vendor_id.id == self.env.ref('material_request.test_vendor').id:
            raise UserError(
                _(F"Hello {self.env.user.name} Kindly Please check Vendor Name [{self.vendor_id.name}] Using for Developer Purpose Select Correct Vendor"))
        else:
            res = super(PurchaseRequest, self).action_confirm()
        return res


class PurchaseRequestWizard(models.TransientModel):
    _name = 'purchase.request.wizard'
    _description = "Purchase Request Wizard"

    material_request_id = fields.Many2one('material.request')
    partner_id = fields.Many2one('res.partner', string='Vendor',
                                 default=lambda self: self.env.ref('material_request.test_vendor'), )
    products_lines = fields.One2many('purchase.request.wizard.lines', 'purchase_request_wizard_id')
    sug_partner_ids = fields.Many2many('res.partner', string='Suggested Vendors')
    required_date = fields.Date(string='Required Date')
    display_required_date = fields.Char(string='Required Date', compute='_compute_display_required_date')

    @api.depends('required_date')
    def _compute_display_required_date(self):
        for rec in self:
            rec.display_required_date = rec.required_date.strftime('%d-%m-%Y') if rec.required_date else ''

    def save_button(self):
        lines = [(0, 0, {'product_id': i.product_id.id, 'product_qty': i.purchase_qty}) for i in self.products_lines]
        self.env['purchase.requisition'].create(
            {'vendor_id': self.partner_id.id, 'reference': self.material_request_id.name,
             'sug_partner_ids': self.sug_partner_ids,
             'date_start': fields.Date.today(), 'date_end': self.required_date, 'line_ids': lines})

        self.material_request_id.write({'state': 'waiting_for_purchase'})
        self.material_request_id.main_mrp_id.write({'request_for_material': 'waiting_for_purchase'})


class PurchaseRequestWizardLines(models.TransientModel):
    _name = 'purchase.request.wizard.lines'
    _description = "Purchase Request Wizard Lines"

    product_id = fields.Many2one('product.product', string='Product')
    purchase_qty = fields.Float(string='Purchase Qty')
    purchase_request_wizard_id = fields.Many2one('purchase.request.wizard')

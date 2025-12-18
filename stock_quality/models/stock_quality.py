from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    quality_test_id = fields.Many2one('quality.test', string='Quality Test')
    requisition_id = fields.Many2one('purchase.requisition', string='Agreements',
                                     domain=[('state', 'in', ['confirmed'])])

    def button_confirm(self):
        res = super(PurchaseOrder, self).button_confirm()
        lines = [
            (0, 0, {'product_id': i.product_id.id, 'product_qty': i.product_qty, 'product_uom': i.product_uom.id})
            for i in self.order_line]

        data = {'ref': self.name, 'type': 'raw', 'date_order': fields.datetime.now(), 'date_planned': self.date_planned,
                'purchase_ids': [(4, self.id)],
                'test_line_ids': lines
                }
        quality_sample_test = self.env['quality.test'].create(data)
        self.quality_test_id = quality_sample_test.id
        return res


class QualityTest(models.Model):
    _name = 'quality.test'
    _description = 'Quality Tests'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Order Reference', required=True, readonly=True, default=lambda self: _('New'))
    ref = fields.Char("Reference")
    date_order = fields.Datetime(string='Order Deadline')
    date_planned = fields.Datetime(string='Expected Arrival')
    company_id = fields.Many2one('res.company', required=True, readonly=True, default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('accept', 'Accepted'),
        ('reject', 'Rejected'),
    ], string='State', default='draft', tracking=True)
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user)
    test_line_ids = fields.One2many('quality.test.lines', 'quality_id')
    purchase_ids = fields.Many2many('purchase.order')

    type = fields.Selection([
        ('raw', 'Raw'),
        ('fg', 'FG'),
    ], string='Type', tracking=True)

    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('quality.main.test.sequence') or _('New')
            return super(QualityTest, self).create(vals)

    def action_approve(self):
        self.state = 'accept'


class QualityTestLines(models.Model):
    _name = 'quality.test.lines'
    _description = 'Quality Test Lines'

    quality_id = fields.Many2one('quality.test')
    product_id = fields.Many2one('product.product', string='Product')
    product_qty = fields.Float(string='Quantity', digits='Product Unit of Measure', required=True,
                               store=True, readonly=False)
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure')
    open_product = fields.Many2one('open.product.quality')

    def action_test_for_product(self):
        view_id = self.env['open.product.quality']
        line = [(0, 0, {'product_id': self.product_id.id}) for i in range(int(self.product_qty))]
        ctx = {'default_product_id': self.product_id.id, 'default_quality_ref': self.quality_id.id,
               'default_qty': self.product_qty, 'default_quality_test_line_id': self.id, 'default_test_line_ids': line}
        return {
            'type': 'ir.actions.act_window',
            'name': 'Product Test',
            'res_model': 'open.product.quality',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': self.open_product.id,
            'view_id': self.env.ref('stock_quality.view_open_product_quality', False).id,
            'target': 'new',
            'context': ctx if not self.open_product else self.open_product.id,
        }


class OpenProductQuality(models.Model):
    _name = 'open.product.quality'
    _description = 'Open Product Quality'

    product_id = fields.Many2one('product.product', string="Product")
    qty = fields.Float(string='Qty')
    quality_ref = fields.Many2one('quality.test', string="Quality Ref")
    company_id = fields.Many2one('res.company', required=True, readonly=True, default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', readonly=True, default=lambda self: self.env.user.id)
    test_line_ids = fields.One2many('open.product.quality.line', 'quality_product_id')
    quality_test_line_id = fields.Many2one('quality.test.lines')
    quality_accept_count = fields.Float('Quality Count')

    def save_button(self):
        self.quality_test_line_id.open_product = self.id

    @api.onchange('test_line_ids')
    def get_quality_accept_count(self):
        count = 0
        for i in self.test_line_ids:
            if i.state == 'accept':
                count += 1
        self.quality_accept_count = count


class OpenProductQualityLine(models.Model):
    _name = 'open.product.quality.line'
    _description = 'Open Product Quality Line'

    quality_product_id = fields.Many2one('open.product.quality')
    product_id = fields.Many2one('product.product', 'product')
    barcode = fields.Char('Barcode')
    # quality_test_id = fields.Many2one('stock.quality.config')
    feedback = fields.Char(string='FeedBack')
    state = fields.Selection([('accept', 'Accept'), ('reject', 'Reject')], string='State')

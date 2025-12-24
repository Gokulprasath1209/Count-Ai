from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class MaterialRequest(models.Model):
    _name = 'user.material.request'
    _description = 'Material Request'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Request No', readonly=True, copy=False, default='New', tracking=True)
    user_id = fields.Many2one('res.users', string='Request User', default=lambda self: self.env.user, tracking=True)
    date = fields.Date(string='Request Date', default=fields.Date.today, tracking=True)
    exception_date = fields.Date(string='Exception Date')
    department = fields.Char(string='Department')
    location_from_id = fields.Many2one('stock.location', string='Location From')
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')
    location_id = fields.Many2one('stock.location', string='Location To')
    line_ids = fields.One2many('user.material.request.line', 'request_id', string='Material Lines')
    note = fields.Char(string='Note')
    state = fields.Selection(
        [('draft', 'Draft'), ('send', 'Send')], string="State", default='draft')

    material_request_count = fields.Integer(string='Material Request Count', compute="get_material_request_count")
    location_id = fields.Many2one('stock.location', string='Location')

    def get_material_request_count(self):
        self.material_request_count = self.env['material.request'].search_count([('ref', '=', self.name)])

    def action_open_material_request(self):
        self.ensure_one()
        purchase_requisition = self.env['material.request'].search([('ref', '=', self.name)])
        return {
            'name': _('Material Request'),
            'type': 'ir.actions.act_window',
            'res_model': 'material.request',
            'view_mode': 'list,kanban,form',
            'domain': [('ref', '=', self.name)],
            'context': {'create': False, 'edit': False}
        }

    def action_request(self):
        lines = []
        for i in self.line_ids:
            val = (0, 0, {'product_id': i.product_id.id, 'demand_qty': i.quantity})
            lines.append(val)
        data = {'ref': self.name, 'user_id': self.env.user.id, 'request_line_ids': lines, 'request_type': 'user',
                'note': self.note,'dest_loc_id':self.location_id.id}
        print("---------------------", data)
        self.env['material.request'].create(data)

    @api.model_create_multi
    def create(self, values_list):
        for vals in values_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'user.material.request'
                ) or 'New'
        return super().create(values_list)


class MaterialRequestLine(models.Model):
    _name = 'user.material.request.line'
    _description = 'Material Request Line'

    request_id = fields.Many2one('user.material.request', string='Material Request', ondelete='cascade', required=True)
    product_id = fields.Many2one('product.product', string='Product', )
    product_uom_id = fields.Many2one('uom.uom', string='UoM', required=True)
    unit_price = fields.Float(string='Unit Price', related="product_id.standard_price")
    quantity = fields.Float(string='Quantity', default=1.0, required=True)
    price_subtotal = fields.Float(string='Subtotal', compute='_compute_price_subtotal', store=True)

    @api.depends('quantity', 'unit_price')
    def _compute_price_subtotal(self):
        for rec in self:
            rec.price_subtotal = (rec.quantity or 0.0) * (rec.unit_price or 0.0)

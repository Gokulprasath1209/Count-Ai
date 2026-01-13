from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class MaterialRequest(models.Model):
    _name = 'user.material.request'
    _description = 'Material Request'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Request No', readonly=True, copy=False, default='New', tracking=True)
    user_id = fields.Many2one('res.users',string='Request By', default=lambda self: self.env.user,tracking=True)
    date = fields.Date(string='Request Date', default=fields.Date.today, tracking=True)
    exception_date = fields.Date(string='Exception Date')
    department = fields.Char(string='Department')
    location_from_id = fields.Many2one('stock.location', string='Location From')
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')
    location_id = fields.Many2one('stock.location', string='Home location')
    line_ids = fields.One2many('user.material.request.line', 'request_id', string='Material Lines')
    note = fields.Char(string='Project ID')
    # received_by = fields.char('res.users', string='Handed To')
    # description = fields.Char(string='Description')
    state = fields.Selection([ ('draft', 'Draft'),('send', 'Sent'),('received', 'Received'),('cancel', 'Cancelled'),], string='Status', default='draft', tracking=True)
    total_amount = fields.Float( string='Total Amount',compute='_compute_total_amount',store=True)
    material_request_count = fields.Integer(string='Material Request Count', compute="get_material_request_count")
    material_request_id = fields.Many2one(
        'material.request',
        string='Material Request',
        readonly=True,
        copy=False
    )
    product_search_id = fields.Many2one(
        'product.product',
        string='Product (Search)',
        store=False,
    )

    def action_return_material(self):
        print("-----------------=========----")

    def write(self, vals):
        if 'user_id' in vals:
            raise UserError("Request User cannot be changed.")
        return super().write(vals)

    def action_cancel(self):
        for rec in self:
            if rec.state == 'received':
                raise UserError(_("Received requests cannot be cancelled."))
            if rec.state == 'cancel':
                continue
            rec.state = 'cancel'
            if rec.material_request_id:
                rec.material_request_id.state = 'cancel'

    def action_receive(self):
        for record in self:
            material_request = self.env['material.request'].search([
                ('ref', '=', record.name)
            ], limit=1)
            if not material_request:
                raise UserError(_("No Material Request found for this record."))
            if material_request.state != 'full_approve':
                raise UserError(
                    _("Material is not approved by store yet. You cannot receive it.")
                )
            record.write({'state': 'received'})
            material_request.write({
                'state': 'received',
                'user_product_accept_bool': True,
            })
            material_request.message_post(
                body=_("Material received by user: %s")
                     % (record.user_id.name or 'User')
            )
    @api.depends('line_ids.price_subtotal')
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = sum(
                rec.line_ids.mapped('price_subtotal')
            )
    location_id = fields.Many2one('stock.location', string='Home location')

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
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("This request is already processed and cannot be sent again."))

            if not rec.line_ids:
                raise UserError(_("Dear %s, Request line is empty.") % self.env.user.name)

            lines = []
            for i in rec.line_ids:
                lines.append((0, 0, {
                    'product_id': i.product_id.id,
                    'demand_qty': i.quantity,
                }))

            material_request = self.env['material.request'].create({
                'ref': rec.name,
                'user_id': rec.user_id.id,
                'request_line_ids': lines,
                'request_type': 'user',
                'note': rec.note,
                'dest_loc_id': rec.location_id.id,
            })

            rec.write({
                'state': 'send',
                'material_request_id': material_request.id
            })

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
    received_qty = fields.Float(string="Received Qty")
    used_qty = fields.Float(string="Used Qty")
    return_qty = fields.Float(string="Return Qty",compute="_compute_return_qty", store=True)

    @api.depends('received_qty', 'used_qty')
    def _compute_return_qty(self):
        for line in self:
            line.return_qty = max(line.received_qty - line.used_qty, 0)

    @api.depends('quantity', 'unit_price')
    def _compute_price_subtotal(self):
        for rec in self:
            rec.price_subtotal = (rec.quantity or 0.0) * (rec.unit_price or 0.0)

    @api.constrains('quantity')
    def _check_quantity(self):
        for rec in self:
            if rec.quantity <= 0:
                raise UserError("Quantity must be greater than 0.")


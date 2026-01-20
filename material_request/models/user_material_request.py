import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger(__name__)

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
    is_returned = fields.Boolean(string="Is Returned", default=False, copy=False)

    def action_return_material(self):
        self.ensure_one()
        
        working_return_lines = []
        non_working_return_lines = []

        for line in self.line_ids:
            if line.working_return_qty > 0:
                working_return_lines.append((0, 0, {
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.working_return_qty,
                    'product_uom': line.product_uom_id.id,
                    'location_id': self.location_id.id,
                    'location_dest_id': self.warehouse_id.lot_stock_id.id, # Placeholder, will be set correctly below
                }))
            if line.non_working_return_qty > 0:
                 non_working_return_lines.append((0, 0, {
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.non_working_return_qty,
                    'product_uom': line.product_uom_id.id,
                    'location_id': self.location_id.id,
                    'location_dest_id': self.warehouse_id.lot_stock_id.id, # Placeholder
                }))

        if not working_return_lines and not non_working_return_lines:
            raise UserError(_("No materials to return. Please enter quantities in Working or Non-Working Return columns."))

        # 1. Find Incoming Picking Type (Same logic as before)
        picking_type = False
        if self.warehouse_id.in_type_id:
            picking_type = self.warehouse_id.in_type_id
        
        if not picking_type:
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'incoming'),
                ('warehouse_id', '=', self.warehouse_id.id)
            ], limit=1)

        if not picking_type:
             picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'incoming'),
                ('company_id', '=', self.env.company.id)
            ], limit=1)

        if not picking_type:
            raise UserError(_("Operation not valid. No 'Incoming' Picking Type found for warehouse %s or company." % self.warehouse_id.name))

        # 2. Find Locations
        
        # Source (Same for both)
        if not self.location_id:
             raise UserError(_("User Location is not set on the request."))
        
        # Working Destination (CW/Store)
        dest_location_stock_id = picking_type.default_location_dest_id.id
        if not dest_location_stock_id:
             dest_location_stock_id = self.warehouse_id.lot_stock_id.id
        if not dest_location_stock_id:
             dest_location_stock_id = self.env.ref('stock.stock_location_stock').id
        
        # Specific check for user requirement: CW/Store
        stock_loc = self.env['stock.location'].search([('complete_name', '=', 'CW/Store')], limit=1)
        if stock_loc:
            dest_location_stock_id = stock_loc.id
        elif not dest_location_stock_id:
             # Fallback to name search 'WH/Stock' if still not found
             stock_loc = self.env['stock.location'].search([('complete_name', 'ilike', 'WH/Stock')], limit=1)
             if stock_loc:
                 dest_location_stock_id = stock_loc.id

        # Non-Working Destination (CW/Store/Scarp warehouse)
        dest_location_scrap_id = False
        if non_working_return_lines:
            scrap_loc = self.env['stock.location'].search([
                ('complete_name', '=', 'CW/Store/Scarp warehouse'),
                ('company_id', 'in', [self.env.company.id, False])
            ], limit=1)
            
            # Fallback to scrap_location boolean flag
            if not scrap_loc:
                scrap_loc = self.env['stock.location'].search([
                    ('scrap_location', '=', True),
                    ('company_id', 'in', [self.env.company.id, False])
                ], limit=1)
            
            # Fallback to name search 'scrap location' if boolean flag is missing
            if not scrap_loc:
                scrap_loc = self.env['stock.location'].search([
                    ('name', 'ilike', 'scrap location'),
                    ('company_id', 'in', [self.env.company.id, False])
                ], limit=1)
            
            if not scrap_loc:
                 raise UserError(_("No Scrap Location found. Please configure a location named 'CW/Store/Scarp warehouse' or with 'Is a Scrap Location' checked."))
            dest_location_scrap_id = scrap_loc.id

        created_pickings = []

        # 3. Create Pickings
        
        # Working Return -> WH/Stock
        if working_return_lines:
             # Update location_dest_id in lines
             for item in working_return_lines:
                 item[2]['location_dest_id'] = dest_location_stock_id

             picking_working = self.env['stock.picking'].create({
                'partner_id': self.user_id.partner_id.id,
                'picking_type_id': picking_type.id,
                'location_id': self.location_id.id,
                'location_dest_id': dest_location_stock_id,
                'origin': self.name + " (Working)",
                'move_ids_without_package': working_return_lines,
            })
             created_pickings.append(picking_working.id)
             _logger.info(f"Created Working Return Picking: {picking_working.name}")

        # Non-Working Return -> Scrap
        if non_working_return_lines:
             # Update location_dest_id in lines
             for item in non_working_return_lines:
                 item[2]['location_dest_id'] = dest_location_scrap_id

             picking_scrap = self.env['stock.picking'].create({
                'partner_id': self.user_id.partner_id.id,
                'picking_type_id': picking_type.id,
                'location_id': self.location_id.id,
                'location_dest_id': dest_location_scrap_id,
                'origin': self.name + " (Non-Working/Scrap)",
                'move_ids_without_package': non_working_return_lines,
            })
             created_pickings.append(picking_scrap.id)
             _logger.info(f"Created Non-Working Return Picking: {picking_scrap.name}")
        
        self.write({'is_returned': True})
        
        # 4. Return Action
        if len(created_pickings) == 1:
            return {
                'name': _('Return Picking'),
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'view_mode': 'form',
                'res_id': created_pickings[0],
            }
        else:
            return {
                'name': _('Return Pickings'),
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'view_mode': 'list,form',
                'domain': [('id', 'in', created_pickings)],
            }

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
            for line in record.line_ids:
                line.received_qty = line.quantity
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
    working_return_qty = fields.Float(string="Working Return Qty", default=0.0)
    non_working_return_qty = fields.Float(string="Non-Working Return Qty", default=0.0)

    @api.depends('quantity', 'unit_price')
    def _compute_price_subtotal(self):
        for rec in self:
            rec.price_subtotal = (rec.quantity or 0.0) * (rec.unit_price or 0.0)

    @api.constrains('quantity')
    def _check_quantity(self):
        for rec in self:
            if rec.quantity <= 0:
                raise UserError("Quantity must be greater than 0.")


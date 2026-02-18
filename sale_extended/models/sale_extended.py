from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sale_approval = fields.Boolean(string="Approval")
    cto_approved_range = fields.Float(string="CTO Approved Range", )
    ceo_approved_range = fields.Float(string="CEO Approved Range", )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        params = self.env['ir.config_parameter'].sudo()
        sale_approval = params.get_param('sale_approval', default=False)
        cto_approved_range = params.get_param('cto_approved_range', default=False)
        ceo_approved_range = params.get_param('ceo_approved_range', default=False)
        res.update(sale_approval=sale_approval)
        res.update(cto_approved_range=cto_approved_range)
        res.update(ceo_approved_range=ceo_approved_range)
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param("sale_approval", self.sale_approval)
        self.env['ir.config_parameter'].sudo().set_param("cto_approved_range", self.cto_approved_range)
        self.env['ir.config_parameter'].sudo().set_param("ceo_approved_range", self.ceo_approved_range)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        if not self.order_line:
            raise UserError(_("Order line is empty."))
        else:
            params = self.env['ir.config_parameter'].sudo()
            sale_approval = params.get_param('sale_approval', )
            cto_approved_range = params.get_param('cto_approved_range', )
            ceo_approved_range = params.get_param('ceo_approved_range', )
            if sale_approval:
                if float(cto_approved_range) <= self.amount_total < float(ceo_approved_range):
                    if self.approval_state == 'cto_approved':
                        res = super().action_confirm()
                    else:
                        raise UserError(
                            _(F"Hello {self.env.user.name} Kindly GET A CTO Approval......"))
                elif self.amount_total >= float(ceo_approved_range):
                    if self.approval_state == 'ceo_approved':
                        print(self.approval_state)
                        res = super().action_confirm()
                    else:
                        raise UserError(
                            _(F"Hello {self.env.user.name} Kindly GET A CEO Approval......"))
                else:
                    res = super().action_confirm()

            return res

    sale_or_spare = fields.Selection(
        [
            ('sale', 'Sales'),
            ('spare', 'Spares')
        ],
        string="Orders",
    )
    approval_state = fields.Selection(
        [
            ('to_approve', 'Waiting for Approval'),
            ('cto_approved', 'CTO Approved'),
            ('ceo_approved', 'CEO Approved'),
            ('rejected', 'Rejected'),
        ],
        string="Approval Status",
    )
    state = fields.Selection(selection_add=[('waiting_ceo_approval', 'Waiting CEO Approval'), ('rejected', 'Rejected')])
    
    approved_by = fields.Many2one('res.users', string="Approved By", readonly=True, copy=False)
    approved_date = fields.Datetime(string="Approved Date", readonly=True, copy=False)
    approval_level = fields.Char(string="Approval Level", readonly=True, copy=False)
    reject_reason = fields.Text(string="Reject Reason", copy=False)
    user_id = fields.Many2one(
        comodel_name='res.users',
        string="Salesperson",
        compute='_compute_user_id',
        store=True, readonly=False, precompute=True, index=True,
        tracking=2,
        domain=lambda self: "[('groups_id', '=', {}), ('share', '=', False), ('company_ids', '=', company_id)]".format(
            self.env.ref("sales_team.group_sale_salesman").id
        ))
    contact_person_id = fields.Many2one(
        'res.partner',
        string="Contact Person", compute='get_parent_id'
    )

    expected_delivery_date = fields.Date(
        string="Expected Delivery Date"
    )

    service_id = fields.Char(string='Service Ticket')
    user_note = fields.Char(string='Note')
    show_store_request_button = fields.Boolean(
        string='Show Store Request Button',
        compute='_compute_show_store_request_button'
    )
    product_return = fields.Selection(
        [
            ('returnable', 'Returnable'),
            ('non_returnable', 'Non Returnable')
        ],
        string='Product Return',
    )
    is_return_validated = fields.Boolean(
        string='Return Validated',
        compute='_compute_is_return_validated'
    )

    @api.depends('name')
    def _compute_is_return_validated(self):
        for order in self:
            # Check for incoming pickings related to this order or its material requests
            mr_names = self.env['material.request'].search([('ref', '=', order.name)]).mapped('name')
            pickings = self.env['stock.picking'].search([
                '|',
                ('origin', '=', order.name),
                ('origin', 'in', mr_names),
                ('picking_type_id.code', '=', 'incoming'),
                ('state', '=', 'done')
            ])
            order.is_return_validated = bool(pickings)

    def action_confirm_spare(self):
        for order in self:
            if order.sale_or_spare == 'spare' and order.product_return == 'returnable':
                if not order.is_return_validated:
                    raise UserError(_("Return product must be validated in stock before completing the order."))
            
            if order.state in ('draft', 'sent', 'waiting_ceo_approval'):
                order._force_confirm_sale_order()
                order._create_manufacturing_order()

    @api.depends_context('uid')
    def _compute_show_store_request_button(self):
        for record in self:
            user = self.env.user
            is_ceo = user.has_group('sale_extended.group_ceo')
            is_cto = user.has_group('sale_extended.group_cto')
            record.show_store_request_button = not (is_ceo or is_cto)

    acknowledgement_ids = fields.One2many(
        'sale.order.acknowledgement', 'order_id', string='Acknowledgements'
    )
    filtered_acknowledgement_ids = fields.Many2many(
        'sale.order.acknowledgement',
        string='Visible Acknowledgements',
        compute='_compute_filtered_acknowledgement_ids'
    )

    def _compute_filtered_acknowledgement_ids(self):
        for order in self:
            is_admin = self.env.user.has_group('sale_extended.group_ceo') or \
                       self.env.user.has_group('sales_team.group_sale_manager')
            if is_admin:
                order.filtered_acknowledgement_ids = order.acknowledgement_ids
            else:
                order.filtered_acknowledgement_ids = order.acknowledgement_ids.filtered(
                    lambda a: a.dest_user_id.id == self.env.user.id
                )

    has_pending_acknowledgement = fields.Boolean(
        compute='_compute_has_pending_acknowledgement',
        string='Has Pending Acknowledgement'
    )

    def _compute_has_pending_acknowledgement(self):
        for order in self:
            pending = self.env['sale.order.acknowledgement'].search_count([
                ('order_id', '=', order.id),
                ('dest_user_id', '=', self.env.user.id),
                ('state', '=', 'pending')
            ])
            order.has_pending_acknowledgement = bool(pending)

    def action_accept_transfer(self):
        self.ensure_one()
        pending_acks = self.env['sale.order.acknowledgement'].search([
            ('order_id', '=', self.id),
            ('dest_user_id', '=', self.env.user.id),
            ('state', '=', 'pending')
        ])
        if not pending_acks:
            raise UserError(_("No pending items found for you to accept."))
        pending_acks.write({
            'state': 'received',
            'date': fields.Datetime.now(),
        })
        self.message_post(body=_("Items hand-over accepted by %s") % self.env.user.name)

    def action_acknowledge_receipt(self):
        self.ensure_one()
        return {
            'name': _('Transfer Items'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order.acknowledgement.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_order_id': self.id},
        }

    def action_request(self):
        self.ensure_one()

        if self.sale_or_spare != 'spare':
            raise UserError(_("Store request allowed only for Spare orders."))

        if self.approval_state != 'ceo_approved':
            raise UserError(_("CEO approval is required before requesting materials."))

        if not self.order_line:
            raise UserError(_("Order line is empty."))

        mr = self.env['material.request'].create({
            'ref': self.name,
            'user_id': self.env.user.id,
            'request_type': 'user',
            'state': 'waiting_ceo_approval',
            'note': self.user_note,
            'request_line_ids': [
                (0, 0, {
                    'product_id': line.product_id.id,
                    'demand_qty': line.product_uom_qty,
                })
                for line in self.order_line if line.product_id
            ],
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Material Request',
            'res_model': 'material.request',
            'view_mode': 'form',
            'res_id': mr.id,
        }

    def get_parent_id(self):
        contact_person_id = self.env['res.partner'].search([('parent_id', '=', self.partner_id.id)])
        self.contact_person_id = contact_person_id.id

    def action_send_approve(self):
        self.write({
            'approval_state': 'to_approve',
            'state': 'waiting_ceo_approval'
        })


class SaleOrderManufacturing(models.Model):
    _inherit = 'sale.order'
    manufacturing_order_id = fields.Many2one('mrp.production', string="Manufacturing Order", readonly=True)

    def action_ceo_approve(self):
        for order in self:
            if order.sale_or_spare == 'spare' and not order.product_return:
                raise UserError(_("Please select Product Return type for Spare Order."))
            order.write({
                'approval_state': 'ceo_approved',
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now(),
                'approval_level': 'ceo'
            })

            if order.sale_or_spare == 'spare' and order.product_return == 'returnable':
                # Returnable spare orders stay in quotation stage
                continue

            if order.state in ('draft', 'sent', 'waiting_ceo_approval'):
                order._force_confirm_sale_order()

            order._create_manufacturing_order()

    def action_cto_approve(self):
        for order in self:
            if not (10000 < order.amount_total <= 20000):
                raise UserError(
                    _("CTO approval is allowed only for orders between ₹10,000 and ₹20,000.")
                )
            order.write({
                'approval_state': 'cto_approved',
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now(),
                'approval_level': 'cto'
            })
            if order.state in ('draft', 'sent', 'waiting_ceo_approval'):
                order._force_confirm_sale_order()
            order._create_manufacturing_order()

    def _force_confirm_sale_order(self):
        for order in self:
            if order.sale_or_spare == 'spare':
                for line in order.order_line:
                    if line.product_id:
                        line.price_unit = line.product_id.standard_price
        self.write({'state': 'sale'})
        self._action_confirm()

    def _create_manufacturing_order(self):
        MrpProduction = self.env['mrp.production']
        for order in self:
            if order.manufacturing_order_id:
                continue
            for line in order.order_line:
                if not line.product_id:
                    continue
                if line.product_id.type != 'product':
                    continue
                mo = MrpProduction.create({
                    'product_id': line.product_id.id,
                    'product_qty': line.product_uom_qty,
                    'product_uom_id': line.product_uom.id,
                    'origin': order.name,
                })
                mo.action_confirm()
                order.manufacturing_order_id = mo.id

    def action_confirm(self):
        raise UserError("Use Approve button to confirm the order.")

    def write(self, vals):
        for order in self:
            if set(vals.keys()) == {'approval_state'}:
                continue
            technical_fields = {
                'state',
                'invoice_status',
                'delivery_status',
                'date_order',
                'commitment_date',
                'service_id',
            }
            if set(vals.keys()).issubset(technical_fields):
                continue
            if order.approval_state in ('to_approve', 'cto_approved', 'ceo_approved'):
                if not (
                        self.env.user.has_group('sale_extended.group_ceo')
                        or self.env.user.has_group('sale_extended.group_cto')
                ):
                    raise UserError(
                        _("Only CEO or CTO can modify orders in approved/waiting states.")
                    )
        return super(SaleOrderManufacturing, self).write(vals)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    machine_id = fields.Char(string='Machine Serial No')
    def write(self, vals):
        if self.env.su:
            return super().write(vals)
        for line in self:
            order = line.order_id
            if order.approval_state == 'draft':
                continue
            if not (
                    self.env.user.has_group('sale_extended.group_ceo')
                    or self.env.user.has_group('sale_extended.group_cto')
            ):
                raise UserError(_("Only CEO or CTO can modify orders in approved/waiting states."))
            allowed = {'product_uom_qty', 'price_unit'}
            if set(vals.keys()) - allowed:
                raise UserError(_("Only Qty and Price can be modified on approved orders."))
        return super().write(vals)


class SaleOrderAcknowledgement(models.Model):
    _name = 'sale.order.acknowledgement'
    _description = 'Sale Order Acknowledgement'
    _order = 'date desc'

    order_id = fields.Many2one('sale.order', string='Order', required=True, ondelete='cascade')
    source_user_id = fields.Many2one('res.users', string='From', default=lambda self: self.env.user, required=True)
    dest_user_id = fields.Many2one('res.users', string='To', required=False)
    is_return_to_store = fields.Boolean(string='Is Return to Store', default=False)
    display_dest_user = fields.Char(string='To', compute='_compute_display_dest_user')

    @api.depends('dest_user_id', 'is_return_to_store')
    def _compute_display_dest_user(self):
        for rec in self:
            if rec.is_return_to_store:
                rec.display_dest_user = _("Store")
            elif rec.dest_user_id:
                rec.display_dest_user = rec.dest_user_id.name
            else:
                rec.display_dest_user = _("Unknown")

    date = fields.Datetime(string='Date', default=fields.Datetime.now, required=True)
    state = fields.Selection([
        ('pending', 'Waiting for Acceptance'),
        ('received', 'Accepted'),
    ], string='Status', default='pending', required=True)
    line_ids = fields.One2many('sale.order.acknowledgement.line', 'acknowledgement_id', string='Lines')

    def name_get(self):
        result = []
        for rec in self:
            dest = rec.dest_user_id.name if rec.dest_user_id else (_("Store") if rec.is_return_to_store else _("Unknown"))
            result.append((rec.id, f"{rec.source_user_id.name} -> {dest} ({rec.date.date()})"))
        return result


class SaleOrderAcknowledgementLine(models.Model):
    _name = 'sale.order.acknowledgement.line'
    _description = 'Sale Order Acknowledgement Line'

    acknowledgement_id = fields.Many2one('sale.order.acknowledgement', string='Acknowledgement', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    quantity = fields.Float(string='Quantity', default=1.0, required=True)
    serial_numbers = fields.Text(string='Serial Numbers')
    display_name = fields.Char(compute='_compute_display_name')

    def _compute_display_name(self):
        for line in self:
            line.display_name = f"{line.product_id.name} ({line.quantity})"

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

    machine_id = fields.Char(string='Machine Serial No')
    service_id = fields.Char(string='Service Ticket')
    user_note = fields.Char(string='Note')

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
        self.write({'approval_state': 'to_approve'})

    class SaleOrder(models.Model):
        _inherit = 'sale.order'
        manufacturing_order_id = fields.Many2one('mrp.production', string="Manufacturing Order", readonly=True)

        def action_ceo_approve(self):
            for order in self:
                order.write({'approval_state': 'ceo_approved'})

                if order.state in ('draft', 'sent'):
                    order._force_confirm_sale_order()

                order._create_manufacturing_order()

        def action_cto_approve(self):
            for order in self:
                if not (10000 < order.amount_total <= 20000):
                    raise UserError(
                        _("CTO approval is allowed only for orders between ₹10,000 and ₹20,000.")
                    )
                order.write({'approval_state': 'cto_approved'})
                if order.state in ('draft', 'sent'):
                    order._force_confirm_sale_order()
                order._create_manufacturing_order()

        def _force_confirm_sale_order(self):
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
                }
                if set(vals.keys()).issubset(technical_fields):
                    continue
                if order.approval_state in ('to_approve', 'cto_approved', 'ceo_approved'):
                    if not (
                            self.env.user.has_group('sale_extended.group_ceo')
                            or self.env.user.has_group('sale_extended.group_cto')
                    ):
                        raise UserError(
                        )
            return super().write(vals)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def write(self, vals):
        for line in self:
            order = line.order_id
            if order.approval_state == 'draft':
                continue
            if not (
                    self.env.user.has_group('sale_extended.group_ceo')
                    or self.env.user.has_group('sale_extended.group_cto')
            ):
                raise UserError(
                )
            allowed = {'product_uom_qty', 'price_unit'}
            if set(vals.keys()) - allowed:
                raise UserError(
                )
        return super().write(vals)

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    sale_or_spare = fields.Selection(
        [
            ('sale', 'Sales'),
            ('spare', 'Spares')
        ],
        string="Orders",
    )

    approval_state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('to_approve', 'Waiting for Approval'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        string="Approval Status",
        default='draft',
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
        string="Contact Person"
    )

    expected_delivery_date = fields.Date(
        string="Expected Delivery Date"
    )

    def action_submit_for_approval(self):
        for rec in self:
            if rec.state not in ('draft', 'sent'):
                raise UserError(_("Only draft quotations can be submitted for approval."))

            rec.approval_state = 'to_approve'

            admin_group = self.env.ref('sales_team.group_sale_manager', raise_if_not_found=False)
            if admin_group:
                partners = admin_group.users.mapped('partner_id').ids
                if partners:
                    rec.message_post(
                        body=_("Sale Order %s has been submitted for approval.") % rec.name,
                        partner_ids=partners,
                        subtype_xmlid="mail.mt_comment",
                    )

    def action_approve_order(self):
        for rec in self:
            if not self.env.user.has_group('sales_team.group_sale_manager'):
                raise UserError(_("Only Sales Managers can approve sale orders."))

            if rec.approval_state != 'to_approve':
                raise UserError(_("Only orders waiting for approval can be approved."))

            rec.approval_state = 'approved'
            rec.action_confirm()

            rec.message_post(
                body=_("Sale Order approved and confirmed by %s.") % self.env.user.name,
                subtype_xmlid="mail.mt_comment",
            )

    def action_reject_order(self):
        for rec in self:
            if not self.env.user.has_group('sales_team.group_sale_manager'):
                raise UserError(_("Only Sales Managers can reject sale orders."))

            if rec.approval_state != 'to_approve':
                raise UserError(_("Only orders waiting for approval can be rejected."))

            rec.approval_state = 'rejected'
            rec.message_post(
                body=_("Sale Order was rejected by %s.") % self.env.user.name,
                subtype_xmlid="mail.mt_comment",
            )

    def action_confirm(self):

        for order in self:
            if not self.env.user.has_group('sales_team.group_sale_manager'):
                if order.approval_state != 'approved':
                    raise UserError(
                        _("You cannot confirm this order.\n"
                          "Please submit for approval and wait for Sales Admin approval.")
                    )

        return super(SaleOrder, self).action_confirm()


    @api.constrains('order_line', 'state')
    def _check_order_line_required(self):
        for order in self:
            if order.state == 'draft':
                continue

            valid_lines = order.order_line.filtered(
                lambda l: not l.display_type
            )
            if not valid_lines:
                raise ValidationError(
                    "You must add at least one Order Line before confirming the Order."
                )



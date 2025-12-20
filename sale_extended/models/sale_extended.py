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



    def get_parent_id(self):
        contact_person_id = self.env['res.partner'].search([('parent_id', '=', self.partner_id.id)])
        self.contact_person_id = contact_person_id.id

    def action_send_approve(self):
        self.write({'approval_state': 'to_approve'})

    def action_ceo_approve(self):
        self.write({'approval_state': 'ceo_approved'})

    def action_cto_approve(self):
        self.write({'approval_state': 'cto_approved'})

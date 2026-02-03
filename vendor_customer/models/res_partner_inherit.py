from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ResPartnerInherit(models.Model):
    _inherit = 'res.partner'

    product_id = fields.Many2many('product.product', string='Products', tracking=True)
    machine_number_ids = fields.Many2many('partner.machine.number', string='Machine Numbers', tracking=True, help="Machine numbers associated with this customer")


class ResUsers(models.Model):
    _inherit = 'res.users'

    allowed_location_ids = fields.Many2many(
        'stock.location',
        compute='_compute_allowed_locations',
        store=False
    )
    def _compute_allowed_locations(self):
        for rec in self:
            rec.allowed_location_ids = rec.user_id.allowed_location_ids
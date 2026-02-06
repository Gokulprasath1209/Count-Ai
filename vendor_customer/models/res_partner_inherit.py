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
        'vendor_customer_res_users_stock_location_rel',
        'user_id',
        'location_id',
        string='Allowed Locations',
        help='Stock locations that this user is allowed to select in material requests'
    )
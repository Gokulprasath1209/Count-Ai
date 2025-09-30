from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class MaterialRequest(models.Model):
    _name = 'material.request'
    _description = 'Material Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']


    name = fields.Char(string='Name')
    main_mrp_id = fields.Many2one('mrp.production', string='Production')
    user_id = fields.Many2one('res.users', string='Request user')
    date = fields.Datetime(string='Date', default=fields.Datetime.now())
    procurement_ids = fields.Many2many('mrp.production', string='Production Child')
    state = fields.Selection([('approve', 'Approve'), ('hold', 'Hold'),
                                             ('reject', 'Reject')], string="Material Request")
    request_line_ids = fields.One2many('material.request.product.line','request_id')

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('material.request.sequence')
        return super(MaterialRequest, self).create(vals)

    def action_approve(self):
        self.main_mrp_id.request_for_material = 'approve'
        self.write({'state':'approve'})

    def action_purchase_request(self):
       self.write({'state':'hold'})


class MaterialRequestProductLines(models.Model):
    _name = 'material.request.product.line'
    _description = 'Material Request Product Lines'

    product_id = fields.Many2one('product.template',string='Raw Material')
    demand_qty =fields.Float(string=' Demand Qty')
    request_id = fields.Many2one('material.request')
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    quality_test_count = fields.Integer(string='Quality Test Count', compute='_compute_quality_test_count')

    def _compute_quality_test_count(self):
        self.quality_test_count = self.env['quality.test'].search_count(
            [('purchase_ids', 'in', self.purchase_id.id)])

    def action_view_quality_tests(self):
        self.ensure_one()
        quality_tests = self.env['quality.test'].search([('purchase_ids', 'in', self.purchase_id.id)])
        return {
            'name': _('Quality Tests'),
            'type': 'ir.actions.act_window',
            'res_model': 'quality.test',
            'view_mode': 'list,form',
            'domain': [('id', 'in', quality_tests.ids)],
            'context': {'create': False, 'edit': False}
        }

    def button_validate(self):
        for picking in self:
            if picking.purchase_id and picking.picking_type_code == 'incoming':
                quality_tests = self.env['quality.test'].search([('purchase_ids', 'in', picking.purchase_id.id)])
                if not quality_tests:
                    raise UserError(
                        _("No quality tests are associated with this purchase order. You must create and accept all quality tests before confirming the order.")
                    )
                for test in quality_tests:
                    if test.state != 'accept':
                        raise UserError(
                            _("Quality test '%s' is not accepted. All quality tests must be in the 'Accepted'") % test.name
                        )

        return super(StockPicking, self).button_validate()

class StockMove(models.Model):
    _inherit = 'stock.move'

    total_stock = fields.Float(
        string="Total Stock",
        compute="_compute_total_stock",
        store=True
    )

    @api.depends('product_id')
    def _compute_total_stock(self):
        for move in self:
            move.total_stock = move.product_id.qty_available if move.product_id else 0.0


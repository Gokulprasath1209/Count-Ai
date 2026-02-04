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
                # Get quality tests for the PO
                quality_tests = self.env['quality.test'].search([('purchase_ids', 'in', picking.purchase_id.id)])
                
                # Check if QC is passed (tests exist and all are accepted)
                qc_passed = all(t.state == 'accept' for t in quality_tests) if quality_tests else False

                for move in picking.move_ids_without_package:
                    if move.product_id.quality_check:
                        # QC Required: Only allow if QC is passed
                        if not qc_passed:
                            move.quantity = 0.0
                    else:
                        # QC Not Required: Auto-complete if not set
                        if move.quantity == 0.0:
                            move.quantity = move.product_uom_qty

        res = super(StockPicking, self).button_validate()
        
        # Automatically handle backorder creation if wizard is returned
        if isinstance(res, dict) and res.get('res_model') == 'stock.backorder.confirmation':
            wizard_id = res.get('res_id')
            if wizard_id:
                wizard = self.env['stock.backorder.confirmation'].browse(wizard_id)
                return wizard.process()
            
        return res

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


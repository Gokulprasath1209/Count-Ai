import logging
from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class InventoryReportsWizard(models.TransientModel):
    _name = 'inventory.reports.wizard'
    _description = "Inventory Reports Wizard"

    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')
    user_ids = fields.Many2many('res.users', string="Responsible")
    product_ids = fields.Many2many('product.product', string="Products")
    shipment_type = fields.Selection([
        ('inward', 'Incoming Stock'),
        ('internal', 'Internal Transfer'),
    ], string="Shipment Type", default='inward')

    def action_print_pdf(self):
        if not self.start_date or not self.end_date:
            raise UserError("Please select both start and end dates.")

        data = {
            'start_date': str(self.start_date),
            'end_date': str(self.end_date),
            'user_ids': self.user_ids.ids,
            'product_ids': self.product_ids.ids,
            'shipment_type': self.shipment_type,
        }

        _logger.info(">>> Inventory Wizard Data Sent to Report: %s", data)

        return self.env.ref('inventory_report.inventory_reports_wizard_report_action').report_action(self, data=data)


class InventoryReport(models.AbstractModel):
    _name = 'report.inventory_report.template_inventory_report_qweb'
    _description = 'Inventory Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        if not data:
            raise UserError("No data received from wizard.")

        domain = []
        if data.get('start_date'):
            domain.append(('scheduled_date', '>=', data['start_date']))
        if data.get('end_date'):
            domain.append(('scheduled_date', '<=', data['end_date']))
        if data.get('user_ids'):
            domain.append(('create_uid', 'in', data['user_ids']))
        if data.get('product_ids'):
            domain.append(('move_lines.product_id', 'in', data['product_ids']))
        if data.get('shipment_type'):
            domain.append(('picking_type_code', '=', data['shipment_type']))

        pickings = self.env['stock.picking'].search(domain)
        _logger.info(">>> Found %s Stock Pickings", len(pickings))

        report_data = []
        for pick in pickings:
            for move in pick.move_lines:
                report_data.append({
                    'picking_name': pick.name,
                    'origin': pick.origin or '',
                    'scheduled_date': pick.scheduled_date.date() if pick.scheduled_date else '',
                    'user': pick.create_uid.name,
                    'shipment_type': pick.picking_type_code,
                    'product_code_name': f"[{move.product_id.default_code or ''}] {move.product_id.name}",
                    'planned_qty': move.product_uom_qty,
                    'done_qty': sum(move.move_line_ids.mapped('quantity_done')),
                    'state': pick.state,
                })

        return {
            'doc_ids': docids,
            'doc_model': 'inventory.reports.wizard',
            'data': data,
            'report_data': report_data,
            'res_company': self.env.company,
        }

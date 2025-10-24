import logging
from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MrpProductionReportsWizard(models.TransientModel):
    _name = 'mrpproduction.reports.wizard'
    _description = "Manufacturing Order Reports Wizard"

    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')
    user_ids = fields.Many2many('res.users', string="Responsible")
    customer_ids = fields.Many2many('res.partner', string="Customers")
    product_ids = fields.Many2many('product.product', string="Products")
    production_type = fields.Selection([
        ('normal', 'Regular Production'),
        ('spare', 'Spare Production'),
    ], string="Production Type", default='normal')

    def action_print_pdf(self):
        if not self.start_date or not self.end_date:
            raise UserError("Please select both start and end dates.")

        data = {
            'start_date': str(self.start_date),
            'end_date': str(self.end_date),
            'user_ids': self.user_ids.ids,
            'product_ids': self.product_ids.ids,
            'production_type': self.production_type,
        }

        _logger.info(">>> Wizard Data Sent to Report: %s", data)

        return self.env.ref('mrp_wizard.mrpproduction_reports_wizard_report_action').report_action(self, data=data)


class MrpProductionReport(models.AbstractModel):
    _name = 'report.mrp_wizard.template_mrp_production_report_qweb'
    _description = 'Manufacturing Order Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        _logger.info(">>> MRP Report Called with Data: %s", data)

        if not data:
            raise UserError("No data received from wizard.")

        domain = []
        if data.get('start_date'):
            domain.append(('date_start', '>=', data['start_date']))
        if data.get('end_date'):
            domain.append(('date_finished', '<=', data['end_date']))
        if data.get('user_ids'):
            domain.append(('user_id', 'in', data['user_ids']))
        if data.get('product_ids'):
            domain.append(('product_id', 'in', data['product_ids']))
        if data.get('production_type'):
            domain.append(('production_type', '=', data['production_type']))

        productions = self.env['mrp.production'].search(domain)
        _logger.info(">>> Found %s Manufacturing Orders for Domain: %s", len(productions), domain)

        report_data = []
        for mo in productions:
            # ✅ Correct field in Odoo 18
            total_produced = sum(mo.move_finished_ids.mapped('move_line_ids.quantity'))

            if mo.state == 'progress':
                status = 'In Progress'
            elif mo.state == 'done':
                status = 'Completed'
            elif mo.state in ['hold', 'cancel']:
                status = 'Hold'
            else:
                status = mo.state.capitalize()

            for move in mo.move_raw_ids:
                actual_issued_qty = sum(move.move_line_ids.mapped('quantity'))
                variance = actual_issued_qty - move.product_uom_qty
                variance_percent = 0
                if move.product_uom_qty:
                    variance_percent = (variance / move.product_uom_qty) * 100

                report_data.append({
                    'mo_number': mo.name,
                    # 'linked_so': mo.sale_id.name or '',
                    'product_code_name': f"[{mo.product_id.default_code or ''}] {mo.product_id.name}",
                    'product_version': getattr(mo.product_id.product_tmpl_id, 'version', ''),
                    'planned_qty': mo.product_qty,
                    'produced_qty': total_produced,
                    'start_date': mo.date_start.date() if mo.date_start else '',
                    'planned_completion': mo.date_finished.date() if mo.date_finished else '',
                    'actual_completion': mo.date_finished.date() if mo.date_finished else '',
                    'status': status,

                    'bom_item_code': move.product_id.default_code or '',
                    'bom_planned_qty': move.product_uom_qty,
                    'actual_issued_qty': actual_issued_qty,
                    'variance': variance,
                    'variance_percent': round(variance_percent, 2),
                })

        return {
            'doc_ids': docids,
            'doc_model': 'mrpproduction.reports.wizard',
            'data': data,
            'report_data': report_data,
            'res_company': self.env.company,
        }

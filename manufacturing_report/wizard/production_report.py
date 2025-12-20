from odoo import api, fields, models
from odoo.exceptions import UserError


class ManufacturingWizardReport(models.TransientModel):
    _name = "manufacturing.wizard.report"
    _description = "Manufacturing Report Wizard"

    start_date = fields.Datetime(string="Start Date", required=True)
    end_date = fields.Datetime(string="End Date", required=True)

    state = fields.Selection(
        [
            ('all', 'All'),
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('progress', 'In Progress'),
            ('to_close', 'To Close'),
            ('done', 'Done'),
            ('cancel', 'Cancelled'),
        ],
        string='State',
        default='all'
    )

    def action_print_pdf(self):
        data = {
            'start_date': self.start_date,
            'end_date': self.end_date,
            'state': self.state,
        }

        return self.env.ref(
            'manufacturing_report.manufacturing_report_action'
        ).report_action(self, data=data)


    class ManufacturingReportPDF(models.AbstractModel):
        _name = 'report.manufacturing_report.template_manufacturing_report_qweb'
        _description = "Manufacturing PDF Report"

        @api.model
        def _get_report_values(self, docids, data=None):
            data = data or {}

            grouped_lines = {
                'draft': [],
                'confirmed': [],
                'progress': [],
                'to_close': [],
                'done': [],
                'cancel': [],
            }

            domain = []

            if data.get('start_date'):
                domain.append(('date_start', '>=', data['start_date']))

            if data.get('end_date'):
                domain.append(('date_start', '<=', data['end_date']))

            if data.get('state') and data['state'] != 'all':
                domain.append(('state', '=', data['state']))

            productions = self.env['mrp.production'].sudo().search(domain)

            for mo in productions:
                # Business Status
                if mo.state in ('confirmed', 'progress', 'to_close'):
                    status = 'In Progress'
                elif mo.state == 'done':
                    status = 'Completed'
                else:
                    status = 'Hold'

                grouped_lines[mo.state].append({
                    'mo_no': mo.name,
                    'so_no': mo.origin or '',
                    'product': f"{mo.product_id.default_code or ''} - {mo.product_id.display_name}",
                    'product_version': mo.bom_id.code if mo.bom_id else '',
                    'planned_qty': mo.product_qty,
                    'produced_qty': mo.qty_produced,
                    'start_date': mo.date_start,
                    'planned_completion_date': mo.date_deadline,
                    'actual_completion_date': mo.date_finished,
                    'state': mo.state,
                })

            return {
                'doc_model': 'manufacturing.wizard.report',
                'grouped_lines': grouped_lines or {},
                'selected_state': data.get('state') or 'all',
                'start_date': data.get('start_date'),
                'end_date': data.get('end_date'),
            }

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


    class ManufacturingReport(models.AbstractModel):
        _name = 'report.manufacturing_report.template_manufacturing_report_qweb'
        _description = 'Manufacturing Report QWeb'

        @api.model
        def _get_report_values(self, docids, data=None):
            wizard = self.env['manufacturing.wizard.report'].browse(docids)

            domain = []
            if wizard.start_date:
                domain.append(('date_start', '>=', wizard.start_date))

            if wizard.end_date:
                domain.append(('date_start', '<=', wizard.end_date))

            if wizard.state and wizard.state != 'all':
                domain.append(('state', '=', wizard.state))
            productions = self.env['mrp.production'].sudo().search(
                domain, order='date_start asc'
            )
            lines = []
            for mo in productions:
                if mo.state in ('confirmed', 'progress', 'to_close'):
                    status = 'In Progress'
                elif mo.state == 'done':
                    status = 'Completed'
                elif mo.state == 'cancel':
                    status = 'Cancelled'
                else:
                    status = 'Draft'

                lines.append({
                    'mo_no': mo.name,
                    'so_no': mo.origin or '',
                    'product': mo.product_id.display_name,
                    'product_version': mo.bom_id.code if mo.bom_id else '',
                    'planned_qty': mo.product_qty,
                    'produced_qty': mo.qty_produced,
                    'start_date': mo.date_start,
                    'planned_completion_date': mo.date_deadline,
                    'actual_completion_date': mo.date_finished,
                    'state': status,
                })

            return {
                'doc_ids': docids,
                'doc_model': 'manufacturing.wizard.report',
                'lines': lines,
                'start_date': wizard.start_date,
                'end_date': wizard.end_date,
                'user': self.env.user,
            }

        def get_report_values(self, docids, data=None):
            return self._get_report_values(docids, data=data)


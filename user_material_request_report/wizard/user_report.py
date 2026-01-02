from odoo import models, fields, api
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class MaterialRequestReportsWizard(models.TransientModel):
    _name = 'material.request.reports.wizard'
    _description = "Material Request Reports Wizard"

    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')
    location_id = fields.Many2one('stock.location', string='Location')
    product_id = fields.Many2one('product.product', string='Product')
    user_id = fields.Many2one('res.users', string='Requested By')

    def action_print_pdf(self):
        if not self.start_date or not self.end_date:
            raise UserError("Please select both start and end dates.")

        data = {
            'start_date': str(self.start_date),
            'end_date': str(self.end_date),
            'location_id': self.location_id.id if self.location_id else False,
            'product_id': self.product_id.id if self.product_id else False,
            'user_id': self.user_id.id if self.user_id else False,
        }

        _logger.info(">>> Material Request Wizard Data Sent to Report: %s", data)

        return self.env.ref(
            'user_material_request_report.material_request_report_action'
        ).report_action(self, data=data)

class MaterialRequestReportPDF(models.AbstractModel):
    _name = 'report.user_report.template_material_request_report_pdf'
    _description = "Material Request PDF Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        if not data:
            raise UserError("No data received.")

        domain = [
            ('date', '>=', data['start_date']),
            ('date', '<=', data['end_date']),
        ]

        if data.get('location_id'):
            domain.append(('location_id', '=', data['location_id']))
        if data.get('user_id'):
            domain.append(('user_id', '=', data['user_id']))

        requests = self.env['user.material.request'].search(domain)

        lines = []
        for request in requests:
            for line in request.line_ids:
                if data.get('product_id') and line.product_id.id != data['product_id']:
                    continue
                lines.append({
                    'request_no': request.name,
                    'request_date': request.date,
                    'requested_by': request.user_id.name,
                    'department': request.department,
                    'location': request.location_id.complete_name if request.location_id else '',
                    'product': line.product_id.display_name,
                    'uom': line.product_uom_id.name,
                    'quantity': line.quantity,
                    'unit_price': line.unit_price,
                    'subtotal': line.price_subtotal,
                    'state': request.state,
                })

        return {
            'doc_model': 'material.request.reports.wizard',
            'lines': lines,
            'start_date': data['start_date'],
            'end_date': data['end_date'],
        }

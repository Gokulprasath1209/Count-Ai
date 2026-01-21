import logging
from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PurchaseOrderReportsWizard(models.TransientModel):
    _name = 'purchaseorder.reports.wizard'
    _description = "Purchase Order Reports Wizard"

    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')
    user_ids = fields.Many2many('res.users', string="Purchase Representative")
    partner_ids = fields.Many2many('res.partner', string="Vendors")
    purchase_stage = fields.Selection([
        ('rfq', 'Request for Quotation'),
        ('rfq_sent', 'RFQ Sent'),
        ('po', 'Purchase Order'),
    ], string='Stage', default='rfq')

    def action_print_pdf(self):
        if not self.start_date or not self.end_date:
            raise UserError("Please select both start and end dates.")

        data = {
            'start_date': fields.Date.to_string(self.start_date) if self.start_date else '',
            'end_date': fields.Date.to_string(self.end_date) if self.end_date else '',
            'user_ids': self.user_ids.ids,
            'partner_ids': self.partner_ids.ids,
            'purchase_stage': self.purchase_stage,
        }

        _logger.info(">>> Wizard Data Sent to Report: %s", data)

        return self.env.ref(
            'purchase_wizard.purchaseorder_reports_wizard_report_action_new'
        ).report_action(self, data=data)


class PurchaseOrderReport(models.AbstractModel):
    _name = 'report.purchase_wizard.template_purchase_report_qweb'
    _description = 'Purchase Order Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare data for the QWeb template."""
        _logger.info(">>> Report Called with Data: %s", data)

        if not data:
            raise UserError("No data received from wizard.")

        domain = []

        if data.get('start_date'):
            # Convert string back to date object for safe search
            start_date_obj = fields.Date.from_string(data['start_date'])
            domain.append(('date_order', '>=', start_date_obj))
        if data.get('end_date'):
            end_date_obj = fields.Date.from_string(data['end_date'])
            domain.append(('date_order', '<=', end_date_obj))

        if data.get('user_ids'):
            domain.append(('user_id', 'in', data['user_ids']))

        if data.get('partner_ids'):
            domain.append(('partner_id', 'in', data['partner_ids']))

        stage = data.get('purchase_stage')
        if stage == 'rfq':
            domain.append(('state', '=', 'draft'))
        elif stage == 'rfq_sent':
            domain.append(('state', '=', 'sent'))
        elif stage == 'po':
            domain.append(('state', 'in', ['purchase', 'done']))

        orders = self.env['purchase.order'].search(domain)
        _logger.info(">>> Found %s Orders for Domain: %s", len(orders), domain)

        purchase_value = []
        headers = ['S.No', 'PO Number', 'Vendor', 'PO Date', 'Code', 'Product', 'Qty', 'Received',
                   'Unit Price', 'Total']

        total_qty = 0
        total_received = 0
        total_amount = 0

        for order in orders:
            for line in order.order_line:
                purchase_value.append({
                    'order_id': order,
                    'partner_id': order.partner_id,
                    'date': order.date_order.strftime('%d-%m-%Y') if order.date_order else '',
                    'product': line.product_id,
                    'product_qty': line.product_qty,
                    'received_qty': line.qty_received,
                    'unit_price': line.price_unit,
                    'tax_price': line.price_total,
                })
                total_qty += line.product_qty
                total_received += line.qty_received
                total_amount += line.price_total

        return {
            'data': {
                'header': headers,
                'purchase_value': purchase_value,
                'total_qty': total_qty,
                'total_received': total_received,
                'total_amount': total_amount,
            },
            'user': self.env.user,
            'start_date': fields.Date.from_string(data['start_date']).strftime('%d-%m-%Y') if data.get('start_date') else '',
            'end_date': fields.Date.from_string(data['end_date']).strftime('%d-%m-%Y') if data.get('end_date') else '',
            'report_type': 'purchase',
        }

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
        """Trigger the PDF report and send user filters as data."""
        if not self.start_date or not self.end_date:
            raise UserError("Please select both start and end dates.")

        data = {
            'start_date': str(self.start_date),
            'end_date': str(self.end_date),
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

        # Date filter
        if data.get('start_date'):
            domain.append(('date_order', '>=', data['start_date']))
        if data.get('end_date'):
            domain.append(('date_order', '<=', data['end_date']))

        # User filter
        if data.get('user_ids'):
            domain.append(('user_id', 'in', data['user_ids']))

        # Vendor filter
        if data.get('partner_ids'):
            domain.append(('partner_id', 'in', data['partner_ids']))

        # Stage filter
        stage = data.get('purchase_stage')
        if stage == 'rfq':
            domain.append(('state', '=', 'draft'))
        elif stage == 'rfq_sent':
            domain.append(('state', '=', 'sent'))
        elif stage == 'po':
            domain.append(('state', 'in', ['purchase', 'done']))

        # Search matching POs
        orders = self.env['purchase.order'].search(domain)
        _logger.info(">>> Found %s Orders for Domain: %s", len(orders), domain)

        report_data = []
        for order in orders:
            for line in order.order_line:
                report_data.append({
                    'po_number': order.name,
                    'po_date': order.date_order.date() if order.date_order else '',
                    'responsible': order.user_id.name or '',
                    'vendor': order.partner_id.name or '',
                    'product_name': line.product_id.name or '',
                    'ordered_qty': line.product_qty,
                    'received_qty': line.qty_received,
                    'balance_qty': line.product_qty - line.qty_received,
                    'unit_price': line.price_unit,
                    'total_price': line.price_subtotal,
                    'expected_receipt_date': order.date_approve or '',
                    'delivery_status': (
                        'Fully Received' if line.qty_received >= line.product_qty else
                        'Partially Received' if 0 < line.qty_received < line.product_qty else
                        'Pending'
                    ),
                })

        return {
            'doc_ids': docids,
            'doc_model': 'purchaseorder.reports.wizard',
            'data': data,
            'report_data': report_data,
            'res_company': self.env.company,  # So logo works
        }

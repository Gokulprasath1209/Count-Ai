from odoo import api, fields, models
from odoo.exceptions import UserError


class PurchaseOrderReportsWizard(models.TransientModel):
    _name = 'purchaseorder.reports.wizard'
    _description = "Purchase Order Reports Wizard"

    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')
    user_ids = fields.Many2many('res.users', string="Purchase Representative")
    partner_ids = fields.Many2many('res.partner', string="Vendors")
    purchase_type = fields.Selection([
        ('local', 'Local Purchase'),
        ('import', 'Import Purchase'),
    ], string="Order Type")

    def action_print_pdf(self):
        data = {
            'start_date': self.start_date,
            'end_date': self.end_date,
            'user_ids': self.user_ids.ids,
            'partner_ids': self.partner_ids.ids,
            'purchase_type': self.purchase_type,
        }
        return self.env.ref('purchase_wizard.purchaseorder_reports_wizard_report_action').report_action(self, data=data)


class PurchaseOrderReport(models.AbstractModel):
    _name = 'report.your_module_name.template_purchase_report_qweb'
    _description = 'Purchase Report QWeb'

    @api.model
    def _get_report_values(self, docids, data=None):
        if not data:
            raise UserError("No data provided for the report.")

        domain = [
            ('date_order', '>=', data['start_date']),
            ('date_order', '<=', data['end_date']),
        ]

        if data.get('user_ids'):
            domain.append(('user_id', 'in', data['user_ids']))

        if data.get('partner_ids'):
            domain.append(('partner_id', 'in', data['partner_ids']))

        purchase_orders = self.env['purchase.order'].search(domain)

        report_data = []
        for order in purchase_orders:
            responsible = order.user_id.name or "No Responsible"
            vendor = order.partner_id.name or "No Vendor"
            for line in order.order_line:
                report_data.append({
                    'responsible': responsible,
                    'po_number': order.name,
                    'po_date': order.date_order.date() if order.date_order else '',
                    'vendor': vendor,
                    'product_code': line.product_id.default_code or '',
                    'product_name': line.product_id.name,
                    'ordered_qty': line.product_qty,
                    'received_qty': line.qty_received,
                    'balance_qty': line.product_qty - line.qty_received,
                    'unit_price': line.price_unit,
                    'total_price': line.price_subtotal,
                    'currency': order.currency_id.name or '',
                    'status': order.state.capitalize(),
                    'expected_receipt_date': order.date_approve or '',
                    'delivery_status': (
                        'Fully Received' if line.qty_received >= line.product_qty else
                        'Partially Received' if 0 < line.qty_received < line.product_qty else
                        'Pending'
                    ),
                })

        return {
            'doc_ids': docids,
            'doc_model': 'purchase.order',
            'data': data,
            'report_data': report_data,
        }

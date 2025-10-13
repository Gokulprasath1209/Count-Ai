from odoo import api, fields, models
from odoo.exceptions import UserError

class SaleOrderReportsWizard(models.TransientModel):
    _name = 'saleorder.reports.wizard'
    _description = "Sale Order Reports Wizard"

    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')
    user_ids = fields.Many2many('res.users', string="Salesperson")
    partner_ids = fields.Many2many('res.partner', string="Customers")
    sale_or_spare = fields.Selection([('sale', 'Sales'), ('spare', 'Spares')], string="Order Type")
    saleorder_stage = fields.Selection([
        ('rfq', 'Request for Quotation'),
        ('rfq_sent', 'RFQ Sent'),
        ('po', 'sale Order'),
    ], string='saleorder Stage', default='rfq')


    def action_print_pdf(self):
        data = {
            'start_date': self.start_date,
            'end_date': self.end_date,
            'user_ids': self.user_ids.ids,
            'sale_or_spare': self.sale_or_spare,
        }
        return self.env.ref('sale_extended.saleorder_reports_wizard_report_action_new').report_action(self, data=data)


class SalePersonReport(models.AbstractModel):
    _name = 'report.sale_extended.template_sale_report_qweb'
    _description = 'Sale Report QWeb'

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

        sale_orders = self.env['sale.order'].search(domain)

        report_data = []
        for order in sale_orders:
            salesperson = order.user_id.name or "No Salesperson"
            for line in order.order_line:
                report_data.append({
                    'salesperson': salesperson,
                    'so_number': order.name,
                    'so_date': order.date_order.date() if order.date_order else '',
                    'customer_name': order.partner_id.name,
                    'product_code': line.product_id.default_code or '',
                    'product_name': line.product_id.name,
                    'product_version': getattr(line.product_id, 'product_version', ''),
                    'ordered_qty': line.product_uom_qty,
                    'unit_price': line.price_unit,
                    'total_value': order.amount_total,
                    'status': (
                        'Closed' if order.state in ['sale', 'done'] and all(
                            l.qty_delivered >= l.product_uom_qty for l in order.order_line
                        ) else
                        'Partial' if any(
                            0 < l.qty_delivered < l.product_uom_qty for l in order.order_line
                        ) else
                        'Open'
                    ),
                    'approval_status': 'Y' if getattr(order, 'ceo_approved', False) else 'N',
                    'qty_delivered': line.qty_delivered,
                    # 'balance_qty': line.product_uom_qty - line.qty_delivered,
                    'expected_delivery_date': order.commitment_date.date() if order.commitment_date else '',
                    'delivery_status': (
                        'Overdue' if order.commitment_date and order.commitment_date.date() < fields.Date.today() and line.qty_delivered < line.product_uom_qty else
                        'Pending'
                    ),
                })

        return {
            'doc_ids': docids,
            'doc_model': 'sale.order',
            'data': data,
            'report_data': report_data,
        }

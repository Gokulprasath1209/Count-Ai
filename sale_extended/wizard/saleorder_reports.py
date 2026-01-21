from odoo import api, fields, models
from odoo.exceptions import UserError


class SaleOrderReportsWizard(models.TransientModel):
    _name = 'saleorder.reports.wizard'
    _description = "Sale Order Reports Wizard"

    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')
    user_ids = fields.Many2many('res.users', string="Salesperson")
    partner_ids = fields.Many2many('res.partner', string="Customers")
    sale_or_spare = fields.Selection([('sale', 'Sales'), ('spare', 'Spares')], string="Order Type", default='sale')
    stage = fields.Selection([
        ('dc_completed', 'Delivery Completed'),
        ('dc_pending', 'Delivery Pending'),
    ], string='Stage', default='dc_pending')

    def action_print_pdf(self):
        data = {
            'start_date': self.start_date,
            'end_date': self.end_date,
            'user_ids': self.user_ids.ids,
            'stage': self.stage,
            'sale_or_spare': self.sale_or_spare,
            'partner_ids': self.partner_ids.ids,
        }
        return self.env.ref('sale_extended.saleorder_reports_wizard_report_action_new').report_action(self, data=data)


class SalePersonReport(models.AbstractModel):
    _name = 'report.sale_extended.template_sale_report_qweb'
    _description = 'Sale Report QWeb'

    @api.model
    def _get_report_values(self, docids, data=None):
        value = {}
        sale_order = self.env['sale.order']
        print("==================================", type(data['user_ids']))

        start_date = data['start_date']
        end_date = data['end_date']
        domain = [('date_order', '>=', start_date), ('date_order', '<=', end_date)]

        if data['sale_or_spare'] == 'sale':
            domain.append(('sale_or_spare', '=', 'sale'))
        if data['sale_or_spare'] == 'spare':
            domain.append(('sale_or_spare', '=', 'spare'))
        if data['user_ids']:
            domain.append(('user_id', 'in', data['user_ids']))
        if data.get('partner_ids'):
            domain.append(('partner_id', 'in', data['partner_ids']))

        sales = sale_order.search(domain)
        sale_value = []
        headers = ['S.No', 'Order No', 'Customer', 'Order Date', 'sale Person', 'Code', 'Product', 'Qty', 'Delivered',
                   'Unit Price',
                   'Total']
        for i in sales:
            for line in i.order_line:
                sale_value.append({
                    'order_id': i,
                    'partner_id': i.partner_id,
                    'date': i.date_order,
                    'product': line.product_id,
                    'product_qty': line.product_uom_qty,
                    'delivery_qty': line.qty_delivered,
                    'unit_price': line.price_unit,
                    'tax_price': line.price_total,
                })
        value['header'] = headers
        value['sale_value'] = sale_value

        return {
            'data': value,
            'user': self.env.user.name,
            'start_date': start_date,
            'end_date': end_date,
            'report_type': data['sale_or_spare'],
        }

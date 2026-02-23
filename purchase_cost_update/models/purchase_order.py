from odoo import models, api, fields
from odoo.tools import float_compare

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def button_confirm(self):
        res = super(PurchaseOrder, self).button_confirm()
        for order in self:
            order._update_product_cost_from_po()
        return res

    def _update_product_cost_from_po(self):
        """ Update product standard price from purchase order lines """
        for line in self.order_line:
            if not line.product_id:
                continue

            # Get the price in the PO currency
            price_unit = line.price_unit

            # 1. Currency Conversion
            if line.currency_id and line.currency_id != line.company_id.currency_id:
                price_unit = line.currency_id._convert(
                    price_unit,
                    line.company_id.currency_id,
                    line.company_id,
                    line.date_order or fields.Date.today()
                )

            # 2. UoM Conversion
            # price_unit is for line.product_uom
            # We need price for line.product_id.uom_id
            if line.product_uom and line.product_uom != line.product_id.uom_id:
                price_unit = line.product_uom._compute_price(price_unit, line.product_id.uom_id)

            # 3. Update Standard Price and Sales Price (lst_price)
            product = line.product_id
            
            old_price = product.standard_price
            old_lst_price = product.lst_price
            currency = product.cost_currency_id or product.currency_id or self.env.company.currency_id
            precision = currency.decimal_places if currency else 2
            
            update_vals = {}
            log_messages = [f"Prices updated from Purchase Order <b>{self.name}</b>."]

            # Compare and update Cost
            if float_compare(price_unit, old_price, precision_digits=precision) != 0:
                 update_vals['standard_price'] = price_unit
                 log_messages.append(f"Old Cost: {old_price} {currency.symbol} &rarr; New Cost: {price_unit} {currency.symbol}")
                 
            # Compare and update Sales Price
            if float_compare(price_unit, old_lst_price, precision_digits=precision) != 0:
                 update_vals['list_price'] = price_unit
                 log_messages.append(f"Old Sales Price: {old_lst_price} {currency.symbol} &rarr; New Sales Price: {price_unit} {currency.symbol}")

            if update_vals:
                 product.sudo().write(update_vals)
                 
                 # 4. Log the update
                 product.message_post(body="<br/>".join(log_messages))

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    sl_no = fields.Integer(string='S.No', compute='_compute_sl_no', store=False)

    @api.depends('order_id.order_line')
    def _compute_sl_no(self):
        for order in self.mapped('order_id'):
            for i, line in enumerate(order.order_line, start=1):
                line.sl_no = i

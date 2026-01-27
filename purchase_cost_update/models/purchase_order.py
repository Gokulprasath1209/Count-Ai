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

            # 3. Update Standard Price
            product = line.product_id
            
            old_price = product.standard_price
            # Compare with currency precision
            if float_compare(price_unit, old_price, precision_digits=product.cost_currency_id.decimal_places if product.cost_currency_id else 2) != 0:
                 product.sudo().write({'standard_price': price_unit})

                 # 4. Log the update
                 currency = product.cost_currency_id or product.currency_id or self.env.company.currency_id
                 message = (
                     f"Cost updated from Purchase Order <b>{self.name}</b>.<br/>"
                     f"Old Cost: {old_price} {currency.symbol}<br/>"
                     f"New Cost: {price_unit} {currency.symbol}"
                 )
                 product.message_post(body=message)

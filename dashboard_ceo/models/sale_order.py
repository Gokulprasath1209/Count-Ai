from odoo import models, fields, api, _

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    forecast_warning = fields.Html(compute='_compute_forecast_warning')

    @api.depends('order_line.product_id', 'order_line.product_uom_qty', 'commitment_date', 'date_order')
    def _compute_forecast_warning(self):
        for order in self:
            warning_msgs = []
            target_date = order.commitment_date or order.date_order or fields.Datetime.now()
            
            for line in order.order_line:
                if line.product_id.type == 'consu' or not line.product_id:
                    continue
                
                on_hand = line.product_id.with_context(location=order.warehouse_id.lot_stock_id.id).qty_available
                domain = [
                    ('product_id', '=', line.product_id.id),
                    ('state', 'in', ('confirmed', 'assigned', 'waiting')),
                    ('date', '<=', target_date)
                ]
                moves = self.env['stock.move'].search(domain)
                
                incoming = sum(m.product_uom_qty for m in moves if m.location_dest_id.id == order.warehouse_id.lot_stock_id.id)
                outgoing = sum(m.product_uom_qty for m in moves if m.location_id.id == order.warehouse_id.lot_stock_id.id)
                
                forecasted_qty = on_hand + incoming - outgoing
                
                line_qty_in_product_uom = line.product_uom._compute_quantity(line.product_uom_qty, line.product_id.uom_id)
                
                if forecasted_qty < line_qty_in_product_uom:
                    warning_msgs.append(_("Product <b>%s</b> has insufficient forecasted stock (%.2f %s) for the scheduled date.") % (line.product_id.display_name, forecasted_qty, line.product_id.uom_id.name))
            
            if warning_msgs:
                order.forecast_warning = "<div class='alert alert-warning' role='alert'>" + "<br/>".join(warning_msgs) + "</div>"
            else:
                order.forecast_warning = False

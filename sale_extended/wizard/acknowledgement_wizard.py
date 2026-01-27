from odoo import models, fields, api, _

class SaleOrderAcknowledgementWizard(models.TransientModel):
    _name = 'sale.order.acknowledgement.wizard'
    _description = 'Sale Order Acknowledgement Wizard'

    order_id = fields.Many2one('sale.order', string='Order', required=True)
    dest_user_id = fields.Many2one('res.users', string='Tagged User', required=False)
    is_return_to_store = fields.Boolean(string='Return directly to Store', default=False)
    is_returnable = fields.Boolean(
        string="Order is Returnable",
        compute='_compute_is_returnable'
    )

    @api.depends('order_id.product_return')
    def _compute_is_returnable(self):
        for wizard in self:
            wizard.is_returnable = (wizard.order_id.product_return == 'returnable')

    line_ids = fields.One2many(
        'sale.order.acknowledgement.wizard.line', 'wizard_id', string='Products'
    )

    @api.model
    def default_get(self, fields):
        res = super(SaleOrderAcknowledgementWizard, self).default_get(fields)
        active_id = self._context.get('active_id')
        if active_id:
            order = self.env['sale.order'].browse(active_id)
            res.update({'order_id': order.id})
            lines = []
            for line in order.order_line:
                if line.product_id:
                    lines.append((0, 0, {
                        'product_id': line.product_id.id,
                        'quantity': line.product_uom_qty,
                    }))
            res.update({'line_ids': lines})
        return res

    def action_confirm(self):
        self.ensure_one()
        if not self.is_return_to_store and not self.dest_user_id:
            raise UserError(_("Please select a Tagged User or check Return directly to Store."))

        line_vals = []
        picking_lines = []
        for line in self.line_ids:
            if line.product_id and line.quantity > 0:
                line_vals.append((0, 0, {
                    'product_id': line.product_id.id,
                    'quantity': line.quantity,
                }))
                if self.is_return_to_store:
                    picking_lines.append((0, 0, {
                        'name': line.product_id.name,
                        'product_id': line.product_id.id,
                        'product_uom_qty': line.quantity,
                        'product_uom': line.product_id.uom_id.id,
                        'location_id': self.env.ref('stock.stock_location_customers').id, # From Customer
                        'location_dest_id': self.env['stock.location'].search([('complete_name', '=', 'CW/Store')], limit=1).id or self.env.ref('stock.stock_location_stock').id,
                    }))

        if not line_vals:
            raise UserError(_("Please specify quantities for at least one product."))

        if self.is_return_to_store:
            # Create Incoming Picking
            picking_type = self.env['stock.picking.type'].search([('code', '=', 'incoming')], limit=1)
            picking = self.env['stock.picking'].create({
                'partner_id': self.order_id.partner_id.id,
                'picking_type_id': picking_type.id,
                'location_id': self.env.ref('stock.stock_location_customers').id,
                'location_dest_id': self.env['stock.location'].search([('complete_name', '=', 'CW/Store')], limit=1).id or self.env.ref('stock.stock_location_stock').id,
                'origin': self.order_id.name + " (Direct Return)",
                'move_ids_without_package': picking_lines,
            })
            picking.action_confirm()

            # Create Acknowledgement (marked as received since it goes to store)
            self.env['sale.order.acknowledgement'].create({
                'order_id': self.order_id.id,
                'source_user_id': self.env.user.id,
                'is_return_to_store': True,
                'state': 'received',
                'line_ids': line_vals
            })
        else:
            # Normal Transfer
            self.env['sale.order.acknowledgement'].create({
                'order_id': self.order_id.id,
                'source_user_id': self.env.user.id,
                'dest_user_id': self.dest_user_id.id,
                'state': 'pending',
                'line_ids': line_vals
            })
        return {'type': 'ir.actions.act_window_close'}


class SaleOrderAcknowledgementWizardLine(models.TransientModel):
    _name = 'sale.order.acknowledgement.wizard.line'
    _description = 'Sale Order Acknowledgement Wizard Line'

    wizard_id = fields.Many2one('sale.order.acknowledgement.wizard', string='Wizard')
    product_id = fields.Many2one('product.product', string='Product')
    quantity = fields.Float(string='Received Quantity')

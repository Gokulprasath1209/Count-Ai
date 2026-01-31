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
        picking_lines_dict = {}
        for line in self.line_ids:
            if line.product_id and line.quantity > 0:
                line_vals.append((0, 0, {
                    'product_id': line.product_id.id,
                    'quantity': line.quantity,
                    'serial_numbers': line.serial_numbers,
                }))
                if self.is_return_to_store:
                    key = (line.product_id.id, line.quantity)
                    if key not in picking_lines_dict:
                         picking_lines_dict[key] = {
                            'product_id': line.product_id,
                            'qty': 0.0,
                            'serials': []
                         }
                    picking_lines_dict[key]['qty'] += line.quantity
                    if line.serial_numbers:
                        # Split by comma or newline and strip whitespace
                        serials = [s.strip() for s in line.serial_numbers.replace(',', '\n').split('\n') if s.strip()]
                        picking_lines_dict[key]['serials'].extend(serials)

        if not line_vals:
            raise UserError(_("Please specify quantities for at least one product."))

        if self.is_return_to_store:
            picking_type = self.env['stock.picking.type'].search([('code', '=', 'incoming')], limit=1)
            
            stock_moves = []
            for key, data in picking_lines_dict.items():
                product = data['product_id']
                qty = data['qty']
                serials = data['serials']
                
                move_vals = {
                    'name': product.name,
                    'product_id': product.id,
                    'product_uom_qty': qty,
                    'product_uom': product.uom_id.id,
                    'location_id': self.env.ref('stock.stock_location_customers').id,
                    'location_dest_id': self.env['stock.location'].search([('complete_name', '=', 'CW/Store')], limit=1).id or self.env.ref('stock.stock_location_stock').id,
                }

                stock_moves.append((0, 0, move_vals))

            picking = self.env['stock.picking'].create({
                'partner_id': self.order_id.partner_id.id,
                'picking_type_id': picking_type.id,
                'location_id': self.env.ref('stock.stock_location_customers').id,
                'location_dest_id': self.env['stock.location'].search([('complete_name', '=', 'CW/Store')], limit=1).id or self.env.ref('stock.stock_location_stock').id,
                'origin': self.order_id.name + " (Direct Return)",
                'move_ids': stock_moves, 
            })

            picking.action_confirm() # Confirm to generate move lines placeholders if any (or just sets state)

            for move in picking.move_ids:
                data = None
                for k, v in picking_lines_dict.items():
                    if v['product_id'].id == move.product_id.id:
                        data = v
                        break
                
                if data and data['serials'] and move.product_id.tracking != 'none':

                    lines_to_create = []
                    current_serials = data['serials']

                    for sn in current_serials:
                        lines_to_create.append({
                            'move_id': move.id,
                            'product_id': move.product_id.id,
                            'product_uom_id': move.product_uom.id,
                            'quantity': 1.0,
                            'lot_name': sn,
                            'location_id': move.location_id.id,
                            'location_dest_id': move.location_dest_id.id,
                        })
                    
                    if lines_to_create:
                         self.env['stock.move.line'].create(lines_to_create)

            self.env['sale.order.acknowledgement'].create({
                'order_id': self.order_id.id,
                'source_user_id': self.env.user.id,
                'is_return_to_store': True,
                'state': 'received',
                'line_ids': line_vals
            })
        else:
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
    serial_numbers = fields.Text(string='Serial Numbers', help="Enter serial numbers separated by commas or new lines")

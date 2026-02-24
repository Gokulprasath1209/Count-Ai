from odoo import api, fields, models
from odoo.exceptions import UserError


class InventoryWizardReport(models.TransientModel):
    _name = "inventory.wizard.report"
    _description = "Inventory Wizard Report"

    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    code = fields.Selection([('incoming', 'Receipt'), ('outgoing', 'Delivery'), ('internal', 'Internal Transfer')],
                            'Type of Operation', default='incoming', required=True)
    location_id = fields.Many2one('stock.location', string="Warehouse Location", domain=[('usage', '=', 'internal')])
    stock_cost = fields.Float(string="On-hand Stock Cost", compute="_compute_stock_cost")

    @api.depends('location_id')
    def _compute_stock_cost(self):
        for record in self:
            if record.location_id:
                company_id = self.env.company.id
                location_id = record.location_id.id
                
                # Get all child internal locations
                child_locs = self.env['stock.location'].search([
                    ('id', 'child_of', location_id),
                    ('usage', '=', 'internal')
                ]).ids
                
                if not child_locs:
                    record.stock_cost = 0.0
                    continue

                # SQL logic matching CEO Dashboard for 100% consistency
                # This counts total value of products that have on-hand stock in the selected location
                sql = """
                    SELECT COALESCE(SUM(svl.remaining_value), 0.0)
                    FROM stock_valuation_layer svl
                    WHERE svl.company_id = %s
                      AND svl.remaining_qty > 0
                      AND svl.product_id IN (
                          SELECT DISTINCT sq.product_id
                          FROM stock_quant sq
                          WHERE sq.company_id = %s
                            AND sq.quantity > 0
                            AND sq.location_id IN %s
                      )
                """
                self.env.cr.execute(sql, (company_id, company_id, tuple(child_locs)))
                result = self.env.cr.fetchone()
                record.stock_cost = float(result[0]) if result and result[0] is not None else 0.0
            else:
                record.stock_cost = 0.0

    def action_view_on_hand(self):
        self.ensure_one()
        if not self.location_id:
            raise UserError("Please select a Warehouse Location first.")
        
        return {
            'name': 'On-hand Stocks',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.quant',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': [('location_id', 'child_of', self.location_id.id), ('quantity', '>', 0)],
            'context': {'search_default_internal_loc': 1, 'search_default_productgroup': 1},
            'target': 'current',
        }

    def action_print_pdf(self):
        data = {
            'ids': self.ids,
            'model': self._name,
            'code': self.code,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'location_id': self.location_id.id if self.location_id else False,
        }
        return self.env.ref(
            'inventory_report.inventory_stock_report_action'
        ).report_action(self, data=data)


class InventoryStockReportPDF(models.AbstractModel):
    _name = 'report.inventory_report.template_inventory_stock_report_qweb'
    _description = "Inventory Movement PDF Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        if not data:
            raise UserError("No data received for Inventory Report")
        
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        domain = [('state', '=', 'done')]
        if start_date:
            if isinstance(start_date, str):
                start_date = fields.Date.from_string(start_date)
            # Convert Date to Datetime (start of day)
            start_dt = fields.Datetime.to_datetime(start_date)
            domain.append(('date', '>=', start_dt))

        # Ensure inclusive date range (end of day for end_date)
        if end_date:
            if isinstance(end_date, str):
                end_date = fields.Date.from_string(end_date)
            # Convert Date to Datetime (end of day)
            end_dt = fields.Datetime.to_datetime(end_date).replace(hour=23, minute=59, second=59)
            domain.append(('date', '<=', end_dt))
        
        if data.get('location_id'):
            location_id = data['location_id']
            if data['code'] == 'incoming':
                domain.append(('location_dest_id', 'child_of', location_id))
            elif data['code'] == 'outgoing':
                domain.append(('location_id', 'child_of', location_id))
            elif data['code'] == 'internal':
                domain.append('|')
                domain.append(('location_id', 'child_of', location_id))
                domain.append(('location_dest_id', 'child_of', location_id))

        val = self.sudo().env['stock.move'].search(domain, order='date desc')
        datas = []
        for i in val:
            # Logic for 100% record inclusion based on Location Usage
            # This captures moves without picking_id (adjustments, production, etc.)
            source_internal = i.location_id.usage == 'internal'
            dest_internal = i.location_dest_id.usage == 'internal'
            
            is_match = False
            if data['code'] == 'incoming' and not source_internal and dest_internal:
                is_match = True
            elif data['code'] == 'outgoing' and source_internal and not dest_internal:
                is_match = True
            elif data['code'] == 'internal' and source_internal and dest_internal:
                is_match = True
            
            if not is_match:
                continue

            lot_names = ', '.join(
                i.move_line_ids.mapped('lot_id.name')
            ) if i.move_line_ids else ''
            
            values = {
                'date': i.date,
                'product': i.product_id.display_name,
                'qty': i.product_uom_qty,
                'uom': i.product_uom.name,
                'price': i.price_unit or i.product_id.standard_price,
                'reference': i.picking_id.name or i.reference or i.name,
                'serial': lot_names,
                'lot': lot_names,
            }

            if data['code'] == 'incoming':
                values.update({
                    'vendor': i.picking_id.partner_id.name or i.location_id.complete_name or 'NIL',
                    'purchase_no': i.picking_id.origin or i.origin or '',
                    'dept': i.location_dest_id.complete_name or '',
                })
            elif data['code'] == 'outgoing':
                values.update({
                    'customer': i.picking_id.partner_id.name or i.location_dest_id.complete_name or 'NIL',
                    'user': i.picking_id.user_id.name or i.create_uid.name or 'NIL',
                })
            elif data['code'] == 'internal':
                values.update({
                    'Source Location': i.location_id.complete_name or '',
                    'Destination Location': i.location_dest_id.complete_name or '',
                })

            datas.append(values)

        return {
            'doc_model': 'inventory.wizard.report',
            'code': data['code'],
            'lines': datas,
        }

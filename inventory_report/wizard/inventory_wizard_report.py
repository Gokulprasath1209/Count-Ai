from odoo import api, fields, models
from odoo.exceptions import UserError


class InventoryWizardReport(models.TransientModel):
    _name = "inventory.wizard.report"
    _description = "Inventory Wizard Report"

    start_date = fields.Datetime(string="Start Date")
    end_date = fields.Datetime(string="End Date")
    code = fields.Selection([('incoming', 'Receipt'), ('outgoing', 'Delivery'), ('internal', 'Internal Transfer')], 'Type of Operation', default='incoming', required=True)


    def action_print_pdf(self):
        data = {
            'ids': self.ids,
            'model': self._name,
            'code': self.code,
            'start_date': self.start_date,
            'end_date': self.end_date,
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
        val = self.sudo().env['stock.move'].search([('date','>=',data['start_date']),('date','<=',data['end_date'])])
        datas=[]
        for i in val:
            if i.picking_id.picking_type_id.code == 'incoming' and data['code'] == 'incoming':
                lot_names = ', '.join(
                    i.move_line_ids.mapped('lot_id.name')
                ) if i.move_line_ids else ''
                values = {
                    'date': i.date,
                    'vendor': i.picking_id.partner_id.name if i.picking_id.partner_id else 'NIL',
                    'purchase_no': i.picking_id.origin or '',
                    'product': i.product_id.display_name,
                    'qty': i.product_uom_qty,
                    'uom': i.product_uom.name,
                    'serial': lot_names,
                    'lot': lot_names,

                    'reference': i.reference or i.name,

                    'dept': i.location_dest_id.complete_name if i.location_dest_id else '',

                    'price': i.price_unit or i.product_id.standard_price,
                }

                datas.append(values)
            elif i.picking_id.picking_type_id.code == 'outgoing'and data['code'] == 'outgoing':
                lot_names = ', '.join(
                    i.move_line_ids.mapped('lot_id.name')
                ) if i.move_line_ids else ''
                values = {
                    'date': i.date,
                    'customer': i.picking_id.partner_id.name if i.picking_id.partner_id else 'NIL',
                    'product': i.product_id.display_name,
                    'qty': i.product_uom_qty,
                    'uom': i.product_uom.name,
                    'price': i.price_unit or i.product_id.standard_price,
                    'user': i.picking_id.user_id.name if i.picking_id.user_id else 'NIL',

                }
                datas.append(values)

            elif i.picking_id.picking_type_id.code == 'internal' and data['code'] == 'internal':
                lot_names = ', '.join(
                    i.move_line_ids.mapped('lot_id.name')
                ) if i.move_line_ids else ''
                values = {
                    'date': i.date,
                    'reference': i.reference or i.name,
                    'product': i.product_id.display_name,
                    'qty': i.product_uom_qty,
                    'price': i.price_unit or i.product_id.standard_price,
                    'Source Location': i.location_id.complete_name if i.location_id else '',
                    'Destination Location': i.location_dest_id.complete_name if i.location_dest_id else '',
                }

                datas.append(values)



        return {
            'doc_model': 'inventory.wizard.report',
            'code': data['code'],
            'lines': datas,
        }

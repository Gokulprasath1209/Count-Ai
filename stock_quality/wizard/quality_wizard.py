from odoo import models, fields, api
from odoo.exceptions import UserError


class QualityReportWizard(models.TransientModel):
    _name = 'quality.report.wizard'
    _description = 'Quality Report Wizard'

    report_type = fields.Selection([
        ('inward_qc', 'INWARD QC REPORT'),
        ('vendor_quality', 'VENDOR QUALITY REPORT'),
        ('fg_qc', 'FG QC REPORT')
    ], string="Report Type", required=True, default='inward_qc')

    start_date = fields.Date(string="Start Date", required=True)
    end_date = fields.Date(string="End Date", required=True)

    def action_print_report(self):
        data = {
            'ids': self.ids,
            'model': self._name,
            'report_type': self.report_type,
            'start_date': self.start_date,
            'end_date': self.end_date,
        }

        return self.env.ref(
            'stock_quality.action_quality_report'
        ).report_action(self, data=data)


class QualityReportPDF(models.AbstractModel):
    _name = 'report.stock_quality.template_quality_report_qweb'
    _description = "Quality Reports PDF (Inward QC + Vendor Quality)"

    @api.model
    def _get_report_values(self, docids, data=None):
        if not data:
            raise UserError("No data received for Quality Report")

        report_type = data.get('report_type')
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        moves = self.env['stock.move'].sudo().search([
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('picking_id.picking_type_id.code', '=', 'incoming'),
        ])

        datas = []

        if report_type == 'inward_qc':

            for move in moves:
                quality_test = self.env['quality.test'].search([
                    ('purchase_ids', 'in', move.picking_id.purchase_id.id)
                ], limit=1)

                for line in move.move_line_ids:
                    open_qc = self.env['open.product.quality'].search([
                        ('quality_test_line_id.quality_id', '=', quality_test.id),
                        ('product_id', '=', move.product_id.id)
                    ], limit=1)

                    qty_received = move.product_uom_qty
                    qty_accepted = open_qc.quality_accept_count if open_qc else 0
                    qty_rejected = qty_received - qty_accepted

                    if qty_accepted == qty_received and qty_received > 0:
                        qc_result = 'Pass'

                    elif qty_accepted == 0 and qty_rejected == qty_received:
                        qc_result = 'Reject'

                    else:
                        qc_result = 'Partial'

                    datas.append({
                        'grn_no': move.picking_id.name,
                        'po_no': move.picking_id.origin or '',
                        'vendor': move.picking_id.partner_id.name or '',
                        'item': f"{move.product_id.default_code or ''} - {move.product_id.display_name}",
                        'lot': line.lot_id.name if line.lot_id else '',
                        'qty_received': qty_received,
                        'qty_accepted': qty_accepted,
                        'qty_rejected': qty_rejected,
                        'qc_result': qc_result,
                        'qc_date': quality_test.write_date if quality_test else '',
                        'inspector': quality_test.user_id.name if quality_test else '',
                    })


        elif report_type == 'vendor_quality':

            vendor_map = {}

            for move in moves:
                vendor = move.picking_id.partner_id
                if not vendor:
                    continue

                vendor_id = vendor.id

                if vendor_id not in vendor_map:
                    vendor_map[vendor_id] = {
                        'vendor': vendor.name,
                        'deliveries': set(),
                        'qty_received': 0.0,
                        'qty_accepted': 0.0,
                        'qty_rejected': 0.0,
                        'rejection_reasons': set(),
                    }

                vendor_map[vendor_id]['deliveries'].add(move.picking_id.id)
                vendor_map[vendor_id]['qty_received'] += move.product_uom_qty

                quality_test = self.env['quality.test'].search([
                    ('purchase_ids', 'in', move.picking_id.purchase_id.id)
                ], limit=1)

                open_qc = self.env['open.product.quality'].search([
                    ('quality_test_line_id.quality_id', '=', quality_test.id),
                    ('product_id', '=', move.product_id.id)
                ], limit=1)

                accepted = open_qc.quality_accept_count if open_qc else 0.0
                rejected = move.product_uom_qty - accepted

                vendor_map[vendor_id]['qty_accepted'] += accepted
                vendor_map[vendor_id]['qty_rejected'] += rejected

                if rejected > 0 and open_qc:
                    reason_names = []

                    if hasattr(open_qc, 'reason_id') and open_qc.reason_id:
                        reason_names.append(open_qc.reason_id.name)

                    elif hasattr(open_qc, 'reason_ids') and open_qc.reason_ids:
                        reason_names.extend(open_qc.reason_ids.mapped('name'))

                    if reason_names:
                        vendor_map[vendor_id]['rejection_reasons'].update(reason_names)
                    else:
                        vendor_map[vendor_id]['rejection_reasons'].add('Rejected')

            for vendor_data in vendor_map.values():
                total_received = vendor_data['qty_received']
                total_rejected = vendor_data['qty_rejected']

                rejection_percent = (
                    (total_rejected / total_received) * 100
                    if total_received else 0.0
                )

                datas.append({
                    'vendor': vendor_data['vendor'],
                    'no_of_deliveries': len(vendor_data['deliveries']),
                    'qty_received': total_received,
                    'qty_accepted': vendor_data['qty_accepted'],
                    'qty_rejected': total_rejected,
                    'rejection_percent': round(rejection_percent, 2),
                    'major_rejection_reasons': ', '.join(
                        vendor_data['rejection_reasons']
                    ) or 'NIL',
                })



        elif report_type == 'fg_qc':
            fg_qcs = self.env['quality.test'].sudo().search([
                ('write_date', '>=', start_date),
                ('write_date', '<=', end_date),
            ])
            for qc in fg_qcs:
                mo = False
                if hasattr(qc, 'production_id') and qc.production_id:
                    mo = qc.production_id
                elif hasattr(qc, 'picking_id') and qc.picking_id:
                    mo = self.env['mrp.production'].search(
                        [('origin', '=', qc.picking_id.name)],
                        limit=1
                    )
                qty_produced = getattr(mo, 'qty_produced', 0.0) if mo else 0.0
                qty_passed = getattr(qc, 'qty_pass', 0.0)
                qty_rejected = getattr(qc, 'qty_fail', 0.0)
                datas.append({
                    'fgqc_no': qc.name,
                    'mo_no': mo.name if mo else '',
                    'product': (
                        f"{mo.product_id.default_code or ''} - {mo.product_id.display_name}"
                        if mo and mo.product_id else ''
                    ),
                    'product_version': getattr(mo.product_id, 'version', '') if mo else '',
                    'lot': mo.lot_producing_id.name if mo and mo.lot_producing_id else '',
                    'qty_produced': getattr(mo, 'qty_produced', 0.0) if mo else 0.0,
                    'qty_passed': getattr(qc, 'qty_pass', 0.0),
                    'qty_rejected': getattr(qc, 'qty_fail', 0.0),
                    'qc_date': qc.write_date,
                    'inspector': qc.user_id.name if qc.user_id else '',
                    'remarks': getattr(qc, 'note', '') or getattr(qc, 'remarks', '') or '',
                })

        return {
            'doc_model': 'quality.report.wizard',
            'lines': datas,
            'report_type': report_type,
            'start_date': start_date,
            'end_date': end_date,
        }

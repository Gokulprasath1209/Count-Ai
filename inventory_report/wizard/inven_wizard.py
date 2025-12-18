import logging
from odoo import api, fields, models
from odoo.exceptions import UserError



class InventoryReportsWizard(models.TransientModel):
    _name = 'inventory.reports.wizard'
    _description = "Inventory Reports Wizard"

    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True)

    product_ids = fields.Many2many('product.product', string="Products")

    shipment_type = fields.Selection([
        ('inward', 'Inward'),
        ('internal', 'Internal Transfer'),
        ('outward', 'Outward'),
    ], string="Shipment Type", required=True)

    product_type = fields.Selection(
        [
            ('rnd', 'RnD'),
            ('moving', 'Moving'),
            ('non_moving', 'Non Moving'),
        ],
        string="Product Type"
    )

    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string="Warehouse",
        required=False,
        help="Required to determine internal stock location"
    )

    def action_print_pdf(self):
        if not self.start_date or not self.end_date:
            raise UserError("Please select both start and end dates.")

        internal_loc = self.warehouse_id.lot_stock_id.id

        data = {
            'start_date': str(self.start_date),
            'end_date': str(self.end_date),
            'product_ids': self.product_ids.ids,
            'shipment_type': self.shipment_type,
            'product_type': self.product_type,
            'warehouse_id': self.warehouse_id.id,
            'internal_loc': internal_loc,
        }

        _logger.info(">>> Inventory Report Data Sent to PDF: %s", data)

        return self.env.ref(
            'inventory_report.inventory_inward_report_action'
        ).report_action(self, data=data)


class InventoryReportPDF(models.AbstractModel):
    _name = 'report.inventory_report.template_inventory_report_qweb'
    _description = "Inventory Movement PDF Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        if not data:
            raise UserError("No data received for Inventory Report")

        start_date = data.get("start_date")
        end_date = data.get("end_date")
        product_ids = data.get("product_ids") or []
        shipment_type = data.get("shipment_type")
        internal_loc = data.get("internal_loc")

        report_data = []

        if shipment_type == "inward":
            rows = self._get_inward(start_date, end_date, product_ids, internal_loc)
        elif shipment_type == "outward":
            rows = self._get_outward(start_date, end_date, product_ids, internal_loc)
        elif shipment_type == "internal":
            rows = self._get_internal(start_date, end_date, product_ids)
        else:
            rows = []

        for row in rows:
            product_id = row.get("product_id")
            on_hand = self._get_on_hand_qty(product_id, internal_loc)

            report_data.append({
                'product_name': row.get("product_name"),
                'product_id': product_id,
                'qty': row.get("qty"),
                'on_hand_qty': on_hand,

                'partner_name': row.get("partner_name") or "",
                'dest_location': row.get("dest_location") or "",

                'shipment_type': shipment_type.capitalize(),
            })

        return {
            'doc_ids': docids,
            'doc_model': 'inventory.reports.wizard',
            'data': data,
            'report_data': report_data,
            'shipment_type': shipment_type,
            'start_date': start_date,
            'end_date': end_date,
        }

    def _get_inward(self, start, end, products, internal_loc):
        query = """
            SELECT
                sm.date::date                         AS date,
                rp.name                               AS vendor,
                po.name                               AS purchase_no,
                pt.name                               AS product,
                SUM(sml.qty_done)                     AS inward_qty,
                uom.name                              AS uom,
                sml.lot_id                            AS serial_no,
                lot.name                              AS lot_no,
                sm.reference                         AS reference,
                dept.name                             AS dept,
                pol.price_unit                       AS price

            FROM stock_move sm
            JOIN stock_move_line sml ON sml.move_id = sm.id
            JOIN product_product pp ON pp.id = sm.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            JOIN uom_uom uom ON uom.id = sml.product_uom_id

            LEFT JOIN stock_production_lot lot ON lot.id = sml.lot_id
            LEFT JOIN res_partner rp ON rp.id = sm.partner_id

            LEFT JOIN purchase_order_line pol ON pol.id = sm.purchase_line_id
            LEFT JOIN purchase_order po ON po.id = pol.order_id

            LEFT JOIN hr_department dept ON dept.id = sm.department_id

            JOIN stock_location src ON src.id = sm.location_id
            JOIN stock_location dest ON dest.id = sm.location_dest_id

            WHERE sm.state = 'done'
              AND src.usage != 'internal'
              AND dest.usage = 'internal'
              AND sm.location_dest_id = %s
              AND sm.date BETWEEN %s AND %s
        """

        params = [internal_loc, start, end]

        if products:
            query += " AND sm.product_id IN %s"
            params.append(tuple(products))

        query += """
            GROUP BY
                sm.date,
                rp.name,
                po.name,
                pt.name,
                uom.name,
                sml.lot_id,
                lot.name,
                sm.reference,
                dept.name,
                pol.price_unit
            ORDER BY sm.date, pt.name
        """

        self.env.cr.execute(query, tuple(params))
        return self.env.cr.dictfetchall()

    def _get_outward(self, start, end, products, internal_loc):
        query = """
            SELECT
                sm.date::date                    AS date,
                sm.reference                    AS ir_sequence,
                rp.name                         AS customer,
                pt.name                         AS product,
                SUM(sml.qty_done)               AS qty,
                uom.name                        AS uom,
                COALESCE(pol.price_unit, 0)     AS price,
                dept.name                       AS department,
                ru.name                         AS user

            FROM stock_move sm
            JOIN stock_move_line sml ON sml.move_id = sm.id
            JOIN product_product pp ON pp.id = sm.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            JOIN uom_uom uom ON uom.id = sml.product_uom_id

            LEFT JOIN res_partner rp ON rp.id = sm.partner_id
            LEFT JOIN purchase_order_line pol ON pol.id = sm.purchase_line_id
            LEFT JOIN hr_department dept ON dept.id = sm.department_id
            LEFT JOIN res_users ru ON ru.id = sm.create_uid

            JOIN stock_location src ON src.id = sm.location_id
            JOIN stock_location dest ON dest.id = sm.location_dest_id

            WHERE sm.state = 'done'
              AND src.usage = 'internal'
              AND dest.usage != 'internal'
              AND sm.location_id = %s
              AND sm.date BETWEEN %s AND %s
        """

        params = [internal_loc, start, end]

        if products:
            query += " AND sm.product_id IN %s"
            params.append(tuple(products))

        query += """
            GROUP BY
                sm.date,
                sm.reference,
                rp.name,
                pt.name,
                uom.name,
                pol.price_unit,
                dept.name,
                ru.name
            ORDER BY sm.date, pt.name
        """

        self.env.cr.execute(query, tuple(params))
        return self.env.cr.dictfetchall()

    def _get_internal(self, start, end, products):
        query = """
            SELECT
                sm.date::date                     AS date,
                sm.reference                     AS reference_id,
                pt.name                          AS product,
                SUM(sml.qty_done)                AS qty,
                COALESCE(pol.price_unit, 0)      AS price,
                src.complete_name                AS source_location,
                dest.complete_name               AS destination_location,
                sm.state                         AS status

            FROM stock_move sm
            JOIN stock_move_line sml ON sml.move_id = sm.id
            JOIN product_product pp ON pp.id = sm.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id

            JOIN stock_location src ON src.id = sm.location_id
            JOIN stock_location dest ON dest.id = sm.location_dest_id

            LEFT JOIN purchase_order_line pol ON pol.id = sm.purchase_line_id

            WHERE sm.state = 'done'
              AND src.usage = 'internal'
              AND dest.usage = 'internal'
              AND sm.date BETWEEN %s AND %s
        """

        params = [start, end]

        if products:
            query += " AND sm.product_id IN %s"
            params.append(tuple(products))

        query += """
            GROUP BY
                sm.date,
                sm.reference,
                pt.name,
                src.complete_name,
                dest.complete_name,
                sm.state,
                pol.price_unit
            ORDER BY sm.date, pt.name
        """

        self.env.cr.execute(query, tuple(params))
        return self.env.cr.dictfetchall()

    def _get_on_hand_qty(self, product_id, internal_loc):
        self.env.cr.execute("""
                SELECT COALESCE(SUM(quantity), 0)
                FROM stock_quant
                WHERE product_id = %s AND location_id = %s
            """, (product_id, internal_loc))

        qty = self.env.cr.fetchone()
        return qty[0] if qty else 0

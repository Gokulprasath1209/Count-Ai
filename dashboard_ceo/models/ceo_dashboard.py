from odoo import models, fields, api, _, tools
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import pytz

class CEODashboard(models.Model):
    _name = 'ceo.dashboard'
    _description = 'CEO Dashboard'

    def init(self):
        super().init()
        # Create core analytical composite indexes for fast filtering
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_sale_order_dsbd ON sale_order (date_order, company_id, state, partner_id);
            CREATE INDEX IF NOT EXISTS idx_purchase_order_dsbd ON purchase_order (date_approve, company_id, state, partner_id);
            CREATE INDEX IF NOT EXISTS idx_account_move_dsbd ON account_move (invoice_date, company_id, state, partner_id);
            CREATE INDEX IF NOT EXISTS idx_stock_move_dsbd ON stock_move (date, company_id, state, location_id, product_id);
            CREATE INDEX IF NOT EXISTS idx_svl_company ON stock_valuation_layer (company_id);
            CREATE INDEX IF NOT EXISTS idx_svl_product ON stock_valuation_layer (product_id);
            CREATE INDEX IF NOT EXISTS idx_svl_remaining ON stock_valuation_layer (remaining_qty, remaining_value);
            CREATE INDEX IF NOT EXISTS idx_quant_product_loc ON stock_quant (product_id, location_id);
            CREATE INDEX IF NOT EXISTS idx_product_tmpl_categ ON product_template (categ_id);
        """)

    @api.model
    def _get_datetime_range_utc(self, start_date, end_date):
        user_tz = self.env.context.get('tz') or 'UTC'
        local_tz = pytz.timezone(user_tz)
        
        start_utc = None
        end_utc = None
        
        if start_date:
            if isinstance(start_date, str):
                start_date = fields.Date.from_string(start_date)
            local_start = datetime.combine(start_date, datetime.min.time())
            start_utc = local_tz.localize(local_start).astimezone(pytz.UTC).replace(tzinfo=None)
            
        if end_date:
            if isinstance(end_date, str):
                end_date = fields.Date.from_string(end_date)
            local_end = datetime.combine(end_date, datetime.max.time())
            end_utc = local_tz.localize(local_end).astimezone(pytz.UTC).replace(tzinfo=None)
            
        return start_utc, end_utc

    @api.model
    def get_date_range(self, time_range):
        today = fields.Date.today()
        if time_range == 'Today':
            return today, today
        elif time_range == 'This Week':
            start = today - timedelta(days=today.weekday())
            return start, today
        elif time_range == 'This Month':
            start = today.replace(day=1)
            return start, today
        elif time_range == 'This Quarter':
            month = (today.month - 1) // 3 * 3 + 1
            start = today.replace(month=month, day=1)
            return start, today
        elif time_range == 'All':
            return None, None
        return today.replace(day=1), today # Default to This Month



    @api.model
    def get_filter_options(self):
        projects = self.env['project.project'].search([('active', '=', True)], order='name')
        project_list = [{'id': p.id, 'name': p.name, 'code': p.name} for p in projects]
        
        customers = self.env['res.partner'].search([('customer_rank', '>', 0)], order='name')
        customer_list = [{'id': c.id, 'name': c.name} for c in customers]
        
        vendors = self.env['res.partner'].search([('supplier_rank', '>', 0)], order='name')
        vendor_list = [{'id': v.id, 'name': v.name} for v in vendors]
        
        locations = self.env['stock.location'].search([('usage', '=', 'internal')], order='name')
        location_list = [{'id': l.id, 'name': l.complete_name or l.name} for l in locations]
        
        categories = self.env['product.category'].search([], order='name')
        category_list = [{'id': c.id, 'name': c.complete_name or c.name} for c in categories]
        
        return {
            'projects': project_list,
            'customers': customer_list,
            'vendors': vendor_list,
            'locations': location_list,
            'categories': category_list
        }

    @api.model
    def action_approve_record(self, model=None, res_id=None):
        record = self.env[model].browse(res_id)
        vals = {}
        if model == 'sale.order':
            vals.update({
                'state': 'sale',
                'approval_state': 'ceo_approved',
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now(),
                'approval_level': 'ceo'
            })
        elif model == 'material.request':
            vals.update({
                'state': 'approved',
                'approve_type': 'ceo',
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now(),
                'approval_level': 'ceo'
            })
        try:
            record.write(vals)
        except Exception:
            safe_vals = {'state': vals.get('state')}
            # Check which fields actually exist in the record's model to be doubly sure
            available_fields = record._fields.keys()
            for f in ['approval_state', 'approve_type', 'approved_by', 'approved_date', 'approval_level']:
                if f in vals and f in available_fields:
                    # We still try individually because even if in _fields, it might not be in DB
                    try:
                        record.write({f: vals[f]})
                    except:
                        pass
        
        if model == 'sale.order' and hasattr(record, '_create_manufacturing_order'):
            record._create_manufacturing_order()
        return True

    @api.model
    def sync_spare_order_prices(self):
        spare_orders = self.env['sale.order'].sudo().search([('sale_or_spare', '=', 'spare')])
        count = 0
        for order in spare_orders:
            for line in order.order_line:
                if line.product_id:
                    line.sudo().write({'price_unit': line.product_id.standard_price})
                    count += 1
        return {'status': 'success', 'updated_lines': count}

    @api.model
    def get_project_spend_po_action(self, start_date=None, end_date=None, project_id=None):
        domain_so = [('sale_or_spare', '=', 'sale'), ('state', 'not in', ('draft', 'cancel', 'sent'))]
        if project_id:
            domain_so += [('project_id', '=', int(project_id))]
            
        active_sale_orders = self.env['sale.order'].search(domain_so)
        so_names = active_sale_orders.mapped('name')
        related_mos = self.env['mrp.production'].search([('origin', 'in', so_names)])
        mo_names = related_mos.mapped('name')
        mr_names = []
        try:
            with self.env.cr.savepoint():
                mr_data = self.env['material.request'].sudo().search_read([('ref', 'in', so_names)], ['name'])
                mr_names = [r['name'] for r in mr_data]
        except Exception:
            mr_names = []

        domain = [
            ('state', 'in', ('purchase', 'done')),
            '|', '|',
            ('origin', 'in', so_names),
            ('origin', 'in', mo_names),
            ('requisition_id.reference', 'in', mr_names)
        ]
        
        start_utc, end_utc = self._get_datetime_range_utc(start_date, end_date)
        if start_utc:
            domain += [('date_approve', '>=', start_utc)]
        if end_utc:
            domain += [('date_approve', '<=', end_utc)]

        return {
            'name': _('Project Related Purchase Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': domain,
            'target': 'current',
        }

    @api.model
    def _get_bom_cost(self, product):
        if not product:
            return 0.0
        
        bom = self.env['mrp.bom']._bom_find(product)[product]
        if not bom:
            return product.standard_price
            
        total_bom_cost = 0.0
        boms, lines = bom.explode(product, 1)
        for line, line_data in lines:
            comp_product = line.product_id
            comp_qty = line_data['qty']
            total_bom_cost += comp_product.standard_price * comp_qty
        return total_bom_cost

    @api.model
    def get_active_projects_action(self, start_date=None, end_date=None, customer_id=None):
        domain = [
            ('state', 'in', ('sale', 'done')),
            ('company_id', '=', self.env.company.id)
        ]
        start_utc, end_utc = self._get_datetime_range_utc(start_date, end_date)
        if start_utc:
            domain += [('date_order', '>=', start_utc)]
        if end_utc:
            domain += [('date_order', '<=', end_utc)]
        if customer_id:
            domain += [('partner_id', '=', int(customer_id))]

        return {
            'name': _('Active Projects'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': domain,
            'target': 'current',
        }

    @api.model
    def get_approval_action(self, status_type, start_date=None, end_date=None, project_id=None, customer_id=None, vendor_id=None, location_id=None, category_id=None):

        domain_so = [('company_id', '=', self.env.company.id)]
        domain_mr = [('company_id', '=', self.env.company.id)] # MR usually has company_id or uses default rule
        domain_unified = [('company_id', '=', self.env.company.id)]
        
        start_utc, end_utc = self._get_datetime_range_utc(start_date, end_date)
        if start_utc:
            domain_so += [('date_order', '>=', start_utc)]
            domain_mr += [('create_date', '>=', start_utc)]
            domain_unified += [('request_date', '>=', start_utc)]
        if end_utc:
            domain_so += [('date_order', '<=', end_utc)]
            domain_mr += [('create_date', '<=', end_utc)]
            domain_unified += [('request_date', '<=', end_utc)]
            
        if customer_id:
            domain_so += [('partner_id', '=', int(customer_id))]
            domain_unified += [('partner_id', '=', int(customer_id))]
            
        if project_id:
            domain_so += [('project_id', '=', int(project_id))]
            domain_unified += [('project_id', '=', int(project_id))]
            so_names = self.env['sale.order'].sudo().search([('project_id', '=', int(project_id))]).mapped('name')
            if so_names:
                domain_mr += [('ref', 'in', so_names)]
            else:
                domain_mr += [('id', '=', 0)]
                
        if category_id:
            domain_so += [('order_line.product_id.categ_id', 'child_of', int(category_id))]
            # the unified view does not currently sync category_id perfectly down to the line, so we skip it or could add it later
            
        if location_id:
            domain_mr += [('dest_loc_id', 'child_of', int(location_id))]
            domain_unified += [('location_id', 'child_of', int(location_id))]

        target_model = 'sale.order'
        target_domain = []
        name = 'Approvals'

        if status_type == 'pending':
            name = _('Pending Approvals')
            target_model = 'dashboard.ceo.approval'
            target_domain = domain_unified + [('approval_status', '=', 'pending')]
        
        elif status_type == 'approved':
            name = _('Approved Projects')
            domain_so_approved = domain_so + [('state', 'in', ('sale', 'done'))]
            if self.env['sale.order'].search_count(domain_so_approved):
                target_model = 'sale.order'
                target_domain = domain_so_approved
            else:
                target_model = 'material.request'
                target_domain = domain_mr + [('state', 'in', ('approved', 'received', 'full_approve', 'onhand_approve'))]
        
        elif status_type == 'rejected':
            name = _('Rejected / On Hold')
            target_model = 'dashboard.ceo.approval'
            target_domain = domain_unified + [('approval_status', '=', 'rejected')]

        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': target_model,
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')] if target_model not in ('dashboard.ceo.approval',) else [(False, 'list')],
            'domain': target_domain,
            'target': 'current',
        }

    @api.model
    def action_reject_record(self, model=None, res_id=None):
        if not model or not res_id:
            return False
        record = self.env[model].browse(res_id)
        vals = {
            'state': 'rejected',
            'approved_by': self.env.user.id,
            'approved_date': fields.Datetime.now(),
        }
        if model == 'sale.order':
            vals['approval_state'] = 'rejected'
        elif model == 'material.request':
            vals['approve_type'] = 'ceo_reject'
            
        try:
            record.write(vals)
        except Exception:
            try:
                record.write({'state': 'rejected'})
            except:
                pass
        return True

    @api.model
    def get_foc_drilldown_action(self, period='mtd', start_date=None, end_date=None, 
                                project_id=None, customer_id=None, vendor_id=None, 
                                location_id=None, category_id=None):
        if not end_date:
            end_date = fields.Date.today()
        
        if isinstance(start_date, str):
            start_date = fields.Date.from_string(start_date)
        if isinstance(end_date, str):
            end_date = fields.Date.from_string(end_date)
        
        if period == 'mtd':
            start_date = end_date.replace(day=1)
        elif period == 'ytd':
            start_date = end_date.replace(month=1, day=1)
        elif period == 'today':
            start_date = end_date
            
        if period == 'today':
            active_spare_orders = self.env['sale.order'].search([
                ('sale_or_spare', '=', 'spare'),
                ('state', 'not in', ('draft', 'cancel', 'sent')),
                ('company_id', '=', self.env.company.id)
            ])
            spare_so_names = active_spare_orders.mapped('name')
            spare_related_mos = self.env['mrp.production'].search([('origin', 'in', spare_so_names)])
            spare_mo_names = spare_related_mos.mapped('name')
            spare_mr_names = []
            try:
                with self.env.cr.savepoint():
                    mr_data = self.env['material.request'].sudo().search_read([('ref', 'in', spare_so_names)], ['name'])
                    spare_mr_names = [r['name'] for r in mr_data]
            except Exception:
                spare_mr_names = []

            domain = [
                ('state', 'in', ('purchase', 'done')),
                ('company_id', '=', self.env.company.id),
                '|', '|',
                ('origin', 'in', spare_so_names),
                ('origin', 'in', spare_mo_names),
                ('requisition_id.reference', 'in', spare_mr_names)
            ]
            
            start_utc, end_utc = self._get_datetime_range_utc(start_date, end_date)
            domain += [('date_approve', '>=', start_utc), ('date_approve', '<=', end_utc)]

            return {
                'name': _('FOC Purchase Orders (Today)'),
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_mode': 'list,form',
                'views': [[False, 'list'], [False, 'form']],
                'domain': domain,
                'target': 'current',
                'context': {'create': False}
            }

        domain = [
            ('state', 'in', ('sale', 'done')),
            ('sale_or_spare', '=', 'spare'),
            ('company_id', '=', self.env.company.id)
        ]
        
        if customer_id:
            domain += [('partner_id', '=', int(customer_id))]
        if project_id:
            domain += [('project_id', '=', int(project_id))]
        if vendor_id:
            domain += [('partner_id', '=', int(vendor_id))]
            
        date_field = 'expected_delivery_date'
        start_utc, end_utc = self._get_datetime_range_utc(start_date, end_date)
        if start_utc:
            domain += ['|', (date_field, '>=', start_utc), ('date_order', '>=', start_utc)]
        if end_utc:
            domain += ['|', (date_field, '<=', end_utc), ('date_order', '<=', end_utc)]
            
        return {
            'name': _('Spare Orders (%s)') % period.upper(),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': domain,
            'target': 'current',
            'context': {'create': False}
        }

    @api.model
    def _compute_inventory_valuation_sql(self, location_id=None, category_id=None):
        """
        Compute total inventory valuation strictly from stock_valuation_layer.remaining_value.
        Default (no location filter): uses internal locations where name contains CW or Store.
        With a location filter: uses the selected location and its child locations.
        With a category filter: restricts to products in that category hierarchy.
        Returns a float representing total accounting inventory value.
        """
        company_id = self.env.company.id
        params = [company_id]

        # --- Location clause ---
        if location_id:
            # Get all child location IDs for the selected location
            child_locs = self.env['stock.location'].search([
                ('id', 'child_of', int(location_id)),
                ('usage', '=', 'internal')
            ]).ids
            if not child_locs:
                return 0.0
            loc_clause = "AND sq.location_id IN %s"
            params.append(tuple(child_locs))
        else:
            # Default: internal locations named CW or Store
            loc_clause = """AND sq.location_id IN (
                SELECT sl.id FROM stock_location sl
                WHERE sl.usage = 'internal'
                  AND sl.active = TRUE
                  AND sl.company_id = %s
                  AND (sl.complete_name ILIKE '%%CW%%' OR sl.complete_name ILIKE '%%Store%%')
            )"""
            params.append(company_id)

        # --- Category clause ---
        if category_id:
            child_cats = self.env['product.category'].search([
                ('id', 'child_of', int(category_id))
            ]).ids
            if not child_cats:
                return 0.0
            cat_clause = "AND pt.categ_id IN %s"
            params.append(tuple(child_cats))
        else:
            cat_clause = ""

        sql = f"""
            SELECT COALESCE(SUM(svl.remaining_value), 0.0)
            FROM stock_valuation_layer svl
            JOIN product_product pp ON pp.id = svl.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            JOIN stock_quant sq ON sq.product_id = svl.product_id
                AND sq.location_id IN (
                    SELECT location_id FROM stock_quant
                    WHERE company_id = %s AND quantity > 0
                )
            WHERE svl.company_id = %s
              AND svl.remaining_qty > 0
              {loc_clause}
              {cat_clause}
        """
        # Simplify: use a single clean query directly on SVL + product join
        params2 = [company_id]
        if location_id:
            child_locs = self.env['stock.location'].search([
                ('id', 'child_of', int(location_id)),
                ('usage', '=', 'internal')
            ]).ids
            if not child_locs:
                return 0.0
            loc_sub = "sq.location_id IN %s"
            params2.append(tuple(child_locs))
        else:
            loc_sub = """sq.location_id IN (
                SELECT sl.id FROM stock_location sl
                WHERE sl.usage = 'internal'
                  AND sl.active = TRUE
                  AND sl.company_id = %s
                  AND (sl.complete_name ILIKE '%%CW%%' OR sl.complete_name ILIKE '%%Store%%')
            )"""
            params2.append(company_id)

        cat_sub = ""
        if category_id:
            child_cats = self.env['product.category'].search([
                ('id', 'child_of', int(category_id))
            ]).ids
            if not child_cats:
                return 0.0
            cat_sub = "AND pt.categ_id IN %s"
            params2.append(tuple(child_cats))

        final_sql = f"""
            SELECT COALESCE(SUM(svl.remaining_value), 0.0)
            FROM stock_valuation_layer svl
            JOIN product_product pp ON pp.id = svl.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            WHERE svl.company_id = %s
              AND svl.remaining_qty > 0
              AND svl.product_id IN (
                  SELECT DISTINCT sq.product_id
                  FROM stock_quant sq
                  WHERE sq.company_id = %s
                    AND sq.quantity > 0
                    AND {loc_sub}
              )
              {cat_sub}
        """
        params_final = [company_id, company_id] + params2[1:]
        self.env.cr.execute(final_sql, params_final)
        result = self.env.cr.fetchone()
        return float(result[0]) if result and result[0] is not None else 0.0

    @api.model
    def _compute_inventory_split_sql(self, location_id=None, category_id=None):
        """
        Compute inventory split by product category from stock_valuation_layer.remaining_value.
        Returns list of dicts with label, value, percentage, color for chart display.
        """
        company_id = self.env.company.id
        total = self._compute_inventory_valuation_sql(location_id, category_id)

        # Build location sub-query
        if location_id:
            child_locs = self.env['stock.location'].search([
                ('id', 'child_of', int(location_id)),
                ('usage', '=', 'internal')
            ]).ids
            if not child_locs:
                return []
            loc_sub = "sq.location_id IN %s"
            loc_param = (tuple(child_locs),)
        else:
            loc_sub = """sq.location_id IN (
                SELECT sl.id FROM stock_location sl
                WHERE sl.usage = 'internal'
                  AND sl.active = TRUE
                  AND sl.company_id = %s
                  AND (sl.complete_name ILIKE '%%CW%%' OR sl.complete_name ILIKE '%%Store%%')
            )"""
            loc_param = (company_id,)

        cat_sub = ""
        cat_param = ()
        if category_id:
            child_cats = self.env['product.category'].search([
                ('id', 'child_of', int(category_id))
            ]).ids
            if not child_cats:
                return []
            cat_sub = "AND pt.categ_id IN %s"
            cat_param = (tuple(child_cats),)

        split_sql = f"""
            SELECT
                COALESCE(pc.name, 'Uncategorized') AS cat_name,
                COALESCE(SUM(svl.remaining_value), 0.0) AS total_val
            FROM stock_valuation_layer svl
            JOIN product_product pp ON pp.id = svl.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            JOIN product_category pc ON pc.id = pt.categ_id
            WHERE svl.company_id = %s
              AND svl.remaining_qty > 0
              AND svl.product_id IN (
                  SELECT DISTINCT sq.product_id
                  FROM stock_quant sq
                  WHERE sq.company_id = %s
                    AND sq.quantity > 0
                    AND {loc_sub}
              )
              {cat_sub}
            GROUP BY pc.name, pc.id
            ORDER BY total_val DESC
            LIMIT 8
        """
        params_split = [company_id, company_id] + list(loc_param) + list(cat_param)
        self.env.cr.execute(split_sql, params_split)
        rows = self.env.cr.fetchall()

        colors = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#6366f1', '#14b8a6']
        result = []
        for i, (cat_name, val) in enumerate(rows):
            val = float(val)
            if val <= 0:
                continue
            # Handle multilang JSON name if it's a dict-like string
            if isinstance(cat_name, str) and cat_name.startswith('{'):
                try:
                    import json
                    parsed = json.loads(cat_name)
                    cat_name = parsed.get('en_US') or next(iter(parsed.values()), 'Uncategorized')
                except Exception:
                    pass
            result.append({
                'label': cat_name or 'Uncategorized',
                'value': val,
                'percentage': round((val / total * 100), 1) if total else 0,
                'color': colors[i % len(colors)]
            })
        return result[:5]

    @api.model
    def get_dashboard_data(self, time_range='This Month', start_date=None, end_date=None, 
                          project_id=None, customer_id=None, vendor_id=None, 
                          location_id=None, category_id=None, skip_kpi=False):
        try:
            self.env.cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name='material_request' AND column_name='approved_by'")
            if not self.env.cr.fetchone():
                self.env.cr.execute("ALTER TABLE material_request ADD COLUMN approved_by integer")
            self.env.cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name='material_request' AND column_name='company_id'")
            if not self.env.cr.fetchone():
                self.env.cr.execute("ALTER TABLE material_request ADD COLUMN company_id integer")
        except:
            pass

        today = fields.Date.today()
        current_month_start = today.replace(day=1)
        last_30_days = today - timedelta(days=30)
        
        if not (start_date and end_date):
            start_date, end_date = self.get_date_range(time_range)
        
        if isinstance(start_date, str):
            start_date = fields.Date.from_string(start_date)
        if isinstance(end_date, str):
            end_date = fields.Date.from_string(end_date)
        
        start_utc, end_utc = self._get_datetime_range_utc(start_date, end_date)
        
        so_names_for_project = []
        if project_id:
            so_names_for_project = self.env['sale.order'].sudo().search([('project_id', '=', int(project_id))]).mapped('name')

        domain_revenue = [('state', 'in', ('sale', 'done')), ('company_id', '=', self.env.company.id), ('sale_or_spare', '=', 'sale')]
        domain_spend = [('move_type', '=', 'in_invoice'), ('state', '=', 'posted'), ('company_id', '=', self.env.company.id)]
        domain_po = [('state', 'in', ('purchase', 'done')), ('company_id', '=', self.env.company.id)]
        domain_mr = [] # Material requests
        
        if start_utc:
            domain_revenue += [('date_order', '>=', start_utc)]
            domain_po += [('date_order', '>=', start_utc)]
        if end_utc:
            domain_revenue += [('date_order', '<=', end_utc)]
            domain_po += [('date_order', '<=', end_utc)]
            
        if start_date:
            domain_spend += [('invoice_date', '>=', start_date)]
        if end_date:
            domain_spend += [('invoice_date', '<=', end_date)]
        
        if customer_id:
            domain_revenue += [('partner_id', '=', int(customer_id))]
            # Remove customer filter from spend/po to avoid empty results if not cross-linked
            # domain_spend += [('partner_id', '=', int(customer_id))]
            # domain_po += [('partner_id', '=', int(customer_id))]
        
        if vendor_id:
            domain_spend += [('partner_id', '=', int(vendor_id))]
            domain_po += [('partner_id', '=', int(vendor_id))]
            # Remove vendor filter from revenue
            # domain_revenue += [('partner_id', '=', int(vendor_id))]
        
        if project_id:
            if so_names_for_project:
                domain_mr += [('ref', 'in', so_names_for_project)]
            else:
                domain_mr += [('id', '=', 0)] # Force empty if no SO found for project
            # Project filter on SO and PO:
            # Assuming project_id exists on SO and PO
            domain_revenue += [('project_id', '=', int(project_id))]
            domain_po += [('project_id', '=', int(project_id))]
            
        # Optional category / location applying over revenue/spend
        if category_id:
            domain_spend += [('invoice_line_ids.product_id.categ_id', 'child_of', int(category_id))]
            domain_po += [('order_line.product_id.categ_id', 'child_of', int(category_id))]
            domain_revenue += [('order_line.product_id.categ_id', 'child_of', int(category_id))]

        if location_id:
            # For PO, filter by destination location
            domain_po += [('picking_type_id.default_location_dest_id', 'child_of', int(location_id))]
            
        if not skip_kpi:
            # Optimize: use search_read or read_group if possible, but mapped works for now if counts are low
            revenue_val = sum(self.env['sale.order'].sudo().search(domain_revenue).mapped('amount_total'))
            spend_val = sum(self.env['purchase.order'].sudo().search(domain_po).mapped('amount_total'))
            
            margin = revenue_val - spend_val
            margin_pct = (margin / revenue_val * 100) if revenue_val else 0.0
        else:
            revenue_val = spend_val = margin = margin_pct = 0.0

        today_date = fields.Date.today()
        yesterday_date = today_date - timedelta(days=1)

        def get_picking_value(picking_type, target_date):
            start_utc, end_utc = self._get_datetime_range_utc(target_date, target_date)
            domain = [
                ('picking_id.picking_type_id.code', '=', picking_type),
                ('state', '=', 'done'),
                ('company_id', '=', self.env.company.id),
                ('picking_id.date_done', '>=', start_utc),
                ('picking_id.date_done', '<=', end_utc)
            ]
            if location_id:
                loc_field = 'location_dest_id' if picking_type == 'incoming' else 'location_id'
                domain += [(loc_field, 'child_of', int(location_id))]
                
            moves = self.env['stock.move'].search(domain)
            return sum(m.product_uom_qty * m.product_id.standard_price for m in moves)

        outward_today = get_picking_value('outgoing', today_date)
        outward_yesterday = get_picking_value('outgoing', yesterday_date)
        outward_trend = ((outward_today - outward_yesterday) / outward_yesterday * 100) if outward_yesterday else 0

        inward_today = get_picking_value('incoming', today_date)
        inward_yesterday = get_picking_value('incoming', yesterday_date)
        inward_trend = ((inward_today - inward_yesterday) / inward_yesterday * 100) if inward_yesterday else 0

        # 2. Inventory Valuation via stock_valuation_layer.remaining_value (Accounting Source of Truth)
        inventory_value = self._compute_inventory_valuation_sql(location_id, category_id)
        quants = []  # quants will be built later for inventory split only when needed

        # 3. Trends (Last 6 Months) — single SQL query with GROUP BY date_trunc
        trend_start = current_month_start - relativedelta(months=5)
        trend_params_rev = [self.env.company.id, trend_start]
        trend_params_spd = [self.env.company.id, trend_start]
        trend_partner_rev = ""
        trend_partner_spd = ""
        trend_cat_rev = ""
        trend_cat_spd = ""
        if customer_id:
            trend_partner_rev = "AND am.partner_id = %s"
            trend_params_rev.append(int(customer_id))
        if vendor_id:
            trend_partner_spd = "AND am.partner_id = %s"
            trend_params_spd.append(int(vendor_id))

        rev_sql = f"""
            SELECT
                date_trunc('month', am.invoice_date)::date AS month,
                COALESCE(SUM(am.amount_total_signed), 0.0)
            FROM account_move am
            WHERE am.company_id = %s
              AND am.state = 'posted'
              AND am.move_type = 'out_invoice'
              AND am.invoice_date >= %s
              {trend_partner_rev}
            GROUP BY month
            ORDER BY month
        """
        spd_sql = f"""
            SELECT
                date_trunc('month', am.invoice_date)::date AS month,
                COALESCE(SUM(am.amount_total_signed), 0.0)
            FROM account_move am
            WHERE am.company_id = %s
              AND am.state = 'posted'
              AND am.move_type = 'in_invoice'
              AND am.invoice_date >= %s
              {trend_partner_spd}
            GROUP BY month
            ORDER BY month
        """
        self.env.cr.execute(rev_sql, trend_params_rev)
        rev_rows = {str(r[0])[:7]: float(r[1]) for r in self.env.cr.fetchall()}
        self.env.cr.execute(spd_sql, trend_params_spd)
        spd_rows = {str(r[0])[:7]: float(r[1]) for r in self.env.cr.fetchall()}

        trends = []
        for i in range(5, -1, -1):
            ds = current_month_start - relativedelta(months=i)
            key = ds.strftime('%Y-%m')
            trends.append({'month': ds.strftime('%b'), 'revenue': rev_rows.get(key, 0.0), 'spend': spd_rows.get(key, 0.0)})

        # 4. Top Vendors (Based on Purchase Orders if Bills are empty)
        vendors_data = self.env['account.move'].read_group(
            domain_spend,
            ['partner_id', 'amount_total:sum'],
            ['partner_id'],
            orderby='amount_total:sum DESC',
            limit=10
        )
        top_vendors = [{
            'name': v.get('partner_id')[1] if v.get('partner_id') else 'Unknown', 
            'value': v.get('amount_total', 0),
            'partner_id': v.get('partner_id')[0] if v.get('partner_id') else False,
            'model': 'account.move'
        } for v in vendors_data if v.get('partner_id')]
        
        if not top_vendors:
            po_data = self.env['purchase.order'].read_group(
                domain_po,
                ['partner_id', 'amount_total:sum'],
                ['partner_id'],
                orderby='amount_total:sum DESC',
                limit=10
            )
            top_vendors = [{
                'name': v.get('partner_id')[1] if v.get('partner_id') else 'Unknown', 
                'value': v.get('amount_total', 0),
                'partner_id': v.get('partner_id')[0] if v.get('partner_id') else False,
                'model': 'purchase.order'
            } for v in po_data if v.get('partner_id')]

        domain_so_projects = [
            ('state', 'in', ('sale', 'done')),
            ('company_id', '=', self.env.company.id),
            ('sale_or_spare', '=', 'sale')
        ]
        if start_utc:
            domain_so_projects += [('date_order', '>=', start_utc)]
        if end_utc:
            domain_so_projects += [('date_order', '<=', end_utc)]
        if customer_id:
            domain_so_projects += [('partner_id', '=', int(customer_id))]
        if vendor_id:
            domain_so_projects += [('partner_id', '=', int(vendor_id))]
        if project_id:
            domain_so_projects += [('project_id', '=', int(project_id))]
        if category_id:
            domain_so_projects += [('order_line.product_id.categ_id', 'child_of', int(category_id))]
            
        all_active_so = self.env['sale.order'].with_context(prefetch_fields=False).search(domain_so_projects, order='date_order desc', limit=20)
        active_projects_count = self.env['sale.order'].search_count(domain_so_projects)
        
        projects_list = []
        total_budget_allocated = 0.0
        total_project_spent = 0.0
        
        for so in all_active_so:
            so_budget = 0.0
            for line in so.order_line:
                if line.product_id:
                    bom_cost = self._get_bom_cost(line.product_id)
                    line_budget = bom_cost * line.product_uom_qty
                    so_budget += line_budget
            
            mo_names = self.env['mrp.production'].search([('origin', '=', so.name)]).mapped('name')
            mr_names = []
            try:
                with self.env.cr.savepoint():
                    mr_data = self.env['material.request'].sudo().search_read([('ref', '=', so.name)], ['name'])
                    mr_names = [r['name'] for r in mr_data]
            except Exception:
                mr_names = []
            
            domain_so_po = [
                ('state', 'in', ('purchase', 'done')),
                '|', '|',
                ('origin', '=', so.name),
                ('origin', 'in', mo_names),
                ('requisition_id.reference', 'in', mr_names)
            ]
            
            if start_utc:
                domain_so_po += [('date_approve', '>=', start_utc)]
            if end_utc:
                domain_so_po += [('date_approve', '<=', end_utc)]

            so_spent = sum(self.env['purchase.order'].search(domain_so_po).mapped('amount_total'))
            
            projects_list.append({
                'id': so.name,
                'so_id': so.id,
                'name': so.name,
                'client': so.partner_id.name if so.partner_id else 'Internal',
                'budget': so_budget,
                'spent': so_spent,
                'balance': so_budget - so_spent,
                'variance': ((so_spent / so_budget * 100) if so_budget > 0 else 0),
                'status': dict(so._fields['state'].selection).get(so.state, so.state)
            })
            
            total_budget_allocated += so_budget
            total_project_spent += so_spent
        pending_approvals = 0
        approved_requests = 0
        rejected_requests = 0
        blocked_value = 0.0
        bottlenecks_data = []

        domain_so_pending = [
            ('company_id', '=', self.env.company.id),
            '|',
            ('state', '=', 'waiting_ceo_approval'),
            ('approval_state', '=', 'to_approve')
        ]
        if customer_id:
            domain_so_pending += [('partner_id', '=', int(customer_id))]
        if project_id:
            domain_so_pending += [('project_id', '=', int(project_id))]
        if category_id:
            domain_so_pending += [('order_line.product_id.categ_id', 'child_of', int(category_id))]
            
        so_pending = self.env['sale.order'].with_context(prefetch_fields=False).search(domain_so_pending, limit=20)
        for so in so_pending:
            pending_approvals += 1
            blocked_value += so.amount_total
            bottlenecks_data.append({
                'id': f"{so.name}_{so.id}",
                'res_id': so.id,
                'model': 'sale.order',
                'amount': so.amount_total,
                'user': so.user_id.name,
                'date': so.date_order.date().isoformat() if so.date_order else so.create_date.date().isoformat(),
                'waiting': (fields.Date.today() - so.create_date.date()).days,
                'source': 'Spare' if so.sale_or_spare == 'spare' else 'Sale',
                'status': 'Waiting CEO Approval',
                'display_name': so.name
            })

        # Fetch Pending Material Requests (All types including User requests)
        mr_pending_domain = [
            '|',
            ('state', '=', 'waiting_ceo_approval'),
            '&', ('request_type', '=', 'user'), ('approve_type', '=', 'draft')
        ]
        if location_id:
            mr_pending_domain += [('dest_loc_id', 'child_of', int(location_id))]
        if project_id:
            if so_names_for_project:
                mr_pending_domain += [('ref', 'in', so_names_for_project)]
            else:
                mr_pending_domain += [('id', '=', 0)]
        
        mr_pending_data = []
        try:
            with self.env.cr.savepoint():
                mr_pending_data = self.env['material.request'].sudo().search_read(
                    mr_pending_domain, 
                    ['name', 'id', 'user_id', 'create_date', 'request_type', 'ref'],
                    limit=20
                )
        except Exception:
             mr_pending_data = []

        for mr in mr_pending_data:
            if any(b['id'] == mr['name'] and b['model'] == 'material.request' for b in bottlenecks_data):
                continue
            pending_approvals += 1
            
            mr_val = 0.0
            try:
                with self.env.cr.savepoint():
                    line_data = self.env['material.request.product.line'].sudo().search_read(
                        [('request_id', '=', mr['id'])], 
                        ['demand_qty', 'product_id']
                    )
                    for l in line_data:
                        p_id = l['product_id'][0] if isinstance(l['product_id'], (list, tuple)) else l['product_id']
                        if p_id:
                            product = self.env['product.product'].browse(p_id)
                            mr_val += l['demand_qty'] * product.standard_price
            except Exception:
                mr_val = 0.0
            
            blocked_value += mr_val
            bottlenecks_data.append({
                'id': f"{mr['name']}_{mr['id']}",
                'res_id': mr['id'],
                'model': 'material.request',
                'amount': mr_val,
                'user': mr['user_id'][1] if isinstance(mr['user_id'], (list, tuple)) else 'System',
                'date': mr['create_date'].date().isoformat() if mr['create_date'] else fields.Date.today().isoformat(),
                'waiting': (fields.Date.today() - mr['create_date'].date()).days if mr['create_date'] else 0,
                'source': 'Material' if mr['request_type'] == 'user' else 'MRP',
                'status': 'To Approve',
                'display_name': mr['name']
            })

        try:
            domain_so_app = [
                ('company_id', '=', self.env.company.id), 
                ('state', 'in', ('sale', 'done'))
            ]
            if customer_id:
                 domain_so_app += [('partner_id', '=', int(customer_id))]
            if project_id:
                 domain_so_app += [('project_id', '=', int(project_id))]
            if category_id:
                 domain_so_app += [('order_line.product_id.categ_id', 'child_of', int(category_id))]

            with self.env.cr.savepoint():
                so_approved = self.env['sale.order'].search_count(domain_so_app)
        except Exception:
            so_approved = 0
            
        try:
            with self.env.cr.savepoint():
                mr_app_domain = [('state', 'in', ('approved', 'received', 'full_approve', 'onhand_approve'))]
                if location_id:
                    mr_app_domain += [('dest_loc_id', 'child_of', int(location_id))]
                if project_id:
                    if so_names_for_project:
                        mr_app_domain += [('ref', 'in', so_names_for_project)]
                    else:
                        mr_app_domain += [('id', '=', 0)]
                mr_approved = self.env['material.request'].sudo().search_count(mr_app_domain)
        except Exception:
            mr_approved = 0
                
        approved_requests = so_approved + mr_approved

        try:
            domain_so_rej = [
                ('company_id', '=', self.env.company.id), 
                ('state', '=', 'rejected')
            ]
            if customer_id:
                domain_so_rej += [('partner_id', '=', int(customer_id))]
            if project_id:
                domain_so_rej += [('project_id', '=', int(project_id))]
            if category_id:
                domain_so_rej += [('order_line.product_id.categ_id', 'child_of', int(category_id))]

            with self.env.cr.savepoint():
                so_rejected = self.env['sale.order'].search_count(domain_so_rej)
        except Exception:
            so_rejected = 0
            
        try:
            with self.env.cr.savepoint():
                mr_rej_domain = [('state', '=', 'rejected')]
                if location_id:
                    mr_rej_domain += [('dest_loc_id', 'child_of', int(location_id))]
                if project_id:
                    if so_names_for_project:
                        mr_rej_domain += [('ref', 'in', so_names_for_project)]
                    else:
                        mr_rej_domain += [('id', '=', 0)]
                mr_rejected = self.env['material.request'].sudo().search_count(mr_rej_domain)
        except Exception:
            mr_rejected = 0
            
        rejected_requests = so_rejected + mr_rejected

        # 6. Spend Timeline — single SQL with GROUP BY date (stock.move outgoing)
        # Note: sp_params[0] = company_id string for standard_price JSONB key, sp_params[1] = company_id int for WHERE
        company_id_str = str(self.env.company.id)
        sp_params = [company_id_str, self.env.company.id]
        sp_loc_where = ""
        sp_cat_join = ""
        sp_cat_where = ""
        if start_utc:
            sp_params.append(start_utc)
            sp_date_start_where = "AND sp.date_done >= %s"
        else:
            sp_date_start_where = ""
        if end_utc:
            sp_params.append(end_utc)
            sp_date_end_where = "AND sp.date_done <= %s"
        else:
            sp_date_end_where = ""
        if vendor_id:
            sp_params.append(int(vendor_id))
            sp_vendor_where = "AND sp.partner_id = %s"
        else:
            sp_vendor_where = ""
        if location_id:
            child_locs_sm = self.env['stock.location'].search([('id', 'child_of', int(location_id))]).ids
            if child_locs_sm:
                sp_params.append(tuple(child_locs_sm))
                sp_loc_where = "AND sm.location_id IN %s"
        if category_id:
            child_cats_sm = self.env['product.category'].search([('id', 'child_of', int(category_id))]).ids
            if child_cats_sm:
                sp_params.append(tuple(child_cats_sm))
                sp_cat_join = "JOIN product_template pt_sm ON pt_sm.id = pp_sm.product_tmpl_id"
                sp_cat_where = "AND pt_sm.categ_id IN %s"

        timeline_sql = f"""
            SELECT
                sp.date_done::date AS day,
                COALESCE(SUM(sm.product_uom_qty * COALESCE((pp_sm.standard_price->>%s)::numeric, 0.0)), 0.0) AS daily_val
            FROM stock_move sm
            JOIN stock_picking sp ON sp.id = sm.picking_id
            JOIN stock_picking_type spt ON spt.id = sp.picking_type_id
            JOIN product_product pp_sm ON pp_sm.id = sm.product_id
            JOIN product_template pt_sm ON pt_sm.id = pp_sm.product_tmpl_id
            WHERE sm.company_id = %s
              AND sm.state = 'done'
              AND spt.code = 'outgoing'
              AND sp.date_done IS NOT NULL
              {sp_date_start_where}
              {sp_date_end_where}
              {sp_vendor_where}
              {sp_loc_where}
              {sp_cat_where}
            GROUP BY day
            ORDER BY day
        """
        self.env.cr.execute(timeline_sql, sp_params)
        tl_rows = self.env.cr.fetchall()
        spend_timeline = {'labels': [], 'data': [], 'full_dates': [], 'model': 'stock.picking'}
        for row in tl_rows:
            d_obj = row[0]
            spend_timeline['labels'].append(d_obj.strftime('%b %d'))
            spend_timeline['full_dates'].append(d_obj.isoformat())
            spend_timeline['data'].append(float(row[1]))

        # Fallback to Bills if no stock data found
        if not spend_timeline['data']:
            spend_timeline['model'] = 'account.move'
            fb_params = [self.env.company.id]
            fb_clauses = []
            if start_date:
                fb_clauses.append("am.invoice_date >= %s")
                fb_params.append(start_date)
            if end_date:
                fb_clauses.append("am.invoice_date <= %s")
                fb_params.append(end_date)
            if vendor_id:
                fb_clauses.append("am.partner_id = %s")
                fb_params.append(int(vendor_id))
            fb_where = (" AND " + " AND ".join(fb_clauses)) if fb_clauses else ""
            fallback_sql = f"""
                SELECT am.invoice_date AS day, COALESCE(SUM(am.amount_total_signed), 0.0)
                FROM account_move am
                WHERE am.company_id = %s
                  AND am.state = 'posted'
                  AND am.move_type = 'in_invoice'
                  AND am.invoice_date IS NOT NULL
                  {fb_where}
                GROUP BY day ORDER BY day
            """
            self.env.cr.execute(fallback_sql, fb_params)
            for row in self.env.cr.fetchall():
                d_obj = row[0]
                spend_timeline['labels'].append(d_obj.strftime('%b %d'))
                spend_timeline['full_dates'].append(d_obj.isoformat())
                spend_timeline['data'].append(float(row[1]))
        
        domain_spend_lines = [('move_id.move_type', '=', 'in_invoice'), ('move_id.state', '=', 'posted'), ('company_id', '=', self.env.company.id)]
        if start_date: domain_spend_lines += [('move_id.invoice_date', '>=', start_date)]
        if end_date: domain_spend_lines += [('move_id.invoice_date', '<=', end_date)]
        # Apply vendor filter
        if vendor_id:
            domain_spend_lines += [('move_id.partner_id', '=', int(vendor_id))]
        # Apply category filter
        if category_id:
            domain_spend_lines += [('product_id.categ_id', 'child_of', int(category_id))]
        
        # Ensure we only have lines with products for category analysis
        domain_spend_lines += [('product_id', '!=', False)]

        # Group by Product Category to get "Material Based" spend
        # Note: product_id is joined to get categ_id
        category_spend = self.env['account.move.line'].read_group(
            domain_spend_lines, 
            ['price_subtotal:sum'], 
            ['product_id'], # We group by product first to aggregate, OR if Odoo supports product_id.categ_id
            limit=None     # We need to aggregate all then group by category manually if read_group key issues arise
        )
        
        # Odoo read_group with 'product_id.categ_id' can be tricky on non-stored related fields.
        # Safer approach: Fetch aggregated product spend, then aggregate by category in Python.
        # Use a larger limit for products to cover significant spend.
        product_spend = self.env['account.move.line'].read_group(
            domain_spend_lines,
            ['price_subtotal:sum', 'product_id'],
            ['product_id'],
            limit=100, # Top 100 products should cover main spend
            orderby='price_subtotal:sum DESC'
        )
        
        # Optimization:
        product_ids = [p.get('product_id')[0] for p in product_spend if p.get('product_id')]
        products = self.env['product.product'].browse(product_ids)
        prod_cat_map = {prod.id: prod.categ_id.name for prod in products}
        
        cat_map = {}
        for p in product_spend:
             if p.get('product_id'):
                 pid = p.get('product_id')[0]
                 cat_name = prod_cat_map.get(pid, 'Uncategorized')
                 amt = p.get('price_subtotal', 0)
                 cat_map[cat_name] = cat_map.get(cat_name, 0) + amt

        # Fallback to Purchase Orders if no Bill data found (similar to Top Vendors logic)
        if not cat_map:
            domain_po_lines = [('order_id.state', 'in', ('purchase', 'done')), ('company_id', '=', self.env.company.id)]
            if start_date: domain_po_lines += [('order_id.date_order', '>=', start_date)]
            if end_date: domain_po_lines += [('order_id.date_order', '<=', end_date)]
            if vendor_id: domain_po_lines += [('partner_id', '=', int(vendor_id))] # partner_id is on line or header? PO Line has partner_id? No, usually order_id.partner_id
            if category_id: domain_po_lines += [('product_id.categ_id', 'child_of', int(category_id))]
            
            # Correct domain for PO Lines partner filter
            if vendor_id: domain_po_lines += [('order_id.partner_id', '=', int(vendor_id))]

            po_product_spend = self.env['purchase.order.line'].read_group(
                domain_po_lines,
                ['price_subtotal:sum', 'product_id'],
                ['product_id'],
                limit=100,
                orderby='price_subtotal:sum DESC'
            )
            
            po_product_ids = [p.get('product_id')[0] for p in po_product_spend if p.get('product_id')]
            po_products = self.env['product.product'].browse(po_product_ids)
            po_prod_cat_map = {prod.id: prod.categ_id.name for prod in po_products}

            for p in po_product_spend:
                if p.get('product_id'):
                    pid = p.get('product_id')[0]
                    cat_name = po_prod_cat_map.get(pid, 'Uncategorized')
                    amt = p.get('price_subtotal', 0)
                    cat_map[cat_name] = cat_map.get(cat_name, 0) + amt

        # Sort top 5 categories
        sorted_cats = sorted(cat_map.items(), key=lambda x: x[1], reverse=True)[:5]
        
        spend_category = {'labels': [], 'data': []}
        for name, amount in sorted_cats:
             spend_category['labels'].append(name)
             spend_category['data'].append(amount)

        # 7. Projects Detail (Already handled in step 5)
        # projects_list is already populated

        # 8. Bottlenecks (Handled in step 5)
        # bottlenecks_data = bottlenecks_data

        # 9. Inventory Split – grouped by product category using SVL accounting data
        inventory_split = self._compute_inventory_split_sql(location_id, category_id)


        # 10. Money Flow Details
        # Inward Purchase – direct SQL SUM
        po_where_parts = " AND ".join(f"{k}" for k in ["state IN ('purchase', 'done')", "company_id = %s"])
        self.env.cr.execute(
            f"SELECT COALESCE(SUM(amount_total), 0.0) FROM purchase_order WHERE {po_where_parts}",
            [self.env.company.id]
        )
        inward_purchase_val = float(self.env.cr.fetchone()[0])

        # Payables Pending – direct SQL SUM
        self.env.cr.execute(
            """SELECT COALESCE(SUM(amount_residual_signed), 0.0)
               FROM account_move
               WHERE company_id = %s AND state = 'posted'
                 AND move_type = 'in_invoice'
                 AND payment_state IN ('not_paid', 'partial')""",
            [self.env.company.id]
        )
        payables_pending_val = float(self.env.cr.fetchone()[0])

        # Build Project SO / MO / MR name lists for origin-based PO lookup
        active_sale_orders = self.env['sale.order'].with_context(prefetch_fields=False).search_read([
            ('sale_or_spare', '=', 'sale'),
            ('state', 'not in', ('draft', 'cancel', 'sent')),
            ('company_id', '=', self.env.company.id)
        ], ['name'])
        so_names = [r['name'] for r in active_sale_orders]
        related_mos = self.env['mrp.production'].search_read([('origin', 'in', so_names)], ['name'])
        mo_names = [r['name'] for r in related_mos]
        mr_names = []
        try:
            with self.env.cr.savepoint():
                mr_data = self.env['material.request'].sudo().search_read([('ref', 'in', so_names)], ['name'])
                mr_names = [r['name'] for r in mr_data]
        except Exception:
            mr_names = []

        # FOC (Spare) names
        active_spare_orders = self.env['sale.order'].with_context(prefetch_fields=False).search_read([
            ('sale_or_spare', '=', 'spare'),
            ('state', 'not in', ('draft', 'cancel', 'sent')),
            ('company_id', '=', self.env.company.id)
        ], ['name'])
        spare_so_names = [r['name'] for r in active_spare_orders]
        spare_related_mos = self.env['mrp.production'].search_read([('origin', 'in', spare_so_names)], ['name'])
        spare_mo_names = [r['name'] for r in spare_related_mos]
        spare_mr_names = []
        try:
            with self.env.cr.savepoint():
                smr_data = self.env['material.request'].sudo().search_read([('ref', 'in', spare_so_names)], ['name'])
                spare_mr_names = [r['name'] for r in smr_data]
        except Exception:
            spare_mr_names = []

        # Today vs Yesterday for Project Spend – single SQL with FILTER
        today_start, today_end = self._get_datetime_range_utc(today_date, today_date)
        yester_start, yester_end = self._get_datetime_range_utc(yesterday_date, yesterday_date)

        all_project_origins = list(set(so_names + mo_names + mr_names)) or ['']
        all_spare_origins = list(set(spare_so_names + spare_mo_names + spare_mr_names)) or ['']

        self.env.cr.execute(
            """SELECT
                COALESCE(SUM(amount_total) FILTER (WHERE date_approve >= %s AND date_approve <= %s), 0.0) AS today_val,
                COALESCE(SUM(amount_total) FILTER (WHERE date_approve >= %s AND date_approve <= %s), 0.0) AS yest_val
               FROM purchase_order
               WHERE company_id = %s AND state IN ('purchase', 'done') AND origin = ANY(%s)""",
            [today_start, today_end, yester_start, yester_end, self.env.company.id, all_project_origins]
        )
        ps_row = self.env.cr.fetchone()
        project_spend_today = float(ps_row[0]) if ps_row else 0.0
        project_spend_yesterday = float(ps_row[1]) if ps_row else 0.0
        project_spend_trend = ((project_spend_today - project_spend_yesterday) / project_spend_yesterday * 100) if project_spend_yesterday else 0

        self.env.cr.execute(
            """SELECT
                COALESCE(SUM(amount_total) FILTER (WHERE date_approve >= %s AND date_approve <= %s), 0.0) AS today_val,
                COALESCE(SUM(amount_total) FILTER (WHERE date_approve >= %s AND date_approve <= %s), 0.0) AS yest_val
               FROM purchase_order
               WHERE company_id = %s AND state IN ('purchase', 'done') AND origin = ANY(%s)""",
            [today_start, today_end, yester_start, yester_end, self.env.company.id, all_spare_origins]
        )
        foc_row = self.env.cr.fetchone()
        foc_cost_today = float(foc_row[0]) if foc_row else 0.0
        foc_cost_yesterday = float(foc_row[1]) if foc_row else 0.0
        foc_cost_trend = ((foc_cost_today - foc_cost_yesterday) / foc_cost_yesterday * 100) if foc_cost_yesterday else 0

        res = {
            'approvals': {'pending': pending_approvals, 'approved': approved_requests, 'rejected': rejected_requests, 'blocked_value': blocked_value},
            'bottlenecks': bottlenecks_data,
            'trends': trends,
            'top_vendors': top_vendors,
            'money_flow': {
                'outward_spend': {'value': outward_today, 'trend': round(outward_trend, 1)},
                'inward_purchase': {'value': inward_today, 'trend': round(inward_trend, 1)}, 
                'payables_pending': {'value': payables_pending_val, 'trend': 0},
                'project_spend': {'value': project_spend_today, 'trend': round(project_spend_trend, 1)},
                'foc_cost': {'value': foc_cost_today, 'trend': round(foc_cost_trend, 1)},
                'inventory_value': {'value': inventory_value, 'trend': 0}
            },
            'spend_view_data': {'timeline': spend_timeline, 'category': spend_category},
            'projects_page': {
                'active_projects': len(all_active_so),
                'total_budget': total_budget_allocated,
                'total_spent': total_project_spent,
                'project_list': projects_list,
                 'approvals': {
                    'pending': pending_approvals,
                    'approved': approved_requests,
                    'rejected': rejected_requests,
                    'blocked_value': blocked_value,
                    'bottlenecks': bottlenecks_data
                }
            },
            'inventory_page': {
                 'total_value': inventory_value,
                'split': inventory_split,
                'aging_data': self._get_inventory_aging_data(start_date, end_date, location_id, category_id), 
                'forecast': self._get_inventory_forecast(start_date, end_date, project_id, customer_id, vendor_id, location_id, category_id)
            },
            'foc_page': self._get_foc_page_data(start_date, end_date, customer_id, project_id, vendor_id, location_id, category_id),
            'forecast_page': self._get_forecast_page_data(start_date, end_date, customer_id)
        }
        
        if not skip_kpi:
            res.update({
                'revenue': revenue_val,
                'spend': spend_val,
                'margin': margin,
                'margin_pct': margin_pct,
                'inventory': inventory_value,
                'last_updated': datetime.now().strftime('%b %d, %Y - %I:%M %p'),
                'projects': {'on_track': active_projects_count, 'at_risk': 0, 'over_budget': 0},
            })
            
        return res
    @api.model
    def _get_inventory_forecast(self, start_date=None, end_date=None, project_id=None, 
                                customer_id=None, vendor_id=None, location_id=None, category_id=None):
        """
        Document-driven Forecast:
        Calculates forecasted procurement cost based ONLY on real open demand:
          1. Sale Orders (sale_or_spare = 'sale') - undelivered qty causing stock shortage
          2. User Material Requests - un-issued qty
          3. Spare Orders (sale_or_spare = 'spare') - undelivered qty causing stock shortage
        Excludes cancelled, done, closed, fully delivered/received records.
        Cost = remaining_qty * product.standard_price, only when on_hand < required.
        """
        company_id = self.env.company.id

        # --- On-Hand Stock (internal locations) ---
        domain_quant = [
            ('location_id.usage', '=', 'internal'),
            ('company_id', '=', company_id),
            ('quantity', '>', 0)
        ]
        if location_id:
            domain_quant += [('location_id', 'child_of', int(location_id))]
        if category_id:
            domain_quant += [('product_id.categ_id', 'child_of', int(category_id))]

        today = fields.Date.today()
        d30 = today + timedelta(days=30)
        d60 = today + timedelta(days=60)
        d90 = today + timedelta(days=90)

        # Buckets: 0: 0-30, 1: 31-60, 2: 61-90
        forecast_buckets = [0.0, 0.0, 0.0]
        committed_buckets = [0.0, 0.0, 0.0]

        # --- On-Hand Stock (internal locations) ---
        domain_quant = [
            ('location_id.usage', '=', 'internal'),
            ('company_id', '=', company_id),
            ('quantity', '>', 0)
        ]
        if location_id:
            domain_quant += [('location_id', 'child_of', int(location_id))]
        if category_id:
            domain_quant += [('product_id.categ_id', 'child_of', int(category_id))]

        quants = self.env['stock.quant'].sudo().search(domain_quant)
        available_stock = {}
        for q in quants:
            available_stock[q.product_id.id] = available_stock.get(q.product_id.id, 0.0) + q.quantity

        shortage_records = []
        
        # Helper to get date from record
        def get_rec_date(rec, field_name):
            val = getattr(rec, field_name)
            if not val:
                return today
            if isinstance(val, datetime):
                return val.date()
            return val

        # -----------------------------------------------------------------------
        # 1. SALE ORDERS & SPARE ORDERS (DEMAND)
        # -----------------------------------------------------------------------
        so_domain = [
            ('company_id', '=', company_id),
            ('state', 'in', ('sale', 'done')),
            ('commitment_date', '<=', d90.strftime('%Y-%m-%d 23:59:59')) # Only look ahead 90 days
        ]
        if customer_id:
            so_domain += [('partner_id', '=', int(customer_id))]
        if project_id:
            so_domain += [('project_id', '=', int(project_id))]
        if category_id:
            so_domain += [('order_line.product_id.categ_id', 'child_of', int(category_id))]

        sale_orders = self.env['sale.order'].sudo().search(so_domain)

        for so in sale_orders:
            # Use commitment_date if available, else date_order
            so_date = get_rec_date(so, 'commitment_date') or get_rec_date(so, 'date_order')
            bucket_idx = -1
            if so_date <= d30: bucket_idx = 0
            elif so_date <= d60: bucket_idx = 1
            elif so_date <= d90: bucket_idx = 2
            
            if bucket_idx == -1: continue

            for line in so.order_line:
                if not line.product_id or line.product_id.type == 'service':
                    continue
                pending_qty = (line.product_uom_qty or 0.0) - (line.qty_delivered or 0.0)
                if pending_qty <= 0:
                    continue

                pid = line.product_id.id
                on_hand = available_stock.get(pid, 0.0)
                shortage_qty = max(0.0, pending_qty - on_hand)
                
                # Consume stock regardless of bucket (first come first served)
                available_stock[pid] = max(0.0, on_hand - pending_qty)
                
                if shortage_qty > 0:
                    cost = shortage_qty * line.product_id.standard_price
                    forecast_buckets[bucket_idx] += cost
                    
                    shortage_records.append({
                        'id': f"{'so' if so.sale_or_spare != 'spare' else 'spare'}_{so.id}_{line.id}",
                        'source': 'Sale Order' if so.sale_or_spare != 'spare' else 'Spare Order',
                        'document': so.name,
                        'model': 'sale.order',
                        'res_id': so.id,
                        'product': line.product_id.display_name,
                        'ordered_qty': line.product_uom_qty,
                        'delivered_qty': line.qty_delivered,
                        'shortage_qty': shortage_qty,
                        'cost': cost,
                        'impact': 'High Impact' if cost > 10000 else 'Medium Impact',
                        'product_tmpl_id': line.product_id.product_tmpl_id.id
                    })

        # -----------------------------------------------------------------------
        # 2. USER MATERIAL REQUESTS
        # -----------------------------------------------------------------------
        mr_domain = [
            ('state', 'in', ('approved', 'full_approve', 'onhand_approve', 'waiting_ceo_approval')),
            ('request_type', '=', 'user'),
            ('date', '<=', d90)
        ]
        if location_id:
            mr_domain += [('dest_loc_id', 'child_of', int(location_id))]

        mrs = self.env['material.request'].sudo().search(mr_domain)
        for mr in mrs:
            mr_date = get_rec_date(mr, 'date')
            bucket_idx = -1
            if mr_date <= d30: bucket_idx = 0
            elif mr_date <= d60: bucket_idx = 1
            elif mr_date <= d90: bucket_idx = 2
            
            if bucket_idx == -1: continue

            for line in mr.request_line_ids:
                pending_qty = (line.demand_qty or 0.0) - (line.approve_qty or 0.0) # Assuming approve_qty is issued?
                if pending_qty <= 0: continue

                pid = line.product_id.id
                on_hand = available_stock.get(pid, 0.0)
                shortage_qty = max(0.0, pending_qty - on_hand)
                
                available_stock[pid] = max(0.0, on_hand - pending_qty)
                
                if shortage_qty > 0:
                    cost = shortage_qty * line.product_id.standard_price
                    forecast_buckets[bucket_idx] += cost
                    
                    shortage_records.append({
                        'id': f"mr_{mr.id}_{line.id}",
                        'source': 'Material Request',
                        'document': mr.name,
                        'model': 'material.request',
                        'res_id': mr.id,
                        'product': line.product_id.display_name,
                        'ordered_qty': line.demand_qty,
                        'delivered_qty': line.approve_qty,
                        'shortage_qty': shortage_qty,
                        'cost': cost,
                        'impact': 'High Impact' if cost > 10000 else 'Medium Impact',
                        'product_tmpl_id': line.product_id.product_tmpl_id.id
                    })

        # -----------------------------------------------------------------------
        # 3. COMMITTED ORDERS (Confirmed Purchase Orders)
        # -----------------------------------------------------------------------
        po_domain = [
            ('state', 'in', ('purchase', 'done')),
            ('company_id', '=', company_id),
            ('date_planned', '<=', d90.strftime('%Y-%m-%d 23:59:59'))
        ]
        if vendor_id:
            po_domain += [('partner_id', '=', int(vendor_id))]
        
        # Note: Filtering POs by project/category is harder without direct links in all SOs
        purchase_orders = self.env['purchase.order'].sudo().search(po_domain)
        for po in purchase_orders:
            po_date = get_rec_date(po, 'date_planned')
            bucket_idx = -1
            if po_date <= d30: bucket_idx = 0
            elif po_date <= d60: bucket_idx = 1
            elif po_date <= d90: bucket_idx = 2
            
            if bucket_idx == -1: continue
            
            po_val = sum(line.price_subtotal for line in po.order_line)
            committed_buckets[bucket_idx] += po_val

        # Sort shortages and prepare cards
        shortage_records.sort(key=lambda x: x['cost'], reverse=True)
        
        # Cumulative results for the 3 cards
        c30_f = forecast_buckets[0]
        c30_c = committed_buckets[0]
        
        c60_f = c30_f + forecast_buckets[1]
        c60_c = c30_c + committed_buckets[1]
        
        c90_f = c60_f + forecast_buckets[2]
        c90_c = c60_c + committed_buckets[2]

        cards = [
            {'label': 'Next 30 days', 'forecasted': c30_f, 'committed': c30_c, 'pending': max(0, c30_f - c30_c)},
            {'label': 'Next 60 days', 'forecasted': c60_f, 'committed': c60_c, 'pending': max(0, c60_f - c60_c)},
            {'label': 'Next 90 days', 'forecasted': c90_f, 'committed': c90_c, 'pending': max(0, c90_f - c90_c)},
        ]

        # Prepare top items with expected keys for frontend
        top_shortage_items = [
            {
                'id': r['id'],
                'name': r['product'],
                'document': r['document'],
                'source': r['source'],
                'value': r['cost'],
                'impact': r['impact'],
                'product_tmpl_id': r.get('product_tmpl_id')
            }
            for r in shortage_records[:10]
        ]

        # --- Historical: Past 30 days actual PO spend ---
        d_past30 = today - timedelta(days=30)
        self.env.cr.execute("""
            SELECT COALESCE(SUM(pol.price_subtotal), 0.0)
            FROM purchase_order_line pol
            JOIN purchase_order po ON po.id = pol.order_id
            WHERE po.company_id = %s
              AND po.state IN ('purchase', 'done')
              AND po.date_approve >= %s
              AND po.date_approve < %s
        """, [company_id, d_past30, today])
        row = self.env.cr.fetchone()
        past_30d_spend = float(row[0]) if row else 0.0

        # --- Historical: Today's PO spend (committed + received) ---
        self.env.cr.execute("""
            SELECT COALESCE(SUM(pol.price_subtotal), 0.0)
            FROM purchase_order_line pol
            JOIN purchase_order po ON po.id = pol.order_id
            WHERE po.company_id = %s
              AND po.state IN ('purchase', 'done')
              AND po.date_approve::date = %s
        """, [company_id, today])
        row2 = self.env.cr.fetchone()
        today_spend = float(row2[0]) if row2 else 0.0

        return {
            'cash_required_30d': c30_f,
            'cards': cards,
            'shortages': {
                'total_at_risk': c90_f,
                'items': top_shortage_items,
                'full_items': [
                    {
                        'id': r['id'],
                        'name': r['product'],
                        'document': r['document'],
                        'source': r['source'],
                        'value': r['cost'],
                        'impact': r['impact'],
                        'res_id': r.get('res_id'),
                        'model': r.get('model'),
                        'ordered_qty': r.get('ordered_qty', 0),
                        'delivered_qty': r.get('delivered_qty', 0),
                        'shortage_qty': r.get('shortage_qty', 0),
                        'product_tmpl_id': r.get('product_tmpl_id')
                    }
                    for r in shortage_records
                ]
            },
            'cash_requirement': c30_f,
            'daily_projection': [
                {'label': 'Past 30 days', 'forecasted': past_30d_spend, 'committed': past_30d_spend},
                {'label': 'Current Days',  'forecasted': today_spend,    'committed': today_spend},
                {'label': 'Next 30 days',  'forecasted': c30_f,          'committed': c30_c},
                {'label': 'Next 60 days',  'forecasted': c60_f,          'committed': c60_c},
                {'label': 'Next 90 days',  'forecasted': c90_f,          'committed': c90_c},
            ]
        }

    @api.model
    def get_forecast_shortage_drilldown(self, project_id=None, customer_id=None, location_id=None, category_id=None):
        """
        Returns all shortage-causing records for the drill-down view.
        Called from the frontend when the user clicks Forecasted Cost / Material Shortages.
        """
        company_id = self.env.company.id

        # On-hand stock
        domain_quant = [('location_id.usage', '=', 'internal'), ('company_id', '=', company_id), ('quantity', '>', 0)]
        if location_id:
            domain_quant += [('location_id', 'child_of', int(location_id))]
        if category_id:
            domain_quant += [('product_id.categ_id', 'child_of', int(category_id))]
        quants = self.env['stock.quant'].sudo().search(domain_quant)
        available_stock = {}
        for q in quants:
            available_stock[q.product_id.id] = available_stock.get(q.product_id.id, 0.0) + q.quantity

        # Re-run the document scan to collect all shortage record IDs and details
        # (Reuse _get_inventory_forecast data but return full records for drill-down)
        forecast_data = self._get_inventory_forecast(
            project_id=project_id, customer_id=customer_id,
            location_id=location_id, category_id=category_id
        )
        # Return the full list stored dynamically to bypass the top 10 slicing done for the cards
        return forecast_data.get('shortages', {}).get('full_items', [])

    @api.model
    def _get_inventory_aging_data(self, start_date=None, end_date=None, location_id=None, category_id=None):
        """ Calculate inventory aging based on stock move dates """
        today = fields.Date.today()
        
        # Build domain for stock quants
        domain_quants = [
            ('company_id', '=', self.env.company.id),
            ('location_id.usage', '=', 'internal'),
            ('quantity', '>', 0)
        ]
        
        if location_id:
            domain_quants += [('location_id', 'child_of', int(location_id))]
        if category_id:
            domain_quants += [('product_id.categ_id', 'child_of', int(category_id))]
        
        quants = self.env['stock.quant'].search(domain_quants)
        
        # Initialize aging buckets
        aging_buckets = {
            '0-30 days': {'value': 0.0, 'color': '#3b82f6', 'label': '0-30 days'},
            '31-90 days': {'value': 0.0, 'color': '#f59e0b', 'label': '31-90 days'},
            '90+ days': {'value': 0.0, 'color': '#ef4444', 'label': '90+ days'}
        }
        
        for quant in quants:
            # Find the most recent incoming stock move for this product/location
            domain_moves = [
                ('product_id', '=', quant.product_id.id),
                ('location_dest_id', '=', quant.location_id.id),
                ('state', '=', 'done'),
                ('company_id', '=', self.env.company.id)
            ]
            
            # Apply date filters if provided
            # Note: For aging, we want the *original* arrival date, so we do NOT filter by start_date.
            # We only filter by end_date if provided (to simulate "aging as of X", though we are using current quants).
            if end_date:
                _, end_utc = self._get_datetime_range_utc(None, end_date)
                domain_moves += [('date', '<=', end_utc)]
            
            # Get the most recent incoming move
            recent_move = self.env['stock.move'].search(
                domain_moves,
                order='date desc',
                limit=1
            )
            
            if recent_move and recent_move.date:
                move_date = recent_move.date.date() if isinstance(recent_move.date, datetime) else recent_move.date
                age_days = (today - move_date).days
            else:
                # If no move found, assume old stock
                age_days = 91
            
            # Calculate value
            stock_value = quant.quantity * quant.product_id.standard_price
            
            # Assign to appropriate bucket
            if age_days <= 30:
                aging_buckets['0-30 days']['value'] += stock_value
            elif age_days <= 90:
                aging_buckets['31-90 days']['value'] += stock_value
            else:
                aging_buckets['90+ days']['value'] += stock_value
        
        # Convert to list format for frontend
        return [
            {
                'label': bucket['label'],
                'value': bucket['value'],
                'color': bucket['color']
            }
            for bucket in aging_buckets.values()
        ]

    @api.model
    def _get_foc_page_data(self, start_date=None, end_date=None, customer_id=None, project_id=None, vendor_id=None, location_id=None, category_id=None):
        """ Calculate FOC (Free of Cost) data based on Spare Orders (sale_or_spare='spare') """
        if not end_date:
            end_date = fields.Date.today()
        
        # Ensure start_date and end_date are date objects
        if isinstance(start_date, str):
            start_date = fields.Date.from_string(start_date)
        if isinstance(end_date, str):
            end_date = fields.Date.from_string(end_date)
            
        if not start_date:
            start_date = end_date.replace(day=1)
            
        # For MTD/YTD, we use the end_date as the anchor
        current_month_start = end_date.replace(day=1)
        current_year_start = end_date.replace(month=1, day=1)
        
        # Build common domain for FOC items (Spare orders with price_unit=0 or subtotal=0)
        # Requirement: sale_or_spare='spare' and (unit price is 0 or subtotal is 0 or is_foc flag if exists)
        base_foc_domain = [
            ('order_id.state', 'in', ('sale', 'done')),
            ('order_id.sale_or_spare', '=', 'spare'),
            ('product_id', '!=', False),
            ('company_id', '=', self.env.company.id)
        ]
        
        # Apply Global Filters to base domain
        if customer_id:
            base_foc_domain += [('order_id.partner_id', '=', int(customer_id))]
        if project_id:
            base_foc_domain += [('order_id.project_id', '=', int(project_id))]
        if vendor_id:
            base_foc_domain += [('order_id.partner_id', '=', int(vendor_id))] # Filtering by client/vendor
        if category_id:
            base_foc_domain += [('product_id.categ_id', 'child_of', int(category_id))]
        
        # Date filtering logic - use expected_delivery_date if available (on order_id) or date_order
        date_field = 'order_id.expected_delivery_date' # As per sale_extended.py
        
        def apply_date_domain(domain, start, end):
            new_domain = domain + []
            start_utc, end_utc = self._get_datetime_range_utc(start, end)
            if start_utc:
                new_domain += ['|', (date_field, '>=', start_utc), ('order_id.date_order', '>=', start_utc)]
            if end_utc:
                new_domain += ['|', (date_field, '<=', end_utc), ('order_id.date_order', '<=', end_utc)]
            return new_domain

        # Current range domain
        domain_foc = apply_date_domain(base_foc_domain, start_date, end_date)
        
        # Product cost cache to avoid redundant BOM explosions
        product_costs = {}
        def get_product_cost(product):
            if product.id not in product_costs:
                product_costs[product.id] = self._get_bom_cost(product)
            return product_costs[product.id]

        # MTD domain
        domain_mtd = apply_date_domain(base_foc_domain, current_month_start, end_date)
            
        foc_lines_mtd = self.env['sale.order.line'].search(domain_mtd)
        # Using amount_total of the orders instead of BoM cost to match the user's "Spare order cost total" requirement
        # which refers to the total value seen in the Spare Orders list.
        # We group by order to avoid double-counting if we just summed amount_total of all lines' orders.
        mtd_cost = sum(foc_lines_mtd.mapped('order_id').mapped('amount_total'))
        
        # YTD domain
        domain_ytd = apply_date_domain(base_foc_domain, current_year_start, end_date)
            
        foc_lines_ytd = self.env['sale.order.line'].search(domain_ytd)
        ytd_cost = sum(foc_lines_ytd.mapped('order_id').mapped('amount_total'))
        
        # Calculate revenue percentage (using Spare Orders Revenue within selected range)
        # Requirement: FOC percentage of revenue (usually based on all sale orders revenue)
        domain_revenue = [
            ('state', 'in', ('sale', 'done')), 
            ('sale_or_spare', '=', 'spare'),
            ('company_id', '=', self.env.company.id)
        ]
        start_utc, end_utc = self._get_datetime_range_utc(start_date, end_date)
        if start_utc:
            domain_revenue += [('date_order', '>=', start_utc)]
        if end_utc:
            domain_revenue += [('date_order', '<=', end_utc)]
        if customer_id:
            domain_revenue += [('partner_id', '=', int(customer_id))]
        
        total_revenue = sum(self.env['sale.order'].search(domain_revenue).mapped('amount_total'))
        
        # Total FOC cost for selected range
        foc_lines_range = self.env['sale.order.line'].search(domain_foc)
        total_foc_cost_range = sum(line.product_uom_qty * get_product_cost(line.product_id) for line in foc_lines_range)
        
        revenue_pct = (total_foc_cost_range / total_revenue * 100) if total_revenue else 0
        
        # Trend data - monthly grouping
        trend_labels = []
        trend_foc_costs = []
        trend_revenue = []
        
        current_date = start_date.replace(day=1)
        while current_date <= end_date:
            month_start = current_date
            month_end = month_start + relativedelta(months=1, days=-1)
            if month_end > end_date:
                month_end = end_date
            
            month_label = month_start.strftime('%b')
            
            domain_month_foc = apply_date_domain(base_foc_domain, month_start, month_end)
            month_foc_lines = self.env['sale.order.line'].search(domain_month_foc)
            month_foc_cost = sum(line.product_uom_qty * get_product_cost(line.product_id) for line in month_foc_lines)
            
            month_start_utc, month_end_utc = self._get_datetime_range_utc(month_start, month_end)
            domain_month_rev = [
                ('state', 'in', ('sale', 'done')),
                ('sale_or_spare', '=', 'spare'),
                ('date_order', '>=', month_start_utc),
                ('date_order', '<=', month_end_utc)
            ]
            if customer_id:
                domain_month_rev += [('partner_id', '=', int(customer_id))]
            
            month_revenue = sum(self.env['sale.order'].search(domain_month_rev).mapped('amount_total'))
            
            trend_labels.append(month_label)
            trend_foc_costs.append(month_foc_cost)
            trend_revenue.append(month_revenue)
            
            current_date = current_date + relativedelta(months=1)
        
        # Top clients by FOC cost - grouping by partner record for ID and Name
        client_foc_map = {} # partner_record -> cost
        for line in foc_lines_range:
            p = line.order_id.partner_id
            if not p: continue
            client_foc_map[p] = client_foc_map.get(p, 0) + (line.product_uom_qty * get_product_cost(line.product_id))
        
        top_clients = []
        for p, cost in sorted(client_foc_map.items(), key=lambda x: x[1], reverse=True)[:5]:
            top_clients.append({
                'partner_id': p.id,
                'name': p.name,
                'value': cost,
                'reason': 'Replacement / Warranty' if cost > 10000 else 'Sample / Promotion',
                'reason_type': 'replacement' if cost > 10000 else 'sample'
            })
        top_client = top_clients[0]['name'] if top_clients else 'N/A'
        
        # Machine-wise breakdown - grouping by machine_id
        machine_foc_map = {}
        for line in foc_lines_range:
            # Use machine_id if available, fallback to product name
            machine_name = line.machine_id or line.product_id.display_name or 'Unspecified'
            foc_cost = line.product_uom_qty * get_product_cost(line.product_id)
            machine_foc_map[machine_name] = machine_foc_map.get(machine_name, 0) + foc_cost
        
        machines = [{'name': name, 'value': cost} for name, cost in sorted(machine_foc_map.items(), key=lambda x: x[1], reverse=True)[:10]]
        
        return {
            'mtd_cost': mtd_cost,
            'ytd_cost': ytd_cost,
            'revenue_pct': round(revenue_pct, 2),
            'top_client': top_client,
            'trend': {
                'labels': trend_labels,
                'foc_costs': trend_foc_costs,
                'revenue': trend_revenue
            },
            'clients': top_clients,
            'machines': machines
        }

    @api.model
    def _get_forecast_page_data(self, start_date=None, end_date=None, customer_id=None):
        """ Calculate business forecast data """
        # Ensure start_date and end_date are date objects
        if isinstance(start_date, str):
            start_date = fields.Date.from_string(start_date)
        if isinstance(end_date, str):
            end_date = fields.Date.from_string(end_date)
            
        if not start_date:
            start_date = fields.Date.today().replace(day=1)
        if not end_date:
            end_date = (start_date + relativedelta(months=5, day=31))
            
        labels = []
        revenue_data = []
        target_data = []
        
        # Iterate through months from start_date to end_date
        current_date = start_date
        while current_date <= end_date:
            month_start = current_date.replace(day=1)
            month_end = month_start + relativedelta(months=1, days=-1)
            
            # If the month ends after our end_date, cap it (though logically for monthly forecast we usually take whole months)
            # Staying with whole months logic as standard for charts
            
            labels.append(month_start.strftime('%b %Y'))
            
            month_start_utc, month_end_utc = self._get_datetime_range_utc(month_start, month_end)
            domain_so = [
                ('state', 'in', ('sale', 'done')),
                ('commitment_date', '>=', month_start_utc),
                ('commitment_date', '<=', month_end_utc)
            ]
            if customer_id:
                domain_so += [('partner_id', '=', int(customer_id))]
            
            projected_revenue = sum(self.env['sale.order'].search(domain_so).mapped('amount_total'))
            target = projected_revenue * 1.2
            
            revenue_data.append(projected_revenue)
            target_data.append(target)
            
            # Move to next month
            current_date = current_date + relativedelta(months=1)
        
        return {
            'labels': labels,
            'revenue': revenue_data,
            'target': target_data
        }

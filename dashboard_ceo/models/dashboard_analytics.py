from odoo import models, fields, api, tools
from datetime import datetime, timedelta
import pytz

class DashboardAnalyticsService(models.AbstractModel):
    _name = 'dashboard.analytics.service'
    _description = 'Optimized Dashboard Analytics SQL Service'

    @api.model
    def _get_datetime_range_utc(self, start_date, end_date):
        user_tz = self.env.context.get('tz') or 'UTC'
        local_tz = pytz.timezone(user_tz)
        start_utc = end_utc = None
        if start_date:
            if isinstance(start_date, str): start_date = fields.Date.from_string(start_date)
            start_utc = local_tz.localize(datetime.combine(start_date, datetime.min.time())).astimezone(pytz.UTC).replace(tzinfo=None)
        if end_date:
            if isinstance(end_date, str): end_date = fields.Date.from_string(end_date)
            end_utc = local_tz.localize(datetime.combine(end_date, datetime.max.time())).astimezone(pytz.UTC).replace(tzinfo=None)
        return start_utc, end_utc

    @api.model
    def _build_global_filters(self, start_date=None, end_date=None, project_id=None, customer_id=None, vendor_id=None, location_id=None, category_id=None):
        """ Returns a dict of SQL WHERE clauses and parameters for different tables """
        filters = {
            'sale': {'where': ["company_id = %s", "sale_or_spare = 'sale'"], 'params': [self.env.company.id]},
            'purchase': {'where': ["company_id = %s"], 'params': [self.env.company.id]},
            'account_move': {'where': ["company_id = %s"], 'params': [self.env.company.id]},
            'stock_move': {'where': ["company_id = %s"], 'params': [self.env.company.id]},
            'quant': {'where': ["company_id = %s"], 'params': [self.env.company.id]},
        }
        
        start_utc, end_utc = self._get_datetime_range_utc(start_date, end_date)
        
        if start_utc:
            filters['sale']['where'].append("date_order >= %s"); filters['sale']['params'].append(start_utc)
            filters['purchase']['where'].append("date_order >= %s"); filters['purchase']['params'].append(start_utc) # Use date_order for PO too for consistency with SO if that's the intention, or date_approve
            filters['stock_move']['where'].append("date >= %s"); filters['stock_move']['params'].append(start_utc)
        if end_utc:
            filters['sale']['where'].append("date_order <= %s"); filters['sale']['params'].append(end_utc)
            filters['purchase']['where'].append("date_order <= %s"); filters['purchase']['params'].append(end_utc)
            filters['stock_move']['where'].append("date <= %s"); filters['stock_move']['params'].append(end_utc)
            
        if start_date:
            filters['account_move']['where'].append("invoice_date >= %s"); filters['account_move']['params'].append(start_date)
        if end_date:
            filters['account_move']['where'].append("invoice_date <= %s"); filters['account_move']['params'].append(end_date)
            
        if project_id:
            # In Odoo 18, sale.order often links to projects via project_id (if sale_project is installed)
            # or we look up by name/ref if it's a custom field.
            # Based on ceo_dashboard.py, it was trying to use 'id' of sale.order which is wrong.
            # We should filter sale_order where project_id = project_id
            filters['sale']['where'].append("project_id = %s"); filters['sale']['params'].append(int(project_id))
            # For purchase, we might need to look at origin or analytic accounts.
            # For now, let's assume it can be filtered by project_id if the field exists.

        if customer_id:
            filters['sale']['where'].append("partner_id = %s"); filters['sale']['params'].append(int(customer_id))
            filters['account_move']['where'].append("partner_id = %s"); filters['account_move']['params'].append(int(customer_id))
            filters['stock_move']['where'].append("partner_id = %s"); filters['stock_move']['params'].append(int(customer_id))
            
        if vendor_id:
            # DO NOT filter sale by vendor_id
            filters['purchase']['where'].append("partner_id = %s"); filters['purchase']['params'].append(int(vendor_id))
            filters['account_move']['where'].append("partner_id = %s"); filters['account_move']['params'].append(int(vendor_id))
            filters['stock_move']['where'].append("partner_id = %s"); filters['stock_move']['params'].append(int(vendor_id))
            
        if location_id:
            child_locs = self.env['stock.location'].search([('id', 'child_of', int(location_id))]).ids
            if child_locs:
                loc_placeholder = tuple(child_locs)
                filters['stock_move']['where'].append(f"location_id IN %s"); filters['stock_move']['params'].append(loc_placeholder)
                filters['quant']['where'].append(f"location_id IN %s"); filters['quant']['params'].append(loc_placeholder)
                
        if category_id:
            child_cats = self.env['product.category'].search([('id', 'child_of', int(category_id))]).ids
            if child_cats:
                cat_placeholder = tuple(child_cats)
                filters['category_in'] = f"pt.categ_id IN %s"
                filters['category_params'] = [cat_placeholder]
        
        return filters

    @api.model
    def _compute_project_health(self, filters):
        """ Calculate health status for active projects """
        sale_where = " AND ".join(filters['sale']['where']) + " AND state IN ('sale', 'done')"
        
        domain_so_projects = [
            ('state', 'in', ('sale', 'done')),
            ('company_id', '=', self.env.company.id),
            ('sale_or_spare', '=', 'sale')
        ]
        
        # Apply filters as domain
        # The exact same logic from ceo_dashboard.py for project calculations
        if filters['sale']['params']:
             # Not perfectly translating SQL params to domain, so we'll just re-read the context params
             # which are cleaner to pass if we just rebuild it
             pass

        # To keep it optimal but accurate, we use ORM for complex budget calculation since BOM cost is involved
        # For CEO dashboard, we just need to get the active projects and run the same loop as ceo_dashboard.py
        
        # Build domain from scratch based on identical logic
        # We can extract the raw sql IDs to be extremely fast and then browse
        self.env.cr.execute(f"SELECT id FROM sale_order WHERE {sale_where}", filters['sale']['params'])
        active_so_ids = [r[0] for r in self.env.cr.fetchall()]
        
        if not active_so_ids:
            return {
                'on_track': {'count': 0, 'ids': []},
                'at_risk': {'count': 0, 'ids': []},
                'over_budget': {'count': 0, 'ids': []},
            }

        projects = self.env['sale.order'].browse(active_so_ids)
        
        health_data = {
            'on_track': {'count': 0, 'ids': []},
            'at_risk': {'count': 0, 'ids': []},
            'over_budget': {'count': 0, 'ids': []},
        }
        
        for so in projects:
            so_budget = sum(
                (self.env['ceo.dashboard']._get_bom_cost(line.product_id) * line.product_uom_qty)
                for line in so.order_line if line.product_id
            )
            
            mo_names = self.env['mrp.production'].search([('origin', '=', so.name)]).mapped('name')
            mr_names = []
            try:
                with self.env.cr.savepoint():
                    mr_data = self.env['material.request'].sudo().search_read([('ref', '=', so.name)], ['name'])
                    mr_names = [r['name'] for r in mr_data]
            except Exception:
                pass
            
            domain_so_po = [
                ('state', 'in', ('purchase', 'done')),
                '|', '|',
                ('origin', '=', so.name),
                ('origin', 'in', mo_names),
                ('requisition_id.reference', 'in', mr_names)
            ]
            
            so_spent = sum(self.env['purchase.order'].search(domain_so_po).mapped('amount_total'))
            
            budget_utilization = (so_spent / so_budget) if so_budget > 0 else 0
            
            if budget_utilization > 1.0:
                health_data['over_budget']['count'] += 1
                health_data['over_budget']['ids'].append(so.id)
            elif budget_utilization >= 0.8:
                health_data['at_risk']['count'] += 1
                health_data['at_risk']['ids'].append(so.id)
            else:
                health_data['on_track']['count'] += 1
                health_data['on_track']['ids'].append(so.id)
                
        return health_data

    @api.model
    @tools.ormcache('start_date', 'end_date', 'project_id', 'customer_id', 'vendor_id', 'location_id', 'category_id')
    def get_kpi_data(self, start_date=None, end_date=None, project_id=None, customer_id=None, vendor_id=None, location_id=None, category_id=None):
        filters = self._build_global_filters(start_date, end_date, project_id, customer_id, vendor_id, location_id, category_id)

        # 1. Revenue
        sale_where = " AND ".join(filters['sale']['where']) + " AND state IN ('sale', 'done')"
        revenue_query = f"SELECT COALESCE(SUM(amount_total), 0.0) FROM sale_order WHERE {sale_where}"
        self.env.cr.execute(revenue_query, filters['sale']['params'])
        revenue_val = self.env.cr.fetchone()[0]

        # 2. Spend (Purchase Orders)
        po_where = " AND ".join(filters['purchase']['where']) + " AND state IN ('purchase', 'done')"
        po_query = f"SELECT COALESCE(SUM(amount_total), 0.0) FROM purchase_order WHERE {po_where}"
        self.env.cr.execute(po_query, filters['purchase']['params'])
        spend_val = self.env.cr.fetchone()[0]

        # 3. Margin
        margin = revenue_val - spend_val
        margin_pct = (margin / revenue_val * 100) if revenue_val else 0.0

        # 4. Inventory Value – Uses stock_valuation_layer.remaining_value via optimized SQL
        inventory_value = self.env['ceo.dashboard']._compute_inventory_valuation_sql(location_id, category_id)

        # 5. Project Health Status
        project_health = self._compute_project_health(filters)

        return {
            'revenue': revenue_val,
            'spend': spend_val,
            'margin': margin,
            'margin_pct': margin_pct,
            'inventory': inventory_value,
            'projects': {
                'on_track': project_health['on_track']['count'],
                'at_risk': project_health['at_risk']['count'],
                'over_budget': project_health['over_budget']['count'],
                'on_track_ids': project_health['on_track']['ids'],
                'at_risk_ids': project_health['at_risk']['ids'],
                'over_budget_ids': project_health['over_budget']['ids'],
            },
            'last_updated': datetime.now().strftime('%b %d, %Y - %I:%M %p'),
        }

    @api.model
    def get_graph_data(self, start_date=None, end_date=None, project_id=None, customer_id=None, vendor_id=None, location_id=None, category_id=None):
        # We will dispatch to other methods based on needs, or return all graphs here.
        # For performance, this returns the heavier graph data natively without creating dummy records.
        return self.env['ceo.dashboard'].with_context(prefetch_fields=False).get_dashboard_data(
            start_date=start_date, end_date=end_date, project_id=project_id, 
            customer_id=customer_id, vendor_id=vendor_id, 
            location_id=location_id, category_id=category_id,
            skip_kpi=True
        )

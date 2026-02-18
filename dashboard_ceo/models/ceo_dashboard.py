from odoo import models, fields, api, _
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import pytz

class CEODashboard(models.Model):
    _name = 'ceo.dashboard'
    _description = 'CEO Dashboard'

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
    def action_approve_record(self, model, res_id):
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
            domain_so += [('id', '=', int(project_id))] # Use SO id if project filter matches SO
            
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
    def get_approval_action(self, status_type, start_date=None, end_date=None, customer_id=None):

        domain_so = [('company_id', '=', self.env.company.id)]
        domain_mr = [('company_id', '=', self.env.company.id)] # MR usually has company_id or uses default rule
        
        start_utc, end_utc = self._get_datetime_range_utc(start_date, end_date)
        if start_utc:
            domain_so += [('date_order', '>=', start_utc)]
            domain_mr += [('create_date', '>=', start_utc)]
        if end_utc:
            domain_so += [('date_order', '<=', end_utc)]
            domain_mr += [('create_date', '<=', end_utc)]
        if customer_id:
            domain_so += [('partner_id', '=', int(customer_id))]

        target_model = 'sale.order'
        target_domain = []
        name = 'Approvals'

        if status_type == 'pending':
            name = _('Pending Approvals')
            domain_so_pending = domain_so + ['|', ('state', '=', 'waiting_ceo_approval'), ('approval_state', '=', 'to_approve')]
            if self.env['sale.order'].search_count(domain_so_pending):
                target_model = 'sale.order'
                target_domain = domain_so_pending
            else:
                target_model = 'material.request'
                target_domain = domain_mr + ['|', ('state', '=', 'waiting_ceo_approval'), '&', ('request_type', '=', 'user'), ('approve_type', '=', 'draft')]
        
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
            domain_so_rejected = domain_so + [('state', '=', 'rejected')]
            if self.env['sale.order'].search_count(domain_so_rejected):
                target_model = 'sale.order'
                target_domain = domain_so_rejected
            else:
                target_model = 'material.request'
                target_domain = domain_mr + [('state', '=', 'rejected')]

        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': target_model,
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': target_domain,
            'target': 'current',
        }

    @api.model
    def action_reject_record(self, model, res_id, reason):
        record = self.env[model].browse(res_id)
        vals = {
            'state': 'rejected',
            'reject_reason': reason,
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
            available_fields = record._fields.keys()
            safe_vals = {'state': 'rejected'}
            if 'reject_reason' in available_fields: safe_vals['reject_reason'] = reason
            try:
                record.write(safe_vals)
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
            domain += [('id', '=', int(project_id))]
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
    def get_dashboard_data(self, time_range='This Month', start_date=None, end_date=None, 
                          project_id=None, customer_id=None, vendor_id=None, 
                          location_id=None, category_id=None):
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

        domain_revenue = [('state', 'in', ('sale', 'done')), ('company_id', '=', self.env.company.id)]
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
        
        if vendor_id:
            domain_spend += [('partner_id', '=', int(vendor_id))]
            domain_po += [('partner_id', '=', int(vendor_id))]
        
        if project_id:
            domain_mr += [('project_id', '=', int(project_id))]
            
        revenue_val = sum(self.env['sale.order'].search(domain_revenue).mapped('amount_total'))
        
        spend_val = sum(self.env['purchase.order'].search(domain_po).mapped('amount_total'))
        
        margin = revenue_val - spend_val
        margin_pct = (margin / revenue_val * 100) if revenue_val else 0.0

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

        # 2. Inventory Calculation (Strictly based on stock.quant for location filter)
        domain_quants = [('company_id', '=', self.env.company.id), ('location_id.usage', '=', 'internal'), ('quantity', '>', 0)]
        if location_id:
            domain_quants += [('location_id', 'child_of', int(location_id))]
        if category_id:
            domain_quants += [('product_id.categ_id', 'child_of', int(category_id))]
        
        quants = self.env['stock.quant'].search(domain_quants)
        inventory_value = sum(q.quantity * q.product_id.standard_price for q in quants) or 0.0

        # 3. Trends (Last 6 Months - Always fixed 6 months for trend chart usually)
        trends = []
        for i in range(5, -1, -1):
            date_start = (current_month_start - relativedelta(months=i))
            date_end = (date_start + relativedelta(months=1, days=-1))
            month_label = date_start.strftime('%b')
            
            d_rev = [('move_type', '=', 'out_invoice'), ('state', '=', 'posted'), ('invoice_date', '>=', date_start), ('invoice_date', '<=', date_end)]
            d_spd = [('move_type', '=', 'in_invoice'), ('state', '=', 'posted'), ('invoice_date', '>=', date_start), ('invoice_date', '<=', date_end)]
            
            m_rev = sum(self.env['account.move'].search(d_rev).mapped('amount_total'))
            m_spd = sum(self.env['account.move'].search(d_spd).mapped('amount_total'))
            
            trends.append({'month': month_label, 'revenue': m_rev, 'spend': m_spd})

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
            ('company_id', '=', self.env.company.id)
        ]
        if start_utc:
            domain_so_projects += [('date_order', '>=', start_utc)]
        if end_utc:
            domain_so_projects += [('date_order', '<=', end_utc)]
        if customer_id:
            domain_so_projects += [('partner_id', '=', int(customer_id))]
            
        all_active_so = self.env['sale.order'].search(domain_so_projects, order='date_order desc')
        active_projects_count = len(all_active_so)
        
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

        so_pending = self.env['sale.order'].search([
            ('company_id', '=', self.env.company.id),
            '|',
            ('state', '=', 'waiting_ceo_approval'),
            ('approval_state', '=', 'to_approve')
        ])
        for so in so_pending:
            pending_approvals += 1
            blocked_value += so.amount_total
            bottlenecks_data.append({
                'id': so.name,
                'res_id': so.id,
                'model': 'sale.order',
                'amount': so.amount_total,
                'user': so.user_id.name,
                'date': so.date_order.date().isoformat() if so.date_order else so.create_date.date().isoformat(),
                'waiting': (fields.Date.today() - so.create_date.date()).days,
                'source': 'Spare' if so.sale_or_spare == 'spare' else 'Sale',
                'status': 'Waiting CEO Approval'
            })

        # Fetch Pending Material Requests (All types including User requests)
        mr_pending_domain = [
            '|',
            ('state', '=', 'waiting_ceo_approval'),
            '&', ('request_type', '=', 'user'), ('approve_type', '=', 'draft')
        ]
        if location_id:
            mr_pending_domain += [('dest_loc_id', 'child_of', int(location_id))]
        
        mr_pending_data = []
        try:
            with self.env.cr.savepoint():
                mr_pending_data = self.env['material.request'].sudo().search_read(
                    mr_pending_domain, 
                    ['name', 'id', 'user_id', 'create_date', 'request_type', 'ref']
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
                'id': mr['name'],
                'res_id': mr['id'],
                'model': 'material.request',
                'amount': mr_val,
                'user': mr['user_id'][1] if isinstance(mr['user_id'], (list, tuple)) else 'System',
                'date': mr['create_date'].date().isoformat() if mr['create_date'] else fields.Date.today().isoformat(),
                'waiting': (fields.Date.today() - mr['create_date'].date()).days if mr['create_date'] else 0,
                'source': 'Material' if mr['request_type'] == 'user' else 'MRP',
                'status': 'To Approve'
            })

        try:
            with self.env.cr.savepoint():
                so_approved = self.env['sale.order'].search_count([
                    ('company_id', '=', self.env.company.id), 
                    ('state', 'in', ('sale', 'done'))
                ])
        except Exception:
            so_approved = 0
            
        try:
            with self.env.cr.savepoint():
                mr_app_domain = [('state', 'in', ('approved', 'received', 'full_approve', 'onhand_approve'))]
                if location_id:
                    mr_app_domain += [('dest_loc_id', 'child_of', int(location_id))]
                mr_approved = self.env['material.request'].sudo().search_count(mr_app_domain)
        except Exception:
            mr_approved = 0
                
        approved_requests = so_approved + mr_approved

        try:
            with self.env.cr.savepoint():
                so_rejected = self.env['sale.order'].search_count([
                    ('company_id', '=', self.env.company.id), 
                    ('state', '=', 'rejected')
                ])
        except Exception:
            so_rejected = 0
            
        try:
            with self.env.cr.savepoint():
                mr_rej_domain = [('state', '=', 'rejected')]
                if location_id:
                    mr_rej_domain += [('dest_loc_id', 'child_of', int(location_id))]
                mr_rejected = self.env['material.request'].sudo().search_count(mr_rej_domain)
        except Exception:
            mr_rejected = 0
            
        rejected_requests = so_rejected + mr_rejected

        # 6. Spend Analysis
        spend_timeline = {'labels': [], 'data': [], 'full_dates': [], 'model': 'stock.picking'}
        
        # Comprehensive Requirement: Calculate from stock.move (outgoing, done)
        # This allows filtering by category, vendor, and potentially project
        domain_moves = [
            ('picking_id.picking_type_id.code', '=', 'outgoing'),
            ('state', '=', 'done'),
            ('company_id', '=', self.env.company.id)
        ]
        if start_utc: 
            domain_moves += [('picking_id.date_done', '>=', start_utc)]
        if end_utc: 
            domain_moves += [('picking_id.date_done', '<=', end_utc)]
            
        # Filter by customer/vendor (picking partner)
        if vendor_id:
             domain_moves += [('picking_id.partner_id', '=', int(vendor_id))]
             
        # Filter by location
        if location_id:
             domain_moves += [('location_id', 'child_of', int(location_id))]

        # Filter by product category
        if category_id:
             domain_moves += [('product_id.categ_id', 'child_of', int(category_id))]

        moves = self.env['stock.move'].search(domain_moves)
        
        # Group by date
        move_data = {}
        for move in moves:
            if not move.picking_id.date_done:
                continue
            date_key = move.picking_id.date_done.date().isoformat()
            if date_key not in move_data:
                move_data[date_key] = 0.0
            
            # Sum (qty * cost)
            move_data[date_key] += move.product_uom_qty * move.product_id.standard_price

        # Sort dates and build timeline
        sorted_dates = sorted(move_data.keys())
        for d_str in sorted_dates:
            d_obj = fields.Date.from_string(d_str)
            spend_timeline['labels'].append(d_obj.strftime('%b %d'))
            spend_timeline['full_dates'].append(d_str)
            spend_timeline['data'].append(move_data[d_str])
        
        # Fallback to Bills if no material spend found for the timeframe
        if not spend_timeline['data']:
            spend_timeline['model'] = 'account.move'
            daily_spend = self.env['account.move'].read_group(
                domain_spend, ['invoice_date', 'amount_total:sum'], ['invoice_date:day'], orderby='invoice_date:day'
            )
            for day in daily_spend:
                 if day.get('invoice_date:day'):
                     # Odoo 18 returns dates in 'DD Mon YYYY' format from read_group
                     try:
                         date_obj = datetime.strptime(day.get('invoice_date:day'), '%d %b %Y')
                     except ValueError:
                         date_obj = datetime.strptime(day.get('invoice_date:day'), '%Y-%m-%d')
                     spend_timeline['labels'].append(date_obj.strftime('%b %d'))
                     spend_timeline['full_dates'].append(date_obj.strftime('%Y-%m-%d'))
                     spend_timeline['data'].append(day.get('amount_total', 0))
        
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

        # 9. Inventory Split (Use same quants as above for consistency)
        # Note: 'quants' is already filtered by location_id and category_id if they exist
        inventory_split = []
        split_data = {}
        for q in quants:
            cat_name = q.product_id.categ_id.name or 'Uncategorized'
            val = q.quantity * q.product_id.standard_price
            split_data[cat_name] = split_data.get(cat_name, 0.0) + val
        
        # Define a color palette for different categories
        colors = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#6366f1', '#14b8a6']
        
        for index, (cat, val) in enumerate(split_data.items()):
             inventory_split.append({
                 'label': cat,
                 'value': val,
                 'percentage': (val / inventory_value * 100) if inventory_value else 0,
                 'color': colors[index % len(colors)]
             })
        inventory_split.sort(key=lambda x: x['value'], reverse=True)
        inventory_split = inventory_split[:5]

        # 10. Money Flow Details
        inward_purchase_val = sum(self.env['purchase.order'].search(domain_po).mapped('amount_total'))
        
        domain_payables = [('move_type', '=', 'in_invoice'), ('state', '=', 'posted'), ('payment_state', 'in', ('not_paid', 'partial')), ('company_id', '=', self.env.company.id)]
        payables_pending_val = sum(self.env['account.move'].search(domain_payables).mapped('amount_residual'))
        
        # Project Spend Calculation (Sale Orders with sale_or_spare == 'sale')
        active_sale_orders = self.env['sale.order'].search([
            ('sale_or_spare', '=', 'sale'),
            ('state', 'not in', ('draft', 'cancel', 'sent')),
            ('company_id', '=', self.env.company.id)
        ])
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

        domain_project_po_base = [
            ('state', 'in', ('purchase', 'done')),
            ('company_id', '=', self.env.company.id),
            '|', '|',
            ('origin', 'in', so_names),
            ('origin', 'in', mo_names),
            ('requisition_id.reference', 'in', mr_names)
        ]

        # FOC Cost Calculation (Spare Orders) - Recent 24 hrs Purchases
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

        domain_spare_po_base = [
            ('state', 'in', ('purchase', 'done')),
            ('company_id', '=', self.env.company.id),
            '|', '|',
            ('origin', 'in', spare_so_names),
            ('origin', 'in', spare_mo_names),
            ('requisition_id.reference', 'in', spare_mr_names)
        ]

        # Trend calculation (Today vs Yesterday)
        today_start, today_end = self._get_datetime_range_utc(today_date, today_date)
        yester_start, yester_end = self._get_datetime_range_utc(yesterday_date, yesterday_date)

        project_spend_today = sum(self.env['purchase.order'].search(domain_project_po_base + [
            ('date_approve', '>=', today_start),
            ('date_approve', '<=', today_end)
        ]).mapped('amount_total'))
        
        project_spend_yesterday = sum(self.env['purchase.order'].search(domain_project_po_base + [
            ('date_approve', '>=', yester_start),
            ('date_approve', '<=', yester_end)
        ]).mapped('amount_total'))
        
        project_spend_trend = ((project_spend_today - project_spend_yesterday) / project_spend_yesterday * 100) if project_spend_yesterday else 0

        foc_cost_today = sum(self.env['purchase.order'].search(domain_spare_po_base + [
            ('date_approve', '>=', today_start),
            ('date_approve', '<=', today_end)
        ]).mapped('amount_total'))
        
        foc_cost_yesterday = sum(self.env['purchase.order'].search(domain_spare_po_base + [
            ('date_approve', '>=', yester_start),
            ('date_approve', '<=', yester_end)
        ]).mapped('amount_total'))
        
        foc_cost_trend = ((foc_cost_today - foc_cost_yesterday) / foc_cost_yesterday * 100) if foc_cost_yesterday else 0

        return {
            'revenue': revenue_val,
            'spend': spend_val,
            'margin': margin,
            'margin_pct': margin_pct,
            'inventory': inventory_value,
            'last_updated': datetime.now().strftime('%b %d, %Y - %I:%M %p'),
            'projects': {'on_track': active_projects_count, 'at_risk': 0, 'over_budget': 0},
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
    @api.model
    def _get_inventory_forecast(self, start_date=None, end_date=None, project_id=None, 
                                customer_id=None, vendor_id=None, location_id=None, category_id=None):
        """ Calculates real-time inventory forecast projections """
        # Default to next 90 days if no dates provided
        if not start_date:
            start_date = fields.Date.today()
        if not end_date:
            end_date = start_date + timedelta(days=90)
            
        today = fields.Date.today()
        
        # 1. Base On-Hand Stock (Internal Locations) - Strict location/category filtering
        domain_quant = [('location_id.usage', '=', 'internal'), ('company_id', '=', self.env.company.id), ('quantity', '>', 0)]
        if location_id:
            domain_quant += [('location_id', 'child_of', int(location_id))]
        if category_id:
            domain_quant += [('product_id.categ_id', 'child_of', int(category_id))]
        
        quants_forecast = self.env['stock.quant'].search(domain_quant)
        on_hand_by_product = {}
        for q in quants_forecast:
            on_hand_by_product[q.product_id.id] = on_hand_by_product.get(q.product_id.id, 0.0) + q.quantity

        # 2. Future Stock Moves (Incoming/Outgoing)
        domain_moves = [
            ('state', 'in', ('confirmed', 'assigned', 'waiting')),
            ('company_id', '=', self.env.company.id)
        ]
        
        # 3. Fetch Reordering Rules
        domain_rop = []
        if category_id:
            domain_rop += [('product_id.categ_id', 'child_of', int(category_id))]
        if location_id:
            warehouse = self.env['stock.location'].browse(int(location_id)).warehouse_id
            if warehouse:
                domain_rop += [('warehouse_id', '=', warehouse.id)]
        
        rops = self.env['stock.warehouse.orderpoint'].search(domain_rop)
        rop_by_product = {r.product_id.id: r.product_min_qty for r in rops}
        
        # 4. Calculate daily projection
        daily_projection = []
        proj_stock = dict(on_hand_by_product)
        
        # Group moves by date
        moves_by_date = {}
        # Fetch moves within the selected range
        start_utc, end_utc = self._get_datetime_range_utc(start_date, end_date)
        for move in self.env['stock.move'].search(domain_moves + [
            ('date', '>=', start_utc),
            ('date', '<=', end_utc)
        ]):
            if category_id and move.product_id.categ_id.id != int(category_id):
                continue
            
            is_incoming = move.location_dest_id.usage == 'internal' and move.location_id.usage != 'internal'
            is_outgoing = move.location_id.usage == 'internal' and move.location_dest_id.usage != 'internal'
            
            if location_id:
                loc_id = int(location_id)
                loc = self.env['stock.location'].browse(loc_id)
                if is_incoming and not (move.location_dest_id.id == loc_id or move.location_dest_id.parent_path.startswith(loc.parent_path)):
                    is_incoming = False
                if is_outgoing and not (move.location_id.id == loc_id or move.location_id.parent_path.startswith(loc.parent_path)):
                    is_outgoing = False

            if not is_incoming and not is_outgoing:
                continue

            date_key = move.date.date()
            if date_key not in moves_by_date:
                moves_by_date[date_key] = []
            moves_by_date[date_key].append(move)

        total_shortages_at_risk = 0
        shortage_items = []
        running_cash_req = 0
        
        num_days = (end_date - start_date).days + 1
        
        for i in range(num_days):
            target_date = start_date + timedelta(days=i)
            day_moves = moves_by_date.get(target_date, [])
            
            for move in day_moves:
                is_incoming = move.location_dest_id.usage == 'internal' and move.location_id.usage != 'internal'
                is_outgoing = move.location_id.usage == 'internal' and move.location_dest_id.usage != 'internal'
                
                qty = move.product_uom_qty
                if is_incoming:
                    proj_stock[move.product_id.id] = proj_stock.get(move.product_id.id, 0.0) + qty
                elif is_outgoing:
                    proj_stock[move.product_id.id] = proj_stock.get(move.product_id.id, 0.0) - qty

            # Check for shortages and simulate purchase spending
            day_purchase_spending = 0
            for pid, qty in proj_stock.items():
                min_qty = rop_by_product.get(pid, 0.0)
                if qty < min_qty:
                    shortage_qty = min_qty - qty
                    product = self.env['product.product'].browse(pid)
                    vendor_price = product.seller_ids[0].price if product.seller_ids else product.standard_price
                    simulated_cost = shortage_qty * vendor_price
                    
                    day_purchase_spending += simulated_cost
                    proj_stock[pid] = min_qty
                    
                    running_cash_req += simulated_cost
                    if len(shortage_items) < 10 and not any(s['name'] == product.display_name for s in shortage_items):
                        shortage_items.append({
                            'name': product.display_name,
                            'value': simulated_cost,
                            'impact': 'High Impact' if simulated_cost > 10000 else 'Medium Impact'
                        })

            forecasted_val = sum(qty * self.env['product.product'].browse(pid).standard_price for pid, qty in proj_stock.items() if qty > 0)
            
            daily_projection.append({
                'date': target_date.isoformat(),
                'label': target_date.strftime('%b %d'),
                'stock_value': forecasted_val,
                'spend': day_purchase_spending
            })

        # Calculate period cards dynamically based on the range duration
        total_spend = sum(d['spend'] for d in daily_projection)
        cards = [{
            'label': f'Selected Period ({num_days} days)',
            'forecasted': daily_projection[-1]['stock_value'] if daily_projection else 0,
            'committed': total_spend,
            'pending': 0
        }]

        return {
            'cash_required_30d': running_cash_req, # This might need renaming if it covers full period
            'cards': cards,
            'shortages': { 'total_at_risk': running_cash_req, 'items': shortage_items },
            'cash_requirement': running_cash_req,
            'daily_projection': daily_projection
        }

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
            base_foc_domain += [('order_id.id', '=', int(project_id))]
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
        
        # Top clients by FOC cost
        client_foc_map = {}
        for line in foc_lines_range:
            client_name = line.order_id.partner_id.name or "Unknown"
            foc_cost = line.product_uom_qty * get_product_cost(line.product_id)
            client_foc_map[client_name] = client_foc_map.get(client_name, 0) + foc_cost
        
        top_clients = [{'name': name, 'value': cost} for name, cost in sorted(client_foc_map.items(), key=lambda x: x[1], reverse=True)[:5]]
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

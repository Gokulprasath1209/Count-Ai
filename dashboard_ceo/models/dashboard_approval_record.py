from odoo import models, fields, api, tools

class DashboardCeoApproval(models.Model):
    _name = 'dashboard.ceo.approval'
    _description = 'Dashboard CEO Unified Approval View'
    _auto = False
    _order = 'waiting_days desc'

    source_model = fields.Char(string='Model', readonly=True)
    res_id = fields.Integer(string='Resource ID', readonly=True)

    name = fields.Char(string='Document / Project', readonly=True)
    source = fields.Char(string='Source Type', readonly=True)
    user_id = fields.Many2one('res.users', string='Requested By', readonly=True)
    amount = fields.Float(string='Value', readonly=True)
    request_date = fields.Date(string='Request Date', readonly=True)
    waiting_days = fields.Integer(string='Waiting Days', readonly=True)
    state_label = fields.Char(string='Status', readonly=True)
    # Used for domain filtering: 'pending' or 'rejected'
    approval_status = fields.Char(string='Approval Status', readonly=True)

    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    project_id = fields.Many2one('project.project', string='Project', readonly=True)
    location_id = fields.Many2one('stock.location', string='Location', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW dashboard_ceo_approval AS (

                -- ===== PENDING: Sale & Spare Orders =====
                SELECT
                    concat('sale_p_', so.id) as id,
                    'sale.order' as source_model,
                    so.id as res_id,
                    so.name as name,
                    CASE
                        WHEN so.sale_or_spare = 'spare' THEN 'Spare Order'
                        ELSE 'Sale Order'
                    END as source,
                    so.user_id as user_id,
                    so.amount_total as amount,
                    CAST(COALESCE(so.date_order, so.create_date) AS DATE) as request_date,
                    DATE_PART('day', NOW() - COALESCE(so.date_order, so.create_date))::INTEGER as waiting_days,
                    'Waiting CEO Approval' as state_label,
                    'pending' as approval_status,
                    so.company_id as company_id,
                    so.partner_id as partner_id,
                    so.project_id as project_id,
                    NULL::INTEGER as location_id
                FROM sale_order so
                WHERE (so.state = 'waiting_ceo_approval' OR so.approval_state = 'to_approve')

                UNION ALL

                -- ===== PENDING: Material Requests =====
                SELECT
                    concat('mr_p_', mr.id) as id,
                    'material.request' as source_model,
                    mr.id as res_id,
                    mr.name as name,
                    'Material Request' as source,
                    mr.user_id as user_id,
                    0.0 as amount,
                    CAST(mr.create_date AS DATE) as request_date,
                    DATE_PART('day', NOW() - mr.create_date)::INTEGER as waiting_days,
                    'Waiting CEO Approval' as state_label,
                    'pending' as approval_status,
                    mr.company_id as company_id,
                    NULL::INTEGER as partner_id,
                    NULL::INTEGER as project_id,
                    mr.dest_loc_id as location_id
                FROM material_request mr
                WHERE (mr.state = 'waiting_ceo_approval' OR (mr.request_type = 'user' AND mr.approve_type = 'draft'))

                UNION ALL

                -- ===== REJECTED: Sale & Spare Orders =====
                SELECT
                    concat('sale_r_', so.id) as id,
                    'sale.order' as source_model,
                    so.id as res_id,
                    so.name as name,
                    CASE
                        WHEN so.sale_or_spare = 'spare' THEN 'Spare Order'
                        ELSE 'Sale Order'
                    END as source,
                    so.user_id as user_id,
                    so.amount_total as amount,
                    CAST(COALESCE(so.date_order, so.create_date) AS DATE) as request_date,
                    DATE_PART('day', NOW() - COALESCE(so.date_order, so.create_date))::INTEGER as waiting_days,
                    'Rejected / On Hold' as state_label,
                    'rejected' as approval_status,
                    so.company_id as company_id,
                    so.partner_id as partner_id,
                    so.project_id as project_id,
                    NULL::INTEGER as location_id
                FROM sale_order so
                WHERE (so.state = 'rejected' OR so.approval_state = 'rejected')

                UNION ALL

                -- ===== REJECTED: Material Requests =====
                SELECT
                    concat('mr_r_', mr.id) as id,
                    'material.request' as source_model,
                    mr.id as res_id,
                    mr.name as name,
                    'Material Request' as source,
                    mr.user_id as user_id,
                    0.0 as amount,
                    CAST(mr.create_date AS DATE) as request_date,
                    DATE_PART('day', NOW() - mr.create_date)::INTEGER as waiting_days,
                    'Rejected / On Hold' as state_label,
                    'rejected' as approval_status,
                    mr.company_id as company_id,
                    NULL::INTEGER as partner_id,
                    NULL::INTEGER as project_id,
                    mr.dest_loc_id as location_id
                FROM material_request mr
                WHERE (mr.state = 'rejected' OR mr.approve_type = 'ceo_reject')
            )
        """)

    def action_open_record(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.source_model,
            'res_id': self.res_id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }

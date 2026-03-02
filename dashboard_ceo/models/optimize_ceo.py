import re
import os

path = '/home/gowtham/workspace/odoo18/custom_addons/Count-Ai/dashboard_ceo/models/ceo_dashboard.py'
with open(path, 'r') as f:
    content = f.read()

# Chunk 1 replacement logic
original_chunk1 = """        for mo in all_mos:
            mo_budget = self._get_bom_cost(mo.product_id) * mo.product_qty
            
            # Identify Project and Client
            client_name = 'Internal'
            project_id_display = mo.origin or 'N/A'
            
            # 1. Try project_id field
            if 'project_id' in mo._fields and mo.project_id:
                project_id_display = mo.project_id.name
                if hasattr(mo.project_id, 'partner_id') and mo.project_id.partner_id:
                    client_name = mo.project_id.partner_id.name
            
            # 2. Try SO origin
            if client_name == 'Internal' and mo.origin:
                so_linked = self.env['sale.order'].sudo().search([('name', '=', mo.origin)], limit=1)
                if so_linked:
                    client_name = so_linked.partner_id.name if so_linked.partner_id else 'Internal'
                    if project_id_display == mo.origin and 'project_id' in so_linked._fields and so_linked.project_id:
                        project_id_display = so_linked.project_id.name

            # Calculate spent for this MO
            mo_po_domain = [
                ('state', 'in', ('purchase', 'done')),
                '|',
                ('origin', '=', mo.name),
                ('origin', '=', project_id_display)
            ]
            
            project_id_val = False
            if 'project_id' in mo._fields and mo.project_id:
                project_id_val = mo.project_id.id
            elif client_name == 'Internal' and mo.origin:
                so_linked = self.env['sale.order'].sudo().search([('name', '=', mo.origin)], limit=1)
                if so_linked and 'project_id' in so_linked._fields and so_linked.project_id:
                    project_id_val = so_linked.project_id.id
                    
            if project_id_val and 'project_id' in self.env['purchase.order']._fields:
                mo_po_domain = [
                    ('state', 'in', ('purchase', 'done')),
                    '|', '|',
                    ('origin', '=', mo.name),
                    ('origin', '=', project_id_display),
                    ('project_id', '=', project_id_val)
                ]

            mo_po_data = self.env['purchase.order'].sudo().search_read(mo_po_domain, ['amount_total'])
            mo_spent = sum(p['amount_total'] for p in mo_po_data)
            
            mo_list.append({
                'id': mo.id,
                'name': mo.name,
                'project_id': project_id_display,
                'project_id_id': project_id_val,
                'client': client_name,
                'product': mo.product_id.display_name,
                'qty': mo.product_qty,
                'uom': mo.product_uom_id.name,
                'budget': mo_budget,
                'spent': mo_spent,
                'balance': mo_budget - mo_spent,
                'variance': ((mo_spent / mo_budget * 100) if mo_budget > 0 else 0),
                'state': dict(mo._fields['state'].selection).get(mo.state, mo.state),
                'origin': mo.origin,
                'model': 'mrp.production'
            })"""

new_chunk1 = """        # -- PREFETCH FOR MO LOOP --
        mo_origins = list(set([mo.origin for mo in all_mos if mo.origin]))
        mo_names = [mo.name for mo in all_mos]
        
        prefetched_sos = {}
        if mo_origins:
            so_recs = self.env['sale.order'].sudo().search([('name', 'in', mo_origins)])
            for so in so_recs: prefetched_sos[so.name] = so
            
        po_domain_mo = [('state', 'in', ('purchase', 'done')), '|', ('origin', 'in', mo_names), ('origin', 'in', mo_origins)]
        po_has_project = 'project_id' in self.env['purchase.order']._fields
        mo_proj_ids = [mo.project_id.id for mo in all_mos if 'project_id' in mo._fields and mo.project_id]
        so_proj_ids = [so.project_id.id for so in prefetched_sos.values() if 'project_id' in so._fields and so.project_id]
        all_proj_ids = list(set(mo_proj_ids + so_proj_ids))
        if po_has_project and all_proj_ids:
            po_domain_mo = [('state', 'in', ('purchase', 'done')), '|', '|', ('origin', 'in', mo_names), ('origin', 'in', mo_origins), ('project_id', 'in', all_proj_ids)]
            
        prefetched_pos = self.env['purchase.order'].sudo().search_read(po_domain_mo, ['amount_total', 'origin', 'project_id'] if po_has_project else ['amount_total', 'origin'])

        for mo in all_mos:
            mo_budget = self._get_bom_cost(mo.product_id) * mo.product_qty
            
            # Identify Project and Client
            client_name = 'Internal'
            project_id_display = mo.origin or 'N/A'
            project_id_val = False
            
            # 1. Try project_id field
            if 'project_id' in mo._fields and mo.project_id:
                project_id_display = mo.project_id.name
                project_id_val = mo.project_id.id
                if hasattr(mo.project_id, 'partner_id') and mo.project_id.partner_id:
                    client_name = mo.project_id.partner_id.name
            
            # 2. Try SO origin
            if client_name == 'Internal' and mo.origin:
                so_linked = prefetched_sos.get(mo.origin)
                if so_linked:
                    client_name = so_linked.partner_id.name if so_linked.partner_id else 'Internal'
                    if project_id_display == mo.origin and 'project_id' in so_linked._fields and so_linked.project_id:
                        project_id_display = so_linked.project_id.name
                        project_id_val = so_linked.project_id.id

            # Calculate spent for this MO
            mo_spent = 0.0
            for p in prefetched_pos:
                match = False
                if p.get('origin') in (mo.name, project_id_display):
                    match = True
                if project_id_val and po_has_project and p.get('project_id') and p['project_id'][0] == project_id_val:
                    match = True
                    
                if match:
                    mo_spent += p.get('amount_total', 0.0)
            
            mo_list.append({
                'id': mo.id,
                'name': mo.name,
                'project_id': project_id_display,
                'project_id_id': project_id_val,
                'client': client_name,
                'product': mo.product_id.display_name,
                'qty': mo.product_qty,
                'uom': mo.product_uom_id.name,
                'budget': mo_budget,
                'spent': mo_spent,
                'balance': mo_budget - mo_spent,
                'variance': ((mo_spent / mo_budget * 100) if mo_budget > 0 else 0),
                'state': dict(mo._fields['state'].selection).get(mo.state, mo.state),
                'origin': mo.origin,
                'model': 'mrp.production'
            })"""

if original_chunk1 in content:
    print("Chunk 1 matches perfectly!")
    content = content.replace(original_chunk1, new_chunk1)
else:
    print("Chunk 1 does NOT match.")

with open('/tmp/optimized_ceo_1.py', 'w') as f:
    f.write(content)

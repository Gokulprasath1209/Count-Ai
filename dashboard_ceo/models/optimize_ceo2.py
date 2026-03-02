import os

path = '/home/gowtham/workspace/odoo18/custom_addons/Count-Ai/dashboard_ceo/models/ceo_dashboard.py'
with open('/tmp/optimized_ceo_1.py', 'r') as f:
    content = f.read()

# Chunk 2 replacement logic
original_chunk2 = """        for so in all_active_so:
            so_budget = 0.0
            for line in so.order_line:
                if line.product_id:
                    bom_cost = self._get_bom_cost(line.product_id)
                    line_budget = bom_cost * line.product_uom_qty
                    so_budget += line_budget
            
            # Fetch MOs for this project (needed for SO spent calculation)
            related_mos = self.env['mrp.production'].search([('origin', '=', so.name)])

            mo_names = related_mos.mapped('name')
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
            
            if 'project_id' in so._fields and so.project_id and 'project_id' in self.env['purchase.order']._fields:
                domain_so_po = [
                    ('state', 'in', ('purchase', 'done')),
                    '|', '|', '|',
                    ('origin', '=', so.name),
                    ('origin', 'in', mo_names),
                    ('requisition_id.reference', 'in', mr_names),
                    ('project_id', '=', so.project_id.id)
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
            total_project_spent += so_spent"""

new_chunk2 = """        # -- PREFETCH FOR SO LOOP --
        active_so_names = [so.name for so in all_active_so]
        
        prefetched_related_mos = {}
        if active_so_names:
            all_rt_mos = self.env['mrp.production'].sudo().search_read([('origin', 'in', active_so_names)], ['name', 'origin'])
            for mo in all_rt_mos:
                prefetched_related_mos.setdefault(mo['origin'], []).append(mo['name'])
                
        prefetched_mr_names = {}
        if active_so_names:
            try:
                with self.env.cr.savepoint():
                    mr_data = self.env['material.request'].sudo().search_read([('ref', 'in', active_so_names)], ['name', 'ref'])
                    for mr in mr_data:
                        prefetched_mr_names.setdefault(mr['ref'], []).append(mr['name'])
            except:
                pass

        # Since we might have hundreds of MO names and MR names, gather all of them to prefetch PO once
        all_mo_names_for_so = [m for vals in prefetched_related_mos.values() for m in vals]
        all_mr_names_for_so = [m for vals in prefetched_mr_names.values() for m in vals]
        
        po_domain_so_base = [('state', 'in', ('purchase', 'done')), '|', '|', ('origin', 'in', active_so_names), ('origin', 'in', all_mo_names_for_so), ('requisition_id.reference', 'in', all_mr_names_for_so)]
        po_has_project_so = 'project_id' in self.env['purchase.order']._fields
        if po_has_project_so:
             po_domain_so_base = [('state', 'in', ('purchase', 'done'))]
             so_pids = [so.project_id.id for so in all_active_so if 'project_id' in so._fields and so.project_id]
             
             po_domain_so_base += ['|', '|', '|', 
                 ('origin', 'in', active_so_names),
                 ('origin', 'in', all_mo_names_for_so),
                 ('requisition_id.reference', 'in', all_mr_names_for_so),
                 ('project_id', 'in', so_pids)
             ]

        if start_utc:
            po_domain_so_base += [('date_approve', '>=', start_utc)]
        if end_utc:
            po_domain_so_base += [('date_approve', '<=', end_utc)]

        # Read specific required fields from PO mapping
        po_read_fields = ['amount_total', 'origin', 'requisition_id']
        if po_has_project_so:
             po_read_fields.append('project_id')
             
        prefetched_so_pos = self.env['purchase.order'].sudo().search_read(po_domain_so_base, po_read_fields)

        for so in all_active_so:
            so_budget = 0.0
            for line in so.order_line:
                if line.product_id:
                    bom_cost = self._get_bom_cost(line.product_id)
                    line_budget = bom_cost * line.product_uom_qty
                    so_budget += line_budget
            
            mo_names = prefetched_related_mos.get(so.name, [])
            mr_names = prefetched_mr_names.get(so.name, [])
            
            so_spent = 0.0
            for p in prefetched_so_pos:
                match = False
                if p.get('origin') in (so.name, ):
                    match = True
                elif p.get('origin') in mo_names:
                    match = True
                elif p.get('requisition_id') and hasattr(p.get('requisition_id'), '__iter__') and len(p.get('requisition_id')) > 1 and p.get('requisition_id')[1] in mr_names:
                    match = True
                # Actually requisition_id comes back as [id, name], so p['requisition_id'][1] is the reference name usually
                # To be safe, try matching by reference directly if it's stored in a standard way, but in the domain it was requisition_id.reference
                elif po_has_project_so and 'project_id' in so._fields and so.project_id and p.get('project_id') and p['project_id'][0] == so.project_id.id:
                    match = True
                    
                if match:
                    so_spent += p.get('amount_total', 0.0)
            
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
            total_project_spent += so_spent"""

if original_chunk2 in content:
    print("Chunk 2 matches perfectly!")
    content = content.replace(original_chunk2, new_chunk2)
else:
    print("Chunk 2 does NOT match.")

with open('/tmp/optimized_ceo_2.py', 'w') as f:
    f.write(content)

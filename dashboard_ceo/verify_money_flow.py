from odoo import api, fields
import pytz
from datetime import datetime

def verify():
    # Simulate the dashboard environment
    env = api.Environment(env.cr, 1, {})  # Assuming admin and no specific context
    dashboard = env['ceo.dashboard']
    
    today = fields.Date.today()
    print(f"Today (fields.Date.today()): {today}")
    
    # 1. Check Today's Outward Spend
    today_start_utc, today_end_utc = dashboard._get_datetime_range_utc(today, today)
    print(f"Today UTC Range: {today_start_utc} to {today_end_utc}")
    
    moves = env['stock.move'].search([
        ('picking_id.picking_type_id.code', '=', 'outgoing'),
        ('state', '=', 'done'),
        ('picking_id.date_done', '>=', today_start_utc),
        ('picking_id.date_done', '<=', today_end_utc)
    ])
    outward_val = sum(m.product_uom_qty * m.product_id.standard_price for m in moves)
    print(f"Today Outward Spend Value: {outward_val}")
    print(f"Found {len(moves)} outgoing moves today.")
    
    # 2. Check the Month's Outward Spend for comparison
    month_start = today.replace(day=1)
    month_start_utc, month_end_utc = dashboard._get_datetime_range_utc(month_start, today)
    print(f"Month UTC Range: {month_start_utc} to {month_end_utc}")
    
    month_moves = env['stock.move'].search([
        ('picking_id.picking_type_id.code', '=', 'outgoing'),
        ('state', '=', 'done'),
        ('picking_id.date_done', '>=', month_start_utc),
        ('picking_id.date_done', '<=', month_end_utc)
    ])
    month_val = sum(m.product_uom_qty * m.product_id.standard_price for m in month_moves)
    print(f"Month Outward Spend Value: {month_val}")
    print(f"Found {len(month_moves)} outgoing moves this month.")

# How to run this in Odoo:
# python3 odoo-bin shell -d <db_name> --command="import verify_money_flow; verify_money_flow.verify()"

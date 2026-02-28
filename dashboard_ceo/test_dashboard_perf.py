import sys
import time
import odoo
from odoo import api, SUPERUSER_ID

def main():
    odoo.tools.config.parse_config(['-c', '/home/gowtham/workspace/odoo18/odoo.conf'])
    registry = odoo.registry('odoo18')
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        dashboard = env['ceo.dashboard']
        
        start = time.time()
        print("Starting get_dashboard_data...")
        res = dashboard.get_dashboard_data()
        duration = time.time() - start
        
        print(f"Time taken: {duration:.2f} seconds")
        
        # Optionally test with a project filter
        # ...
        
if __name__ == '__main__':
    main()

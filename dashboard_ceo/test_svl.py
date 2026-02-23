import sys
# we will run this via odoo shell
fields = env['stock.valuation.layer']._fields.keys()
if 'location_id' in fields:
    print("HAS_LOCATION_ID")
else:
    print("NO_LOCATION_ID")

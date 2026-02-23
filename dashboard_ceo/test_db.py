import psycopg2
conn = psycopg2.connect("dbname=db_name user=odoo") 
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='stock_valuation_layer'")
print([row[0] for row in cur.fetchall()])

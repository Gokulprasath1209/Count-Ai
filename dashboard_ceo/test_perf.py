import time

dashboard = env['ceo.dashboard']
start = time.time()
res = dashboard.get_dashboard_data()
dur = time.time() - start
print(f"Time taken: {dur:.2f} seconds")

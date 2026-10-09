from datetime import date, timedelta


yesterday_str = (date.today() - timedelta(days=1)).strftime("%y_%m_%d")

print(yesterday_str)
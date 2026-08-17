import sqlite3, sys

db = sqlite3.connect('wiki_local.db')
sql = sys.argv[1]
try:
    limit = int(sys.argv[2])
except IndexError:
    limit = 20
for row in db.execute(sql).fetchmany(limit):
    print('\t'.join('' if v is None else str(v)[:160] for v in row))

import sqlite3, sys

c = sqlite3.connect('wiki_local.db')
lines = [l for l in open(sys.argv[1], encoding='utf-8').read().splitlines() if l.strip()]
srcs = [l.split('\t')[1].replace('\\n', '\n') for l in lines]
done = {r[0] for r in c.execute(
    "select source_text from translations where translated_text is not null and translated_text <> ''").fetchall()}
hit = sum(1 for s in srcs if s in done)
print('overlap:', hit, '/', len(srcs))

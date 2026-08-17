import sqlite3, sys, json

db = sqlite3.connect('wiki_local.db')

def status_of(batchfile):
    lines = [l.rstrip('\n') for l in open(batchfile, encoding='utf-8') if l.strip()]
    pending = []
    for line in lines:
        parts = line.split('\t')
        if len(parts) < 3:
            continue
        typ, src, h = parts[0], parts[1], parts[2]
        row = db.execute('select translated_text from translations where source_hash=?', (h,)).fetchone()
        tr = row[0] if row else None
        if not tr:
            pending.append((typ, src, h))
    return pending

if __name__ == '__main__':
    for f in sys.argv[1:]:
        p = status_of(f)
        print(f, len(p))
        for typ, src, h in p:
            print(f'{typ}\t{src}\t{h}')

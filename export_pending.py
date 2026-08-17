import sqlite3, sys

db = sqlite3.connect('wiki_local.db')
pattern = sys.argv[1]  # SQL LIKE pattern on page_title
outfile = sys.argv[2]

rows = db.execute(
    "SELECT context, source_text, source_hash FROM translations "
    "WHERE (translated_text IS NULL OR translated_text='') AND page_title LIKE ? "
    "ORDER BY length(source_text) DESC", (pattern,)
).fetchall()
with open(outfile, 'w', encoding='utf-8') as f:
    for ctx, src, h in rows:
        src = src.replace('\n', '\\n').replace('\t', ' ')
        f.write(f'{ctx}\t{src}\t{h}\n')
print(f'{len(rows)} items -> {outfile}')

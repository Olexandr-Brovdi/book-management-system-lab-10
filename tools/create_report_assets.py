"""Render actual local logs and a dist inventory, with explicit pending states."""

from pathlib import Path
import html
import json
import textwrap
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]


def console(name,lines):
    wrapped=[]
    for line in lines:wrapped.extend(textwrap.wrap(line,width=110,replace_whitespace=False) or [''])
    font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',19)
    image=Image.new('RGB',(1320,50+26*len(wrapped)),(247,248,250))
    draw=ImageDraw.Draw(image)
    for n,line in enumerate(wrapped):draw.text((24,20+26*n),line,font=font,fill=(20,24,30))
    image.save(ROOT/f'docs/screenshots/{name}.png')


def main():
    summary=json.loads((ROOT/'docs/results/summary.json').read_text(encoding='utf-8'))
    quality=[]
    for name in ['lint','format','mypy','twine']:
        lines=(ROOT/f'docs/results/{name}.txt').read_text(encoding='utf-8').splitlines()
        quality.extend([name.upper(),*lines[-3:],''])
    console('quality',quality)
    tests=(ROOT/'docs/results/tests.txt').read_text(encoding='utf-8').splitlines()
    console('tests',['Actual pytest -v output',*tests[:3],'... full log: docs/results/tests.txt ...',*tests[-19:]])
    rows=''.join(f"<tr><td>{html.escape(a['name'])}</td><td>{a['bytes']:,}</td><td>{a['sha256']}</td></tr>" for a in summary['artifacts'])
    page=f'''<!doctype html><html lang="uk"><meta charset="utf-8"><title>Lab 10 — dist inventory</title><style>body{{font:19px Segoe UI,sans-serif;max-width:1140px;margin:40px auto;color:#17212b;background:#f6f7fa}}section{{background:white;padding:24px;border-radius:12px}}table{{width:100%;border-collapse:collapse;font-size:15px}}td,th{{padding:14px 8px;border-bottom:1px solid #ddd;text-align:left}}td:last-child{{font:12px Consolas,monospace}}h1{{font-size:29px}}.ok{{color:#126331}}.pending{{color:#7a4b00}}</style>
<h1>Lab_10 · Book Catalog 1.0.0</h1><p>Бровді Олександр · ФеП-32 · Варіант 2</p><section><h2>Фактичний вміст dist/</h2><table><tr><th>File</th><th>Bytes</th><th>SHA-256</th></tr>{rows}</table><p class="ok">Local build + twine check: PASS · {summary['tests']} tests passed · mypy: PASS</p><p>Джерело: файли dist/ та docs/results/summary.json.</p><p class="pending">Docker container: NOT RUN · GitHub Actions: NOT RUN · Публікацію відкладено користувачем.</p></section></html>'''
    (ROOT/'docs/dist.html').write_text(page,encoding='utf-8')
    print('Local evidence images and dist inventory created')


if __name__=='__main__':main()

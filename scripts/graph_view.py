#!/usr/bin/env python
# ruff: noqa: T201, S324, D103, PTH207, PLR2004
# CLI tool: printing IS the output; md5 here is a change fingerprint, not a security hash.
"""Render PROJECT_GRAPH.md as a standalone interactive HTML graph (or a Mermaid dump).

Deliberately outside the library: this reads the markdown and writes a file, and adds no dependency
to `src/`. Vanilla JS, no CDN, works offline.

    python graph_view.py                  # -> project_graph.html
    python graph_view.py --open           # and open it
    python graph_view.py --mermaid        # print a Mermaid graph to stdout
    python graph_view.py --chain 3        # only the nodes in chain section 3

Node colour is `type`; `dead` / `stale-*` / `unverified` nodes are dimmed. Hover shows the purpose
and any `nuances`; click pins the full record in the side panel.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


# Which project to read comes from GRAPH_REPO, else the working directory, else the directory this
# script sits in. Resolving it from __file__ alone means the bundled copy can only ever draw its own
# skill directory, which has no graph in it.
_cwd = Path.cwd()
REPO = Path(os.environ.get("GRAPH_REPO")
            or (_cwd if (_cwd / "PROJECT_GRAPH.md").exists() else Path(__file__).resolve().parent.parent))
GRAPH = REPO / "PROJECT_GRAPH.md"
OUT = REPO / "project_graph.html"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from graph_check import edge_ids, parse_nodes  # noqa: E402

TYPE_COLOUR = {
    "notebook-pipeline": "#bd93f9",
    "data-artifact": "#8be9fd",
    "model-artifact": "#50fa7b",
    "library-module": "#ffb86c",
    "manual-step": "#ff5555",
    "paper-section": "#f1fa8c",
    "paper-figure": "#ff79c6",
    "external-source": "#6272a4",
    "script": "#a0a0b0",
    "exploratory": "#44475a",
}

HTML = """<!doctype html>
<meta charset="utf-8"><title>open-sensing-analysis project graph</title>
<style>
 :root{--bg:#282a36;--fg:#f8f8f2;--dim:#6272a4;--panel:#21222c}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--fg);
   font:13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;overflow:hidden}
 #wrap{display:flex;height:100vh}
 #cv{flex:1;cursor:grab} #cv:active{cursor:grabbing}
 #side{width:380px;background:var(--panel);overflow-y:auto;padding:16px;
   border-left:1px solid #44475a}
 h1{font-size:15px;margin:0 0 4px} .sub{color:var(--dim);font-size:11px;margin-bottom:12px}
 #controls{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:12px}
 input,button{background:#282a36;color:var(--fg);border:1px solid #44475a;border-radius:5px;
   padding:5px 8px;font:inherit;font-size:11px}
 button{cursor:pointer} button.off{opacity:.35}
 #detail{font-size:12px} #detail .k{color:var(--dim);text-transform:uppercase;font-size:9.5px;
   letter-spacing:.06em;margin-top:11px}
 #detail .v{white-space:pre-wrap;word-break:break-word}
 #detail .nu{color:#ff9d9d} #detail .id{font-weight:600;font-size:14px}
 .lg{display:flex;align-items:center;gap:5px;font-size:10.5px;margin:2px 6px 2px 0}
 .sw{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:6px;vertical-align:-1px}
 .lg{font-size:11px;color:#c9ccd8;white-space:nowrap}
 .lg b{color:#7d8296;font-weight:500}
 #legend{display:grid;grid-template-columns:1fr 1fr;gap:2px 10px;margin:6px 0 12px}
 a{color:#8be9fd}
 #tip{position:absolute;pointer-events:none;background:#191a21;border:1px solid #44475a;
   border-radius:6px;padding:7px 9px;max-width:340px;font-size:11.5px;display:none;z-index:9}
</style>
<div id=wrap><canvas id=cv></canvas><div id=side>
 <h1>open-sensing-analysis project graph</h1>
 <div class=sub id=count></div>
 <div id=controls>
   <input id=q placeholder="search id / purpose / nuance" style="width:100%">
   <button id=fit>fit</button><button id=labels class=off>labels</button>
   <button id=hideExp class=off>hide exploratory</button>
   <button id=onlyProb class=off>only stale / dead / unverified</button>
 </div>
 <div id=legend></div>
 <div id=detail>Click a node to pin its record. Drag to move, scroll to zoom.</div>
</div></div><div id=tip></div>
<script>
const NODES = __NODES__, EDGES = __EDGES__, COLOUR = __COLOUR__;
const cv = document.getElementById('cv'), ctx = cv.getContext('2d'), tip = document.getElementById('tip');
let W, H, DPR = devicePixelRatio || 1;
function size(){ W = cv.clientWidth; H = cv.clientHeight;
  cv.width = W*DPR; cv.height = H*DPR; ctx.setTransform(DPR,0,0,DPR,0,0); }
new ResizeObserver(size).observe(cv); size();

const byId = {}; NODES.forEach((n,i) => { n.i = i; byId[n.id] = n; });
const links = EDGES.filter(e => byId[e[0]] && byId[e[1]]).map(e => ({s: byId[e[0]], t: byId[e[1]]}));
const deg = {}; links.forEach(l => { deg[l.s.id]=(deg[l.s.id]||0)+1; deg[l.t.id]=(deg[l.t.id]||0)+1; });
const R = n => 4 + Math.min(9, Math.sqrt(deg[n.id]||1)*2.1);

// Deterministic layered layout: one column per pipeline stage, ordered within the column by the
// average position of each node's neighbours (barycentre sweeps). No physics, so it never drifts.
const LAYER = {'external-source':0,'notebook-pipeline':1,'script':1,'data-artifact':2,
  'model-artifact':2,'manual-step':3,'library-module':4,'paper-figure':5,'paper-section':6,
  'exploratory':7};
const COLW = 330, ROWH = 30;
NODES.forEach(n => { n.layer = LAYER[n.type] ?? 7; });
const cols = {}; NODES.forEach(n => (cols[n.layer] = cols[n.layer] || []).push(n));
Object.values(cols).forEach(col => col.sort((a,b) => a.id.localeCompare(b.id)));
function place(){ for(const [L,col] of Object.entries(cols))
  col.forEach((n,r) => { n.x = 90 + L*COLW; n.y = 70 + r*ROWH; }); }
place();
// A network layout is computed in Python (networkx spring layout, fixed seed) and injected as fx/fy.
// When present it wins: dots positioned by connectivity rather than by pipeline stage.
const NETWORK = NODES.length > 0 && NODES[0].fx !== undefined;
if(NETWORK){ NODES.forEach(n => { n.x = n.fx; n.y = n.fy; }); }
for(let pass=0; pass<(NETWORK?0:14); pass++){
  const dir = pass % 2 === 0;
  for(const col of Object.values(cols)){
    const bary = new Map();
    for(const n of col){
      const nb = links.filter(l => (dir ? l.t===n : l.s===n)).map(l => dir ? l.s : l.t)
        .concat(links.filter(l => (dir ? l.s===n : l.t===n)).map(l => dir ? l.t : l.s))
        .filter(m => m.layer !== n.layer);
      bary.set(n, nb.length ? nb.reduce((s,m) => s+m.y, 0)/nb.length : n.y);
    }
    col.sort((a,b) => bary.get(a) - bary.get(b));
  }
  place();
}
const LABELS = ['external','notebooks','artifacts','manual steps','library','figures','paper','exploratory'];

let view = {x:0, y:0, k:.78}, allLabels = false, hideExp = false, onlyProb = false, q = '', pinned = null, hover = null;
const dim = n => ['dead','stale-vintage','stale-in-paper','unverified'].includes(n.status);
const visible = n => (!hideExp || n.type !== 'exploratory') && (!onlyProb || dim(n));
const matches = n => !q || (n.id+' '+(n.purpose||'')+' '+(n.nuances||'')).toLowerCase().includes(q);
function tick(){ draw(); requestAnimationFrame(tick); }
function draw(){
  ctx.clearRect(0,0,W,H); ctx.save(); ctx.translate(view.x,view.y); ctx.scale(view.k,view.k);
  ctx.lineWidth = 1/view.k;
  for(const l of links){
    if(!visible(l.s)||!visible(l.t)) continue;
    const hot = hover && (l.s===hover||l.t===hover) || pinned && (l.s===pinned||l.t===pinned);
    ctx.strokeStyle = hot ? '#f8f8f2' : 'rgba(98,114,164,.28)';
    ctx.beginPath(); ctx.moveTo(l.s.x,l.s.y);
    ctx.bezierCurveTo((l.s.x+l.t.x)/2, l.s.y, (l.s.x+l.t.x)/2, l.t.y, l.t.x, l.t.y); ctx.stroke();
    if(hot){ // arrowhead toward the target
      const a = Math.atan2(l.t.y-l.s.y, l.t.x-l.s.x), r = R(l.t)+3;
      const hx = l.t.x-Math.cos(a)*r, hy = l.t.y-Math.sin(a)*r;
      ctx.beginPath(); ctx.moveTo(hx,hy);
      ctx.lineTo(hx-Math.cos(a-.4)*8, hy-Math.sin(a-.4)*8);
      ctx.lineTo(hx-Math.cos(a+.4)*8, hy-Math.sin(a+.4)*8);
      ctx.fillStyle='#f8f8f2'; ctx.fill();
    }
  }
  ctx.font = `${Math.max(10, 12/view.k)}px -apple-system,sans-serif`;
  for(const [L,col] of Object.entries(cols)){
    if(!col.some(visible)) continue;
    if(!NETWORK){ ctx.fillStyle='#6272a4'; ctx.fillText((LABELS[L]||'').toUpperCase(), 90+L*COLW-30, 40); }
  }
  const focus = pinned || hover;
  const near = new Set();
  if(focus){ near.add(focus.id);
    for(const l of links){ if(l.s===focus) near.add(l.t.id); if(l.t===focus) near.add(l.s.id); } }
  for(const n of NODES){
    if(!visible(n)) continue;
    const m = matches(n);
    ctx.globalAlpha = m ? (dim(n)?.42:1) : .09;
    ctx.beginPath(); ctx.arc(n.x,n.y,R(n),0,7); ctx.fillStyle = COLOUR[n.type]||'#888'; ctx.fill();
    if(n.nuances && n.nuances!=='-'){ ctx.strokeStyle='rgba(255,85,85,.55)'; ctx.lineWidth=1.1/view.k; ctx.stroke(); }
    if(n.status==='dead'||n.status==='unverified'){ ctx.setLineDash([2.5/view.k,2.5/view.k]);
      ctx.strokeStyle='#ff5555'; ctx.lineWidth=1.8/view.k; ctx.stroke(); ctx.setLineDash([]); }
    if(n===pinned||n===hover){ ctx.strokeStyle='#f8f8f2'; ctx.lineWidth=2/view.k; ctx.stroke(); }
    // Labels only on demand: hovered node and its neighbours, a search hit, or the toggle. Showing
    // every label past a zoom threshold made the picture unreadable exactly when you leaned in.
    if(m && (allLabels || near.has(n.id) || (q && matches(n)))){
      ctx.globalAlpha = dim(n)?.55:.95; ctx.fillStyle='#f8f8f2';
      ctx.font = `${Math.max(9, 11/view.k)}px -apple-system,sans-serif`;
      ctx.fillText(n.id.replace(/^[a-z-]+\\//,''), n.x+R(n)+3, n.y+3.5);
    }
  }
  ctx.globalAlpha=1; ctx.restore();
}
const toWorld = e => { const r = cv.getBoundingClientRect();
  return {x:(e.clientX-r.left-view.x)/view.k, y:(e.clientY-r.top-view.y)/view.k}; };
const pick = p => NODES.filter(visible).find(n => Math.hypot(n.x-p.x,n.y-p.y) < R(n)+5);

// `moved` is the whole point: mousemove assigns drag.x = pointer.x, so comparing the node to the
// pointer at mouseup always measured zero and pinned the node on every release, drag or not.
let drag=null, pan=null, moved=false;
cv.addEventListener('mousedown', e => { const p=toWorld(e), n=pick(p);
  moved=false;
  if(n){ drag=n; } else { pan={x:e.clientX-view.x, y:e.clientY-view.y}; } });
addEventListener('mousemove', e => { const p=toWorld(e);
  if(drag){ drag.x=p.x; drag.y=p.y; moved=true; return; }
  if(pan){ view.x=e.clientX-pan.x; view.y=e.clientY-pan.y; return; }
  const n=pick(p); hover=n;
  if(n){ tip.style.display='block'; tip.style.left=(e.clientX+13)+'px'; tip.style.top=(e.clientY+13)+'px';
    tip.innerHTML = `<b>${n.id}</b> <span style="color:#6272a4">${n.type} · ${n.status}</span><br>${esc(n.purpose||'')}`
      + (n.nuances && n.nuances!=='-' ? `<br><span style="color:#ff9d9d">⚠ ${esc(n.nuances)}</span>` : '');
  } else tip.style.display='none';
});
addEventListener('mouseup', () => {
  // Dragged: the node keeps its new position and nothing stays selected. Clicked without moving:
  // pin its record.
  if(drag){ if(moved){ pinned=null; document.getElementById('detail').innerHTML=''; } else { show(drag); } }
  drag=null; pan=null; moved=false; });
cv.addEventListener('wheel', e => { e.preventDefault();
  const r=cv.getBoundingClientRect(), mx=e.clientX-r.left, my=e.clientY-r.top;
  const k=view.k*(e.deltaY<0?1.12:0.893);
  view.x = mx-(mx-view.x)*k/view.k; view.y = my-(my-view.y)*k/view.k; view.k=k; }, {passive:false});

const esc = s => (s||'').replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function show(n){
  pinned = n;
  const ins = links.filter(l=>l.t===n).map(l=>l.s.id), outs = links.filter(l=>l.s===n).map(l=>l.t.id);
  const row = (k,v,cls='') => v && v!=='-' ? `<div class=k>${k}</div><div class="v ${cls}">${esc(v)}</div>` : '';
  document.getElementById('detail').innerHTML =
    `<div class="v id" style="color:${COLOUR[n.type]}">${esc(n.id)}</div>`
    + `<div class=sub>${n.type} · ${n.status}</div>`
    + row('file', n.file) + row('inputs', n.inputs) + row('purpose', n.purpose)
    + row('what follows', n.what_follows) + row('nuances', n.nuances, 'nu')
    + row('evidence', n.evidence)
    + row('fed by ('+ins.length+')', ins.join('\\n')) + row('feeds ('+outs.length+')', outs.join('\\n'))
    + row('last modified', n.last_modified) + row('checked', n.checked);
}
document.getElementById('labels').onclick = e => { allLabels=!allLabels; e.target.classList.toggle('off',!allLabels); };
document.getElementById('q').addEventListener('input', e => q = e.target.value.toLowerCase().trim());
document.getElementById('hideExp').onclick = e => { hideExp=!hideExp; e.target.classList.toggle('off',!hideExp); };
document.getElementById('onlyProb').onclick = e => { onlyProb=!onlyProb; e.target.classList.toggle('off',!onlyProb); };
document.getElementById('fit').onclick = () => {
  const v = NODES.filter(visible); if(!v.length) return;
  const xs=v.map(n=>n.x), ys=v.map(n=>n.y);
  const x0=Math.min(...xs), x1=Math.max(...xs), y0=Math.min(...ys), y1=Math.max(...ys);
  view.k = Math.min(W/(x1-x0+140), H/(y1-y0+140), 2);
  view.x = (W-(x1+x0)*view.k)/2; view.y = (H-(y1+y0)*view.k)/2;
};
const tcount = {}; NODES.forEach(n => tcount[n.type] = (tcount[n.type]||0)+1);
document.getElementById('legend').innerHTML = Object.entries(COLOUR)
  .filter(([t]) => tcount[t])
  .sort((a,b) => tcount[b[0]] - tcount[a[0]])
  .map(([t,c]) => `<span class=lg><i class=sw style="background:${c}"></i>${t} <b>${tcount[t]}</b></span>`)
  .join('');
document.getElementById('count').textContent =
  `${NODES.length} nodes · ${links.length} edges · ` +
  (NETWORK ? 'network layout, position = connectivity' : 'columns = pipeline stage')
  + ` · red ring = nuances · dashed = dead/unverified · hover a node to label its neighbours`;
// The 1400 ms wait lets the column layout's barycentre passes settle. A network layout is already
// final when it arrives, so frame it as soon as the browser has laid the canvas out — two frames,
// not a guessed delay. Firing at 0 ms measured the canvas in device pixels and framed twice too wide.
tick();
if(NETWORK){ requestAnimationFrame(() => requestAnimationFrame(() => {
  size(); document.getElementById('fit').click(); })); }
else { setTimeout(()=>document.getElementById('fit').click(), 1400); }
// Re-frame when the window changes size, so it stays readable without touching anything.
addEventListener('resize', () => { size(); if(NETWORK) document.getElementById('fit').click(); });
</script>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mermaid", action="store_true", help="print a Mermaid graph instead")
    ap.add_argument("--open", action="store_true", help="open the HTML when done")
    ap.add_argument("--chain", help="restrict to one chain section number, e.g. 3")
    ap.add_argument("--columns", action="store_true",
                    help="lay the nodes out in one column per pipeline stage instead of as a "
                         "network. Easier for tracing a single chain end to end; harder to see "
                         "shape, hubs, and isolated nodes.")
    ap.add_argument("--network", action="store_true", default=True, help=argparse.SUPPRESS)
    ap.add_argument("--iterations", type=int, default=300,
                    help="spring layout iterations for --network; more is tidier and slower")
    ap.add_argument("--algorithm", choices=("kamada", "spring"), default="kamada",
                    help="kamada (default) minimises edge-length stress and reads much cleaner on a "
                         "graph this size; spring is the classic force layout and clumps nodes that "
                         "share the same neighbours")
    ap.add_argument("--spacing", type=float, default=26.0,
                    help="minimum pixels between two node centres; a relaxation pass pushes apart "
                         "anything closer, which is what stops the clumping")
    args = ap.parse_args()
    if args.columns:
        args.network = False

    if not GRAPH.exists():
        print(f"FATAL: {GRAPH} not found")
        return 2

    text = GRAPH.read_text()
    if args.chain:
        parts = re.split(r"^## (\d+)\. ", text, flags=re.M)
        chunk = next(
            (parts[i + 1] for i in range(1, len(parts), 2) if parts[i] == args.chain), None
        )
        if chunk is None:
            print(f"no chain section {args.chain}")
            return 2
        text = chunk

    nodes = parse_nodes(text)
    ids = {n["id"] for n in nodes}
    edges = [
        [n["id"], t]
        for n in nodes
        for t in edge_ids(n.get("to", ""))
        if t in ids
    ] + [
        [t, n["id"]]
        for n in nodes
        for t in edge_ids(n.get("from", ""))
        if t in ids
    ]
    # dedupe, keeping direction
    edges = [list(e) for e in dict.fromkeys(tuple(e) for e in edges)]

    if args.network:
        try:
            import networkx as nx
            import numpy as np
        except ImportError:
            print("networkx and numpy are needed for the network layout; falling back to columns")
            args.network = False

    if args.network:
        g = nx.DiGraph()
        g.add_nodes_from(n["id"] for n in nodes)
        g.add_edges_from((a, b) for a, b in edges)
        # Fixed seed so the picture is the same every run; a layout that moves between runs cannot be
        # compared against yesterday's.
        if args.algorithm == "kamada":
            # Kamada-Kawai places nodes so that geometric distance tracks graph distance. On a
            # pipeline of this size it separates the groups a force layout piles on top of each other.
            pos = nx.kamada_kawai_layout(g.to_undirected())
        else:
            pos = nx.spring_layout(g, seed=42, iterations=args.iterations, k=1.9 / (len(nodes) ** 0.5))

        xs = [q[0] for q in pos.values()]
        ys = [q[1] for q in pos.values()]
        spanx = (max(xs) - min(xs)) or 1
        spany = (max(ys) - min(ys)) or 1
        pts = np.array([
            [120 + (pos[n["id"]][0] - min(xs)) / spanx * 2100,
             90 + (pos[n["id"]][1] - min(ys)) / spany * 1250]
            for n in nodes
        ])

        # Nodes that share every neighbour can land on exactly the same point. The push below is
        # along the vector between two centres, which is zero when they coincide, so they would stay
        # welded together forever. Nudge them apart first, deterministically.
        rng = np.random.default_rng(42)
        for i in range(len(pts)):
            same = np.hypot(pts[:i, 0] - pts[i, 0], pts[:i, 1] - pts[i, 1]) < 1e-9
            if same.any():
                pts[i] += rng.uniform(-1.5, 1.5, 2)

        # Relaxation: any two centres closer than --spacing get pushed apart. A force layout puts
        # nodes with identical neighbours in identical places, which is true but unreadable; this
        # keeps the structure and makes the dots countable.
        moved = 0
        for _ in range(400):
            d = pts[:, None, :] - pts[None, :, :]
            dist = np.hypot(d[:, :, 0], d[:, :, 1])
            np.fill_diagonal(dist, np.inf)
            too_close = dist < args.spacing
            if not too_close.any():
                break
            moved += 1
            push = np.where(too_close[:, :, None], d / np.maximum(dist, 1e-6)[:, :, None], 0.0)
            pts += push.sum(axis=1) * (args.spacing * 0.28)

        for n, (px, py) in zip(nodes, pts, strict=True):
            n["fx"] = round(float(px), 1)
            n["fy"] = round(float(py), 1)
        print(f"network layout: {args.algorithm}, {len(nodes)} nodes, {len(edges)} edges, "
              f"{moved} separation passes at {args.spacing:g}px minimum")

    if args.mermaid:
        print("graph LR")
        slug = lambda s: re.sub(r"\W", "_", s)  # noqa: E731
        for n in nodes:
            print(f'  {slug(n["id"])}["{n["id"]}"]')
        for a, b in edges:
            print(f"  {slug(a)} --> {slug(b)}")
        return 0

    html = (
        HTML.replace("__NODES__", json.dumps(nodes))
        .replace("__EDGES__", json.dumps(edges))
        .replace("__COLOUR__", json.dumps(TYPE_COLOUR))
    )
    OUT.write_text(html)
    print(f"wrote {OUT.relative_to(REPO)}  ({len(nodes)} nodes, {len(edges)} edges)")
    if args.open:
        subprocess.run(["/usr/bin/open", str(OUT)], check=False)  # noqa: S603
    return 0


if __name__ == "__main__":
    sys.exit(main())

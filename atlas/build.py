"""Build standalone original SVG schematics and their chapter index using the catalog JSON."""
import argparse
import json
from collections import Counter
from html import escape
from pathlib import Path

from topologies import DRAWINGS, Stage

STYLE = """
svg{color:#223738;font-family:system-ui,'Microsoft YaHei',sans-serif}
path,line,polyline,rect,polygon,circle{fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
text{fill:currentColor;font-size:13px;stroke:none}.net{fill:#00675e;font-weight:600}
.symbol{fill:#fff}.dot{fill:currentColor;stroke:none}.part{font-size:13px}.minor{font-size:11px;fill:#536969}
"""


class Canvas:
    def __init__(self):
        self.parts = []
        self.count = Counter()

    def path(self, d, style=""):
        self.parts.append(f'<path d="{d}" class="{style}"/>')

    def wire(self, x, y, x2, y2):
        self.path(f"M{x} {y} L{x2} {y2}")

    def circle(self, x, y, r, style="symbol"):
        self.parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" class="{style}"/>')

    def label(self, x, y, value, anchor="middle", style="part"):
        self.parts.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" class="{style}">{escape(value)}</text>')

    def ground(self, x, y):
        self.path(f"M{x} {y}v4m-10 0h20m-16 4h12m-8 4h4")

    def port(self, x, y, name, top):
        if name == "GND" and not top:
            self.ground(x,y)
        else:
            self.circle(x,y,3.6)
            self.label(x, y-9 if top else y+18, name, style="net")

    def device(self, x, y, spec, upper, lower, gate_target=None, face_right=False):
        fields = spec.split(":")
        kind, name = fields[:2]
        note = fields[2] if len(fields)>2 else ""
        self.count[kind] += 1
        if kind in ("N","P","Q"):
            if face_right:
                self.parts.append(f'<g transform="translate({2*x} 0) scale(-1 1)">')
            self.wire(x,y-42,x,y-15)
            self.wire(x,y+15,x,y+42)
            if kind=="Q":
                self.path(f"M{x} {y-15}l-16 10v-8m0 8v18m0-10l16 12m-6-1 6 1-2-6")
                self.wire(x-38,y,x-16,y)
            else:
                self.path(f"M{x} {y-15}h-13v30h13M{x-18} {y-13}v26")
                if kind=="P":
                    self.circle(x-22,y,3)
                self.wire(x-38,y,x-(25 if kind=="P" else 18),y)
            if name in (upper,lower):
                direction = -1 if name==upper else 1
                self.path(f"M{x-38} {y}v{direction*24}h38")
                self.circle(x,y+direction*24,2.4,"dot")
            elif gate_target:
                gx,gy=gate_target
                self.path(f"M{x-38} {y}H{x-65}V{gy}H{gx}")
                self.circle(gx,gy,2.8,"dot")
            else:
                self.circle(x-38,y,2.6)
            if face_right:
                self.parts.append("</g>")
            if name not in (upper,lower) and not gate_target:
                self.label(x+42 if face_right else x-42,y+4,name,"start" if face_right else "end","net")
            prefix = {"N":"MN","P":"MP","Q":"Q"}[kind]
            self.label(x-7 if face_right else x+7,y+3,prefix+str(self.count[kind]),"end" if face_right else "start")
            if note:
                self.label(x+7,y+18,note,"start","minor")
            return
        self.wire(x,y-42,x,y-17)
        self.wire(x,y+17,x,y+42)
        if kind=="R":
            self.path(f"M{x} {y-17}v2l-5 3 10 5-10 5 10 5-10 5 10 5-5 3v1")
        elif kind=="C":
            self.path(f"M{x} {y-17}v14m-12 0h24m-24 6h24m-12 0v14")
        elif kind=="L":
            self.path(f"M{x} {y-17}v1"+"q14 4 0 8"*4+"v1")
        elif kind in ("I","V","G"):
            if kind=="G":
                self.path(f"M{x} {y-17}l13 17-13 17-13-17z","symbol")
            else:
                self.circle(x,y,17)
            if kind=="V":
                self.path(f"M{x-4} {y-6}h8m-4-4v8m-4 10h8")
            else:
                self.path(f"M{x} {y-9}v18m-4-5 4 5 4-5")
        elif kind in ("PD","LD"):
            self.path(f"M{x} {y-17}v6m-8 0h16l-8 19-8-19m0 20h16m-8 0v8")
            if kind=="LD":
                self.path(f"M{x+10} {y-4}l12-9m-5 0h5v5m-9 10 12-9m-5 0h5v5")
                self.label(x+30,y-12,"光","start","net")
            else:
                self.path(f"M{x-24} {y-17}l12 10m-5 0h5v-5m-13 5 12 10m-5 0h5v-5")
        elif kind=="Z":
            self.path(f"M{x} {y-17}v3m-7 0h14v28h-14zm7 28v3")
        else:
            raise ValueError(f"Unknown component {kind}")
        self.label(x+20,y+8,name,"start")

    def branch(self, x, y, tokens, *, show_top=True, show_bottom=True, gates=None, outward=False):
        start_y=y
        for j in range(1,len(tokens),2):
            self.device(x,y+42,tokens[j],tokens[j-1],tokens[j+1],
                        (gates or {}).get(j),outward and j==len(tokens)-2)
            y += 84
            node = tokens[j+1]
            if j==len(tokens)-2:
                if show_bottom:
                    self.port(x,y,node,False)
            elif node!=".":
                self.circle(x,y,2.8,"dot")
                self.label(x+6,y-4,node,"start","net")

        if show_top:
            self.port(x,start_y,tokens[0],True)

    def stage(self,x,y,s):
        if s.symbol=="sense":
            for dy,node,sign in [(-22,s.inputs[0],"+"),(22,s.inputs[1],"−")]:
                self.circle(x-22,y+dy,3)
                self.wire(x-19,y+dy,x-5,y+dy)
                self.label(x-30,y+dy+4,node,"end","net")
                self.label(x+6,y+dy+4,sign)
            self.label(x+6,y+4,s.title)
            return
        half=45
        # Distinct port labels retain their vertical order at multi-input stages.
        def ys(n):
            return [y+(i-(n-1)/2)*21 for i in range(n)]
        height=max(22, max(len(s.inputs),len(s.outputs))*11+4)
        if s.symbol=="amp":
            self.path(f"M{x-half} {y-29}v58l90-29z","symbol")
        elif s.symbol=="inv":
            self.path(f"M{x-24} {y-18}v36l44-18z","symbol")
            self.circle(x+24,y,4)
        else:
            self.path(f"M{x-half} {y-height}h90v{2*height}h-90z","symbol")
        for i,(node,py) in enumerate(zip(s.inputs,ys(len(s.inputs)))):
            self.wire(x-62,py,x-(24 if s.symbol=="inv" else half),py)
            self.label(x-65,py+4,node,"end","net")
            if s.symbol=="amp":
                self.label(x-half+8,py+4,("+" if i==0 else "−"))
        for node,py in zip(s.outputs,ys(len(s.outputs))):
            self.wire(x+(28 if s.symbol=="inv" else half),py,x+62,py)
            self.label(x+65,py+4,node,"start","net")
        self.label(x,y+4 if s.symbol=="block" else y-height-12,s.title)


def flow(canvas, stages):
    # Use an uninterrupted signal path where successive blocks share a signal.
    spacing=145
    for i,s in enumerate(stages):
        x=65+i*spacing
        y=83
        if s.symbol=="inv":
            canvas.path(f"M{x-20} {y-15}v30l34-15z","symbol")
            canvas.circle(x+18,y,4)
            left,right=x-20,x+22
        else:
            canvas.path(f"M{x-37} {y-17}h74v34h-74z","symbol")
            canvas.label(x,y+4,s.title)
            left,right=x-37,x+37
        if i==0:
            canvas.wire(5,y,left,y)
            canvas.label(7,y-7,s.inputs[0],"start","net")
        if i:
            canvas.wire(previous,y,left,y)
            canvas.label((previous+left)/2,y-7,s.inputs[0],style="net")
        if len(s.inputs)==2:
            canvas.wire(x,y-17,x,y-38)
            canvas.label(x,y-44,s.inputs[1],style="net")
        previous=right
    canvas.wire(right,y,x+62,y)
    canvas.label(x+62,y-7,s.outputs[0],"end","net")
    return x+72,145


def fanout(c):
    c.path("M38 83v34l33-17z","symbol")
    c.circle(75,100,4)
    c.wire(9,100,38,100)
    c.label(9,91,"Vin","start","net")
    c.path("M79 100h42m0-55v110")
    c.circle(121,100,3,"dot")
    for n,y in enumerate((45,100,155),1):
        c.wire(121,y,164,y)
        c.path(f"M164 {y-16}v32l32-16z","symbol")
        c.circle(200,y,4)
        c.wire(204,y,235,y)
        c.label(240,y+4,f"Y{n}","start","net")
    return 280,200


def sensor(c,differential):
    x=105
    c.path("M105 26v32m-38 0h76M67 75h76m-38 0h62")
    c.label(x,19,"Vexc+" if differential else "Vref",style="net")
    c.label(172,79,"Vsense","start","net")
    if differential:
        c.path("M67 92h76m-38 0v25")
        c.label(x,134,"Vexc−",style="net")
    c.path("M46 63v25m-4-20 4-5 4 5m-8 15 4 5 4-5")
    c.label(35,79,"x","end","net")
    c.label(169,105,"可动极板","start","minor")
    return 247,152


def differential_core(canvas, specs):
    if len(specs)<3 or not all(isinstance(s,str) for s in specs[:3]):
        return None
    left,right,tail=[s.split() for s in specs[:3]]
    if left[-1]!="T" or right[-1]!="T" or tail[0]!="T" or len(left)!=len(right):
        return None
    # Bring the common source node and its bias branch together on the page.
    x1,x2=106,323
    mid=(x1+x2)/2
    y=27
    base=y+84*(len(left)//2)
    canvas.path(f"M{x1} {base}H{x2}")
    gates={}
    for j in range(1,len(right),2):
        gate=right[j].split(":")[1]
        if right[j][0] in ("P","N") and gate==left[j+1] and gate!=right[j+1]:
            gates[j]=(x1,y+84*((j+1)//2))
    canvas.branch(x1,y,left,show_bottom=False)
    canvas.branch(x2,y,right,show_bottom=False,gates=gates,outward=True)
    canvas.circle(mid,base,3,"dot")
    canvas.label(mid+5,base-4,"T","start","net")
    canvas.branch(mid,base,tail,show_top=False)
    return 432,base+84*(len(tail)//2)+25


def render(title, specs):
    c=Canvas()
    if title=="反相器扇出驱动网络":
        w,h=fanout(c)
    elif title in ("差动电容传感器","单端可变电容传感器"):
        w,h=sensor(c,title.startswith("差动"))
    elif all(isinstance(s,Stage) for s in specs) and all(a.outputs[0]==b.inputs[0] for a,b in zip(specs,specs[1:])):
        w,h=flow(c,specs)
    else:
        core=differential_core(c,specs)
        if core:
            specs=specs[3:]
        columns=min(3 if core else 4,len(specs))
        col_width=232 if any(isinstance(s,Stage) for s in specs) else 184
        offset=core[0] if core else 0
        w=offset+columns*col_width
        top=26
        for start in range(0,len(specs),max(1,columns)):
            row=specs[start:start+columns]
            previous={}
            max_height=100
            for j,s in enumerate(row):
                x=offset+col_width*(j+0.5)
                if isinstance(s,Stage):
                    c.stage(x,top+52,s)
                    previous={}
                    continue
                tokens=s.split()
                assert len(tokens)>=3 and len(tokens)%2==1,(title,s)
                nets={i*84:node for i,node in enumerate(tokens[::2]) if node not in (".","VDD","GND")}
                for dy,node in nets.items():
                    if previous.get(dy)==node:
                        c.wire(x-col_width,top+dy,x,top+dy)
                c.branch(x,top,tokens)
                previous=nets
                max_height=max(max_height,84*(len(tokens)//2)+25)
            top+=max_height+26
        h=max(core[1] if core else 0,top-16)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" role="img" viewBox="0 0 {w} {h}">'
            f'<title>{escape(title)}</title><style>{STYLE}</style>'+''.join(c.parts)+'</svg>')


def build(source,dest):
    entries=json.loads(source.read_text())
    keys=[(e["章节"],e["名字"]) for e in entries]
    if len(set(keys))!=len(keys) or set(keys)!=set(DRAWINGS):
        raise ValueError(f"Catalog and diagrams disagree: {set(keys)^set(DRAWINGS)}")
    graphics=dest/"diagrams"
    graphics.mkdir(exist_ok=True,parents=True)
    chapters=Counter()
    catalog=[]
    for entry,key in zip(entries,keys):
        chapter,title=key
        chapters[chapter]+=1
        slug=f'c{int(chapter[1:-1]):02}-{chapters[chapter]:02}'
        svg=render(title,DRAWINGS[key])
        (graphics/(slug+".svg")).write_text(svg)
        catalog.append(dict(entry,id=slug))
    (dest/"catalog.json").write_text(json.dumps(catalog,ensure_ascii=False))
    print(f"Built {len(catalog)} diagrams in {len(chapters)} chapters.")


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("source",type=Path)
    parser.add_argument("destination",type=Path)
    args=parser.parse_args()
    build(args.source,args.destination)

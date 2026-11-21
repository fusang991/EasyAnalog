"""Compile the drawing's named nets into ngspice circuits and explicit test fixtures."""
from collections import Counter
from topologies import Stage

# Input ports, default readout, bias and peak amplitude in the displayed units.
# An @ input modulates a labeled current source in µA, or an external test current.
BENCHES = {
    "c01-01": ("Vin","Vout",2.5,2.2), "c01-02": ("Vin","Y1",2.5,2.2),
    "c01-03": ("@photo","Vout",10,5), "c01-04": ("Vexc±","Vsense",0,1),
    "c01-05": ("基带","射频场",0,.4), "c01-06": ("射频场","基带",0,.1),
    "c01-07": ("Vin","Vout",0,.8), "c01-08": ("数据","接收端",1,.4),
    "c01-09": ("Vref","Vsense",0,1),
    "c02-01": ("端口A","端口B",2.5,2.4), "c02-02": ("端口A","端口B",2.5,2.4),
    "c02-05": ("Vbias","#1",1.05,.05), "c02-06": ("D","#1",.08,.03),
    "c02-08": ("VDD","Vd",5,.1),"c02-09": ("VDD","#1",5,.1),
    "c02-10": ("VDD","#2",5,.1),"c02-11": ("VDD","Vd",5,.1),
    "c02-15": ("B","C",0,.01), "c03-16": ("Vin","Vout",.2,.02),
    "c04-13": ("RF±","Vo±",0,.04),
    "c05-01": ("VDD","#3",5,.1),"c05-04": ("@Iref","#4",100,10),
    "c05-13": ("@Iref","#3",100,10),
    "c06-05": ("Vin","Vout",0,.01), "c06-01": ("Vs","Vout",0,1),"c06-02": ("@load","Vout",0,10),
    "c06-18": ("VG","#2",1.1,.1),"c06-19": ("VG","#3",1.1,.1),
    "c08-06": ("Vin","Vout",.2,.02),"c08-07": ("Vin","#1",.4,.04),
    "c08-09": ("Vin","#1",.4,.04),"c08-10": ("Vin","Vout",.95,.005),
    "c08-11": ("Vin","Vout",3,.02),"c08-12": ("@Iin","Iout",0,5),
    "c08-13": ("@Iin","Iout:load",214,5),"c08-20": ("@Isense","#2",100,10),
    "c09-23": ("共模","Vcm",2.5,.1),"c09-24": ("共模","Vcm",2.5,.1),
    "c09-25": ("共模","#1",1.4,.1),"c09-42": ("耦合输入","Vout",0,.01),
    "c09-56": ("Vs","Vout",0,1),
    "c10-10": ("Xo","Vout",4,.01),"c10-11": ("VDD","#1",5,.05),
}
for code in ("c02-12","c02-13","c02-14","c06-17"):
    BENCHES[code]=("G","D",0,.01)
for code in ("c05-02","c05-03","c05-06","c05-07","c05-08","c05-09","c05-10",
             "c05-11","c05-12","c05-14","c05-15","c05-21"):
    BENCHES[code]=("@Iref","Iout:load",100,10)

R_VALUES = {"RD":10,"RS":1,"RL":10,"RG":100,"Rsig":1,"Rf":10,"Ri":1,"Rg":1,
            "Re":1,"Rs":1,"ro":50,"rπ":10,"Rset":1,"Rshift":7,"Rz":1,"Zf":10}
C_VALUES = {"Cgd":3,"Cgs":10,"Cdb":3,"Csb":3,"CL":20,"Cc":10,"Cf":50,"Cg":50,
            "Ci":100,"Cb":200,"Cff":10,"Cx":10,"Ctail":10}
BIAS = {"Vbn":1.02,"Vbp":3.98,"Vbc":1.8,"VbcN":1.8,"VbcP":3.2,"VbcA":1.8,
        "Vbn3":2.45,"Vbp3":2.55,"Vb2":1.75,"Vb3":2.45,"Vbias":1.35,
        "Vbt":1.15,"Vc1":1.1,"Vc2":.94,"Vctrl":1.12,"Vrz":4.8,
        "Vref":1.7,"VrefP":3.7,"EN":5,"EN̅":0}


class Bench:
    def __init__(self,slug,specs):
        self.id=slug
        self.specs=specs
        self.nodes={"GND":"0"}
        self.lines=[]
        self.notes=[]
        self.params={}
        self.probes={}
        self.attached=set()
        self.gates=set()
        self.branch_ids={}
        self.counter=Counter()
        self.ac=True
        self.f=1e4
        self.wave="sin"
        self.components=[]
        for spec in specs:
            if isinstance(spec,Stage):
                for name in (*spec.inputs,*spec.outputs):
                    self.node(name)
                continue
            parts=spec.split()
            for i in range(1,len(parts),2):
                a,desc,b=parts[i-1:i+2]
                self.attached.update([a,b])
                self.node(a);self.node(b)
                kind,tag,*extra=desc.split(":")
                if kind in ("N","P","Q"):
                    self.gates.add(tag);self.node(tag)
                self.components.append((a,kind,tag,b,extra))
        self.src,self.out,self.dc,self.amp=self.plan()
        if slug in ("c04-02","c04-09","c09-47"): self.amp=.015
        # Open-loop fixtures need an input offset trim to bias the second stage
        # inside its output swing. These are for the default geometry and supply.
        trim={"c10-13":-.012175,"c10-14":-.012631,"c10-16":-.012141}
        if slug in ("c06-16","c10-05","c10-06","c10-07","c10-08","c10-09","c10-12","c10-15") or slug in trim:
            self.dc=trim.get(slug,-.016323)
            self.amp=.00001
            self.notes.append("开环测试用微小差分直流偏置将输出调入放大区。改变器件后可重新调整偏置。")
        if slug=="c09-17":self.dc=1.00972;self.amp=.00005
        if slug in ("c09-14","c09-15","c10-04","c09-19","c09-20","c09-22","c09-55",
                    "c03-20","c03-21","c03-22","c09-52","c09-53","c10-18"):self.amp=.0001
        self.unit="µA" if self.src.startswith("@") else "V"
        self.source_name=self.src.removeprefix("@")
        if self.source_name=="photo": self.source_name="光电流"
        if self.source_name=="load": self.source_name="测试电流"
        if slug=="c01-08": self.source_name="驱动电压"

    def node(self,name):
        if name not in self.nodes:
            self.nodes[name]="n"+str(len(self.nodes))
        return self.nodes[name]

    def plan(self):
        if self.id in BENCHES:
            return BENCHES[self.id]
        if self.id in ("c08-14","c08-15","c08-16","c08-18"):
            return "@Iin","Vout",0,1
        if "Vin+" in self.nodes:
            return "Vin±",("Vo±" if "Vo+" in self.nodes else "Vout"),0,.005
        if "Vin" not in self.nodes:
            raise ValueError(f"Missing experiment input for {self.id}")
        out="Vo±" if "Vo+" in self.nodes else "Vout"
        dc=1.02
        if self.id in ("c02-03","c03-12","c04-01","c09-41"): dc=2.5
        if self.id in ("c03-21","c09-52"): dc=3.98
        if self.id in ("c02-04","c03-13","c03-14","c04-18","c06-09","c09-05","c09-09","c09-12","c09-39","c09-40","c10-19","c10-21","c09-38","c08-05","c10-01"): dc=1.8
        if self.id in ("c04-17","c06-10"): dc=.18
        if self.id in ("c08-02","c08-04","c09-01","c09-02","c09-50","c06-03","c06-04","c06-05","c06-06","c06-07"):dc=0
        return "Vin",out,dc,.015

    def param(self,name,unit,value,positive=True):
        key=(name,unit)
        if key not in self.params:
            self.params[key]=dict(key="p"+str(len(self.params)),label=name,unit=unit,value=value,positive=positive)
        return self.params[key]["key"]

    def fixed(self,name,value):
        p=self.param(name,"V",value,False)
        self.lines.append(f"Vbias{self.node(name)} {self.node(name)} 0 {{{p}}}")

    def probe(self,label,expression,unit="V"):
        self.probes[label]=dict(label=label,element=expression,unit=unit)

    def fixture(self):
        n=self.node
        a=self.src
        self.lines.append(".options reltol=0.001 abstol=1e-12 itl1=500 itl4=100 method=gear")
        need_supply="VDD" in self.nodes or any(x[1] in ("P","N") for x in self.components) or any(isinstance(s,Stage) and s.symbol=="inv" for s in self.specs)
        if need_supply and a!="VDD": self.fixed("VDD",5)
        if a in ("Vin±","RF±","Vexc±","共模"):
            pair={"Vin±":("Vin+","Vin−"),"RF±":("RF+","RF−"),"Vexc±":("Vexc+","Vexc−"),"共模":("Vo+","Vo−")}[a]
            if a=="共模":
                for i,port in enumerate(pair):
                    self.lines.append(f"Ecm{i} {n(port)} 0 in 0 1")
            else:
                cm=self.param("输入共模","V",0 if a=="Vexc±" or self.id=="c04-08" else (3.25 if self.id in ("c05-20","c09-10","c10-18") else (1.05 if self.id in ("c04-02","c04-09","c09-47") else 1.7)),False)
                self.lines.append(f"Vcmtest cmtest 0 {{{cm}}}")
                for i,port in enumerate(pair):
                    end=f"drive{i}" if self.id=="c04-08" else n(port)
                    self.lines.append(f"Ein{i} {end} cmtest in 0 {(.5,-.5)[i]}")
                    if self.id=="c04-08": self.lines.append(f"Rsrc{i} {end} {n(port)} 50")
        elif a=="耦合输入":
            self.lines.extend([f"Cfixture in {n('G')} 1u"])
            self.notes.append("输入通过外接 1 µF 电容耦合到 G。")
        elif a.startswith("@"):
            if a in ("@load","@Isense","@photo"):
                port={"@load":"Vout","@Isense":"Isense","@photo":"K"}[a]
                self.lines.append(f"Gstim 0 {n(port)} in 0 1u")
        else:
            self.lines.append(f"Edrive {n(a)} 0 in 0 1")
        # Current-output ports need a compliance voltage. A 0 V series sensor
        # gives the sink current a positive orientation into the circuit.
        for port in ("Iout","If","I½","I₂","Iload","Tail"):
            if port not in self.nodes or self.id in ("c08-07","c08-12"): continue
            p=self.param("输出钳位电压","V",2.5,False)
            key=n(port)
            self.lines.extend([f"Vhold{key} hold{key} 0 {{{p}}}",f"Vsink{key} hold{key} {key} 0"])
            polarity="-1e6" if self.id in ("c05-03","c08-13") or port=="Iload" else "1e6"
            self.probe(port+":load",f"Hread out 0 Vsink{key} {polarity}","µA")
        if any(k.endswith(":load") for k in self.probes): self.notes.append("输出电流端用可调钳位电源设定顺从电压。")
        for port,value in BIAS.items():
            if port in self.nodes and (port not in self.attached or (port=="Vbias" and self.id=="c03-05")) and port!=a:
                if self.id in ("c03-22","c09-53") and port=="Vbp":value=3.838
                if self.id in ("c03-21","c09-52") and port=="Vbn":value=1.162
                if port=="Vbp":
                    value={"c09-14":3.9985,"c09-15":4.0742,"c10-04":4.0742,
                           "c09-20":3.98225,"c09-55":3.94375}.get(self.id,value)
                if self.id=="c09-31" and port=="Vbn":value=1.05075
                if port=="Vbt" and any(k=="P" and t=="Vbt" for _,k,t,_,_ in self.components):value=3.85
                if port=="Vctrl" and self.id=="c03-07": value=2.0
                if port=="Vbias" and self.id=="c03-05":value=1.05
                self.fixed(port,value)
        if a=="@Iin" and self.id=="c08-18":self.dc=100
        if self.id in ("c02-06","c09-25"):
            self.fixed("S",0)
            if self.id=="c09-25":self.fixed("D",.08)
        if self.id in ("c02-12","c02-13","c02-14","c02-15","c06-17"):
            self.fixed("E" if self.id=="c02-15" else "S",0)
            if "B" in self.nodes and a!="B":self.fixed("B",0)
            self.lines.append(f"Rtest {n(self.out)} 0 10k")
            self.notes.append("小信号模型的输出接 10 kΩ 测试负载。")
        if self.id in ("c02-01","c02-02"):
            rail="0" if self.id=="c02-01" else n("VDD")
            self.lines.append(f"Rload {n('端口B')} {rail} 1meg")
        if self.id=="c01-09":
            self.lines.append(f"Rread {n('Vsense')} 0 1meg")
            self.notes.append("Vsense 外接 1 MΩ 读出电阻。")
        if self.id=="c01-04":
            self.lines.append(f"Rread {n('Vsense')} 0 1g")
        if self.id in ("c08-01","c08-05","c08-06","c08-18","c08-19","c09-38","c09-51","c10-01"):
            gate="Σ" if "Σ" in self.nodes else "Vfb"
            bias=.98 if self.id in ("c08-01","c08-18") else 1.7
            if self.id=="c08-06":bias=1.25
            self.lines.extend([f"Vdcpath dcpath 0 {bias}",f"Rdcpath dcpath {n(gate)} 1g"])
            self.notes.append(f"{gate} 通过 1 GΩ 偏置支路建立电容反馈的直流工作点。")
        if self.id=="c08-16":self.lines.append(f"Rdcpath {n('Σ')} {n('Vout')} 1g")
        if self.id in ("c04-13","c01-05","c01-06"):
            self.ac=False
            self.f=1e4 if self.id!="c01-06" else 1.1e5
            lo=self.param("本振","Hz",1e5)
            if self.id=="c04-13":
                self.lines.extend([f"Vlo lo 0 sin(0 0.4 {{{lo}}})","Vlocm locm 0 3",
                                   f"Elo1 {n('LO+')} locm lo 0 1",f"Elo2 {n('LO−')} locm lo 0 -1"])
            else:self.lines.append(f"Vlo {n('LO')} 0 sin(0 1 {{{lo}}})")
            self.notes.append("混频在时域观察，单频 AC 线性化无法给出变频增益。")
        if self.id in ("c01-05","c01-06","c01-07"):
            self.ac=False
            self.notes.append("采用归一化行为级信号，转换器使用 8 位静态量化，采样时钟及噪声未建模。")
        if self.id=="c01-08":self.notes.append("接收端以电压表示归一化光功率，使用线性斜率和激光阈值模型。")
        if self.id=="c09-56": self.wave="step";self.f=1000
        if self.id in ("c04-06","c04-08","c04-09"):self.f=1e7
        if self.id=="c03-09":self.dc=2.05
        if self.id=="c06-01":self.f=159.155
        if self.id in ("c01-01","c01-02"):
            cap=self.param("输出测试负载","pF",5)
            self.lines.append(f"Ctest {n(self.out)} 0 {{{cap}*1p}}")
            self.notes.append("所选末级输出接可调测试电容，PMOS 宽度为 NMOS 的两倍。")
        if self.id=="c10-17":
            self.amp=.0005
            self.lines.extend(["Vqtest gateq 0 1.01",f"Rfirst gateq {n('Xo')} 200k"])
            self.notes.append("首级采用差分跨导与 200 kΩ 输出电阻，镜像参考支路含可调静态偏置。")
        if self.id=="c10-11":
            self.lines.append(f"Rstartup {n('VDD')} {n('G')} 10meg")
            self.notes.append("10 MΩ 启动电阻帮助自偏置基准离开零电流解。")

    def element(self,i,a,kind,tag,b,extra):
        n=self.node
        top,low=n(a),n(b)
        # Name the node between a zero-volt ammeter and the component.
        lead=f"tap{i}"
        self.lines.append(f"Vmeas{i} {top} {lead} 0")
        self.counter[kind]+=1
        label=({"N":"MN","P":"MP","Q":"Q"}.get(kind,"")+str(self.counter[kind])) if kind in ("N","P","Q") else tag
        probe=f"I({label}) · {a} → {b}"
        if probe in self.probes:probe+=f" [{i}]"
        self.probe(probe,f"Hread out 0 Vmeas{i} 1e6","µA")
        self.branch_ids["#"+str(i)]=probe
        if kind in ("N","P"):
            wide=4 if extra and extra[0]=="宽管" else 1
            if self.id=="c09-31" and kind=="P" and tag=="Dr" and b.startswith("F"):wide=2
            if self.id=="c09-55" and kind=="N" and tag=="Vcm1":wide=.005
            if self.id in ("c09-48","c09-49") and kind=="P" and b.startswith("Vo"):wide=2
            length=3 if extra and extra[0] in ("L长","长沟道","W/3L") else 1
            width=self.param("NMOS W/L 基准" if kind=="N" else "PMOS W/L 基准","",20 if kind=="N" else 40)
            d,s,body=(lead,low,"0") if kind=="N" else (low,lead,n("VDD"))
            self.lines.append(f"M{i} {d} {n(tag)} {s} {body} m{kind} W={{{width}*{wide}*1u}} L={length}u")
        elif kind in ("R","Z"):
            val=R_VALUES.get(tag,10)
            if self.id in ("c06-01","c09-56"):val=1
            if tag=="R1" and self.id in ("c02-08","c05-01"):val=39
            p=self.param(tag,"kΩ",val)
            self.lines.append(f"R{i} {lead} {low} {{{p}*1k}}")
        elif kind=="C":
            val=C_VALUES.get(tag,100)
            if self.id in ("c06-01","c09-56"): val=1e6
            if self.id in ("c01-04","c01-09"):
                p=self.param("静止电容 C₀","pF",10)
                x=self.param("位移 / 初始间距","",.2,False)
                self.params[("位移 / 初始间距","")].update(min=-.95,max=.95)
                denominator="1+"+x if "₂" in tag else "1-"+x
                value=f"{p}*1p/({denominator})"
            else:
                p=self.param(tag,"pF",val)
                value=f"{p}*1p"
            self.lines.append(f"C{i} {lead} {low} {{{value}}}")
        elif kind=="L":
            p=self.param(tag,"µH",100 if tag=="Lf" else 1)
            self.lines.extend([f"L{i} {lead} coil{i} {{{p}*1u}}",f"Rcoil{i} coil{i} {low} 0.2"])
        elif kind=="I":
            if self.src=="@"+tag:
                self.lines.append(f"G{i} {lead} {low} in 0 1u")
            else:
                val=200 if tag in ("It","Ip","In","I₁") else (10 if tag=="Ishift" else 100)
                if (self.id,tag) in (("c10-13","Ibuf"),("c10-16","Iref")):val=2
                if self.id=="c09-20" and tag=="Ia":val=200
                p=self.param(tag,"µA",val)
                self.lines.append(f"Bbias{i} {lead} {low} I={p}*1u*tanh(v({lead},{low})/0.15)")
                self.lines.append(f"Rbias{i} {lead} {low} 1g")
        elif kind=="V":
            if self.src==a:
                # The input fixture drives this explicit source instead of adding
                # another voltage source in parallel with its current sensor.
                self.lines.remove(f"Edrive {top} 0 in 0 1")
                self.lines.append(f"E{i} {lead} {low} in 0 1")
            else:
                p=self.param(tag,"V",2.5,False)
                self.lines.append(f"V{i} {lead} {low} {{{p}}}")
        elif kind=="Q":self.lines.append(f"Q{i} {lead} {n(tag)} {low} qnpn")
        elif kind in ("PD","LD"):
            self.lines.append(f"D{i} {lead} {low} diode")
            if kind=="LD":
                self.lines.append(f"Bopt {n('光')} 0 V=max(0,i(Vmeas{i})*1000-0.5)")
        elif kind=="G":
            controls={"gm·vgs":("G","S"),"gmb·vbs":("B","S"),"gm·vbe":("B","E"),
                      "gm·vin":("Vin","GND"),"gm₁·vin":("Vin","GND"),"gm₂·vx":("X","GND")}
            if tag in controls:
                pos,neg=controls[tag]
                p=self.param(tag.split("·")[0],"mS",.2 if tag.startswith("gmb") else 1)
                self.lines.append(f"G{i} {lead} {low} {n(pos)} {n(neg)} {{{p}*1m}}")
            elif tag=="β·iout":self.lines.append(f"G{i} {lead} {low} {n('Iout')} 0 0.1m")
            elif tag=="Is":self.lines.append(f"G{i} {lead} {low} {n('Is')} 0 1m")
            elif tag=="α·Is":
                iq=self.param("镜像静态电流","µA",100)
                self.lines.append(f"Bref{i} {lead} {low} I=max(0,{iq}*1u+0.5m*v({n('Is')}))")
            else:raise ValueError(tag)
        else:raise ValueError(kind)

    def stage(self,i,s):
        if s.symbol=="sense":return
        inputs=[self.node(x) for x in s.inputs]
        outputs=[self.node(x) for x in s.outputs]
        v=[f"v({x})" for x in inputs]
        out=outputs[0]
        if s.symbol in ("inv","amp") or s.title in ("缓冲器","反相增益级","−Av","输出级","LNA"):
            lead=f"port{i}"
            self.lines.append(f"Vport{i} {lead} {out} 0")
            self.probe(f"I({s.title}) → {s.outputs[0]}",f"Hread out 0 Vport{i} 1e6","µA")
            out=lead
        if s.symbol=="inv":
            width=self.param("反相器 NMOS W/L","",20)
            self.lines.extend([f"Vdown{i} {out} nd{i} 0",f"Vup{i} {self.node('VDD')} ps{i} 0",
                               f"Min{i} nd{i} {inputs[0]} 0 0 mN W={{{width}*1u}} L=1u",
                               f"Mip{i} {out} {inputs[0]} ps{i} {self.node('VDD')} mP W={{{width}*2u}} L=1u"])
            self.probe(f"I(MN{i}) · 下拉",f"Hread out 0 Vdown{i} 1e6","µA")
            self.probe(f"I(MP{i}) · 上拉",f"Hread out 0 Vup{i} 1e6","µA")
            return
        if s.symbol=="amp":
            gain=self.param("运放直流增益","V/V",1000)
            if s.title in ("A","TIA"):
                expression=f"{gain}*({v[0]}-{v[1]})"
                self.notes.append("运放采用有限增益、单极点模型，支持双极性输出。")
            else:
                expression=f"2.5+2.5*tanh({gain}*({v[0]}-{v[1]})/2.5)"
            self.lines.extend([f"Bamp{i} amp{i} 0 V={expression}",f"Ramp{i} amp{i} {out} 100",f"Camp{i} {out} 0 1n"])
            return
        if s.title=="混频器": expr=f"{v[0]}*{v[1]}"
        elif s.title in ("ADC","DAC"):expr=f"floor(min(1,max(-1,{v[0]}))*127+0.5)/127"
        elif s.title=="数字解调":
            self.lines.extend([f"Bdemod{i} dem{i} 0 V=2*{v[0]}*cos(2*pi*10000*time)",
                               f"Rdem{i} dem{i} {out} 1k",f"Cdem{i} {out} 0 100n"])
            return
        elif s.title=="射频滤波":
            self.lines.extend([f"Cfilter{i} {inputs[0]} band{i} 10n", f"Rband{i} band{i} 0 1k",
                               f"Rfilter{i} band{i} {out} 100",f"Cband{i} {out} 0 1n"])
            return
        elif s.title=="电流驱动器":
            self.lines.append(f"Gdriver{i} 0 {out} {inputs[0]} 0 1m")
            return
        elif s.title=="差分电流求和":
            for k,port in enumerate(inputs):
                self.lines.append(f"Vsum{i}_{k} {port} sumcm 0")
            self.lines.extend(["Vsumcm sumcm 0 2.5",f"Bsum{i} {out} 0 V=2.5+1k*(i(Vsum{i}_0)-i(Vsum{i}_1)-i(Vsum{i}_2)+i(Vsum{i}_3))"])
            return
        elif s.title=="差分跨导输入级":
            self.lines.append(f"Gstage{i} 0 {out} {inputs[0]} {inputs[1]} 1m")
            return
        elif s.title=="差分跨导级":expr=f"{v[0]}-{v[1]}"
        elif s.title=="电流增益 Ai":
            self.lines.append(f"Rsense{i} {inputs[0]} 0 1k")
            expr=f"10*{v[0]}"
        else:
            gains={"缓冲器":1,"反相增益级":-10,"−Av":-10,"LNA":3,"后级接收":1,"功率放大器":2,
                   "天线":1,"DAC":1,"数字处理":1,"模拟前端":1,"输出级":1,"光纤":.8,"串联电流取样":1}
            expr=f"{gains[s.title]}*{v[0]}"
        self.lines.append(f"Bstage{i} {out} 0 V={expr}")

    def finish(self,title):
        self.title=title
        self.fixture()
        for i,component in enumerate(self.components,1):self.element(i,*component)
        for i,s in enumerate(self.specs,1):
            if isinstance(s,Stage):self.stage(i,s)
        if self.id=="c06-07":
            # A finite source impedance exposes the Miller input capacitance.
            node=self.node("Vin")
            self.lines.remove(f"Edrive {node} 0 in 0 1")
            self.lines.append(f"Rsig in {node} 10k")
            self.notes.append("测试信号经 10 kΩ 源电阻驱动输入。")
        for key,net in self.nodes.items():
            if key=="GND":continue
            self.probe(key,f"Eread out 0 {net} 0 1")
        self.probe("GND","Vread out 0 0")
        if self.out=="Vo±":
            self.probe("Vo±",f"Eread out 0 {self.nodes['Vo+']} {self.nodes['Vo−']} 1")
        if self.id=="c08-12":
            self.probe("Iout",f"Eread out 0 {self.nodes['Iout']} 0 1000","µA")
            self.notes.append("电流增益和取样框采用 1 kΩ 电流－电压换算。")
        if self.id=="c05-04": self.out="Iload:load"
        if self.id=="c08-13": self.out="Iout:load"
        output=self.branch_ids.get(self.out,self.out)
        assert output in self.probes,(self.id,output)
        if self.id in ("c02-03","c03-12","c04-01","c09-41"):self.dc=2.5
        if self.id=="c08-11": self.notes.append("辅助运放使用有限开环增益和单极点近似。")
        # Save only the two active traces. Large schematics otherwise export
        # every device and internal timestep across the WebAssembly boundary.
        self.lines += [".model mN NMOS (level=1 vto=0.7 kp=100u lambda=.025 cgso=0.2n cgdo=0.2n)",
                       ".model mP PMOS (level=1 vto=-0.7 kp=50u lambda=.025 cgso=0.2n cgdo=0.2n)",
                       ".model qnpn NPN (bf=150 is=1e-15 vaf=80 cje=2p cjc=1p)",
                       ".model diode D (is=1e-15 n=1.5 cjo=2p)",".save v(in) v(out)"]
        if any("Bbias" in line for line in self.lines):
            self.notes.append("偏置电流源含 0.15 V 顺从电压模型与 1 GΩ 输出电阻。")
        if self.id in ("c02-04","c03-02"):
            self.lines=[line.replace("kp=100u","kp=100u gamma=.4 phi=.7") for line in self.lines]
            self.notes.append("NMOS 体端接地，模型启用体效应。")
        device={"c06-18":"m2","c06-19":"m3"}.get(self.id)
        return dict(device=device,lines=self.lines,params=list(self.params.values()),probes=list(self.probes.values()),
                    output=output,source=self.source_name,unit=self.unit,dc=self.dc,amp=self.amp,
                    f=self.f,lo=min(self.f/100,10),hi=max(self.f*100,1e7),ac=self.ac,wave=self.wave,notes=self.notes,nodes=self.nodes)

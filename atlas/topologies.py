"""Named electrical nets connect branches, including across a folded drawing.
Each branch alternates net and component. A period is a local unnamed node.
MOS elements list their gate net, optionally followed by a device annotation.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Stage:
    title: str
    inputs: tuple
    outputs: tuple
    symbol: str = "block"


def block(title, inputs, outputs, symbol="block"):
    return Stage(title, tuple(inputs.split()), tuple(outputs.split()), symbol)


def amp(plus, minus, out, name="A"):
    return block(name, plus + " " + minus, out, "amp")


def cs(load="R:RD", source="GND", gate="Vin", out="Vout"):
    return f"VDD {load} {out} N:{gate} {source}"


def follower(gate="Vin", load="I:Ib", out="Vout"):
    return f"VDD N:{gate} {out} {load} GND"


def pair(load="R:RD", tail="I:It", left="X", right="Y", g1="Vin+", g2="Vin−"):
    return [cs(load.replace("{d}", left), "T", g1, left),
            cs(load.replace("{d}", right), "T", g2, right), f"T {tail} GND"]


def ota(g1="Vin+", g2="Vin−", out="Vout"):
    return pair("P:X", "N:Vbn", "X", out, g1, g2)


def telescope(single=False, wide=False, feedback=False, triple=False):
    outputs = ["K", "Vout"] if single else ["Vo−", "Vo+"]
    branches = []
    for i, out in enumerate(outputs):
        pc = ("K" if single and not wide else "VbcP")
        pg = (("K" if wide else "P1") if single else "Vbp")
        load = f"P:{pg} P{i+1} P:{pc}"
        if triple:
            load += f" Q{i+1} P:Vbp3"
        signal = (f"N:Vbn3 J{i+1} " if triple else "") + f"N:VbcN D{i+1} N:"
        gate = ("Vin" if i==0 else "Vout") if feedback else ("Vin+" if i==0 else "Vin−")
        branches.append(f"VDD {load} {out} {signal}{gate} T")
    return branches + ["T N:Vbn GND"]


def folded(p_input=False, differential=True, tail_gate="Vbt", sink_gate="Vbn", mirror=False, feedback=False, source_res=False):
    branches = []
    for i in range(2 if differential else 1):
        side = str(i+1)
        gate = (("Vin" if i==0 else "Vout") if feedback else ("Vin+" if i==0 else "Vin−")) if differential else "Vin"
        fold = "F"+side
        out = (("K" if i==0 else "Vout") if mirror else ("Vo+" if i==0 else "Vo−")) if differential else "Vout"
        if p_input:
            branches.extend([f"{'T' if differential else 'VDD'} P:{gate} {fold} N:{sink_gate} GND",
                             f"VDD P:Vbp U{side} P:VbcP {out} N:VbcN {fold}"])
        else:
            low = ("Sdet" if source_res else "GND")
            branches.extend([f"VDD P:Vbp {fold} N:{gate} "+("T" if differential else "GND"),
                             f"{fold} P:VbcP {out} N:VbcN L{side} N:"+("K" if mirror else sink_gate)+f" {low}"])
    if differential:
        branches.append(f"VDD P:{tail_gate} T" if p_input else f"T N:{tail_gate} GND")
    return branches


def model(body=False, hf=False):
    paths = [block("vgs", "G S", "", "sense"), "D G:gm·vgs S"]
    if body:
        paths.extend([block("vbs", "B S", "", "sense"), "D G:gmb·vbs S", "D R:ro S"])
    if hf:
        paths.extend(["G C:Cgs S", "G C:Cgd D", "D C:Cdb B", "S C:Csb B"])
    return paths


def differential_output(first="pair", out_gate="Vbp", second_gate="Vbp"):
    if first=="telescope":
        inputs = [b.replace("Vo−", "X").replace("Vo+", "Y") for b in telescope()]
    elif first=="folded":
        inputs = [b.replace("Vo+", "X").replace("Vo−", "Y") for b in folded()]
    else:
        inputs = pair("P:"+out_gate)
    return inputs+[cs("P:"+second_gate,gate="X",out="Vo+"),cs("P:"+second_gate,gate="Y",out="Vo−")]


def average(left="Vo+", right="Vo−", mid="Vcm"):
    return f"{left} R:R {mid} R:R {right}"


def mirror(p=False):
    if p:
        return ["VDD P:K K I:Iref GND", "VDD P:K Iout"]
    return ["VDD I:Iref K N:K GND", "Iout N:K GND"]


def diff_fold_feedback(which, replica=False, matched=False):
    detector = ["Sdet N:Vo+ GND", "Sdet N:Vo− GND"]
    if which=="tail":
        branches = folded()[:-1]+["T N:Vbt Sdet"]
    else:
        branches = folded(source_res=True)
    if replica:
        branches = [s.replace("N:Vbt Sdet", "N:Vctl Sdet") for s in branches]
        if matched:
            branches = [s.replace("P:Vbp F","P:Dr F") for s in branches]
            branches += ["VDD I:Iref Vctl N:Vctl GND", "VDD P:Dr Dr N:Vin+ Srep", "Dr N:Vin− Srep", "Srep N:Vctl Sref"]
        else:
            branches.append("VDD I:Iref Vctl N:Vctl Sref")
        branches += ["Sref N:Vref GND", "Sref N:Vref GND"]
    return branches+detector


def ab_stage(g1="Vin+", g2="Vin−", tails=True):
    main, aux = ("T1", "T2") if tails else ("GND", "GND")
    branches = [cs("P:K2", main, g1, "Vo−"), cs("P:K1", main, g2, "Vo+"),
                cs("P:K1", aux, g1, "K1"), cs("P:K2", aux, g2, "K2")]
    if tails:
        branches.extend(["T1 I:I₁ GND", "T2 I:I₂ GND"])
    return branches


def two_stage():
    return ota(out="Xo")+[cs("I:Ib",gate="Xo"), "Vout C:CL GND"]


def compensation(branch):
    return two_stage()+[branch]


def divider_caps():
    return ["Vout C:Cf Vfb C:Cg GND"]


def cap_ota(inverting=False):
    if inverting:
        return ota("Vref","Σ")+["Vin C:Ci Σ C:Cf Vout"]
    return ota("Vin","Vfb")+divider_caps()


def boosted(aux="single", upper=False):
    branches = []
    for n, gate in [(1,"Vin+"),(2,"Vin−")]:
        out = "Vo−" if n==1 else "Vo+"
        pgate = f"Ap{n}" if upper else "VbcP"
        branches.append(f"VDD P:Vbp U{n} P:{pgate} {out} N:A{n} D{n} N:{gate} T")
    branches.append("T N:Vbt GND")
    if aux=="single":
        branches.extend([amp("Vref", f"D{n}", f"A{n}", "增益辅助") for n in [1,2]])
    else:
        if aux=="差分辅助放大":
            branches.extend(["VDD I:I1 A1 N:D1 Ta", "VDD I:I2 A2 N:D2 Ta", "Ta I:Ia GND"])
        else:
            branches.extend(["VDD I:Ia Ta P:D1 F1 I:Ib1 GND","Ta P:D2 F2 I:Ib2 GND",
                             "VDD I:I1 A1 N:VbcA F1","VDD I:I2 A2 N:VbcA F2"])
    if upper:
        branches.extend([amp("VrefP", f"U{n}", f"Ap{n}", "负载辅助") for n in [1,2]])
    return branches


def rc_stage(step=False):
    return [("Vs V:阶跃 GND" if step else "Vs V:Vin GND"), "Vs R:R Vout C:C GND"]


# A dictionary entry identifies one published catalog entry by chapter and title.
DRAWINGS = {}
def chapter(number, entries):
    for name, elements in entries.items():
        DRAWINGS[(f"第{number}章", name)] = elements

chapter(1, {
    "反相器链": [block("反相器", "Vin", "A", "inv"), block("反相器", "A", "B", "inv"), block("反相器", "B", "Vout", "inv")],
    "反相器扇出驱动网络": [block("驱动门","Vin","X","inv"), block("负载门 1","X","Y1","inv"), block("负载门 2","X","Y2","inv"), block("负载门 3","X","Y3","inv")],
    "光接收前端": ["K PD:光电二极管 GND", amp("GND","K","Vtia","TIA"), "Vtia R:Rf K", block("后级接收","Vtia","Vout")],
    "差动电容传感器": ["Vexc+ C:C₁(x) Vsense C:C₂(x) Vexc−"],
    "射频发射链": [block("DAC","基带","BB"),block("混频器","BB LO","RF"),block("功率放大器","RF","TX"),block("天线","TX","射频场")],
    "射频接收链": [block("天线","射频场","RF"),block("射频滤波","RF","RF1"),block("LNA","RF1","RF2"),block("混频器","RF2 LO","IF"),block("ADC","IF","D"),block("数字解调","D","基带")],
    "模数与数模转换接口链": [block("模拟前端","Vin","Va"),block("ADC","Va","Din"),block("数字处理","Din","Dout"),block("DAC","Dout","Vd"),block("输出级","Vd","Vout")],
    "直接调制激光发射前端": [block("电流驱动器","数据","Imod"),"Imod LD:激光二极管 GND", block("光纤","光","接收端")],
    "单端可变电容传感器": ["Vsense C:C(x) Vref"],
})

chapter(2, {
    "NMOS 传输开关": ["端口A N:EN 端口B"],
    "PMOS 传输开关": ["端口A P:EN̅ 端口B"],
    "CMOS 反相器": [cs("P:Vin")],
    "恒流偏置源极跟随器": [follower()],
    "固定栅压 NMOS 电流沉": ["Iout N:Vbias GND"],
    "深三极区 MOS 压控电阻": ["D N:Vctrl:三极区 S"],
    "电阻负载共源放大器": [cs()],
    "分压偏置 MOS 管": ["VDD R:R1 Vg R:R2 GND","VDD R:RD Vd N:Vg GND"],
    "二极管连接 PMOS 偏置支路": ["VDD P:GND GND"],
    "电阻上拉栅极的 NMOS 偏置支路": ["VDD R:RG Vg", "VDD N:Vg GND"],
    "接地栅极、电阻负载的 PMOS 支路": ["VDD P:GND Vd R:RD GND"],
    "MOS 低频跨导等效电路": model(),
    "含体效应和输出电阻的 MOS 等效电路": model(True),
    "含寄生电容的 MOS 高频等效电路": model(True,True),
    "双极型晶体管混合 π 小信号电路": ["B R:rπ E","C G:gm·vbe E","C R:ro E"],
})

chapter(3, {
    "电阻负载共源放大器": [cs()],
    "二极管连接 NMOS 负载共源级": [cs("N:VDD")],
    "二极管连接 PMOS 负载共源级": [cs("P:Vout")],
    "二极管负载与恒流支路并联的共源级": [cs("P:Vout"),"VDD P:Vbp Vout"],
    "电容耦合输入、电阻与电流源并联负载的共源级": [cs("R:RD",gate="Vg"),"Vin C:Ci Vg","Vbias R:RG Vg","VDD I:Ib Vout"],
    "恒流源负载共源级": [cs("P:Vbp")],
    "三极区 PMOS 负载共源级": [cs("P:Vctrl:三极区")],
    "电阻源退化共源级": [cs(source="Vs R:RS GND")],
    "二极管连接 PMOS 源退化共源级": [cs(source="Vs P:GND GND")],
    "电流源管源退化共源级": [cs(source="Vs N:Vbn GND")],
    "电流源负载、电阻源退化共源级": [cs("P:Vbp","Vs R:RS GND")],
    "互补共源放大器（反相器型）": [cs("P:Vin")],
    "电阻负载源极跟随器": [follower(load="R:RS")],
    "恒流源负载源极跟随器": [follower()],
    "共源增益级接源极跟随缓冲级": [cs(out="X"),follower("X"),"Vout R:RL GND"],
    "直接耦合共栅放大器": [cs(source="Vin",gate="Vbias")],
    "电容耦合共栅放大器": [cs(source="S I:Ib GND",gate="Vbias"),"Vin C:Ci S"],
    "电阻负载共源共栅放大器": ["VDD R:RD Vout N:Vbc X N:Vin GND"],
    "多重共源共栅放大器": ["VDD R:RD Vout N:Vb3 Y N:Vb2 X N:Vin GND"],
    "上下级联的套筒式放大器": ["VDD P:Vbp P1 P:VbcP Vout N:VbcN X N:Vin GND"],
    "PMOS 输入折叠式共源共栅级": folded(True,False),
    "NMOS 输入折叠式共源共栅级": folded(False,False),
})

chapter(4, {
    "互补反相器增益级": [cs("P:Vin")],
    "独立共源支路组成的伪差分放大器": [cs(gate="Vin+",out="Vo−"),cs(gate="Vin−",out="Vo+")],
    "电阻负载、恒流尾源差分对": pair(left="Vo−",right="Vo+"),
    "二极管连接负载差分对": pair("P:{d}",left="Vo−",right="Vo+"),
    "恒流源负载全差分对": pair("P:Vbp",left="Vo−",right="Vo+"),
    "电感负载差分对": pair("L:LD",left="Vo−",right="Vo+"),
    "电容负载差分积分级": pair("P:Vbp",left="Vo−",right="Vo+")+["Vo− C:CL GND","Vo+ C:CL GND"],
    "差分共栅低噪声放大器": [cs("L:LD","Vin+ L:LS GND","Vbias","Vo+"),cs("L:LD","Vin− L:LS GND","Vbias","Vo−")],
    "电感源退化差分共源低噪声放大器": [cs("L:LD","S1 L:LS GND","Vin+","Vo−"),cs("L:LD","S2 L:LS GND","Vin−","Vo+")],
    "套筒式共源共栅差分放大器": telescope(),
    "尾电流可调差分放大器（VGA）": pair(tail="N:Vctrl",left="Vo−",right="Vo+"),
    "交叉汇流的双差分对": [cs(source="T1",gate="Vin+",out="Vo−"),cs(source="T1",gate="Vin−",out="Vo+"), "Vo− N:Vin− T2","Vo+ N:Vin+ T2","T1 N:Vc1 GND","T2 N:Vc2 GND"],
    "吉尔伯特单元（Gilbert cell）": ["VDD R:R1 Vo− N:LO+ A N:RF+ T","VDD R:R2 Vo+ N:LO− A","Vo− N:LO− B N:RF− T","Vo+ N:LO+ B","T I:It GND"],
    "二极管负载并联交叉耦合负载的差分放大器": pair("P:{d}",left="Vo−",right="Vo+")+["VDD P:Vo+ Vo−","VDD P:Vo− Vo+"],
    "下管作电流沉的共源放大器": [cs(source="Vs N:Vbn GND")],
    "有源负载、电阻源退化共源级": [cs("P:Vbp","Vs R:RS GND")],
    "共栅放大器": [cs(source="Vs",gate="Vbias"),"Vin R:Rsig Vs"],
    "源极跟随器": [follower(),"Vout R:RL GND"],
    "单端电阻负载共源级": [cs()],
})

chapter(5, {
    "分压偏置单管电流沉": ["VDD R:R1 Vg R:R2 GND","Iout N:Vg GND"],
    "基本 NMOS 电流镜": mirror(),
    "基本 PMOS 电流镜": mirror(True),
    "互补电流镜多路偏置网络": mirror()[:1]+["VDD P:Pgate Pgate N:K GND","VDD P:Pgate Iload","Tail N:K GND"],
    "电流镜转移信号的共源放大器": [cs("P:X",out="X"),"VDD P:X Vout R:RL GND"],
    "外加栅偏置的共源共栅电流镜": mirror()[:1]+["Iout N:Vbc X N:K GND"],
    "自偏置共源共栅电流镜": ["VDD I:Iref B N:B K N:K GND","Iout N:B X N:K GND"],
    "低压宽摆幅共源共栅电流镜": ["VDD I:Iref K N:Vbc X N:K GND","Iout N:Vbc Y N:K GND"],
    "长沟道参考管级联偏置电路": ["VDD I:Ib Vbc N:Vbc:L长 GND","VDD I:Iref K N:Vbc X N:K GND","Iout N:Vbc Y N:K GND"],
    "串叠单位管级联偏置电路": ["VDD I:Ib Vbc N:Vbc A N:Vbc B N:Vbc C N:Vbc GND","Iout N:Vbc Y N:K GND","VDD I:Iref K N:Vbc X N:K GND"],
    "电阻移位式级联偏置电路": ["VDD I:Ib B R:Rshift Vbc N:B D N:D GND","K N:Vbc X N:K GND","Iout N:Vbc Y N:K GND","VDD I:Iref K"],
    "MOS 移位式级联偏置电路": ["VDD I:Ib B N:B:宽管 Vbc N:B D N:D GND","K N:Vbc X N:K GND","Iout N:Vbc Y N:K GND","VDD I:Iref K"],
    "串并联单位管比例电流镜": mirror()[:1]+["I½ N:K A N:K GND","I₂ N:K GND","I₂ N:K GND"],
    "三支路宽摆幅级联电流镜": ["VDD I:Ib Vbc N:Vbc:长沟道 GND","VDD I:Iref K N:Vbc X N:K GND","Iout N:Vbc Y N:K GND"],
    "改进型威尔逊电流镜": ["VDD I:Iref A N:A B N:K GND","Iout N:A K N:K GND"],
    "电流源负载共源级": [cs("P:K"),"VDD P:K K I:Iref GND"],
    "共模反馈控制尾源的全差分放大器": pair("P:Vbp","N:Vctl","Vo−","Vo+")+[average(),amp("Vcm","Vref","Vctl","共模误差")],
    "独立参考镜偏置的单端差分放大器": ["VDD P:K K I:Iref GND","VDD N:Vin+ T","VDD P:K Vout N:Vin− T","T N:Vbn GND"],
    "有源电流镜负载差分对（五管 OTA）": ota(),
    "对称 CMOS OTA（三电流镜型）": ["VDD I:It T P:Vin+ K1 N:K1 GND","T P:Vin− K2 N:K2 GND","VDD P:K3 K3 N:K1 GND","VDD P:K3 Vout N:K2 GND"],
    "多支路串叠偏置电流源": ["VDD I:Iref V2 N:V2 V3 N:V2:W/3L K N:V3 V5 N:K GND","Iout N:V3 V4 N:K GND"],
    "MOS 尾源偏置的电阻负载差分对": pair(tail="N:Vbn",left="Vo−",right="Vo+"),
    "恒流源负载、单侧取样的差分对": pair("P:Vbp",left="X",right="Vout"),
    "五管 OTA 加源极跟随输出级": ota(out="Xo")+[follower("Xo")],
})

chapter(6, {
    "一阶 RC 低通电路": rc_stage(),
    "带串联 RC 分流支路的并联负载": ["Vout R:Ro GND","Vout R:Rz X C:Cz GND"],
    "跨导级并联前馈电容": ["Vout G:gm·vin GND","Vin C:Cff Vout","Vout R:RL GND"],
    "缓冲隔离的多节点 RC 级联网络": ["Vin R:R1 X C:C1 GND",block("缓冲器","X","B1"),"B1 R:R2 Y C:C2 GND",block("缓冲器","Y","B2"),"B2 R:R3 Vout C:C3 GND"],
    "并联 RC 负载的级联跨导放大器": ["X G:gm₁·vin GND","X R:R1 GND","X C:C1 GND","Vout G:gm₂·vx GND","Vout R:R2 GND","Vout C:C2 GND"],
    "串联 RC 跨节点反馈放大器": ["Vin R:Ri X",block("反相增益级","X","Vout"),"Vout R:Rf F C:Cf X","X C:C1 GND","Vout C:CL GND"],
    "电容跨接反相增益级的米勒电路": [block("−Av","Vin","Vout"),"Vin C:Cm Vout"],
    "电阻负载共源级": [cs(gate="G"),"Vin R:Rsig G","G C:Cgd Vout","G C:Cgs GND"],
    "驱动电容负载的源极跟随器": [follower("G"),"Vin R:Rsig G","G C:Cgs Vout","Vout C:CL GND"],
    "共栅放大器": [cs(source="S",gate="Vbias"),"Vin R:Rsig S","S C:Cgs GND","Vout C:CL GND"],
    "共源共栅放大器": ["VDD R:RD Vout N:Vbc X N:Vin GND","Vin C:Cgd X","X C:Cx GND","Vout C:CL GND"],
    "电阻负载差分对": pair(left="Vo−",right="Vo+")+["T C:Ctail GND"],
    "共偏置电流源负载的全差分级": pair("P:K",left="Vo−",right="Vo+")+["VDD P:K K I:Iref GND","Vo− C:CL GND","Vo+ C:CL GND"],
    "有源电流镜负载单端差分级": ota()+["X C:Cx GND","Vout C:CL GND"],
    "源极跟随器加共源反馈管": [follower("G"),"Vin R:Rsig G","G N:Vout GND"],
    "跨第二级接补偿电容的两级 OTA": compensation("Xo C:Cc Vout"),
    "含端口寄生电容的 MOS 小信号模型": model(True,True),
    "二极管连接 MOS 的参数提取电路": ["VG V:扫描 GND","VG N:VG GND"],
    "栅漏独立偏置的本征增益测试电路": ["VG V:VG GND","VD V:VD GND","VD N:VG GND"],
})

chapter(8, {
    "电容比反馈的反相共源放大器": [cs(gate="Σ"),"Vin C:Ci Σ C:Cf Vout"],
    "反相运放电阻反馈网络": [amp("GND","Σ","Vout"),"Vin R:Ri Σ R:Rf Vout","Σ R:Rg GND"],
    "电阻反馈至第一级源端的两级 MOS 放大器": [cs(source="S R:RS GND",out="X"),cs(gate="X"),"Vout R:Rf S"],
    "电阻分压反馈同相运放": [amp("Vin","Vfb","Vout"),"Vout R:Rf Vfb R:Rg GND"],
    "电容分压反馈的同相 OTA": cap_ota(),
    "电容分压反馈共栅级": [cs(source="Vin",gate="Vfb")]+divider_caps(),
    "电流串联反馈跨导放大器": [amp("Vin","Vs","Vg"),"VDD R:RL Iout N:Vg Vs R:Rs GND"],
    "源极或发射极电阻退化跨导级": [cs(source="Vs R:RS GND")],
    "压控调节型共源共栅电流源": [amp("Vin","Vs","Vg"),"Iout N:Vg Vs R:Rs GND"],
    "晶体管同相电压反馈放大器": ["VDD P:Vbp X Q:Vin Ve R:Re GND","VDD P:Vbp Vout N:X GND","Vout R:Rf Ve"],
    "栅耦合管对电压放大器": ["Vin P:A A N:Vbn GND","VDD P:Vg Vout P:A B N:Vbn GND",amp("B","Vref","Vg","辅助放大")],
    "电流并联反馈电流放大器": [block("电流增益 Ai","Σ","Ia"),block("串联电流取样","Ia","Iout"),"VDD I:Iin Σ","Σ G:β·iout GND"],
    "镜像取样的 MOS 电流反馈放大器": ["VDD P:Vbp G N:Vbn Σ N:Vbt GND","VDD P:K K P:G Iout","VDD P:K Σ","Σ I:Iin GND"],
    "电压并联反馈跨阻放大器": [amp("GND","Σ","Vout"),"VDD I:Iin Σ","Vout Z:Zf Σ"],
    "电阻反馈反相跨阻放大器": [amp("GND","Σ","Vout"),"VDD I:Iin Σ","Vout R:Rf Σ"],
    "米勒电容反馈跨阻级": [block("−Av","Σ","Vout"),"VDD I:Iin Σ","Vout C:Cf Σ"],
    "电阻并联反馈的共源级加源极跟随器": [cs(gate="Σ",out="X"),follower("X"),"Vin R:Ri Σ","Vout R:Rf Σ"],
    "电容取样、共栅输入的反馈跨阻级": [cs(source="Σ N:Vfb GND",gate="Vbias"),"VDD I:Iin Σ"]+divider_caps(),
    "电容求和输入的反相差分 OTA": cap_ota(True),
    "电流镜取样器": ["Isense N:Isense GND","If N:Isense GND"],
})

chapter(9, {
    "电阻分压同相运算放大器": [amp("Vin","Vfb","Vout"),"Vout R:Rf Vfb R:Rg GND"],
    "串联 RL 反馈的同相运放": [amp("Vin","Vfb","Vout"),"Vout L:Lf X R:Rf Vfb R:Rg GND"],
    "五管单端 OTA": ota(),
    "恒流源负载全差分 OTA": pair("P:Vbp",left="Vo−",right="Vo+"),
    "五管 OTA 单位增益跟随器": ota("Vin","Vout"),
    "普通级联镜负载的单端套筒式 OTA": telescope(single=True),
    "宽摆幅级联镜负载的单端套筒式 OTA": telescope(single=True,wide=True),
    "全差分套筒式 OTA": telescope(),
    "单端套筒式 OTA 单位增益跟随器": telescope(single=True,feedback=True),
    "PMOS 输入全差分折叠式 OTA": folded(True),
    "NMOS 输入全差分折叠式 OTA": folded(),
    "镜像汇流的单端折叠式 OTA 跟随器": folded(mirror=True,feedback=True),
    "三重级联全差分 OTA": telescope(triple=True),
    "差分共源输出的全差分两级运放": differential_output(),
    "套筒式首级的高增益全差分两级 OTA": differential_output("telescope"),
    "镜像汇流输出的单端两级运放": pair("P:Vbp")+["VDD P:K K N:X GND","VDD P:K Vout N:Y GND"],
    "调节型共源共栅增益级（regulated cascode）": ["VDD I:Ib Vout N:Vctl X N:Vin GND",amp("Vref","X","Vctl","辅助放大")],
    "单管辅助放大的增益增强共源共栅级": ["VDD I:Ib Vout N:Vctl X N:Vin GND",cs("I:Ia",gate="X",out="Vctl")],
    "差分共源共栅级的独立双辅助放大器": boosted(),
    "共享差分辅助放大器的增益增强级": boosted("差分辅助放大"),
    "折叠式辅助放大器的增益增强级": boosted("折叠式差分辅助"),
    "上下支路双重增益增强 OTA": boosted(upper=True),
    "双电阻输出共模检测器": [average()],
    "源极跟随缓冲的共模检测器": [follower("Vo+",out="S1"),follower("Vo−",out="S2"),average("S1","S2")],
    "双三极区 MOS 共模检测器": ["D N:Vo+:三极区 S","D N:Vo−:三极区 S"],
    "调节输出下拉电流的折叠式 OTA 共模反馈": folded(sink_gate="Vctl")+[average(),amp("Vcm","Vref","Vctl","共模误差")],
    "调节输入尾电流的折叠式 OTA 共模反馈": folded(tail_gate="Vctl")+[average(),amp("Vcm","Vref","Vctl","共模误差")],
    "输出支路源端串三极区管的共模反馈": diff_fold_feedback("output"),
    "尾支路三极区共模反馈": diff_fold_feedback("tail"),
    "带复制参考的三极区共模反馈": diff_fold_feedback("tail",replica=True),
    "漏压匹配的复制参考共模反馈": diff_fold_feedback("tail",replica=True,matched=True),
    "电阻自偏置有源负载共模反馈": pair("P:Vcm",left="Vo−",right="Vo+")+[average()],
    "带电流偏移的低压电阻共模反馈": pair("P:Vg",left="Vo−",right="Vo+")+[average(mid="Vg"),"Vg I:Ishift GND"],
    "跨两级的有源共模反馈": differential_output(out_gate="Vctl")+[average(),amp("Vref","Vcm","Vctl","跨级共模误差")],
    "逐级独立的电阻共模反馈": differential_output(out_gate="Vcm1",second_gate="Vcm2")+[average("X","Y","Vcm1"),average(mid="Vcm2")],
    "带中点偏置电流的逐级共模反馈": differential_output(out_gate="Vcm1",second_gate="Vcm2")+[average("X","Y","Vcm1"),average(mid="Vcm2"),"Vcm2 I:Ishift GND"],
    "互补差分对轨到轨输入 OTA": ["VDD I:Ip Tp P:Vin+ P1","Tp P:Vin− P2","N1 N:Vin+ Tn I:In GND","N2 N:Vin− Tn",block("差分电流求和","P1 P2 N1 N2","Vout")],
    "电容分压反馈的五管 OTA": cap_ota(),
    "交叉控制钳位管的折叠式 OTA": folded(mirror=True,feedback=True)+["VDD N:F2 F1","VDD N:F1 F2"],
    "二极管连接钳位管的折叠式 OTA": folded(mirror=True,feedback=True)+["VDD N:VDD F1","VDD N:VDD F2"],
    "反相器型 OTA": [cs("P:Vin"),"Vout C:CL GND"],
    "电阻自偏置反相器放大器": [cs("P:G",gate="G"),"Vout R:Rf G"],
    "PMOS 源端旁路的反相器放大器": ["VDD I:Ib Sp P:Vin Vout N:Vin GND","Sp C:Cb GND"],
    "电容耦合、自偏置反相器放大器": ["VDD I:Ib Sp P:G Vout N:G GND","Sp C:Cb GND","Vin C:Ci G R:Rf Vout"],
    "镜像偏置的 A 类共源输出级": [cs("P:K"),"VDD P:K K I:Iref GND","Vout C:CL GND"],
    "输入驱动镜像支路的单端输出级": [cs("P:K"),cs("P:K",gate="Vin",out="K"),"Vout C:CL GND"],
    "交叉镜像驱动的无尾源差分输出级": ab_stage(tails=False),
    "双尾源差分 AB 类放大器": ab_stage(),
    "高压摆率两级 OTA": pair("P:Vbp")+ab_stage("X","Y"),
    "反相电阻反馈运放": [amp("GND","Σ","Vout"),"Vin R:Ri Σ R:Rf Vout"],
    "反相电容反馈五管 OTA": cap_ota(True),
    "PMOS 单管输入折叠级": folded(True,False),
    "NMOS 单管输入折叠级": folded(False,False),
    "电阻负载全差分放大器": pair(left="Vo−",right="Vo+"),
    "折叠首级、分级共模反馈的两级运放": [s.replace("N:Vbn GND","N:Vcm1 GND") for s in differential_output("folded",second_gate="Vcm2")]+[average("F1","F2","Vcm1"),average(mid="Vcm2")],
    "一阶 RC 阶跃响应电路": rc_stage(True),
})

chapter(10, {
    "电容分压反馈单级 OTA": cap_ota(),
    "单端级联 OTA 的输出电容补偿": telescope(single=True)+["Vout C:CL GND"],
    "全差分套筒式 OTA": telescope(),
    "未加补偿的全差分两级运放": differential_output("telescope")+["Vo+ C:CL GND","Vo− C:CL GND"],
    "级间节点对地电容主极点补偿": compensation("Xo C:Cc GND"),
    "级间节点对地串联 RC 补偿": compensation("Xo R:Rz F C:Cc GND"),
    "两级 OTA 的简单米勒补偿": compensation("Xo C:Cc Vout"),
    "串联调零电阻的米勒补偿": compensation("Xo R:Rz F C:Cc Vout"),
    "MOS 调零电阻米勒补偿": compensation("Xo N:Vrz:三极区 F C:Cc Vout"),
    "调零 MOS 的跟踪偏置支路": ["VDD P:K K P:Vrz Vrz I:Iref GND","VDD P:Xo Vout N:Vbn GND","Xo P:Vrz:三极区 F C:Cc Vout","Vout C:CL GND"],
    "电阻设定跨导的自偏置电流基准": ["VDD P:K G N:G GND","VDD R:Rset S P:K:宽管 K N:G GND"],
    "源极跟随器缓冲的米勒补偿": two_stage()+[follower("Vout",out="B"),"B C:Cc Xo"],
    "共栅电流缓冲米勒补偿": two_stage()+["Xo N:Vbc B I:Ibuf GND","Vout C:Cc B"],
    "利用首级共栅管的间接补偿": [block("差分跨导输入级","Vin+ Vin−","F"),"VDD P:Vbp Xo N:Vbc F I:Ib GND",cs("I:Io",gate="Xo"),"Vout C:Cc F","Vout C:CL GND"],
    "分裂输出米勒补偿": two_stage()+[cs("I:Iaux",gate="Xo",out="Vaux"),"Vaux C:Cc Xo"],
    "电流镜米勒补偿": two_stage()+["VDD I:Iref K N:K GND","Xo N:K GND","Vout C:Cc K"],
    "AB 类两级补偿运放": [block("差分跨导级","Vin+ Vin−","Is"),"Xo G:Is GND","VDD P:K K G:α·Is GND","VDD P:K Vout N:Xo GND","Xo C:Cc Vout","Vout C:CL GND"],
    "PMOS 差分首级、NMOS 共源次级的单端米勒 OTA": ["VDD P:Vbt T P:Vin+ K N:K GND","T P:Vin− Xo N:K GND",cs("P:Vbp",gate="Xo"),"Xo C:Cc Vout","Vout C:CL GND"],
    "差分 OTA 加源极跟随器的闭环缓冲器": ota("Vin","Vout","Xo")+[follower("Xo"),"Vout C:CL GND"],
    "带栅漏电容的电阻负载共源级": [cs(gate="G"),"Vin R:Rsig G","G C:Cgd Vout"],
    "NMOS 差分首级、PMOS 共源次级的米勒跟随器": ota("Vout","Vin","Xo")+["VDD P:Xo Vout N:Vbn GND","Xo C:Cc Vout","Vout C:CL GND"],
})

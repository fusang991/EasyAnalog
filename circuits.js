// The two resistor terminals define the positive direction of the current probe.
const caseBook = {
  lowpass: {
    name: '一阶 RC 低通', chapter: '第6章 · 放大器的频率响应',
    hint: '固定 R 和 C，逐步提高输入频率，观察输出的衰减和延迟。',
    defaults: [1, 1, 1, 1, 159.155], capacitorUnit: 'µF', capacitorScale: 1e-6,
    resistorNodes: ['in', 'out'], currentLabel: 'I(R) · Vin → Vout',
    net: p => ['R1 in out '+p.R, 'C1 out 0 '+p.C]
  },
  highpass: {
    name: '一阶 RC 高通', chapter: '第6章 · 放大器的频率响应',
    hint: '把输入频率从截止频率降低十倍，观察输出幅值，以及输出相对于输入的相位超前。',
    defaults: [1, 1, 1, 1, 159.155], capacitorUnit: 'µF', capacitorScale: 1e-6,
    resistorNodes: ['out', 'gnd'], currentLabel: 'I(R) · Vout → GND',
    net: p => ['C1 in out '+p.C, 'R1 out 0 '+p.R]
  },
  'common-source': {
    name: '电阻负载 NMOS 共源级', chapter: '第3章 · 单级放大器',
    hint: '在低频观察栅压上升时漏压下降。把输入峰值从 0.05 V 调到 0.5 V，观察输出失真。',
    defaults: [4.7, 1, 1.2, 0.05, 1000], capacitorUnit: 'nF', capacitorScale: 1e-9,
    resistorNodes: ['vdd', 'out'], currentLabel: 'I(RD) · VDD → 漏极',
    mos: true, resistorLabel: '漏极电阻 RD',
    net: p => ['Vdd vdd 0 '+p.supply, 'RD vdd out '+p.R, 'M1 out in 0 0 NM W=20u L=1u',
      'CL out 0 '+p.C, mosModel]
  },
  follower: {
    name: '电阻偏置 NMOS 源极跟随器', chapter: '第3章 · 单级放大器',
    hint: '输入接栅极，输出取自源极。改变栅极直流偏置，观察输出工作点与小信号增益。',
    defaults: [4.7, 1, 2.2, 0.1, 1000], capacitorUnit: 'nF', capacitorScale: 1e-9,
    resistorNodes: ['out', 'gnd'], currentLabel: 'I(RS) · 源极 → GND',
    mos: true, resistorLabel: '源极电阻 RS',
    net: p => ['Vdd vdd 0 '+p.supply, 'M1 vdd in out 0 NM W=20u L=1u', 'RS out 0 '+p.R,
      'CL out 0 '+p.C, mosModel]
  }
};
const mosModel = '.model NM NMOS (LEVEL=1 VTO=0.7 KP=100u LAMBDA=0 GAMMA=0)';

function schematic(id) {
  const path = d => '<path d="'+d+'" stroke="currentColor" stroke-width="2.4" fill="none"/>';
  const label = (x,y,s,anchor='start') => '<text x="'+x+'" y="'+y+'" text-anchor="'+anchor+'" fill="currentColor" font-size="15">'+s+'</text>';
  const probe = (x,y,node,name) => {
    const caption = node==='vdd' ? label(x,y-12,name,'middle') : label(x+10,y-8,name);
    return '<g class="probe" data-probe="'+node+'" tabindex="0" role="button" aria-label="测量 '+name+'"><circle cx="'+x+'" cy="'+y+'" r="6"/>'+caption+'</g>';
  };
  const ground = (x,y) => path('M'+x+' '+y+'v5m-12 0h24m-19 5h14m-10 5h6');
  const source = (x,y) => '<circle cx="'+x+'" cy="'+y+'" r="16" fill="none" stroke="currentColor" stroke-width="2"/>'+path('M'+(x-9)+' '+y+'q4-10 9 0t9 0');
  const resistor = (x,y) => path('M'+x+' '+y+'v5l-5 3 10 5-10 5 10 5-10 5 5 3v5');
  const capacitor = (x,y) => path('M'+x+' '+y+'v9m-13 0h26m-26 7h26m-13 0v10');
  if (!caseBook[id].mos) {
    const low = id==='lowpass';
    const series = low ? path('M161 51l5-7 7 14 7-14 7 14 7-14 7 14 5-7') : path('M177 51v-13m0 13v13m9-26v26');
    return source(70,85)+path('M70 69V51H'+(low?161:177)+'M'+(low?206:186)+' 51H300V64M70 101v28h230V'+(low?90:100))
      +series+(low?capacitor(300,64):resistor(300,64))+ground(205,129)
      +label(176,28,low?'R':'C')+label(322,88,low?'C':'R')+probe(99,51,'in','Vin')+probe(300,51,'out','Vout');
  }
  const cs = id==='common-source';
  const top = cs ? resistor(235,18)+path('M235 54v20') : path('M235 18v56');
  const bottom = cs ? path('M235 106v37') : path('M235 106v3')+resistor(235,109);
  const outputY = cs?60:107;
  return path('M235 6V18')+top+bottom+ground(235,cs?143:145)+path('M235 74h-20v32h20M208 76v28M107 90h101')
    +path('M235 '+outputY+'h92v10')+capacitor(327,outputY+10)+ground(327,outputY+36)
    +source(107,110)+path('M107 94v-4m0 36v8')+ground(107,134)
    +label(259,cs?42:140,cs?'RD':'RS')+label(347,outputY+27,'CL')+label(224,96,'M1')
    +probe(235,0,'vdd','VDD')+probe(130,90,'in','Vin')+probe(294,outputY,'out','Vout');
}

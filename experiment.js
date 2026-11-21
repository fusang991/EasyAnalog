// The stimulus monitor and selected readout both use ngspice voltage vectors.
// Their numerical units are carried separately, including for current probes.
function experimentDeck(id,model,probe,values,dc,amp,f,lo=model.lo,hi=model.hi) {
 const duration=3/f,step=1/(200*f);
 const stimulus=model.wave==='step'
  ? 'PULSE('+dc+' '+(dc+amp)+' '+(step*4)+' '+(step/10)+' '+(step/10)+' '+(duration*2)+' '+(duration*4)+')'
  : 'SIN('+dc+' '+amp+' '+f+')';
 const source='Vstim in 0 DC '+dc+' AC '+amp+' '+stimulus;
 const params=model.params.map(p=>'.param '+p.key+'='+values[p.key]);
 return {title:'EasyAnalog '+id,source,elements:[...params,...model.lines,probe.element],
  dc,amp,f,lo,hi,duration,tran:'.tran '+step+' '+duration+' 0 '+step,
  device:model.device,noAC:!model.ac,inputLabel:model.source,outputLabel:probe.label,inputUnit:model.unit,outputUnit:probe.unit};
}

function field(spec,form){
 const label=document.createElement('label'),input=document.createElement('input');
 label.className='field';label.textContent=spec.label+(spec.unit?'（'+spec.unit+'）':'');
 input.name=spec.key;input.type='number';input.required=true;input.step='any';
 if(spec.min!==undefined||spec.positive)input.min=spec.min??1e-9;
 if(spec.max)input.max=spec.max;
 input.value=spec.value;
 label.append(input);form.append(label);
}

function prepareExperiment(model){
 $('lab-fields').replaceChildren();$('lab-extra').replaceChildren();
 const primary=[
  {key:'dc',label:model.source+' 偏置',unit:model.unit,value:model.dc},
  {key:'amp',label:'输入幅度',unit:model.unit,value:model.amp,positive:true},
  {key:'f',label:'输入频率',unit:'Hz',value:model.f,positive:true,min:0.001,max:1e9}
 ];
 for(const item of primary)field(item,$('lab-fields'));
 // Keep the stimulus and representative component values in the first row.
 const params=[...model.params].sort((a,b)=>parameterRank(a)-parameterRank(b));
 params.forEach((item,i)=>field(item,i<3?$('lab-fields'):$('lab-extra')));
 if(model.ac){
  field({key:'lo',label:'扫频起点',unit:'Hz',value:model.lo,positive:true},$('lab-extra'));
  field({key:'hi',label:'扫频终点',unit:'Hz',value:model.hi,positive:true},$('lab-extra'));
 }
 $('more').hidden=params.length<=3&&!model.ac;$('more').open=false;
 const selector=$('probe');selector.replaceChildren();
 const voltages=document.createElement('optgroup'),currents=document.createElement('optgroup');
 voltages.label='节点电压';currents.label='支路电流';
 for(const p of model.probes){
  const group=p.unit==='V'?voltages:currents;
  group.append(new Option(p.label.replace(':load',' · 端口电流'),p.label));
 }
 selector.append(voltages,currents);selector.value=model.output;
 $('freq-tab').disabled=!model.ac;
 if(!model.ac)selectResultTab($('time-tab'));
 const obj=$('atlas-circuit');
 obj.onload=()=>{
  if(active?.model!==model||!obj.contentDocument)return;
  const known=new Set(model.probes.map(p=>p.label));
  for(const text of obj.contentDocument.querySelectorAll('text.net')){
   const name=text.textContent;if(!known.has(name))continue;
   text.style.cursor='pointer';text.setAttribute('role','button');text.setAttribute('tabindex','0');
   text.setAttribute('aria-label','测量 '+name);
   text.onclick=()=>{selector.value=name;update()};
   text.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();text.onclick()}};
  }
 };
 obj.data='diagrams/'+model.id+'.svg';
 $('modelNote').hidden=false;
 $('modelNote').textContent=['元件数值与偏置为教学示例。',model.ac?'频率响应在当前直流工作点做小信号线性化。':'',...model.notes].join(' ');
}

function parameterRank(p){
 if(['kΩ','pF','µH','µA','mS','Hz','V/V'].includes(p.unit))return 0;
 if(p.label==='VDD')return 1;
 return 2;
}

function readExperiment(){
 const form=$('lab-params'),m=active.model;
 if(!m||!form.checkValidity())return null;
 const value=key=>form.elements.namedItem(key).valueAsNumber;
 const probe=m.probes.find(p=>p.label===$('probe').value);
 if(m.ac&&value('lo')>=value('hi'))return null;
 return experimentDeck(m.id,m,probe,Object.fromEntries(m.params.map(p=>[p.key,value(p.key)])),value('dc'),value('amp'),value('f'),m.ac?value('lo'):m.lo,m.ac?value('hi'):m.hi);
}

const experimentCatalog=new Map();
let selectionRevision=0;
function toggleLab(on){
 $('params').hidden=on;$('lab-params').hidden=!on;
 document.querySelector('svg.circuit').toggleAttribute('hidden',on);$('atlas-circuit').hidden=!on;
 $('engine').disabled=on;
 $('freq-tab').disabled=false;
 $('lab-link').href=on?'atlas.html#'+$('case').value:'atlas.html';
}
async function openExperiment(id,selection){
 const e=experimentCatalog.get(id);
 active={catalog:true};result=null;settings=null;
 clearTimeout(timer);++revision;if(busy)stopWorker();
 $('status').textContent='正在加载电路…';$('net').textContent='';$('retry').hidden=true;
 $('lab-fields').replaceChildren();$('lab-extra').replaceChildren();$('more').hidden=true;
 $('probe').replaceChildren();$('atlas-circuit').removeAttribute('data');
 $('cutoff').hidden=true;$('engine').value='spice';$('modelNote').hidden=true;
 document.title=e.名字+' · EasyAnalog';document.querySelector('h1').textContent=e.名字;
 document.querySelector('.chapter').textContent=e.章节+' · '+e.标题;$('caseHint').textContent=e.电路简单介绍;
 $('freqCaption').textContent='扫频范围';$('fc').textContent='—';draw();
 try{
  if(!e.model){
   const response=await fetch('experiments/'+id+'.json');
   if(!response.ok)throw Error('无法读取电路模型');
   e.model={...await response.json(),id};
  }
  if(selection!==selectionRevision)return;
  active.model=e.model;
  prepareExperiment(e.model);$('timeSlider').value=100;update();
 }catch(err){
  if(selection!==selectionRevision)return;
  $('status').textContent='电路加载失败：'+err.message;$('retry').hidden=false;
 }
}

function waveLabels(p){
 const a=p.inputLabel||'Vin', b=(p.outputLabel||'Vout').replace(':load','');
 const u=p.inputUnit||'V',v=p.outputUnit||'V';
 $('wave-in').textContent='┄ '+a+' ('+u+')';
 $('wave-out').textContent='━ '+b+' ('+v+')';
 $('wave-note').textContent=active.model?.wave==='step'?'阶跃响应':'前 3 个输入周期';
 $('transfer-label').textContent=b+' / '+a;
 return {a,b,u,v};
}
function gainUnit(p){
 if(!p.outputUnit||p.outputUnit===p.inputUnit)return ['dB',0];
 return p.inputUnit==='µA'?['dBΩ',120]:['dBS',-120];
}

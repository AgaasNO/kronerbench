<script lang="ts">
 import * as Plot from '@observablehq/plot';
 import {onMount} from 'svelte';
 export let data: Record<string,any>[]=[];
 export let kind='bar';
 export let label='Silent error rate';
 export let percent=true;
 export let xLabel='Coverage';
 export let xPercent=false;
 let target: HTMLDivElement;
 let width=700;
 let mounted=false;
 const palette=['#b43737','#247a8c','#8f70b7','#aa7028','#627d4d','#4b72a6','#cf8266'];
 function tickLabel(value:any){
  let text=String(value);
  for(const [id,name] of Object.entries({'deepseek/deepseek-v4.1-flash':'DeepSeek Flash','openai/gpt-5.6-luna':'GPT Luna','z-ai/glm-5.3-flash':'GLM Flash','tencent/hy3':'Tencent Hy3','typesafe/jev-1.13':'Jev 1.13'}))text=text.replace(id,name);
  return text.replace('fake/','').replace(' · ','\n');
 }
 function draw(){
  if(!target || !mounted || !data.length)return;
  const common:any={width:Math.max(280,width),height:Math.max(260,Math.min(860,data.length*38+70)),marginLeft:['forest','bar','stack'].includes(kind)?120:65,marginBottom:60,style:{background:'transparent',color:'currentColor',fontFamily:'inherit',fontSize:'12px'},color:{range:palette,legend:kind==='line'||kind==='scatter'||kind==='stack'},x:{label,grid:true,ticks:width<500?3:8,tickFormat:percent?'.1%':undefined},y:{label:null,tickFormat:tickLabel}};
  let marks:any[]=[];
  if(kind==='bar'){marks=[Plot.barX(data,{x:'x',y:'y',fill:percent?'#b43737':'#247a8c',sort:{y:'-x'},tip:true}),Plot.ruleX([0])];}
  if(kind==='forest'){marks=[Plot.ruleX([0],{strokeDasharray:'3,3'}),Plot.ruleY(data,{x1:'lo',x2:'hi',y:'y',stroke:'#247a8c',strokeWidth:2}),Plot.dot(data,{x:'x',y:'y',fill:'#b43737',r:4,tip:true})];}
  if(kind==='heat'){common.x={label:null,tickRotate:-30};common.y={label:null};common.marginLeft=130;common.color={scheme:'YlOrRd',legend:true,label:'SER',type:'linear',domain:[0,Math.max(.01,...data.map(d=>d.value))]};marks=[Plot.cell(data,{x:'x',y:'y',fill:'value',inset:1,tip:true}),Plot.text(data,{x:'x',y:'y',text:d=>`${(d.value*100).toFixed(1)}%`,fill:'#172d46'})];}
  if(kind==='line'){common.height=400;common.x={label:xLabel,grid:true,ticks:width<500?3:6,tickFormat:xPercent?'.0%':undefined};common.y={label,grid:true,ticks:6,tickFormat:'.1%'};marks=[Plot.line(data,{x:'x',y:'y',stroke:'group',tip:true}),Plot.dot(data,{x:'x',y:'y',stroke:'group',r:2})];}
  if(kind==='scatter'){common.x={label:'USD / 1,000 fields',type:'log',grid:true};common.y={label:'Silent error rate',type:'symlog',grid:true,tickFormat:'.1%'};marks=[Plot.dot(data,{x:'x',y:'y',fill:'group',symbol:'group',r:6,tip:true,title:d=>d.label})];}
  if(kind==='stack'){common.x={label,grid:true,ticks:width<500?3:8};const groups=[...new Set(data.map(d=>d.group))];if(groups.some(g=>g==='correct'||g==='loud_flag'))common.color={domain:groups,range:groups.map(g=>g==='silent_error'?'#b43737':g.startsWith('loud')?'#627386':'#247a8c'),legend:true};marks=[Plot.barX(data,{x:'x',y:'y',fill:'group',tip:true})];}
  if(kind==='reliability'){common.x={label:'Mean confidence',domain:[0,1]};common.y={label:'Observed accuracy',domain:[0,1]};marks=[Plot.line([{x:0,y:0},{x:1,y:1}],{x:'x',y:'y',strokeDasharray:'4,4'}),Plot.dot(data,{x:'x',y:'y',r:6,fill:'#247a8c',tip:true})];}
  target.replaceChildren(Plot.plot({...common,marks}));
 }
 onMount(()=>{mounted=true;const observer=new ResizeObserver(e=>{width=e[0].contentRect.width;draw()});observer.observe(target);draw();return()=>observer.disconnect()});
 $: if(mounted&&data&&kind)draw();
</script>
<div class={data.length?"chart":"unavailable"} bind:this={target} aria-label={label}>{#if !data.length}No applicable observations in this run. This panel is n/a, not a zero error rate.{/if}</div>

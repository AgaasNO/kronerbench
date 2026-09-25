<script lang="ts">
 import {onMount} from 'svelte';
 import Chart from './Chart.svelte';
 type Row=Record<string,any>;
 const data:Row=(window as any).KRONERBENCH;
 const summary=data.summary, rows:Row[]=data.fields, cases:Row[]=data.cases;
 const pages=['Verdict','Leaderboard','Strict vs lenient','Where it breaks','Error anatomy','Retry lab','Parser lab','Cost vs reliability','Jev and confidence','Case explorer','Methods'];
 const slug=(s:string)=>s.toLowerCase().replaceAll(' ','-');
 let page=decodeURIComponent(location.hash.slice(1))||'verdict';
 let dark=false, search='',suite='',selected='',metric='ser';
 const fmt=(n:number|null,d=2)=>n==null?'n/a':(n*100).toFixed(d)+'%';
 const overall:Row[]=summary.cells.filter((c:Row)=>c.suite==='all');
 const conditionNames=[...new Set(overall.map(c=>c.condition))] as string[];
 const modelNames=[...new Set(overall.map(c=>c.model))] as string[];
 const conditionCopy:Record<string,{name:string,detail:string}>={
  strict:{name:'Strict',detail:'Rewrite the source amount in a fixed format, such as 1234,56.'},
  strict_constrained:{name:'Constrained strict',detail:'Use the strict format, with a tool schema that also restricts the output.'},
  lenient:{name:'Lenient',detail:'Copy a normal source format, such as 1.234,56. Code parses it only when the value is unambiguous.'},
  verbatim:{name:'Verbatim',detail:'Copy the exact amount from the source; code checks that it really appears there.'},
  json_number:{name:'JSON number',detail:'Write a JSON number with a decimal point, such as 1234.56.'},
  minor_units:{name:'Minor units',detail:'Write an integer number of øre or cents.'},
  select:{name:'Select',detail:'Choose from amounts extracted from the document, or flag the field for review.'}
 };
 const metricCopy:Record<string,string>={
  ser:'Silent error rate: the share of fields where a wrong value was recorded. Lower is safer.',
  accuracy:'Accuracy: the share of fields recorded correctly or correctly flagged for review. Higher is better.',
  loud_rate:'Loud failure rate: the share left unresolved or flagged when a definite value was available. Lower is better.',
  usd_per_1000:'Estimated USD spent per 1,000 scored fields. Lower is cheaper.',
  p95_ms:'95th percentile trial time in milliseconds. Lower is faster.'
 };
 const example=overall.filter(c=>c.condition==='strict'&&c.n&&c.silent>0&&c.loud_rate>0).sort((a,b)=>b.accuracy-a.accuracy)[0];
 $: rankedModels=[...modelNames].sort((a,b)=>{
  const best=(model:string)=>{
   const values=overall.filter(c=>c.model===model&&c[metric]!=null).map(c=>c[metric] as number);
   return metric==='accuracy'?Math.max(...values):Math.min(...values);
  };
  const difference=metric==='accuracy'?best(b)-best(a):best(a)-best(b);
  return difference||a.localeCompare(b);
 });
 const counts=(group:Row[])=>{const scored=group.filter(r=>r.outcome!=='api_error');return scored.length?scored.filter(r=>r.outcome==='silent_error').length/scored.length:0};
 const aggregate=(key:string)=>{const map=new Map<string,Row[]>();for(const r of rows){const k=String(r[key]);map.set(k,[...(map.get(k)||[]),r])}return [...map].map(([y,g])=>({y,x:counts(g)}))};
 const forest=summary.comparisons.filter((c:Row)=>c.a==='lenient'&&c.b==='strict'&&c.n).map((c:Row)=>({y:c.model,x:-c.difference,lo:-c.ci[1],hi:-c.ci[0]}));
 if(summary.pooled.difference!=null)forest.push({y:'Pooled · case bootstrap',x:summary.pooled.difference,lo:summary.pooled.ci[0],hi:summary.pooled.ci[1]});
 const heat=summary.cells.filter((c:Row)=>c.suite!=='all'&&c.ser!=null).reduce((acc:Row[],c:Row)=>{let p=acc.find(p=>p.x===c.condition&&p.y===c.suite);if(!p){p={x:c.condition,y:c.suite,n:0,silent:0,value:0};acc.push(p)}p.n+=c.n;p.silent+=c.silent;p.value=p.silent/p.n;return acc},[]);
 const byDigits=rows.reduce((acc:Row[],r:Row)=>{if(r.outcome==='api_error')return acc;let p=acc.find(p=>p.x===r.digits&&p.group===r.condition);if(!p){p={x:r.digits,group:r.condition,n:0,k:0,y:0};acc.push(p)}p.n++;p.k+=r.outcome==='silent_error'?1:0;p.y=p.k/p.n;return acc},[]).sort((a,b)=>a.x-b.x);
 const anatomy=rows.filter(r=>r.error_class).reduce((acc:Row[],r:Row)=>{let p=acc.find(p=>p.y===r.condition&&p.group===r.error_class);if(!p){p={y:r.condition,group:r.error_class,x:0};acc.push(p)}p.x++;return acc},[]);
 const retries=overall.filter(c=>c.retry_eligible).map(c=>({y:c.model+' · '+c.condition,x:c.retry_drift}));
 const calibration=summary.calibration;
 const risk=calibration.curve.filter((p:Row)=>p.ser!=null).map((p:Row)=>({x:p.coverage,y:p.ser,group:'Jev evaluation'}));
 const reliability=calibration.reliability.map((b:Row)=>({x:b.confidence,y:b.accuracy}));
 const costs=overall.filter(c=>c.ser!=null&&c.usd_per_1000>0).map(c=>({x:c.usd_per_1000,y:c.ser,group:c.condition,label:c.model+' · '+c.condition}));
 $: visibleCases=cases.filter(c=>(!suite||c.suite===suite)&&(`${c.id} ${c.source} ${c.rationale}`).toLowerCase().includes(search.toLowerCase()));
 $: active=cases.find(c=>c.id===selected);
 $: answers=rows.filter(r=>r.case_id===selected);
 $: title=pages.find(p=>slug(p)===page)||'Verdict';
 function navigate(name:string){page=slug(name);location.hash=page;window.scrollTo(0,0)}
 function toggle(){dark=!dark;document.documentElement.dataset.theme=dark?'dark':'light'}
 onMount(()=>{const listener=()=>page=decodeURIComponent(location.hash.slice(1))||'verdict';window.addEventListener('hashchange',listener);return()=>window.removeEventListener('hashchange',listener)});
</script>
<svelte:head><title>{title} · KronerBench</title></svelte:head>
<div class="shell">
 <aside><a class="brand" href="#verdict" onclick={()=>navigate('Verdict')}><span class="brandmark">kr</span>KronerBench<span class="version">01</span></a><p class="strap">A ledger of model mistakes.</p><nav aria-label="Report pages">{#each pages as name,i}<a href={'#'+slug(name)} class:active={page===slug(name)} onclick={()=>navigate(name)}><span>{String(i+1).padStart(2,'0')}</span>{name}</a>{/each}</nav><div class="aside-bottom"><button onclick={toggle} aria-label="Toggle dark mode">{dark?'Light paper':'Dark paper'}</button><a href="https://github.com/AgaasNO/kronerbench">Source & method ↗</a><small>Amounts stay exact.<br>Uncertainty stays visible.</small></div></aside>
 <main><header><span>THE MONEY FORMAT EXPERIMENT</span><span>{data.manifest.created_utc.slice(0,10)} · {summary.trial_count.toLocaleString()} trials</span></header>
 {#if summary.fixture}<div class="fixture">FIXTURE RUN · Deterministic fake models. These numbers test the pipeline and are not evidence about real models.</div>{/if}
 {#if summary.pilot&&!summary.fixture}<div class="fixture">BUDGET PILOT · Four LLMs and Jev, with a USD 5 total spending limit. Cases have not received the independent two-model audit. Findings are provisional.</div>{/if}
 <div class="heading"><p class="eyebrow">{String(pages.indexOf(title)+1).padStart(2,'0')} / {title}</p><h1>{title==='Verdict'?'When the amount is wrong, the ledger remembers.':title}</h1></div>
 {#if page==='verdict'}
  <p class="lead">{summary.findings[0]?.text||'No paired comparison is available for this run.'}</p>
  <div class="cards">{#each summary.conditions as c}<article class="stat"><span>{c.condition}</span><strong class="silent">{c.ser==null?'n/a':Math.round(c.ser*10000).toLocaleString()}</strong><small>silent errors / 10,000 fields</small><p>95% CI {fmt(c.ser_ci[0])} to {fmt(c.ser_ci[1])}<br>{c.n.toLocaleString()} scored fields · {fmt(c.loud_rate)} loud</p></article>{/each}</div>
  <section><div class="section-title"><h2>Wrong values committed</h2><span>Lower is better</span></div><Chart data={summary.conditions.filter((c:Row)=>c.ser!=null).map((c:Row)=>({y:c.condition,x:c.ser}))}/></section>
  <div class="two"><section><h2>What the run found</h2>{#each summary.findings as finding}<a class="finding" href={'#'+finding.page} onclick={()=>{page=finding.page}}>{finding.text}<span>Explore ↗</span></a>{/each}</section><section><h2>Hypotheses, including null results</h2>{#each summary.hypotheses as h}<div class="hypothesis"><strong>{h.id}</strong><span>{h.status}</span><small>{h.detail}</small></div>{/each}</section></div>
 {:else if page==='leaderboard'}
  <p class="lead">{metricCopy[metric]}</p>
  <label>Metric <select bind:value={metric}><option value="ser">Silent error rate</option><option value="accuracy">Accuracy</option><option value="loud_rate">Loud rate</option><option value="usd_per_1000">USD / 1,000</option><option value="p95_ms">p95 latency, ms</option></select></label>
  <section class="reading-guide"><h2>What the columns mean</h2><p>These examples show money amounts. Rates and dates have their own rules on the Methods page.</p><div class="condition-grid">{#each conditionNames as condition}<article><h3>{conditionCopy[condition]?.name||condition}</h3><p>{conditionCopy[condition]?.detail||'See Methods for this condition.'}</p></article>{/each}</div><p class="note">For each field, a model can get it right, record a wrong value silently, or fail to record a recoverable value. Accuracy, silent error rate and loud failure rate add to 100%.</p>{#if example}<p class="reading-example">Example: {example.model} with Strict handled {Math.round(example.accuracy*example.n)} of {example.n} fields correctly. It recorded {example.silent} wrong values and left {example.n-Math.round(example.accuracy*example.n)-example.silent} unresolved.</p>{/if}</section>
  <p class="note">Each cell shows its number of scored fields. Select skips cases with amounts written only as words; Jev uses a separate evaluation sample. Compare models within the same column, and check both silent errors and loud failures.</p>
  <p class="table-swipe-hint">Swipe the table sideways to see every condition.</p>
  <section class="table-wrap"><table class="leaderboard-table"><thead><tr><th>Model</th>{#each conditionNames as c}<th>{conditionCopy[c]?.name||c}</th>{/each}</tr></thead><tbody>{#each rankedModels as model}<tr><th>{model}</th>{#each conditionNames as condition}{@const c=overall.find(c=>c.model===model&&c.condition===condition)}<td class:silent={metric==='ser'&&c?.ser>0} title={c?`95% SER CI ${fmt(c.ser_ci[0])} to ${fmt(c.ser_ci[1])}; n=${c.n}`:'n/a: not applicable or unsupported'}>{#if c}{metric.includes('usd')||metric.includes('ms')?c[metric]?.toFixed(2):fmt(c[metric])}<small>{c.n} fields</small>{:else}n/a{/if}</td>{/each}</tr>{/each}</tbody></table></section>
 {:else if page==='strict-vs-lenient'}
  <p class="lead">{summary.findings.find((f:Row)=>f.id==='paired')?.text}</p><section><h2>Paired silent error difference</h2><p>Left favors strict. Right favors lenient. Each row uses the same cases, fields and repeats.</p><Chart kind="forest" data={forest} label="SER strict − lenient"/></section><p class="note">{summary.power_note}</p><section><h2>All condition estimates</h2><Chart kind="forest" data={overall.filter(c=>c.ser!=null).map(c=>({y:c.model+' · '+c.condition,x:c.ser,lo:c.ser_ci[0],hi:c.ser_ci[1]}))}/></section>
 {:else if page==='where-it-breaks'}
  <p class="lead">{summary.findings.find((f:Row)=>f.id==='hardest')?.text}</p><section><h2>Suite × condition</h2><Chart kind="heat" data={heat}/></section><section><h2>Silent error rate by digit count</h2><p>Descriptive slice of money, rate and date fields. Length effects are exploratory.</p><Chart kind="line" data={byDigits} xLabel="Digits in expected value"/></section><div class="two">{#each ['sep_style','currency','lang'] as key}<section><h2>{key.replace('_',' ')}</h2><Chart data={aggregate(key)}/></section>{/each}</div>
 {:else if page==='error-anatomy'}
  <p class="lead">{Object.entries(summary.error_classes).sort((a:any,b:any)=>b[1]-a[1])[0]?.[0]||'No class'} is the most frequent silent-error class in this run.</p><section><Chart kind="stack" data={anatomy} label="Silent errors" percent={false}/></section><h2>Committed mistakes, with their sources</h2><div class="gallery">{#each rows.filter(r=>r.outcome==='silent_error').slice(0,24) as row}{@const c=cases.find(c=>c.id===row.case_id)}<article><span class="eyebrow">{row.error_class} · {row.condition}</span><h3>{row.model}</h3><pre>{c?.source}</pre><dl><dt>Expected</dt><dd>{row.expected}</dd><dt>Committed</dt><dd class="silent">{row.committed}</dd></dl><button onclick={()=>{selected=row.case_id;navigate('Case explorer')}}>Inspect attempts ↗</button></article>{/each}</div>
 {:else if page==='retry-lab'}
  <p class="lead">{summary.findings.find((f:Row)=>f.id==='retry')?.text}</p><div class="cards">{#each summary.conditions as c}<article class="stat"><span>{c.condition}</span><strong>{c.retry_rescue} / <span class="silent">{c.retry_corruption}</span></strong><small>rescued / corrupted fields</small></article>{/each}</div><section><h2>Digit drift after rejection</h2><Chart data={retries} label="Share of accepted retries with changed digits"/></section><section><h2>Attempt transitions</h2><Chart kind="stack" percent={false} data={rows.filter(r=>r.attempts>1).reduce((a:Row[],r:Row)=>{const y=r.condition+' · '+(r.first_attempt_valid?'accepted first':'rejected first'),group=r.outcome;let p=a.find(p=>p.y===y&&p.group===group);if(!p){p={y,group,x:0};a.push(p)}p.x++;return a},[])} label="Fields after retry"/></section>
 {:else if page==='parser-lab'}
  <p class="lead">Identical first-attempt strings isolate what the parser changes. Float conversion changed {summary.float_changed} stored amounts.</p><section><h2>One output, three parsers</h2><Chart data={summary.offline_parsers.filter((p:Row)=>p.ser!=null).map((p:Row)=>({y:p.parser,x:p.ser}))}/><table><thead><tr><th>Parser</th><th>Scored</th><th>Silent</th><th>Loud</th></tr></thead><tbody>{#each summary.offline_parsers as p}<tr><td>{p.parser}</td><td>{p.n}</td><td class="silent">{p.silent}</td><td>{p.loud}</td></tr>{/each}</tbody></table></section><p class="note">The naive parser strips dots and spaces and changes commas to dots. Currency tokens cause loud rejections. No extra model calls are involved.</p>
 {:else if page==='cost-vs-reliability'}
  <p class="lead">This run cost USD {summary.total_cost_usd.toFixed(4)}. A lower observed SER may trade away coverage through more flags.</p><section><h2>Cost of a committed mistake</h2><Chart kind="scatter" data={costs} label="Cost versus silent error rate"/></section><section><h2>Latency by model and condition</h2><Chart data={overall.map(c=>({y:c.model+' · '+c.condition,x:c.p95_ms}))} label="p95 latency, milliseconds" percent={false}/></section>
 {:else if page==='jev-and-confidence'}
  <p class="lead">Threshold selection uses {calibration.calibration_n} calibration fields; evaluation uses {calibration.evaluation_n} separate fields.</p><p class="note">{calibration.policy} Chosen threshold: {calibration.threshold.toFixed(2)}. ECE: {calibration.ece==null?'n/a':calibration.ece.toFixed(3)}. Confidence concentration is not a guarantee of correctness. Jev headline rates use only evaluation cases at this threshold. The explorer preserves raw attempts alongside the recalibrated outcomes.</p><div class="two"><section><h2>Risk versus coverage</h2><Chart kind="line" data={risk} xLabel="Committed field coverage" xPercent={true}/></section><section><h2>Reliability on held-out cases</h2><Chart kind="reliability" data={reliability}/></section></div>
 {:else if page==='case-explorer'}
  <p class="lead">Read the source, the expected value and every model attempt. Nothing is inferred from the screenshot.</p><div class="filters"><label>Search <input bind:value={search} placeholder="Case, source or rationale"/></label><label>Suite <select bind:value={suite}><option value="">All suites</option>{#each [...new Set(cases.map(c=>c.suite))] as s}<option>{s}</option>{/each}</select></label></div>
  <div class="explorer"><div class="case-list">{#each visibleCases as c}<button class:chosen={c.id===selected} onclick={()=>selected=c.id}><strong>{c.id}</strong><small>{c.rationale}</small></button>{/each}</div><section>{#if active}<h2>{active.id}</h2><pre class="source">{active.source}</pre><p>{active.instruction}</p><p class="note">{active.rationale}</p><pre>{JSON.stringify(active.fields,null,2)}</pre><div class="table-wrap"><table><thead><tr><th>Model / condition</th><th>Expected</th><th>Committed</th><th>Outcome</th></tr></thead><tbody>{#each answers as r}<tr><td>{r.model}<br>{r.condition} · {r.field}</td><td>{r.expected}</td><td class:silent={r.outcome==='silent_error'}>{r.committed??'—'}</td><td>{r.outcome}</td></tr>{/each}</tbody></table></div>{#each data.trials.filter((t:Row)=>t.case_id===selected) as trial}<details><summary>{trial.model} · {trial.condition} · {trial.turns} turns</summary><pre>{JSON.stringify(trial.attempts,null,2)}</pre>{#each trial.request_keys as key}<details><summary>Full request and response</summary><pre>{JSON.stringify(data.transcripts[key],null,2)}</pre></details>{/each}</details>{/each}{:else}<div class="unavailable">Choose a case to inspect the document and full transcript.</div>{/if}</section></div>
 {:else}
  <p class="lead">Silent errors are wrong committed values. Rejected values are loud failures; provider failures are excluded and counted separately.</p><section><h2>Experimental design</h2><p>Cases, seeds, model settings and reasoning effort are held constant across conditions. Conditions run back to back within each case and model. Rates use percentage points; monetary truth uses integer minor units.</p><p>{summary.power_note}</p><p>Paired tests use exact McNemar with Holm correction within each model. The pooled interval resamples whole cases 2,000 times. Jev thresholds use a case-hash calibration split. Unsupported cells and extractor skips are n/a.</p><p>Excluded trial reasons: {JSON.stringify(summary.skips)}. Scored trial fraction: {fmt(summary.scored_trial_fraction)}.</p></section><section><h2>Prompts, verbatim</h2>{#each Object.entries(data.prompts) as [name,text]}<details><summary>{name}</summary><pre>{text}</pre></details>{/each}</section><section><h2>Frozen analysis plan</h2><pre>{data.analysis_plan}</pre></section><section><h2>Run manifest</h2><pre>{JSON.stringify(data.manifest,null,2)}</pre></section><section><h2>Prior work</h2><a href="https://arxiv.org/abs/2402.14903">Singh & Strouse: Tokenization counts</a><br><a href="https://arxiv.org/abs/2408.02442">Tam et al.: Let Me Speak Freely?</a><br><a href="https://arxiv.org/abs/2405.21047">Park et al.: Grammar-Aligned Decoding</a><br><a href="https://openrouter.ai/docs/guides/community/jev-tutorial">OpenRouter Decisions tutorial</a></section>
 {/if}
 <footer><span>KronerBench · Code MIT · Cases and results CC BY 4.0</span><span>{data.manifest.run_id} · {data.manifest.git_commit.slice(0,8)}</span></footer>
 </main>
</div>

import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const root=path.resolve(import.meta.dirname,'..');
const target=process.env.KB_REPORT||path.join(root,'reports/latest/index.html');
const pages=['verdict','leaderboard','strict-vs-lenient','where-it-breaks','error-anatomy','retry-lab','parser-lab','cost-vs-reliability','jev-and-confidence','case-explorer','methods'];
const browser=await chromium.launch({headless:true});
const checks=[];
let runId;
await fs.mkdir(path.join(root,'docs/img'),{recursive:true});
try{
 for(const width of [1440,390])for(const theme of ['light','dark']){
  const page=await browser.newPage({viewport:{width,height:1000},deviceScaleFactor:1});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  await page.goto(target.startsWith('http')?target:pathToFileURL(target).href);
  runId=await page.evaluate(()=>window.KRONERBENCH.manifest.run_id);
  if(theme==='dark')await page.getByRole('button',{name:'Toggle dark mode'}).click();
  for(const name of pages){
   await page.evaluate(name=>location.hash=name,name);
   await page.waitForFunction(name=>location.hash==='#'+name,name);
   await page.waitForTimeout(200);
   if(name==='case-explorer')await page.locator('.case-list button').first().click();
   const empty=await page.locator('.chart').evaluateAll(nodes=>nodes.filter(n=>!n.querySelector('svg')).length);
   const heading=await page.locator('h1').textContent();
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
   if(empty||errors.length||!heading||overflow)throw new Error(JSON.stringify({name,width,theme,empty,errors,heading,overflow}));
   const file=`${name}-${theme}-${width}.png`;
   await page.screenshot({path:path.join(root,'docs/img',file),fullPage:true});
   checks.push({page:name,width,theme,file,passed:true});
   if(name==='leaderboard'){
    await page.getByLabel('Metric').selectOption('accuracy');
    await page.waitForTimeout(100);
    const accuracyLead=await page.locator('.lead').textContent();
    const ranking=await page.locator('.leaderboard-table tbody tr th').allTextContents();
    const expected=await page.evaluate(()=>{
     const cells=window.KRONERBENCH.summary.cells.filter(c=>c.suite==='all');
     return [...new Set(cells.map(c=>c.model))].sort((a,b)=>{
      const best=model=>Math.max(...cells.filter(c=>c.model===model).map(c=>c.accuracy));
      return best(b)-best(a)||a.localeCompare(b);
     });
    });
    if(!accuracyLead.includes('Higher is better')||JSON.stringify(ranking)!==JSON.stringify(expected)||errors.length)throw new Error(JSON.stringify({name,width,theme,accuracyLead,ranking,expected,errors}));
    const accuracyFile=`leaderboard-accuracy-${theme}-${width}.png`;
    await page.screenshot({path:path.join(root,'docs/img',accuracyFile),fullPage:true});
    checks.push({page:'leaderboard-accuracy',width,theme,file:accuracyFile,passed:true});
    await page.getByLabel('Metric').selectOption('ser');
   }
  }
  await page.close();
 }
 await fs.writeFile(path.join(root,'docs/img/qa.json'),JSON.stringify({passed:true,run_id:runId,report:target.startsWith('http')?target:path.relative(root,target),checks},null,2)+'\n');
 console.log(`Passed ${checks.length} views: no console errors, horizontal overflow or empty charts.`);
}finally{await browser.close()}

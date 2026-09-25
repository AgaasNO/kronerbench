import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
export default defineConfig({plugins:[svelte()],build:{lib:{entry:'src/main.ts',name:'KronerBench',formats:['iife'],fileName:()=> 'app.js'},cssCodeSplit:false,outDir:'../src/kronerbench/report/static',emptyOutDir:true}});

// 極簡 DOM/canvas stub：只要遊戲初始化會丟例外就會被抓到
const noop = () => {};
const ctx = new Proxy({}, { get: (t,k) => {
  if (k === 'canvas') return {width:300,height:600};
  if (k === 'measureText') return () => ({width:10});
  if (k === 'createLinearGradient') return () => ({addColorStop:noop});
  return typeof k === 'string' ? noop : undefined; }, set: () => true });
const mkEl = (tag) => new Proxy({
  tagName: tag, style:{}, width:300, height:600, children:[],
  getContext: () => ctx, addEventListener: noop, appendChild: noop,
  setAttribute: noop, focus: noop, classList:{add:noop,remove:noop,toggle:noop,contains:()=>false},
}, { get:(t,k)=> k in t ? t[k] : (k==='textContent'||k==='innerHTML'||k==='innerText' ? '' : noop),
     set:(t,k,v)=>{t[k]=v; return true;} });
global.document = {
  getElementById: () => mkEl('div'), querySelector: () => mkEl('div'),
  querySelectorAll: () => [], createElement: mkEl, addEventListener: noop,
  body: mkEl('body'), documentElement: mkEl('html'), readyState: 'complete',
};
global.window = new Proxy({
  addEventListener: noop, requestAnimationFrame: () => 1, cancelAnimationFrame: noop,
  setInterval: () => 1, setTimeout: () => 1, clearInterval: noop, clearTimeout: noop,
  innerWidth: 1280, innerHeight: 800, document: global.document, localStorage:{getItem:()=>null,setItem:noop},
}, { get:(t,k)=> k in t ? t[k] : (global[k] !== undefined ? global[k] : noop), set:(t,k,v)=>{t[k]=v;return true;} });
global.requestAnimationFrame = () => 1;
global.cancelAnimationFrame = noop;
global.alert = noop;
global.localStorage = {getItem:()=>null,setItem:noop};
global.navigator = {userAgent:'node'};

const fs = require('fs');
const file = process.argv[2];
try {
  new Function(fs.readFileSync(file,'utf8'))();
  console.log("LOAD_OK");
} catch (e) {
  console.log("LOAD_FAIL " + e.constructor.name + ": " + String(e.message).slice(0,90));
}

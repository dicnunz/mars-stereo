// Dependency-free interaction regression: execute the shipped script against DOM-shaped controls.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const dir=process.argv[2]||require('node:path').resolve(__dirname,'../web');
class Element {constructor(){this.value='0';this.children=[];this.handlers={};this.disabled=false;this.hidden=false;}append(x){this.children.push(x)}replaceChildren(...x){this.children=x}setAttribute(k,v){this[k]=v}addEventListener(k,v){this.handlers[k]=v}getContext(){return {clearRect(){},createImageData(){return {data:new Uint8ClampedArray(48*48*4)}},putImageData(){}}}}
const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id)};
const ctx={window:{},document:{getElementById:get,createElement:()=>new Element()}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(dir+'/data.js','utf8'),ctx);vm.runInContext(fs.readFileSync(dir+'/app.js','utf8'),ctx);
const d=ctx.window.DATA;assert.equal(get('choice').children.length,d.items.length);assert.equal(get('previous').disabled,true);
for(let i=0;i<d.items.length;i++){get('position').value=String(i);get('position').handlers.input();assert.equal(get('caption').textContent,d.items[i].label);assert.equal(Number(get('choice').value),i);if(d.kind==='gallery')assert.equal(get('visual').src,d.items[i].asset);if(d.kind==='apollo')for(const k of ['P','V','N','R1','R2','R3'])assert.equal(get(k).textContent,d.items[i].state[k]||' ');if(d.kind==='eht')assert.equal(get('visual').hidden,!d.items[i].pixels)}
assert.equal(get('next').disabled,true);get('choice').value='0';get('choice').handlers.change();assert.equal(get('previous').disabled,true);get('next').handlers.click();assert.equal(Number(get('choice').value),1);get('previous').handlers.click();assert.equal(Number(get('choice').value),0);console.log(dir+': all selections, slider/select sync, endpoint states and previous/next passed');

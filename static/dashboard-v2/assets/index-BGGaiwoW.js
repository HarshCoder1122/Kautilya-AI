const __vite__mapDeps=(i,m=__vite__mapDeps,d=(m.f||(m.f=["assets/LoginView-C35571ZD.js","assets/sparkles-D4UCrXYo.js","assets/OverviewView-D2DWiSy5.js","assets/agents-Di2AYxl0.js","assets/globe-Cqlt-DiI.js","assets/trending-up-zMnaNkaY.js","assets/AgentsView-az14nKQK.js","assets/trash-2-C2gUrs0H.js","assets/AgentsView-EDBr8QkN.css","assets/AgentDetailView-GaC-XYQe.js","assets/history-DS_zT8Ld.js","assets/CallsView-cWFjsZi3.js"])))=>i.map(i=>d[i]);
(function(){const t=document.createElement("link").relList;if(t&&t.supports&&t.supports("modulepreload"))return;for(const s of document.querySelectorAll('link[rel="modulepreload"]'))r(s);new MutationObserver(s=>{for(const i of s)if(i.type==="childList")for(const o of i.addedNodes)o.tagName==="LINK"&&o.rel==="modulepreload"&&r(o)}).observe(document,{childList:!0,subtree:!0});function n(s){const i={};return s.integrity&&(i.integrity=s.integrity),s.referrerPolicy&&(i.referrerPolicy=s.referrerPolicy),s.crossOrigin==="use-credentials"?i.credentials="include":s.crossOrigin==="anonymous"?i.credentials="omit":i.credentials="same-origin",i}function r(s){if(s.ep)return;s.ep=!0;const i=n(s);fetch(s.href,i)}})();/**
* @vue/shared v3.5.33
* (c) 2018-present Yuxi (Evan) You and Vue contributors
* @license MIT
**/function wi(e){const t=Object.create(null);for(const n of e.split(","))t[n]=1;return n=>n in t}const de={},Sn=[],ft=()=>{},Ga=()=>!1,ss=e=>e.charCodeAt(0)===111&&e.charCodeAt(1)===110&&(e.charCodeAt(2)>122||e.charCodeAt(2)<97),is=e=>e.startsWith("onUpdate:"),Ee=Object.assign,Si=(e,t)=>{const n=e.indexOf(t);n>-1&&e.splice(n,1)},Eu=Object.prototype.hasOwnProperty,ie=(e,t)=>Eu.call(e,t),U=Array.isArray,Tn=e=>vr(e)==="[object Map]",Bn=e=>vr(e)==="[object Set]",oo=e=>vr(e)==="[object Date]",z=e=>typeof e=="function",ge=e=>typeof e=="string",je=e=>typeof e=="symbol",oe=e=>e!==null&&typeof e=="object",za=e=>(oe(e)||z(e))&&z(e.then)&&z(e.catch),qa=Object.prototype.toString,vr=e=>qa.call(e),Iu=e=>vr(e).slice(8,-1),Ja=e=>vr(e)==="[object Object]",os=e=>ge(e)&&e!=="NaN"&&e[0]!=="-"&&""+parseInt(e,10)===e,Jn=wi(",key,ref,ref_for,ref_key,onVnodeBeforeMount,onVnodeMounted,onVnodeBeforeUpdate,onVnodeUpdated,onVnodeBeforeUnmount,onVnodeUnmounted"),as=e=>{const t=Object.create(null);return n=>t[n]||(t[n]=e(n))},wu=/-\w/g,De=as(e=>e.replace(wu,t=>t.slice(1).toUpperCase())),Su=/\B([A-Z])/g,mn=as(e=>e.replace(Su,"-$1").toLowerCase()),cs=as(e=>e.charAt(0).toUpperCase()+e.slice(1)),Cs=as(e=>e?`on${cs(e)}`:""),lt=(e,t)=>!Object.is(e,t),xr=(e,...t)=>{for(let n=0;n<e.length;n++)e[n](...t)},Ya=(e,t,n,r=!1)=>{Object.defineProperty(e,t,{configurable:!0,enumerable:!1,writable:r,value:n})},ls=e=>{const t=parseFloat(e);return isNaN(t)?e:t},Tu=e=>{const t=ge(e)?Number(e):NaN;return isNaN(t)?e:t};let ao;const us=()=>ao||(ao=typeof globalThis<"u"?globalThis:typeof self<"u"?self:typeof window<"u"?window:typeof global<"u"?global:{});function fs(e){if(U(e)){const t={};for(let n=0;n<e.length;n++){const r=e[n],s=ge(r)?Pu(r):fs(r);if(s)for(const i in s)t[i]=s[i]}return t}else if(ge(e)||oe(e))return e}const Au=/;(?![^(]*\))/g,Cu=/:([^]+)/,Ru=/\/\*[^]*?\*\//g;function Pu(e){const t={};return e.replace(Ru,"").split(Au).forEach(n=>{if(n){const r=n.split(Cu);r.length>1&&(t[r[0].trim()]=r[1].trim())}}),t}function ln(e){let t="";if(ge(e))t=e;else if(U(e))for(let n=0;n<e.length;n++){const r=ln(e[n]);r&&(t+=r+" ")}else if(oe(e))for(const n in e)e[n]&&(t+=n+" ");return t.trim()}const Ou="itemscope,allowfullscreen,formnovalidate,ismap,nomodule,novalidate,readonly",ku=wi(Ou);function Xa(e){return!!e||e===""}function Nu(e,t){if(e.length!==t.length)return!1;let n=!0;for(let r=0;n&&r<e.length;r++)n=Jt(e[r],t[r]);return n}function Jt(e,t){if(e===t)return!0;let n=oo(e),r=oo(t);if(n||r)return n&&r?e.getTime()===t.getTime():!1;if(n=je(e),r=je(t),n||r)return e===t;if(n=U(e),r=U(t),n||r)return n&&r?Nu(e,t):!1;if(n=oe(e),r=oe(t),n||r){if(!n||!r)return!1;const s=Object.keys(e).length,i=Object.keys(t).length;if(s!==i)return!1;for(const o in e){const a=e.hasOwnProperty(o),c=t.hasOwnProperty(o);if(a&&!c||!a&&c||!Jt(e[o],t[o]))return!1}}return String(e)===String(t)}function Ti(e,t){return e.findIndex(n=>Jt(n,t))}const Qa=e=>!!(e&&e.__v_isRef===!0),Ge=e=>ge(e)?e:e==null?"":U(e)||oe(e)&&(e.toString===qa||!z(e.toString))?Qa(e)?Ge(e.value):JSON.stringify(e,Za,2):String(e),Za=(e,t)=>Qa(t)?Za(e,t.value):Tn(t)?{[`Map(${t.size})`]:[...t.entries()].reduce((n,[r,s],i)=>(n[Rs(r,i)+" =>"]=s,n),{})}:Bn(t)?{[`Set(${t.size})`]:[...t.values()].map(n=>Rs(n))}:je(t)?Rs(t):oe(t)&&!U(t)&&!Ja(t)?String(t):t,Rs=(e,t="")=>{var n;return je(e)?`Symbol(${(n=e.description)!=null?n:t})`:e};/**
* @vue/reactivity v3.5.33
* (c) 2018-present Yuxi (Evan) You and Vue contributors
* @license MIT
**/let Ie;class ec{constructor(t=!1){this.detached=t,this._active=!0,this._on=0,this.effects=[],this.cleanups=[],this._isPaused=!1,this.__v_skip=!0,this.parent=Ie,!t&&Ie&&(this.index=(Ie.scopes||(Ie.scopes=[])).push(this)-1)}get active(){return this._active}pause(){if(this._active){this._isPaused=!0;let t,n;if(this.scopes)for(t=0,n=this.scopes.length;t<n;t++)this.scopes[t].pause();for(t=0,n=this.effects.length;t<n;t++)this.effects[t].pause()}}resume(){if(this._active&&this._isPaused){this._isPaused=!1;let t,n;if(this.scopes)for(t=0,n=this.scopes.length;t<n;t++)this.scopes[t].resume();for(t=0,n=this.effects.length;t<n;t++)this.effects[t].resume()}}run(t){if(this._active){const n=Ie;try{return Ie=this,t()}finally{Ie=n}}}on(){++this._on===1&&(this.prevScope=Ie,Ie=this)}off(){if(this._on>0&&--this._on===0){if(Ie===this)Ie=this.prevScope;else{let t=Ie;for(;t;){if(t.prevScope===this){t.prevScope=this.prevScope;break}t=t.prevScope}}this.prevScope=void 0}}stop(t){if(this._active){this._active=!1;let n,r;for(n=0,r=this.effects.length;n<r;n++)this.effects[n].stop();for(this.effects.length=0,n=0,r=this.cleanups.length;n<r;n++)this.cleanups[n]();if(this.cleanups.length=0,this.scopes){for(n=0,r=this.scopes.length;n<r;n++)this.scopes[n].stop(!0);this.scopes.length=0}if(!this.detached&&this.parent&&!t){const s=this.parent.scopes.pop();s&&s!==this&&(this.parent.scopes[this.index]=s,s.index=this.index)}this.parent=void 0}}}function tc(e){return new ec(e)}function nc(){return Ie}function xu(e,t=!1){Ie&&Ie.cleanups.push(e)}let pe;const Ps=new WeakSet;class rc{constructor(t){this.fn=t,this.deps=void 0,this.depsTail=void 0,this.flags=5,this.next=void 0,this.cleanup=void 0,this.scheduler=void 0,Ie&&Ie.active&&Ie.effects.push(this)}pause(){this.flags|=64}resume(){this.flags&64&&(this.flags&=-65,Ps.has(this)&&(Ps.delete(this),this.trigger()))}notify(){this.flags&2&&!(this.flags&32)||this.flags&8||ic(this)}run(){if(!(this.flags&1))return this.fn();this.flags|=2,co(this),oc(this);const t=pe,n=Je;pe=this,Je=!0;try{return this.fn()}finally{ac(this),pe=t,Je=n,this.flags&=-3}}stop(){if(this.flags&1){for(let t=this.deps;t;t=t.nextDep)Ri(t);this.deps=this.depsTail=void 0,co(this),this.onStop&&this.onStop(),this.flags&=-2}}trigger(){this.flags&64?Ps.add(this):this.scheduler?this.scheduler():this.runIfDirty()}runIfDirty(){Qs(this)&&this.run()}get dirty(){return Qs(this)}}let sc=0,Yn,Xn;function ic(e,t=!1){if(e.flags|=8,t){e.next=Xn,Xn=e;return}e.next=Yn,Yn=e}function Ai(){sc++}function Ci(){if(--sc>0)return;if(Xn){let t=Xn;for(Xn=void 0;t;){const n=t.next;t.next=void 0,t.flags&=-9,t=n}}let e;for(;Yn;){let t=Yn;for(Yn=void 0;t;){const n=t.next;if(t.next=void 0,t.flags&=-9,t.flags&1)try{t.trigger()}catch(r){e||(e=r)}t=n}}if(e)throw e}function oc(e){for(let t=e.deps;t;t=t.nextDep)t.version=-1,t.prevActiveLink=t.dep.activeLink,t.dep.activeLink=t}function ac(e){let t,n=e.depsTail,r=n;for(;r;){const s=r.prevDep;r.version===-1?(r===n&&(n=s),Ri(r),Du(r)):t=r,r.dep.activeLink=r.prevActiveLink,r.prevActiveLink=void 0,r=s}e.deps=t,e.depsTail=n}function Qs(e){for(let t=e.deps;t;t=t.nextDep)if(t.dep.version!==t.version||t.dep.computed&&(cc(t.dep.computed)||t.dep.version!==t.version))return!0;return!!e._dirty}function cc(e){if(e.flags&4&&!(e.flags&16)||(e.flags&=-17,e.globalVersion===ir)||(e.globalVersion=ir,!e.isSSR&&e.flags&128&&(!e.deps&&!e._dirty||!Qs(e))))return;e.flags|=2;const t=e.dep,n=pe,r=Je;pe=e,Je=!0;try{oc(e);const s=e.fn(e._value);(t.version===0||lt(s,e._value))&&(e.flags|=128,e._value=s,t.version++)}catch(s){throw t.version++,s}finally{pe=n,Je=r,ac(e),e.flags&=-3}}function Ri(e,t=!1){const{dep:n,prevSub:r,nextSub:s}=e;if(r&&(r.nextSub=s,e.prevSub=void 0),s&&(s.prevSub=r,e.nextSub=void 0),n.subs===e&&(n.subs=r,!r&&n.computed)){n.computed.flags&=-5;for(let i=n.computed.deps;i;i=i.nextDep)Ri(i,!0)}!t&&!--n.sc&&n.map&&n.map.delete(n.key)}function Du(e){const{prevDep:t,nextDep:n}=e;t&&(t.nextDep=n,e.prevDep=void 0),n&&(n.prevDep=t,e.nextDep=void 0)}let Je=!0;const lc=[];function Pt(){lc.push(Je),Je=!1}function Ot(){const e=lc.pop();Je=e===void 0?!0:e}function co(e){const{cleanup:t}=e;if(e.cleanup=void 0,t){const n=pe;pe=void 0;try{t()}finally{pe=n}}}let ir=0;class Mu{constructor(t,n){this.sub=t,this.dep=n,this.version=n.version,this.nextDep=this.prevDep=this.nextSub=this.prevSub=this.prevActiveLink=void 0}}class Pi{constructor(t){this.computed=t,this.version=0,this.activeLink=void 0,this.subs=void 0,this.map=void 0,this.key=void 0,this.sc=0,this.__v_skip=!0}track(t){if(!pe||!Je||pe===this.computed)return;let n=this.activeLink;if(n===void 0||n.sub!==pe)n=this.activeLink=new Mu(pe,this),pe.deps?(n.prevDep=pe.depsTail,pe.depsTail.nextDep=n,pe.depsTail=n):pe.deps=pe.depsTail=n,uc(n);else if(n.version===-1&&(n.version=this.version,n.nextDep)){const r=n.nextDep;r.prevDep=n.prevDep,n.prevDep&&(n.prevDep.nextDep=r),n.prevDep=pe.depsTail,n.nextDep=void 0,pe.depsTail.nextDep=n,pe.depsTail=n,pe.deps===n&&(pe.deps=r)}return n}trigger(t){this.version++,ir++,this.notify(t)}notify(t){Ai();try{for(let n=this.subs;n;n=n.prevSub)n.sub.notify()&&n.sub.dep.notify()}finally{Ci()}}}function uc(e){if(e.dep.sc++,e.sub.flags&4){const t=e.dep.computed;if(t&&!e.dep.subs){t.flags|=20;for(let r=t.deps;r;r=r.nextDep)uc(r)}const n=e.dep.subs;n!==e&&(e.prevSub=n,n&&(n.nextSub=e)),e.dep.subs=e}}const jr=new WeakMap,dn=Symbol(""),Zs=Symbol(""),or=Symbol("");function Ce(e,t,n){if(Je&&pe){let r=jr.get(e);r||jr.set(e,r=new Map);let s=r.get(n);s||(r.set(n,s=new Pi),s.map=r,s.key=n),s.track()}}function bt(e,t,n,r,s,i){const o=jr.get(e);if(!o){ir++;return}const a=c=>{c&&c.trigger()};if(Ai(),t==="clear")o.forEach(a);else{const c=U(e),l=c&&os(n);if(c&&n==="length"){const u=Number(r);o.forEach((f,p)=>{(p==="length"||p===or||!je(p)&&p>=u)&&a(f)})}else switch((n!==void 0||o.has(void 0))&&a(o.get(n)),l&&a(o.get(or)),t){case"add":c?l&&a(o.get("length")):(a(o.get(dn)),Tn(e)&&a(o.get(Zs)));break;case"delete":c||(a(o.get(dn)),Tn(e)&&a(o.get(Zs)));break;case"set":Tn(e)&&a(o.get(dn));break}}Ci()}function Lu(e,t){const n=jr.get(e);return n&&n.get(t)}function yn(e){const t=ee(e);return t===e?t:(Ce(t,"iterate",or),He(e)?t:t.map(Xe))}function ds(e){return Ce(e=ee(e),"iterate",or),e}function at(e,t){return kt(e)?Nn(Rt(e)?Xe(t):t):Xe(t)}const Uu={__proto__:null,[Symbol.iterator](){return Os(this,Symbol.iterator,e=>at(this,e))},concat(...e){return yn(this).concat(...e.map(t=>U(t)?yn(t):t))},entries(){return Os(this,"entries",e=>(e[1]=at(this,e[1]),e))},every(e,t){return gt(this,"every",e,t,void 0,arguments)},filter(e,t){return gt(this,"filter",e,t,n=>n.map(r=>at(this,r)),arguments)},find(e,t){return gt(this,"find",e,t,n=>at(this,n),arguments)},findIndex(e,t){return gt(this,"findIndex",e,t,void 0,arguments)},findLast(e,t){return gt(this,"findLast",e,t,n=>at(this,n),arguments)},findLastIndex(e,t){return gt(this,"findLastIndex",e,t,void 0,arguments)},forEach(e,t){return gt(this,"forEach",e,t,void 0,arguments)},includes(...e){return ks(this,"includes",e)},indexOf(...e){return ks(this,"indexOf",e)},join(e){return yn(this).join(e)},lastIndexOf(...e){return ks(this,"lastIndexOf",e)},map(e,t){return gt(this,"map",e,t,void 0,arguments)},pop(){return jn(this,"pop")},push(...e){return jn(this,"push",e)},reduce(e,...t){return lo(this,"reduce",e,t)},reduceRight(e,...t){return lo(this,"reduceRight",e,t)},shift(){return jn(this,"shift")},some(e,t){return gt(this,"some",e,t,void 0,arguments)},splice(...e){return jn(this,"splice",e)},toReversed(){return yn(this).toReversed()},toSorted(e){return yn(this).toSorted(e)},toSpliced(...e){return yn(this).toSpliced(...e)},unshift(...e){return jn(this,"unshift",e)},values(){return Os(this,"values",e=>at(this,e))}};function Os(e,t,n){const r=ds(e),s=r[t]();return r!==e&&!He(e)&&(s._next=s.next,s.next=()=>{const i=s._next();return i.done||(i.value=n(i.value)),i}),s}const Fu=Array.prototype;function gt(e,t,n,r,s,i){const o=ds(e),a=o!==e&&!He(e),c=o[t];if(c!==Fu[t]){const f=c.apply(e,i);return a?Xe(f):f}let l=n;o!==e&&(a?l=function(f,p){return n.call(this,at(e,f),p,e)}:n.length>2&&(l=function(f,p){return n.call(this,f,p,e)}));const u=c.call(o,l,r);return a&&s?s(u):u}function lo(e,t,n,r){const s=ds(e),i=s!==e&&!He(e);let o=n,a=!1;s!==e&&(i?(a=r.length===0,o=function(l,u,f){return a&&(a=!1,l=at(e,l)),n.call(this,l,at(e,u),f,e)}):n.length>3&&(o=function(l,u,f){return n.call(this,l,u,f,e)}));const c=s[t](o,...r);return a?at(e,c):c}function ks(e,t,n){const r=ee(e);Ce(r,"iterate",or);const s=r[t](...n);return(s===-1||s===!1)&&hs(n[0])?(n[0]=ee(n[0]),r[t](...n)):s}function jn(e,t,n=[]){Pt(),Ai();const r=ee(e)[t].apply(e,n);return Ci(),Ot(),r}const Bu=wi("__proto__,__v_isRef,__isVue"),fc=new Set(Object.getOwnPropertyNames(Symbol).filter(e=>e!=="arguments"&&e!=="caller").map(e=>Symbol[e]).filter(je));function Vu(e){je(e)||(e=String(e));const t=ee(this);return Ce(t,"has",e),t.hasOwnProperty(e)}class dc{constructor(t=!1,n=!1){this._isReadonly=t,this._isShallow=n}get(t,n,r){if(n==="__v_skip")return t.__v_skip;const s=this._isReadonly,i=this._isShallow;if(n==="__v_isReactive")return!s;if(n==="__v_isReadonly")return s;if(n==="__v_isShallow")return i;if(n==="__v_raw")return r===(s?i?Yu:mc:i?gc:pc).get(t)||Object.getPrototypeOf(t)===Object.getPrototypeOf(r)?t:void 0;const o=U(t);if(!s){let c;if(o&&(c=Uu[n]))return c;if(n==="hasOwnProperty")return Vu}const a=Reflect.get(t,n,_e(t)?t:r);if((je(n)?fc.has(n):Bu(n))||(s||Ce(t,"get",n),i))return a;if(_e(a)){const c=o&&os(n)?a:a.value;return s&&oe(c)?ti(c):c}return oe(a)?s?ti(a):yr(a):a}}class hc extends dc{constructor(t=!1){super(!1,t)}set(t,n,r,s){let i=t[n];const o=U(t)&&os(n);if(!this._isShallow){const l=kt(i);if(!He(r)&&!kt(r)&&(i=ee(i),r=ee(r)),!o&&_e(i)&&!_e(r))return l||(i.value=r),!0}const a=o?Number(n)<t.length:ie(t,n),c=Reflect.set(t,n,r,_e(t)?t:s);return t===ee(s)&&(a?lt(r,i)&&bt(t,"set",n,r):bt(t,"add",n,r)),c}deleteProperty(t,n){const r=ie(t,n);t[n];const s=Reflect.deleteProperty(t,n);return s&&r&&bt(t,"delete",n,void 0),s}has(t,n){const r=Reflect.has(t,n);return(!je(n)||!fc.has(n))&&Ce(t,"has",n),r}ownKeys(t){return Ce(t,"iterate",U(t)?"length":dn),Reflect.ownKeys(t)}}class Hu extends dc{constructor(t=!1){super(!0,t)}set(t,n){return!0}deleteProperty(t,n){return!0}}const ju=new hc,$u=new Hu,Wu=new hc(!0);const ei=e=>e,Rr=e=>Reflect.getPrototypeOf(e);function Ku(e,t,n){return function(...r){const s=this.__v_raw,i=ee(s),o=Tn(i),a=e==="entries"||e===Symbol.iterator&&o,c=e==="keys"&&o,l=s[e](...r),u=n?ei:t?Nn:Xe;return!t&&Ce(i,"iterate",c?Zs:dn),Ee(Object.create(l),{next(){const{value:f,done:p}=l.next();return p?{value:f,done:p}:{value:a?[u(f[0]),u(f[1])]:u(f),done:p}}})}}function Pr(e){return function(...t){return e==="delete"?!1:e==="clear"?void 0:this}}function Gu(e,t){const n={get(s){const i=this.__v_raw,o=ee(i),a=ee(s);e||(lt(s,a)&&Ce(o,"get",s),Ce(o,"get",a));const{has:c}=Rr(o),l=t?ei:e?Nn:Xe;if(c.call(o,s))return l(i.get(s));if(c.call(o,a))return l(i.get(a));i!==o&&i.get(s)},get size(){const s=this.__v_raw;return!e&&Ce(ee(s),"iterate",dn),s.size},has(s){const i=this.__v_raw,o=ee(i),a=ee(s);return e||(lt(s,a)&&Ce(o,"has",s),Ce(o,"has",a)),s===a?i.has(s):i.has(s)||i.has(a)},forEach(s,i){const o=this,a=o.__v_raw,c=ee(a),l=t?ei:e?Nn:Xe;return!e&&Ce(c,"iterate",dn),a.forEach((u,f)=>s.call(i,l(u),l(f),o))}};return Ee(n,e?{add:Pr("add"),set:Pr("set"),delete:Pr("delete"),clear:Pr("clear")}:{add(s){const i=ee(this),o=Rr(i),a=ee(s),c=!t&&!He(s)&&!kt(s)?a:s;return o.has.call(i,c)||lt(s,c)&&o.has.call(i,s)||lt(a,c)&&o.has.call(i,a)||(i.add(c),bt(i,"add",c,c)),this},set(s,i){!t&&!He(i)&&!kt(i)&&(i=ee(i));const o=ee(this),{has:a,get:c}=Rr(o);let l=a.call(o,s);l||(s=ee(s),l=a.call(o,s));const u=c.call(o,s);return o.set(s,i),l?lt(i,u)&&bt(o,"set",s,i):bt(o,"add",s,i),this},delete(s){const i=ee(this),{has:o,get:a}=Rr(i);let c=o.call(i,s);c||(s=ee(s),c=o.call(i,s)),a&&a.call(i,s);const l=i.delete(s);return c&&bt(i,"delete",s,void 0),l},clear(){const s=ee(this),i=s.size!==0,o=s.clear();return i&&bt(s,"clear",void 0,void 0),o}}),["keys","values","entries",Symbol.iterator].forEach(s=>{n[s]=Ku(s,e,t)}),n}function Oi(e,t){const n=Gu(e,t);return(r,s,i)=>s==="__v_isReactive"?!e:s==="__v_isReadonly"?e:s==="__v_raw"?r:Reflect.get(ie(n,s)&&s in r?n:r,s,i)}const zu={get:Oi(!1,!1)},qu={get:Oi(!1,!0)},Ju={get:Oi(!0,!1)};const pc=new WeakMap,gc=new WeakMap,mc=new WeakMap,Yu=new WeakMap;function Xu(e){switch(e){case"Object":case"Array":return 1;case"Map":case"Set":case"WeakMap":case"WeakSet":return 2;default:return 0}}function Qu(e){return e.__v_skip||!Object.isExtensible(e)?0:Xu(Iu(e))}function yr(e){return kt(e)?e:ki(e,!1,ju,zu,pc)}function _c(e){return ki(e,!1,Wu,qu,gc)}function ti(e){return ki(e,!0,$u,Ju,mc)}function ki(e,t,n,r,s){if(!oe(e)||e.__v_raw&&!(t&&e.__v_isReactive))return e;const i=Qu(e);if(i===0)return e;const o=s.get(e);if(o)return o;const a=new Proxy(e,i===2?r:n);return s.set(e,a),a}function Rt(e){return kt(e)?Rt(e.__v_raw):!!(e&&e.__v_isReactive)}function kt(e){return!!(e&&e.__v_isReadonly)}function He(e){return!!(e&&e.__v_isShallow)}function hs(e){return e?!!e.__v_raw:!1}function ee(e){const t=e&&e.__v_raw;return t?ee(t):e}function Ni(e){return!ie(e,"__v_skip")&&Object.isExtensible(e)&&Ya(e,"__v_skip",!0),e}const Xe=e=>oe(e)?yr(e):e,Nn=e=>oe(e)?ti(e):e;function _e(e){return e?e.__v_isRef===!0:!1}function $r(e){return vc(e,!1)}function Zu(e){return vc(e,!0)}function vc(e,t){return _e(e)?e:new ef(e,t)}class ef{constructor(t,n){this.dep=new Pi,this.__v_isRef=!0,this.__v_isShallow=!1,this._rawValue=n?t:ee(t),this._value=n?t:Xe(t),this.__v_isShallow=n}get value(){return this.dep.track(),this._value}set value(t){const n=this._rawValue,r=this.__v_isShallow||He(t)||kt(t);t=r?t:ee(t),lt(t,n)&&(this._rawValue=t,this._value=r?t:Xe(t),this.dep.trigger())}}function Y(e){return _e(e)?e.value:e}const tf={get:(e,t,n)=>t==="__v_raw"?e:Y(Reflect.get(e,t,n)),set:(e,t,n,r)=>{const s=e[t];return _e(s)&&!_e(n)?(s.value=n,!0):Reflect.set(e,t,n,r)}};function yc(e){return Rt(e)?e:new Proxy(e,tf)}function nf(e){const t=U(e)?new Array(e.length):{};for(const n in e)t[n]=sf(e,n);return t}class rf{constructor(t,n,r){this._object=t,this._defaultValue=r,this.__v_isRef=!0,this._value=void 0,this._key=je(n)?n:String(n),this._raw=ee(t);let s=!0,i=t;if(!U(t)||je(this._key)||!os(this._key))do s=!hs(i)||He(i);while(s&&(i=i.__v_raw));this._shallow=s}get value(){let t=this._object[this._key];return this._shallow&&(t=Y(t)),this._value=t===void 0?this._defaultValue:t}set value(t){if(this._shallow&&_e(this._raw[this._key])){const n=this._object[this._key];if(_e(n)){n.value=t;return}}this._object[this._key]=t}get dep(){return Lu(this._raw,this._key)}}function sf(e,t,n){return new rf(e,t,n)}class of{constructor(t,n,r){this.fn=t,this.setter=n,this._value=void 0,this.dep=new Pi(this),this.__v_isRef=!0,this.deps=void 0,this.depsTail=void 0,this.flags=16,this.globalVersion=ir-1,this.next=void 0,this.effect=this,this.__v_isReadonly=!n,this.isSSR=r}notify(){if(this.flags|=16,!(this.flags&8)&&pe!==this)return ic(this,!0),!0}get value(){const t=this.dep.track();return cc(this),t&&(t.version=this.dep.version),this._value}set value(t){this.setter&&this.setter(t)}}function af(e,t,n=!1){let r,s;return z(e)?r=e:(r=e.get,s=e.set),new of(r,s,n)}const Or={},Wr=new WeakMap;let on;function cf(e,t=!1,n=on){if(n){let r=Wr.get(n);r||Wr.set(n,r=[]),r.push(e)}}function lf(e,t,n=de){const{immediate:r,deep:s,once:i,scheduler:o,augmentJob:a,call:c}=n,l=N=>s?N:He(N)||s===!1||s===0?Et(N,1):Et(N);let u,f,p,g,I=!1,w=!1;if(_e(e)?(f=()=>e.value,I=He(e)):Rt(e)?(f=()=>l(e),I=!0):U(e)?(w=!0,I=e.some(N=>Rt(N)||He(N)),f=()=>e.map(N=>{if(_e(N))return N.value;if(Rt(N))return l(N);if(z(N))return c?c(N,2):N()})):z(e)?t?f=c?()=>c(e,2):e:f=()=>{if(p){Pt();try{p()}finally{Ot()}}const N=on;on=u;try{return c?c(e,3,[g]):e(g)}finally{on=N}}:f=ft,t&&s){const N=f,H=s===!0?1/0:s;f=()=>Et(N(),H)}const L=nc(),M=()=>{u.stop(),L&&L.active&&Si(L.effects,u)};if(i&&t){const N=t;t=(...H)=>{N(...H),M()}}let A=w?new Array(e.length).fill(Or):Or;const x=N=>{if(!(!(u.flags&1)||!u.dirty&&!N))if(t){const H=u.run();if(s||I||(w?H.some((te,J)=>lt(te,A[J])):lt(H,A))){p&&p();const te=on;on=u;try{const J=[H,A===Or?void 0:w&&A[0]===Or?[]:A,g];A=H,c?c(t,3,J):t(...J)}finally{on=te}}}else u.run()};return a&&a(x),u=new rc(f),u.scheduler=o?()=>o(x,!1):x,g=N=>cf(N,!1,u),p=u.onStop=()=>{const N=Wr.get(u);if(N){if(c)c(N,4);else for(const H of N)H();Wr.delete(u)}},t?r?x(!0):A=u.run():o?o(x.bind(null,!0),!0):u.run(),M.pause=u.pause.bind(u),M.resume=u.resume.bind(u),M.stop=M,M}function Et(e,t=1/0,n){if(t<=0||!oe(e)||e.__v_skip||(n=n||new Map,(n.get(e)||0)>=t))return e;if(n.set(e,t),t--,_e(e))Et(e.value,t,n);else if(U(e))for(let r=0;r<e.length;r++)Et(e[r],t,n);else if(Bn(e)||Tn(e))e.forEach(r=>{Et(r,t,n)});else if(Ja(e)){for(const r in e)Et(e[r],t,n);for(const r of Object.getOwnPropertySymbols(e))Object.prototype.propertyIsEnumerable.call(e,r)&&Et(e[r],t,n)}return e}/**
* @vue/runtime-core v3.5.33
* (c) 2018-present Yuxi (Evan) You and Vue contributors
* @license MIT
**/function br(e,t,n,r){try{return r?e(...r):e()}catch(s){ps(s,t,n)}}function Qe(e,t,n,r){if(z(e)){const s=br(e,t,n,r);return s&&za(s)&&s.catch(i=>{ps(i,t,n)}),s}if(U(e)){const s=[];for(let i=0;i<e.length;i++)s.push(Qe(e[i],t,n,r));return s}}function ps(e,t,n,r=!0){const s=t?t.vnode:null,{errorHandler:i,throwUnhandledErrorInProduction:o}=t&&t.appContext.config||de;if(t){let a=t.parent;const c=t.proxy,l=`https://vuejs.org/error-reference/#runtime-${n}`;for(;a;){const u=a.ec;if(u){for(let f=0;f<u.length;f++)if(u[f](e,c,l)===!1)return}a=a.parent}if(i){Pt(),br(i,null,10,[e,c,l]),Ot();return}}uf(e,n,s,r,o)}function uf(e,t,n,r=!0,s=!1){if(s)throw e;console.error(e)}const xe=[];let it=-1;const An=[];let Ht=null,En=0;const bc=Promise.resolve();let Kr=null;function gs(e){const t=Kr||bc;return e?t.then(this?e.bind(this):e):t}function ff(e){let t=it+1,n=xe.length;for(;t<n;){const r=t+n>>>1,s=xe[r],i=ar(s);i<e||i===e&&s.flags&2?t=r+1:n=r}return t}function xi(e){if(!(e.flags&1)){const t=ar(e),n=xe[xe.length-1];!n||!(e.flags&2)&&t>=ar(n)?xe.push(e):xe.splice(ff(t),0,e),e.flags|=1,Ec()}}function Ec(){Kr||(Kr=bc.then(wc))}function df(e){U(e)?An.push(...e):Ht&&e.id===-1?Ht.splice(En+1,0,e):e.flags&1||(An.push(e),e.flags|=1),Ec()}function uo(e,t,n=it+1){for(;n<xe.length;n++){const r=xe[n];if(r&&r.flags&2){if(e&&r.id!==e.uid)continue;xe.splice(n,1),n--,r.flags&4&&(r.flags&=-2),r(),r.flags&4||(r.flags&=-2)}}}function Ic(e){if(An.length){const t=[...new Set(An)].sort((n,r)=>ar(n)-ar(r));if(An.length=0,Ht){Ht.push(...t);return}for(Ht=t,En=0;En<Ht.length;En++){const n=Ht[En];n.flags&4&&(n.flags&=-2),n.flags&8||n(),n.flags&=-2}Ht=null,En=0}}const ar=e=>e.id==null?e.flags&2?-1:1/0:e.id;function wc(e){try{for(it=0;it<xe.length;it++){const t=xe[it];t&&!(t.flags&8)&&(t.flags&4&&(t.flags&=-2),br(t,t.i,t.i?15:14),t.flags&4||(t.flags&=-2))}}finally{for(;it<xe.length;it++){const t=xe[it];t&&(t.flags&=-2)}it=-1,xe.length=0,Ic(),Kr=null,(xe.length||An.length)&&wc()}}let Ae=null,Sc=null;function Gr(e){const t=Ae;return Ae=e,Sc=e&&e.type.__scopeId||null,t}function Gt(e,t=Ae,n){if(!t||e._n)return e;const r=(...s)=>{r._d&&Jr(-1);const i=Gr(t);let o;try{o=e(...s)}finally{Gr(i),r._d&&Jr(1)}return o};return r._n=!0,r._c=!0,r._d=!0,r}function Yv(e,t){if(Ae===null)return e;const n=bs(Ae),r=e.dirs||(e.dirs=[]);for(let s=0;s<t.length;s++){let[i,o,a,c=de]=t[s];i&&(z(i)&&(i={mounted:i,updated:i}),i.deep&&Et(o),r.push({dir:i,instance:n,value:o,oldValue:void 0,arg:a,modifiers:c}))}return e}function tn(e,t,n,r){const s=e.dirs,i=t&&t.dirs;for(let o=0;o<s.length;o++){const a=s[o];i&&(a.oldValue=i[o].value);let c=a.dir[r];c&&(Pt(),Qe(c,n,8,[e.el,a,e,t]),Ot())}}function Dr(e,t){if(Pe){let n=Pe.provides;const r=Pe.parent&&Pe.parent.provides;r===n&&(n=Pe.provides=Object.create(r)),n[e]=t}}function ze(e,t,n=!1){const r=Bi();if(r||hn){let s=hn?hn._context.provides:r?r.parent==null||r.ce?r.vnode.appContext&&r.vnode.appContext.provides:r.parent.provides:void 0;if(s&&e in s)return s[e];if(arguments.length>1)return n&&z(t)?t.call(r&&r.proxy):t}}function hf(){return!!(Bi()||hn)}const pf=Symbol.for("v-scx"),gf=()=>ze(pf);function Qn(e,t,n){return Tc(e,t,n)}function Tc(e,t,n=de){const{immediate:r,deep:s,flush:i,once:o}=n,a=Ee({},n),c=t&&r||!t&&i!=="post";let l;if(fr){if(i==="sync"){const g=gf();l=g.__watcherHandles||(g.__watcherHandles=[])}else if(!c){const g=()=>{};return g.stop=ft,g.resume=ft,g.pause=ft,g}}const u=Pe;a.call=(g,I,w)=>Qe(g,u,I,w);let f=!1;i==="post"?a.scheduler=g=>{Ue(g,u&&u.suspense)}:i!=="sync"&&(f=!0,a.scheduler=(g,I)=>{I?g():xi(g)}),a.augmentJob=g=>{t&&(g.flags|=4),f&&(g.flags|=2,u&&(g.id=u.uid,g.i=u))};const p=lf(e,t,a);return fr&&(l?l.push(p):c&&p()),p}function mf(e,t,n){const r=this.proxy,s=ge(e)?e.includes(".")?Ac(r,e):()=>r[e]:e.bind(r,r);let i;z(t)?i=t:(i=t.handler,n=t);const o=Er(this),a=Tc(s,i.bind(r),n);return o(),a}function Ac(e,t){const n=t.split(".");return()=>{let r=e;for(let s=0;s<n.length&&r;s++)r=r[n[s]];return r}}const _f=Symbol("_vte"),Cc=e=>e.__isTeleport,ot=Symbol("_leaveCb"),$n=Symbol("_enterCb");function vf(){const e={isMounted:!1,isLeaving:!1,isUnmounting:!1,leavingVNodes:new Map};return Di(()=>{e.isMounted=!0}),Lc(()=>{e.isUnmounting=!0}),e}const Ke=[Function,Array],Rc={mode:String,appear:Boolean,persisted:Boolean,onBeforeEnter:Ke,onEnter:Ke,onAfterEnter:Ke,onEnterCancelled:Ke,onBeforeLeave:Ke,onLeave:Ke,onAfterLeave:Ke,onLeaveCancelled:Ke,onBeforeAppear:Ke,onAppear:Ke,onAfterAppear:Ke,onAppearCancelled:Ke},Pc=e=>{const t=e.subTree;return t.component?Pc(t.component):t},yf={name:"BaseTransition",props:Rc,setup(e,{slots:t}){const n=Bi(),r=vf();return()=>{const s=t.default&&Nc(t.default(),!0),i=s&&s.length?Oc(s):n.subTree?In():void 0;if(!i)return;const o=ee(e),{mode:a}=o;if(r.isLeaving)return Ns(i);const c=fo(i);if(!c)return Ns(i);let l=ni(c,o,r,n,f=>l=f);c.type!==Re&&cr(c,l);let u=n.subTree&&fo(n.subTree);if(u&&u.type!==Re&&!cn(u,c)&&Pc(n).type!==Re){let f=ni(u,o,r,n);if(cr(u,f),a==="out-in"&&c.type!==Re)return r.isLeaving=!0,f.afterLeave=()=>{r.isLeaving=!1,n.job.flags&8||n.update(),delete f.afterLeave,u=void 0},Ns(i);a==="in-out"&&c.type!==Re?f.delayLeave=(p,g,I)=>{const w=kc(r,u);w[String(u.key)]=u,p[ot]=()=>{g(),p[ot]=void 0,delete l.delayedLeave,u=void 0},l.delayedLeave=()=>{I(),delete l.delayedLeave,u=void 0}}:u=void 0}else u&&(u=void 0);return i}}};function Oc(e){let t=e[0];if(e.length>1){for(const n of e)if(n.type!==Re){t=n;break}}return t}const bf=yf;function kc(e,t){const{leavingVNodes:n}=e;let r=n.get(t.type);return r||(r=Object.create(null),n.set(t.type,r)),r}function ni(e,t,n,r,s){const{appear:i,mode:o,persisted:a=!1,onBeforeEnter:c,onEnter:l,onAfterEnter:u,onEnterCancelled:f,onBeforeLeave:p,onLeave:g,onAfterLeave:I,onLeaveCancelled:w,onBeforeAppear:L,onAppear:M,onAfterAppear:A,onAppearCancelled:x}=t,N=String(e.key),H=kc(n,e),te=(C,j)=>{C&&Qe(C,r,9,j)},J=(C,j)=>{const Z=j[1];te(C,j),U(C)?C.every(O=>O.length<=1)&&Z():C.length<=1&&Z()},G={mode:o,persisted:a,beforeEnter(C){let j=c;if(!n.isMounted)if(i)j=L||c;else return;C[ot]&&C[ot](!0);const Z=H[N];Z&&cn(e,Z)&&Z.el[ot]&&Z.el[ot](),te(j,[C])},enter(C){if(H[N]===e)return;let j=l,Z=u,O=f;if(!n.isMounted)if(i)j=M||l,Z=A||u,O=x||f;else return;let X=!1;C[$n]=Oe=>{X||(X=!0,Oe?te(O,[C]):te(Z,[C]),G.delayedLeave&&G.delayedLeave(),C[$n]=void 0)};const ve=C[$n].bind(null,!1);j?J(j,[C,ve]):ve()},leave(C,j){const Z=String(e.key);if(C[$n]&&C[$n](!0),n.isUnmounting)return j();te(p,[C]);let O=!1;C[ot]=ve=>{O||(O=!0,j(),ve?te(w,[C]):te(I,[C]),C[ot]=void 0,H[Z]===e&&delete H[Z])};const X=C[ot].bind(null,!1);H[Z]=e,g?J(g,[C,X]):X()},clone(C){const j=ni(C,t,n,r,s);return s&&s(j),j}};return G}function Ns(e){if(ms(e))return e=Yt(e),e.children=null,e}function fo(e){if(!ms(e))return Cc(e.type)&&e.children?Oc(e.children):e;if(e.component)return e.component.subTree;const{shapeFlag:t,children:n}=e;if(n){if(t&16)return n[0];if(t&32&&z(n.default))return n.default()}}function cr(e,t){e.shapeFlag&6&&e.component?(e.transition=t,cr(e.component.subTree,t)):e.shapeFlag&128?(e.ssContent.transition=t.clone(e.ssContent),e.ssFallback.transition=t.clone(e.ssFallback)):e.transition=t}function Nc(e,t=!1,n){let r=[],s=0;for(let i=0;i<e.length;i++){let o=e[i];const a=n==null?o.key:String(n)+String(o.key!=null?o.key:i);o.type===Te?(o.patchFlag&128&&s++,r=r.concat(Nc(o.children,t,a))):(t||o.type!==Re)&&r.push(a!=null?Yt(o,{key:a}):o)}if(s>1)for(let i=0;i<r.length;i++)r[i].patchFlag=-2;return r}function xc(e,t){return z(e)?Ee({name:e.name},t,{setup:e}):e}function Dc(e){e.ids=[e.ids[0]+e.ids[2]+++"-",0,0]}function ho(e,t){let n;return!!((n=Object.getOwnPropertyDescriptor(e,t))&&!n.configurable)}const zr=new WeakMap;function Zn(e,t,n,r,s=!1){if(U(e)){e.forEach((w,L)=>Zn(w,t&&(U(t)?t[L]:t),n,r,s));return}if(Cn(r)&&!s){r.shapeFlag&512&&r.type.__asyncResolved&&r.component.subTree.component&&Zn(e,t,n,r.component.subTree);return}const i=r.shapeFlag&4?bs(r.component):r.el,o=s?null:i,{i:a,r:c}=e,l=t&&t.r,u=a.refs===de?a.refs={}:a.refs,f=a.setupState,p=ee(f),g=f===de?Ga:w=>ho(u,w)?!1:ie(p,w),I=(w,L)=>!(L&&ho(u,L));if(l!=null&&l!==c){if(po(t),ge(l))u[l]=null,g(l)&&(f[l]=null);else if(_e(l)){const w=t;I(l,w.k)&&(l.value=null),w.k&&(u[w.k]=null)}}if(z(c))br(c,a,12,[o,u]);else{const w=ge(c),L=_e(c);if(w||L){const M=()=>{if(e.f){const A=w?g(c)?f[c]:u[c]:I()||!e.k?c.value:u[e.k];if(s)U(A)&&Si(A,i);else if(U(A))A.includes(i)||A.push(i);else if(w)u[c]=[i],g(c)&&(f[c]=u[c]);else{const x=[i];I(c,e.k)&&(c.value=x),e.k&&(u[e.k]=x)}}else w?(u[c]=o,g(c)&&(f[c]=o)):L&&(I(c,e.k)&&(c.value=o),e.k&&(u[e.k]=o))};if(o){const A=()=>{M(),zr.delete(e)};A.id=-1,zr.set(e,A),Ue(A,n)}else po(e),M()}}}function po(e){const t=zr.get(e);t&&(t.flags|=8,zr.delete(e))}us().requestIdleCallback;us().cancelIdleCallback;const Cn=e=>!!e.type.__asyncLoader,ms=e=>e.type.__isKeepAlive;function Ef(e,t){Mc(e,"a",t)}function If(e,t){Mc(e,"da",t)}function Mc(e,t,n=Pe){const r=e.__wdc||(e.__wdc=()=>{let s=n;for(;s;){if(s.isDeactivated)return;s=s.parent}return e()});if(_s(t,r,n),n){let s=n.parent;for(;s&&s.parent;)ms(s.parent.vnode)&&wf(r,t,n,s),s=s.parent}}function wf(e,t,n,r){const s=_s(t,e,r,!0);Uc(()=>{Si(r[t],s)},n)}function _s(e,t,n=Pe,r=!1){if(n){const s=n[e]||(n[e]=[]),i=t.__weh||(t.__weh=(...o)=>{Pt();const a=Er(n),c=Qe(t,n,e,o);return a(),Ot(),c});return r?s.unshift(i):s.push(i),i}}const Dt=e=>(t,n=Pe)=>{(!fr||e==="sp")&&_s(e,(...r)=>t(...r),n)},Sf=Dt("bm"),Di=Dt("m"),Tf=Dt("bu"),Af=Dt("u"),Lc=Dt("bum"),Uc=Dt("um"),Cf=Dt("sp"),Rf=Dt("rtg"),Pf=Dt("rtc");function Of(e,t=Pe){_s("ec",e,t)}const Fc="components";function kf(e,t){return Vc(Fc,e,!0,t)||e}const Bc=Symbol.for("v-ndc");function Gn(e){return ge(e)?Vc(Fc,e,!1)||e:e||Bc}function Vc(e,t,n=!0,r=!1){const s=Ae||Pe;if(s){const i=s.type;{const a=md(i,!1);if(a&&(a===t||a===De(t)||a===cs(De(t))))return i}const o=go(s[e]||i[e],t)||go(s.appContext[e],t);return!o&&r?i:o}}function go(e,t){return e&&(e[t]||e[De(t)]||e[cs(De(t))])}function xs(e,t,n,r){let s;const i=n,o=U(e);if(o||ge(e)){const a=o&&Rt(e);let c=!1,l=!1;a&&(c=!He(e),l=kt(e),e=ds(e)),s=new Array(e.length);for(let u=0,f=e.length;u<f;u++)s[u]=t(c?l?Nn(Xe(e[u])):Xe(e[u]):e[u],u,void 0,i)}else if(typeof e=="number"){s=new Array(e);for(let a=0;a<e;a++)s[a]=t(a+1,a,void 0,i)}else if(oe(e))if(e[Symbol.iterator])s=Array.from(e,(a,c)=>t(a,c,void 0,i));else{const a=Object.keys(e);s=new Array(a.length);for(let c=0,l=a.length;c<l;c++){const u=a[c];s[c]=t(e[u],u,c,i)}}else s=[];return s}function Nf(e,t,n={},r,s){if(Ae.ce||Ae.parent&&Cn(Ae.parent)&&Ae.parent.ce){const l=Object.keys(n).length>0;return le(),ut(Te,null,[fe("slot",n,r)],l?-2:64)}let i=e[t];i&&i._c&&(i._d=!1),le();const o=i&&Hc(i(n)),a=n.key||o&&o.key,c=ut(Te,{key:(a&&!je(a)?a:`_${t}`)+(!o&&r?"_fb":"")},o||[],o&&e._===1?64:-2);return i&&i._c&&(i._d=!0),c}function Hc(e){return e.some(t=>ur(t)?!(t.type===Re||t.type===Te&&!Hc(t.children)):!0)?e:null}const ri=e=>e?al(e)?bs(e):ri(e.parent):null,er=Ee(Object.create(null),{$:e=>e,$el:e=>e.vnode.el,$data:e=>e.data,$props:e=>e.props,$attrs:e=>e.attrs,$slots:e=>e.slots,$refs:e=>e.refs,$parent:e=>ri(e.parent),$root:e=>ri(e.root),$host:e=>e.ce,$emit:e=>e.emit,$options:e=>$c(e),$forceUpdate:e=>e.f||(e.f=()=>{xi(e.update)}),$nextTick:e=>e.n||(e.n=gs.bind(e.proxy)),$watch:e=>mf.bind(e)}),Ds=(e,t)=>e!==de&&!e.__isScriptSetup&&ie(e,t),xf={get({_:e},t){if(t==="__v_skip")return!0;const{ctx:n,setupState:r,data:s,props:i,accessCache:o,type:a,appContext:c}=e;if(t[0]!=="$"){const p=o[t];if(p!==void 0)switch(p){case 1:return r[t];case 2:return s[t];case 4:return n[t];case 3:return i[t]}else{if(Ds(r,t))return o[t]=1,r[t];if(s!==de&&ie(s,t))return o[t]=2,s[t];if(ie(i,t))return o[t]=3,i[t];if(n!==de&&ie(n,t))return o[t]=4,n[t];si&&(o[t]=0)}}const l=er[t];let u,f;if(l)return t==="$attrs"&&Ce(e.attrs,"get",""),l(e);if((u=a.__cssModules)&&(u=u[t]))return u;if(n!==de&&ie(n,t))return o[t]=4,n[t];if(f=c.config.globalProperties,ie(f,t))return f[t]},set({_:e},t,n){const{data:r,setupState:s,ctx:i}=e;return Ds(s,t)?(s[t]=n,!0):r!==de&&ie(r,t)?(r[t]=n,!0):ie(e.props,t)||t[0]==="$"&&t.slice(1)in e?!1:(i[t]=n,!0)},has({_:{data:e,setupState:t,accessCache:n,ctx:r,appContext:s,props:i,type:o}},a){let c;return!!(n[a]||e!==de&&a[0]!=="$"&&ie(e,a)||Ds(t,a)||ie(i,a)||ie(r,a)||ie(er,a)||ie(s.config.globalProperties,a)||(c=o.__cssModules)&&c[a])},defineProperty(e,t,n){return n.get!=null?e._.accessCache[t]=0:ie(n,"value")&&this.set(e,t,n.value,null),Reflect.defineProperty(e,t,n)}};function mo(e){return U(e)?e.reduce((t,n)=>(t[n]=null,t),{}):e}let si=!0;function Df(e){const t=$c(e),n=e.proxy,r=e.ctx;si=!1,t.beforeCreate&&_o(t.beforeCreate,e,"bc");const{data:s,computed:i,methods:o,watch:a,provide:c,inject:l,created:u,beforeMount:f,mounted:p,beforeUpdate:g,updated:I,activated:w,deactivated:L,beforeDestroy:M,beforeUnmount:A,destroyed:x,unmounted:N,render:H,renderTracked:te,renderTriggered:J,errorCaptured:G,serverPrefetch:C,expose:j,inheritAttrs:Z,components:O,directives:X,filters:ve}=t;if(l&&Mf(l,r,null),o)for(const q in o){const re=o[q];z(re)&&(r[q]=re.bind(n))}if(s){const q=s.call(n,n);oe(q)&&(e.data=yr(q))}if(si=!0,i)for(const q in i){const re=i[q],pt=z(re)?re.bind(n,n):z(re.get)?re.get.bind(n,n):ft,Mt=!z(re)&&z(re.set)?re.set.bind(n):ft,et=Fe({get:pt,set:Mt});Object.defineProperty(r,q,{enumerable:!0,configurable:!0,get:()=>et.value,set:Le=>et.value=Le})}if(a)for(const q in a)jc(a[q],r,n,q);if(c){const q=z(c)?c.call(n):c;Reflect.ownKeys(q).forEach(re=>{Dr(re,q[re])})}u&&_o(u,e,"c");function ae(q,re){U(re)?re.forEach(pt=>q(pt.bind(n))):re&&q(re.bind(n))}if(ae(Sf,f),ae(Di,p),ae(Tf,g),ae(Af,I),ae(Ef,w),ae(If,L),ae(Of,G),ae(Pf,te),ae(Rf,J),ae(Lc,A),ae(Uc,N),ae(Cf,C),U(j))if(j.length){const q=e.exposed||(e.exposed={});j.forEach(re=>{Object.defineProperty(q,re,{get:()=>n[re],set:pt=>n[re]=pt,enumerable:!0})})}else e.exposed||(e.exposed={});H&&e.render===ft&&(e.render=H),Z!=null&&(e.inheritAttrs=Z),O&&(e.components=O),X&&(e.directives=X),C&&Dc(e)}function Mf(e,t,n=ft){U(e)&&(e=ii(e));for(const r in e){const s=e[r];let i;oe(s)?"default"in s?i=ze(s.from||r,s.default,!0):i=ze(s.from||r):i=ze(s),_e(i)?Object.defineProperty(t,r,{enumerable:!0,configurable:!0,get:()=>i.value,set:o=>i.value=o}):t[r]=i}}function _o(e,t,n){Qe(U(e)?e.map(r=>r.bind(t.proxy)):e.bind(t.proxy),t,n)}function jc(e,t,n,r){let s=r.includes(".")?Ac(n,r):()=>n[r];if(ge(e)){const i=t[e];z(i)&&Qn(s,i)}else if(z(e))Qn(s,e.bind(n));else if(oe(e))if(U(e))e.forEach(i=>jc(i,t,n,r));else{const i=z(e.handler)?e.handler.bind(n):t[e.handler];z(i)&&Qn(s,i,e)}}function $c(e){const t=e.type,{mixins:n,extends:r}=t,{mixins:s,optionsCache:i,config:{optionMergeStrategies:o}}=e.appContext,a=i.get(t);let c;return a?c=a:!s.length&&!n&&!r?c=t:(c={},s.length&&s.forEach(l=>qr(c,l,o,!0)),qr(c,t,o)),oe(t)&&i.set(t,c),c}function qr(e,t,n,r=!1){const{mixins:s,extends:i}=t;i&&qr(e,i,n,!0),s&&s.forEach(o=>qr(e,o,n,!0));for(const o in t)if(!(r&&o==="expose")){const a=Lf[o]||n&&n[o];e[o]=a?a(e[o],t[o]):t[o]}return e}const Lf={data:vo,props:yo,emits:yo,methods:zn,computed:zn,beforeCreate:ke,created:ke,beforeMount:ke,mounted:ke,beforeUpdate:ke,updated:ke,beforeDestroy:ke,beforeUnmount:ke,destroyed:ke,unmounted:ke,activated:ke,deactivated:ke,errorCaptured:ke,serverPrefetch:ke,components:zn,directives:zn,watch:Ff,provide:vo,inject:Uf};function vo(e,t){return t?e?function(){return Ee(z(e)?e.call(this,this):e,z(t)?t.call(this,this):t)}:t:e}function Uf(e,t){return zn(ii(e),ii(t))}function ii(e){if(U(e)){const t={};for(let n=0;n<e.length;n++)t[e[n]]=e[n];return t}return e}function ke(e,t){return e?[...new Set([].concat(e,t))]:t}function zn(e,t){return e?Ee(Object.create(null),e,t):t}function yo(e,t){return e?U(e)&&U(t)?[...new Set([...e,...t])]:Ee(Object.create(null),mo(e),mo(t??{})):t}function Ff(e,t){if(!e)return t;if(!t)return e;const n=Ee(Object.create(null),e);for(const r in t)n[r]=ke(e[r],t[r]);return n}function Wc(){return{app:null,config:{isNativeTag:Ga,performance:!1,globalProperties:{},optionMergeStrategies:{},errorHandler:void 0,warnHandler:void 0,compilerOptions:{}},mixins:[],components:{},directives:{},provides:Object.create(null),optionsCache:new WeakMap,propsCache:new WeakMap,emitsCache:new WeakMap}}let Bf=0;function Vf(e,t){return function(r,s=null){z(r)||(r=Ee({},r)),s!=null&&!oe(s)&&(s=null);const i=Wc(),o=new WeakSet,a=[];let c=!1;const l=i.app={_uid:Bf++,_component:r,_props:s,_container:null,_context:i,_instance:null,version:vd,get config(){return i.config},set config(u){},use(u,...f){return o.has(u)||(u&&z(u.install)?(o.add(u),u.install(l,...f)):z(u)&&(o.add(u),u(l,...f))),l},mixin(u){return i.mixins.includes(u)||i.mixins.push(u),l},component(u,f){return f?(i.components[u]=f,l):i.components[u]},directive(u,f){return f?(i.directives[u]=f,l):i.directives[u]},mount(u,f,p){if(!c){const g=l._ceVNode||fe(r,s);return g.appContext=i,p===!0?p="svg":p===!1&&(p=void 0),e(g,u,p),c=!0,l._container=u,u.__vue_app__=l,bs(g.component)}},onUnmount(u){a.push(u)},unmount(){c&&(Qe(a,l._instance,16),e(null,l._container),delete l._container.__vue_app__)},provide(u,f){return i.provides[u]=f,l},runWithContext(u){const f=hn;hn=l;try{return u()}finally{hn=f}}};return l}}let hn=null;const Hf=(e,t)=>t==="modelValue"||t==="model-value"?e.modelModifiers:e[`${t}Modifiers`]||e[`${De(t)}Modifiers`]||e[`${mn(t)}Modifiers`];function jf(e,t,...n){if(e.isUnmounted)return;const r=e.vnode.props||de;let s=n;const i=t.startsWith("update:"),o=i&&Hf(r,t.slice(7));o&&(o.trim&&(s=n.map(u=>ge(u)?u.trim():u)),o.number&&(s=n.map(ls)));let a,c=r[a=Cs(t)]||r[a=Cs(De(t))];!c&&i&&(c=r[a=Cs(mn(t))]),c&&Qe(c,e,6,s);const l=r[a+"Once"];if(l){if(!e.emitted)e.emitted={};else if(e.emitted[a])return;e.emitted[a]=!0,Qe(l,e,6,s)}}const $f=new WeakMap;function Kc(e,t,n=!1){const r=n?$f:t.emitsCache,s=r.get(e);if(s!==void 0)return s;const i=e.emits;let o={},a=!1;if(!z(e)){const c=l=>{const u=Kc(l,t,!0);u&&(a=!0,Ee(o,u))};!n&&t.mixins.length&&t.mixins.forEach(c),e.extends&&c(e.extends),e.mixins&&e.mixins.forEach(c)}return!i&&!a?(oe(e)&&r.set(e,null),null):(U(i)?i.forEach(c=>o[c]=null):Ee(o,i),oe(e)&&r.set(e,o),o)}function vs(e,t){return!e||!ss(t)?!1:(t=t.slice(2).replace(/Once$/,""),ie(e,t[0].toLowerCase()+t.slice(1))||ie(e,mn(t))||ie(e,t))}function bo(e){const{type:t,vnode:n,proxy:r,withProxy:s,propsOptions:[i],slots:o,attrs:a,emit:c,render:l,renderCache:u,props:f,data:p,setupState:g,ctx:I,inheritAttrs:w}=e,L=Gr(e);let M,A;try{if(n.shapeFlag&4){const N=s||r,H=N;M=ct(l.call(H,N,u,f,g,p,I)),A=a}else{const N=t;M=ct(N.length>1?N(f,{attrs:a,slots:o,emit:c}):N(f,null)),A=t.props?a:Wf(a)}}catch(N){tr.length=0,ps(N,e,1),M=fe(Re)}let x=M;if(A&&w!==!1){const N=Object.keys(A),{shapeFlag:H}=x;N.length&&H&7&&(i&&N.some(is)&&(A=Kf(A,i)),x=Yt(x,A,!1,!0))}return n.dirs&&(x=Yt(x,null,!1,!0),x.dirs=x.dirs?x.dirs.concat(n.dirs):n.dirs),n.transition&&cr(x,n.transition),M=x,Gr(L),M}const Wf=e=>{let t;for(const n in e)(n==="class"||n==="style"||ss(n))&&((t||(t={}))[n]=e[n]);return t},Kf=(e,t)=>{const n={};for(const r in e)(!is(r)||!(r.slice(9)in t))&&(n[r]=e[r]);return n};function Gf(e,t,n){const{props:r,children:s,component:i}=e,{props:o,children:a,patchFlag:c}=t,l=i.emitsOptions;if(t.dirs||t.transition)return!0;if(n&&c>=0){if(c&1024)return!0;if(c&16)return r?Eo(r,o,l):!!o;if(c&8){const u=t.dynamicProps;for(let f=0;f<u.length;f++){const p=u[f];if(Gc(o,r,p)&&!vs(l,p))return!0}}}else return(s||a)&&(!a||!a.$stable)?!0:r===o?!1:r?o?Eo(r,o,l):!0:!!o;return!1}function Eo(e,t,n){const r=Object.keys(t);if(r.length!==Object.keys(e).length)return!0;for(let s=0;s<r.length;s++){const i=r[s];if(Gc(t,e,i)&&!vs(n,i))return!0}return!1}function Gc(e,t,n){const r=e[n],s=t[n];return n==="style"&&oe(r)&&oe(s)?!Jt(r,s):r!==s}function zf({vnode:e,parent:t,suspense:n},r){for(;t;){const s=t.subTree;if(s.suspense&&s.suspense.activeBranch===e&&(s.suspense.vnode.el=s.el=r,e=s),s===e)(e=t.vnode).el=r,t=t.parent;else break}n&&n.activeBranch===e&&(n.vnode.el=r)}const zc={},qc=()=>Object.create(zc),Jc=e=>Object.getPrototypeOf(e)===zc;function qf(e,t,n,r=!1){const s={},i=qc();e.propsDefaults=Object.create(null),Yc(e,t,s,i);for(const o in e.propsOptions[0])o in s||(s[o]=void 0);n?e.props=r?s:_c(s):e.type.props?e.props=s:e.props=i,e.attrs=i}function Jf(e,t,n,r){const{props:s,attrs:i,vnode:{patchFlag:o}}=e,a=ee(s),[c]=e.propsOptions;let l=!1;if((r||o>0)&&!(o&16)){if(o&8){const u=e.vnode.dynamicProps;for(let f=0;f<u.length;f++){let p=u[f];if(vs(e.emitsOptions,p))continue;const g=t[p];if(c)if(ie(i,p))g!==i[p]&&(i[p]=g,l=!0);else{const I=De(p);s[I]=oi(c,a,I,g,e,!1)}else g!==i[p]&&(i[p]=g,l=!0)}}}else{Yc(e,t,s,i)&&(l=!0);let u;for(const f in a)(!t||!ie(t,f)&&((u=mn(f))===f||!ie(t,u)))&&(c?n&&(n[f]!==void 0||n[u]!==void 0)&&(s[f]=oi(c,a,f,void 0,e,!0)):delete s[f]);if(i!==a)for(const f in i)(!t||!ie(t,f))&&(delete i[f],l=!0)}l&&bt(e.attrs,"set","")}function Yc(e,t,n,r){const[s,i]=e.propsOptions;let o=!1,a;if(t)for(let c in t){if(Jn(c))continue;const l=t[c];let u;s&&ie(s,u=De(c))?!i||!i.includes(u)?n[u]=l:(a||(a={}))[u]=l:vs(e.emitsOptions,c)||(!(c in r)||l!==r[c])&&(r[c]=l,o=!0)}if(i){const c=ee(n),l=a||de;for(let u=0;u<i.length;u++){const f=i[u];n[f]=oi(s,c,f,l[f],e,!ie(l,f))}}return o}function oi(e,t,n,r,s,i){const o=e[n];if(o!=null){const a=ie(o,"default");if(a&&r===void 0){const c=o.default;if(o.type!==Function&&!o.skipFactory&&z(c)){const{propsDefaults:l}=s;if(n in l)r=l[n];else{const u=Er(s);r=l[n]=c.call(null,t),u()}}else r=c;s.ce&&s.ce._setProp(n,r)}o[0]&&(i&&!a?r=!1:o[1]&&(r===""||r===mn(n))&&(r=!0))}return r}const Yf=new WeakMap;function Xc(e,t,n=!1){const r=n?Yf:t.propsCache,s=r.get(e);if(s)return s;const i=e.props,o={},a=[];let c=!1;if(!z(e)){const u=f=>{c=!0;const[p,g]=Xc(f,t,!0);Ee(o,p),g&&a.push(...g)};!n&&t.mixins.length&&t.mixins.forEach(u),e.extends&&u(e.extends),e.mixins&&e.mixins.forEach(u)}if(!i&&!c)return oe(e)&&r.set(e,Sn),Sn;if(U(i))for(let u=0;u<i.length;u++){const f=De(i[u]);Io(f)&&(o[f]=de)}else if(i)for(const u in i){const f=De(u);if(Io(f)){const p=i[u],g=o[f]=U(p)||z(p)?{type:p}:Ee({},p),I=g.type;let w=!1,L=!0;if(U(I))for(let M=0;M<I.length;++M){const A=I[M],x=z(A)&&A.name;if(x==="Boolean"){w=!0;break}else x==="String"&&(L=!1)}else w=z(I)&&I.name==="Boolean";g[0]=w,g[1]=L,(w||ie(g,"default"))&&a.push(f)}}const l=[o,a];return oe(e)&&r.set(e,l),l}function Io(e){return e[0]!=="$"&&!Jn(e)}const Mi=e=>e==="_"||e==="_ctx"||e==="$stable",Li=e=>U(e)?e.map(ct):[ct(e)],Xf=(e,t,n)=>{if(t._n)return t;const r=Gt((...s)=>Li(t(...s)),n);return r._c=!1,r},Qc=(e,t,n)=>{const r=e._ctx;for(const s in e){if(Mi(s))continue;const i=e[s];if(z(i))t[s]=Xf(s,i,r);else if(i!=null){const o=Li(i);t[s]=()=>o}}},Zc=(e,t)=>{const n=Li(t);e.slots.default=()=>n},el=(e,t,n)=>{for(const r in t)(n||!Mi(r))&&(e[r]=t[r])},Qf=(e,t,n)=>{const r=e.slots=qc();if(e.vnode.shapeFlag&32){const s=t._;s?(el(r,t,n),n&&Ya(r,"_",s,!0)):Qc(t,r)}else t&&Zc(e,t)},Zf=(e,t,n)=>{const{vnode:r,slots:s}=e;let i=!0,o=de;if(r.shapeFlag&32){const a=t._;a?n&&a===1?i=!1:el(s,t,n):(i=!t.$stable,Qc(t,s)),o=t}else t&&(Zc(e,t),o={default:1});if(i)for(const a in s)!Mi(a)&&o[a]==null&&delete s[a]},Ue=sd;function ed(e){return td(e)}function td(e,t){const n=us();n.__VUE__=!0;const{insert:r,remove:s,patchProp:i,createElement:o,createText:a,createComment:c,setText:l,setElementText:u,parentNode:f,nextSibling:p,setScopeId:g=ft,insertStaticContent:I}=e,w=(d,h,m,_=null,b=null,v=null,R=void 0,T=null,S=!!h.dynamicChildren)=>{if(d===h)return;d&&!cn(d,h)&&(_=y(d),Le(d,b,v,!0),d=null),h.patchFlag===-2&&(S=!1,h.dynamicChildren=null);const{type:E,ref:V,shapeFlag:k}=h;switch(E){case ys:L(d,h,m,_);break;case Re:M(d,h,m,_);break;case Mr:d==null&&A(h,m,_,R);break;case Te:O(d,h,m,_,b,v,R,T,S);break;default:k&1?H(d,h,m,_,b,v,R,T,S):k&6?X(d,h,m,_,b,v,R,T,S):(k&64||k&128)&&E.process(d,h,m,_,b,v,R,T,S,F)}V!=null&&b?Zn(V,d&&d.ref,v,h||d,!h):V==null&&d&&d.ref!=null&&Zn(d.ref,null,v,d,!0)},L=(d,h,m,_)=>{if(d==null)r(h.el=a(h.children),m,_);else{const b=h.el=d.el;h.children!==d.children&&l(b,h.children)}},M=(d,h,m,_)=>{d==null?r(h.el=c(h.children||""),m,_):h.el=d.el},A=(d,h,m,_)=>{[d.el,d.anchor]=I(d.children,h,m,_,d.el,d.anchor)},x=({el:d,anchor:h},m,_)=>{let b;for(;d&&d!==h;)b=p(d),r(d,m,_),d=b;r(h,m,_)},N=({el:d,anchor:h})=>{let m;for(;d&&d!==h;)m=p(d),s(d),d=m;s(h)},H=(d,h,m,_,b,v,R,T,S)=>{if(h.type==="svg"?R="svg":h.type==="math"&&(R="mathml"),d==null)te(h,m,_,b,v,R,T,S);else{const E=d.el&&d.el._isVueCE?d.el:null;try{E&&E._beginPatch(),C(d,h,b,v,R,T,S)}finally{E&&E._endPatch()}}},te=(d,h,m,_,b,v,R,T)=>{let S,E;const{props:V,shapeFlag:k,transition:B,dirs:$}=d;if(S=d.el=o(d.type,v,V&&V.is,V),k&8?u(S,d.children):k&16&&G(d.children,S,null,_,b,Ms(d,v),R,T),$&&tn(d,null,_,"created"),J(S,d,d.scopeId,R,_),V){for(const ce in V)ce!=="value"&&!Jn(ce)&&i(S,ce,null,V[ce],v,_);"value"in V&&i(S,"value",null,V.value,v),(E=V.onVnodeBeforeMount)&&st(E,_,d)}$&&tn(d,null,_,"beforeMount");const ne=nd(b,B);ne&&B.beforeEnter(S),r(S,h,m),((E=V&&V.onVnodeMounted)||ne||$)&&Ue(()=>{try{E&&st(E,_,d),ne&&B.enter(S),$&&tn(d,null,_,"mounted")}finally{}},b)},J=(d,h,m,_,b)=>{if(m&&g(d,m),_)for(let v=0;v<_.length;v++)g(d,_[v]);if(b){let v=b.subTree;if(h===v||sl(v.type)&&(v.ssContent===h||v.ssFallback===h)){const R=b.vnode;J(d,R,R.scopeId,R.slotScopeIds,b.parent)}}},G=(d,h,m,_,b,v,R,T,S=0)=>{for(let E=S;E<d.length;E++){const V=d[E]=T?yt(d[E]):ct(d[E]);w(null,V,h,m,_,b,v,R,T)}},C=(d,h,m,_,b,v,R)=>{const T=h.el=d.el;let{patchFlag:S,dynamicChildren:E,dirs:V}=h;S|=d.patchFlag&16;const k=d.props||de,B=h.props||de;let $;if(m&&nn(m,!1),($=B.onVnodeBeforeUpdate)&&st($,m,h,d),V&&tn(h,d,m,"beforeUpdate"),m&&nn(m,!0),(k.innerHTML&&B.innerHTML==null||k.textContent&&B.textContent==null)&&u(T,""),E?j(d.dynamicChildren,E,T,m,_,Ms(h,b),v):R||re(d,h,T,null,m,_,Ms(h,b),v,!1),S>0){if(S&16)Z(T,k,B,m,b);else if(S&2&&k.class!==B.class&&i(T,"class",null,B.class,b),S&4&&i(T,"style",k.style,B.style,b),S&8){const ne=h.dynamicProps;for(let ce=0;ce<ne.length;ce++){const he=ne[ce],ye=k[he],we=B[he];(we!==ye||he==="value")&&i(T,he,ye,we,b,m)}}S&1&&d.children!==h.children&&u(T,h.children)}else!R&&E==null&&Z(T,k,B,m,b);(($=B.onVnodeUpdated)||V)&&Ue(()=>{$&&st($,m,h,d),V&&tn(h,d,m,"updated")},_)},j=(d,h,m,_,b,v,R)=>{for(let T=0;T<h.length;T++){const S=d[T],E=h[T],V=S.el&&(S.type===Te||!cn(S,E)||S.shapeFlag&198)?f(S.el):m;w(S,E,V,null,_,b,v,R,!0)}},Z=(d,h,m,_,b)=>{if(h!==m){if(h!==de)for(const v in h)!Jn(v)&&!(v in m)&&i(d,v,h[v],null,b,_);for(const v in m){if(Jn(v))continue;const R=m[v],T=h[v];R!==T&&v!=="value"&&i(d,v,T,R,b,_)}"value"in m&&i(d,"value",h.value,m.value,b)}},O=(d,h,m,_,b,v,R,T,S)=>{const E=h.el=d?d.el:a(""),V=h.anchor=d?d.anchor:a("");let{patchFlag:k,dynamicChildren:B,slotScopeIds:$}=h;$&&(T=T?T.concat($):$),d==null?(r(E,m,_),r(V,m,_),G(h.children||[],m,V,b,v,R,T,S)):k>0&&k&64&&B&&d.dynamicChildren&&d.dynamicChildren.length===B.length?(j(d.dynamicChildren,B,m,b,v,R,T),(h.key!=null||b&&h===b.subTree)&&tl(d,h,!0)):re(d,h,m,V,b,v,R,T,S)},X=(d,h,m,_,b,v,R,T,S)=>{h.slotScopeIds=T,d==null?h.shapeFlag&512?b.ctx.activate(h,m,_,R,S):ve(h,m,_,b,v,R,S):Oe(d,h,S)},ve=(d,h,m,_,b,v,R)=>{const T=d.component=fd(d,_,b);if(ms(d)&&(T.ctx.renderer=F),dd(T,!1,R),T.asyncDep){if(b&&b.registerDep(T,ae,R),!d.el){const S=T.subTree=fe(Re);M(null,S,h,m),d.placeholder=S.el}}else ae(T,d,h,m,b,v,R)},Oe=(d,h,m)=>{const _=h.component=d.component;if(Gf(d,h,m))if(_.asyncDep&&!_.asyncResolved){q(_,h,m);return}else _.next=h,_.update();else h.el=d.el,_.vnode=h},ae=(d,h,m,_,b,v,R)=>{const T=()=>{if(d.isMounted){let{next:k,bu:B,u:$,parent:ne,vnode:ce}=d;{const nt=nl(d);if(nt){k&&(k.el=ce.el,q(d,k,R)),nt.asyncDep.then(()=>{Ue(()=>{d.isUnmounted||E()},b)});return}}let he=k,ye;nn(d,!1),k?(k.el=ce.el,q(d,k,R)):k=ce,B&&xr(B),(ye=k.props&&k.props.onVnodeBeforeUpdate)&&st(ye,ne,k,ce),nn(d,!0);const we=bo(d),tt=d.subTree;d.subTree=we,w(tt,we,f(tt.el),y(tt),d,b,v),k.el=we.el,he===null&&zf(d,we.el),$&&Ue($,b),(ye=k.props&&k.props.onVnodeUpdated)&&Ue(()=>st(ye,ne,k,ce),b)}else{let k;const{el:B,props:$}=h,{bm:ne,m:ce,parent:he,root:ye,type:we}=d,tt=Cn(h);nn(d,!1),ne&&xr(ne),!tt&&(k=$&&$.onVnodeBeforeMount)&&st(k,he,h),nn(d,!0);{ye.ce&&ye.ce._hasShadowRoot()&&ye.ce._injectChildStyle(we,d.parent?d.parent.type:void 0);const nt=d.subTree=bo(d);w(null,nt,m,_,d,b,v),h.el=nt.el}if(ce&&Ue(ce,b),!tt&&(k=$&&$.onVnodeMounted)){const nt=h;Ue(()=>st(k,he,nt),b)}(h.shapeFlag&256||he&&Cn(he.vnode)&&he.vnode.shapeFlag&256)&&d.a&&Ue(d.a,b),d.isMounted=!0,h=m=_=null}};d.scope.on();const S=d.effect=new rc(T);d.scope.off();const E=d.update=S.run.bind(S),V=d.job=S.runIfDirty.bind(S);V.i=d,V.id=d.uid,S.scheduler=()=>xi(V),nn(d,!0),E()},q=(d,h,m)=>{h.component=d;const _=d.vnode.props;d.vnode=h,d.next=null,Jf(d,h.props,_,m),Zf(d,h.children,m),Pt(),uo(d),Ot()},re=(d,h,m,_,b,v,R,T,S=!1)=>{const E=d&&d.children,V=d?d.shapeFlag:0,k=h.children,{patchFlag:B,shapeFlag:$}=h;if(B>0){if(B&128){Mt(E,k,m,_,b,v,R,T,S);return}else if(B&256){pt(E,k,m,_,b,v,R,T,S);return}}$&8?(V&16&&We(E,b,v),k!==E&&u(m,k)):V&16?$&16?Mt(E,k,m,_,b,v,R,T,S):We(E,b,v,!0):(V&8&&u(m,""),$&16&&G(k,m,_,b,v,R,T,S))},pt=(d,h,m,_,b,v,R,T,S)=>{d=d||Sn,h=h||Sn;const E=d.length,V=h.length,k=Math.min(E,V);let B;for(B=0;B<k;B++){const $=h[B]=S?yt(h[B]):ct(h[B]);w(d[B],$,m,null,b,v,R,T,S)}E>V?We(d,b,v,!0,!1,k):G(h,m,_,b,v,R,T,S,k)},Mt=(d,h,m,_,b,v,R,T,S)=>{let E=0;const V=h.length;let k=d.length-1,B=V-1;for(;E<=k&&E<=B;){const $=d[E],ne=h[E]=S?yt(h[E]):ct(h[E]);if(cn($,ne))w($,ne,m,null,b,v,R,T,S);else break;E++}for(;E<=k&&E<=B;){const $=d[k],ne=h[B]=S?yt(h[B]):ct(h[B]);if(cn($,ne))w($,ne,m,null,b,v,R,T,S);else break;k--,B--}if(E>k){if(E<=B){const $=B+1,ne=$<V?h[$].el:_;for(;E<=B;)w(null,h[E]=S?yt(h[E]):ct(h[E]),m,ne,b,v,R,T,S),E++}}else if(E>B)for(;E<=k;)Le(d[E],b,v,!0),E++;else{const $=E,ne=E,ce=new Map;for(E=ne;E<=B;E++){const Be=h[E]=S?yt(h[E]):ct(h[E]);Be.key!=null&&ce.set(Be.key,E)}let he,ye=0;const we=B-ne+1;let tt=!1,nt=0;const Hn=new Array(we);for(E=0;E<we;E++)Hn[E]=0;for(E=$;E<=k;E++){const Be=d[E];if(ye>=we){Le(Be,b,v,!0);continue}let rt;if(Be.key!=null)rt=ce.get(Be.key);else for(he=ne;he<=B;he++)if(Hn[he-ne]===0&&cn(Be,h[he])){rt=he;break}rt===void 0?Le(Be,b,v,!0):(Hn[rt-ne]=E+1,rt>=nt?nt=rt:tt=!0,w(Be,h[rt],m,null,b,v,R,T,S),ye++)}const ro=tt?rd(Hn):Sn;for(he=ro.length-1,E=we-1;E>=0;E--){const Be=ne+E,rt=h[Be],so=h[Be+1],io=Be+1<V?so.el||rl(so):_;Hn[E]===0?w(null,rt,m,io,b,v,R,T,S):tt&&(he<0||E!==ro[he]?et(rt,m,io,2):he--)}}},et=(d,h,m,_,b=null)=>{const{el:v,type:R,transition:T,children:S,shapeFlag:E}=d;if(E&6){et(d.component.subTree,h,m,_);return}if(E&128){d.suspense.move(h,m,_);return}if(E&64){R.move(d,h,m,F);return}if(R===Te){r(v,h,m);for(let k=0;k<S.length;k++)et(S[k],h,m,_);r(d.anchor,h,m);return}if(R===Mr){x(d,h,m);return}if(_!==2&&E&1&&T)if(_===0)T.beforeEnter(v),r(v,h,m),Ue(()=>T.enter(v),b);else{const{leave:k,delayLeave:B,afterLeave:$}=T,ne=()=>{d.ctx.isUnmounted?s(v):r(v,h,m)},ce=()=>{v._isLeaving&&v[ot](!0),k(v,()=>{ne(),$&&$()})};B?B(v,ne,ce):ce()}else r(v,h,m)},Le=(d,h,m,_=!1,b=!1)=>{const{type:v,props:R,ref:T,children:S,dynamicChildren:E,shapeFlag:V,patchFlag:k,dirs:B,cacheIndex:$,memo:ne}=d;if(k===-2&&(b=!1),T!=null&&(Pt(),Zn(T,null,m,d,!0),Ot()),$!=null&&(h.renderCache[$]=void 0),V&256){h.ctx.deactivate(d);return}const ce=V&1&&B,he=!Cn(d);let ye;if(he&&(ye=R&&R.onVnodeBeforeUnmount)&&st(ye,h,d),V&6)en(d.component,m,_);else{if(V&128){d.suspense.unmount(m,_);return}ce&&tn(d,null,h,"beforeUnmount"),V&64?d.type.remove(d,h,m,F,_):E&&!E.hasOnce&&(v!==Te||k>0&&k&64)?We(E,h,m,!1,!0):(v===Te&&k&384||!b&&V&16)&&We(S,h,m),_&&_n(d)}const we=ne!=null&&$==null;(he&&(ye=R&&R.onVnodeUnmounted)||ce||we)&&Ue(()=>{ye&&st(ye,h,d),ce&&tn(d,null,h,"unmounted"),we&&(d.el=null)},m)},_n=d=>{const{type:h,el:m,anchor:_,transition:b}=d;if(h===Te){vn(m,_);return}if(h===Mr){N(d);return}const v=()=>{s(m),b&&!b.persisted&&b.afterLeave&&b.afterLeave()};if(d.shapeFlag&1&&b&&!b.persisted){const{leave:R,delayLeave:T}=b,S=()=>R(m,v);T?T(d.el,v,S):S()}else v()},vn=(d,h)=>{let m;for(;d!==h;)m=p(d),s(d),d=m;s(h)},en=(d,h,m)=>{const{bum:_,scope:b,job:v,subTree:R,um:T,m:S,a:E}=d;wo(S),wo(E),_&&xr(_),b.stop(),v&&(v.flags|=8,Le(R,d,h,m)),T&&Ue(T,h),Ue(()=>{d.isUnmounted=!0},h)},We=(d,h,m,_=!1,b=!1,v=0)=>{for(let R=v;R<d.length;R++)Le(d[R],h,m,_,b)},y=d=>{if(d.shapeFlag&6)return y(d.component.subTree);if(d.shapeFlag&128)return d.suspense.next();const h=p(d.anchor||d.el),m=h&&h[_f];return m?p(m):h};let D=!1;const P=(d,h,m)=>{let _;d==null?h._vnode&&(Le(h._vnode,null,null,!0),_=h._vnode.component):w(h._vnode||null,d,h,null,null,null,m),h._vnode=d,D||(D=!0,uo(_),Ic(),D=!1)},F={p:w,um:Le,m:et,r:_n,mt:ve,mc:G,pc:re,pbc:j,n:y,o:e};return{render:P,hydrate:void 0,createApp:Vf(P)}}function Ms({type:e,props:t},n){return n==="svg"&&e==="foreignObject"||n==="mathml"&&e==="annotation-xml"&&t&&t.encoding&&t.encoding.includes("html")?void 0:n}function nn({effect:e,job:t},n){n?(e.flags|=32,t.flags|=4):(e.flags&=-33,t.flags&=-5)}function nd(e,t){return(!e||e&&!e.pendingBranch)&&t&&!t.persisted}function tl(e,t,n=!1){const r=e.children,s=t.children;if(U(r)&&U(s))for(let i=0;i<r.length;i++){const o=r[i];let a=s[i];a.shapeFlag&1&&!a.dynamicChildren&&((a.patchFlag<=0||a.patchFlag===32)&&(a=s[i]=yt(s[i]),a.el=o.el),!n&&a.patchFlag!==-2&&tl(o,a)),a.type===ys&&(a.patchFlag===-1&&(a=s[i]=yt(a)),a.el=o.el),a.type===Re&&!a.el&&(a.el=o.el)}}function rd(e){const t=e.slice(),n=[0];let r,s,i,o,a;const c=e.length;for(r=0;r<c;r++){const l=e[r];if(l!==0){if(s=n[n.length-1],e[s]<l){t[r]=s,n.push(r);continue}for(i=0,o=n.length-1;i<o;)a=i+o>>1,e[n[a]]<l?i=a+1:o=a;l<e[n[i]]&&(i>0&&(t[r]=n[i-1]),n[i]=r)}}for(i=n.length,o=n[i-1];i-- >0;)n[i]=o,o=t[o];return n}function nl(e){const t=e.subTree.component;if(t)return t.asyncDep&&!t.asyncResolved?t:nl(t)}function wo(e){if(e)for(let t=0;t<e.length;t++)e[t].flags|=8}function rl(e){if(e.placeholder)return e.placeholder;const t=e.component;return t?rl(t.subTree):null}const sl=e=>e.__isSuspense;function sd(e,t){t&&t.pendingBranch?U(e)?t.effects.push(...e):t.effects.push(e):df(e)}const Te=Symbol.for("v-fgt"),ys=Symbol.for("v-txt"),Re=Symbol.for("v-cmt"),Mr=Symbol.for("v-stc"),tr=[];let Ve=null;function le(e=!1){tr.push(Ve=e?null:[])}function id(){tr.pop(),Ve=tr[tr.length-1]||null}let lr=1;function Jr(e,t=!1){lr+=e,e<0&&Ve&&t&&(Ve.hasOnce=!0)}function il(e){return e.dynamicChildren=lr>0?Ve||Sn:null,id(),lr>0&&Ve&&Ve.push(e),e}function Se(e,t,n,r,s,i){return il(W(e,t,n,r,s,i,!0))}function ut(e,t,n,r,s){return il(fe(e,t,n,r,s,!0))}function ur(e){return e?e.__v_isVNode===!0:!1}function cn(e,t){return e.type===t.type&&e.key===t.key}const ol=({key:e})=>e??null,Lr=({ref:e,ref_key:t,ref_for:n})=>(typeof e=="number"&&(e=""+e),e!=null?ge(e)||_e(e)||z(e)?{i:Ae,r:e,k:t,f:!!n}:e:null);function W(e,t=null,n=null,r=0,s=null,i=e===Te?0:1,o=!1,a=!1){const c={__v_isVNode:!0,__v_skip:!0,type:e,props:t,key:t&&ol(t),ref:t&&Lr(t),scopeId:Sc,slotScopeIds:null,children:n,component:null,suspense:null,ssContent:null,ssFallback:null,dirs:null,transition:null,el:null,anchor:null,target:null,targetStart:null,targetAnchor:null,staticCount:0,shapeFlag:i,patchFlag:r,dynamicProps:s,dynamicChildren:null,appContext:null,ctx:Ae};return a?(Fi(c,n),i&128&&e.normalize(c)):n&&(c.shapeFlag|=ge(n)?8:16),lr>0&&!o&&Ve&&(c.patchFlag>0||i&6)&&c.patchFlag!==32&&Ve.push(c),c}const fe=od;function od(e,t=null,n=null,r=0,s=null,i=!1){if((!e||e===Bc)&&(e=Re),ur(e)){const a=Yt(e,t,!0);return n&&Fi(a,n),lr>0&&!i&&Ve&&(a.shapeFlag&6?Ve[Ve.indexOf(e)]=a:Ve.push(a)),a.patchFlag=-2,a}if(_d(e)&&(e=e.__vccOpts),t){t=ad(t);let{class:a,style:c}=t;a&&!ge(a)&&(t.class=ln(a)),oe(c)&&(hs(c)&&!U(c)&&(c=Ee({},c)),t.style=fs(c))}const o=ge(e)?1:sl(e)?128:Cc(e)?64:oe(e)?4:z(e)?2:0;return W(e,t,n,r,s,o,i,!0)}function ad(e){return e?hs(e)||Jc(e)?Ee({},e):e:null}function Yt(e,t,n=!1,r=!1){const{props:s,ref:i,patchFlag:o,children:a,transition:c}=e,l=t?cd(s||{},t):s,u={__v_isVNode:!0,__v_skip:!0,type:e.type,props:l,key:l&&ol(l),ref:t&&t.ref?n&&i?U(i)?i.concat(Lr(t)):[i,Lr(t)]:Lr(t):i,scopeId:e.scopeId,slotScopeIds:e.slotScopeIds,children:a,target:e.target,targetStart:e.targetStart,targetAnchor:e.targetAnchor,staticCount:e.staticCount,shapeFlag:e.shapeFlag,patchFlag:t&&e.type!==Te?o===-1?16:o|16:o,dynamicProps:e.dynamicProps,dynamicChildren:e.dynamicChildren,appContext:e.appContext,dirs:e.dirs,transition:c,component:e.component,suspense:e.suspense,ssContent:e.ssContent&&Yt(e.ssContent),ssFallback:e.ssFallback&&Yt(e.ssFallback),placeholder:e.placeholder,el:e.el,anchor:e.anchor,ctx:e.ctx,ce:e.ce};return c&&r&&cr(u,c.clone(u)),u}function Ui(e=" ",t=0){return fe(ys,null,e,t)}function Xv(e,t){const n=fe(Mr,null,e);return n.staticCount=t,n}function In(e="",t=!1){return t?(le(),ut(Re,null,e)):fe(Re,null,e)}function ct(e){return e==null||typeof e=="boolean"?fe(Re):U(e)?fe(Te,null,e.slice()):ur(e)?yt(e):fe(ys,null,String(e))}function yt(e){return e.el===null&&e.patchFlag!==-1||e.memo?e:Yt(e)}function Fi(e,t){let n=0;const{shapeFlag:r}=e;if(t==null)t=null;else if(U(t))n=16;else if(typeof t=="object")if(r&65){const s=t.default;s&&(s._c&&(s._d=!1),Fi(e,s()),s._c&&(s._d=!0));return}else{n=32;const s=t._;!s&&!Jc(t)?t._ctx=Ae:s===3&&Ae&&(Ae.slots._===1?t._=1:(t._=2,e.patchFlag|=1024))}else z(t)?(t={default:t,_ctx:Ae},n=32):(t=String(t),r&64?(n=16,t=[Ui(t)]):n=8);e.children=t,e.shapeFlag|=n}function cd(...e){const t={};for(let n=0;n<e.length;n++){const r=e[n];for(const s in r)if(s==="class")t.class!==r.class&&(t.class=ln([t.class,r.class]));else if(s==="style")t.style=fs([t.style,r.style]);else if(ss(s)){const i=t[s],o=r[s];o&&i!==o&&!(U(i)&&i.includes(o))?t[s]=i?[].concat(i,o):o:o==null&&i==null&&!is(s)&&(t[s]=o)}else s!==""&&(t[s]=r[s])}return t}function st(e,t,n,r=null){Qe(e,t,7,[n,r])}const ld=Wc();let ud=0;function fd(e,t,n){const r=e.type,s=(t?t.appContext:e.appContext)||ld,i={uid:ud++,vnode:e,type:r,parent:t,appContext:s,root:null,next:null,subTree:null,effect:null,update:null,job:null,scope:new ec(!0),render:null,proxy:null,exposed:null,exposeProxy:null,withProxy:null,provides:t?t.provides:Object.create(s.provides),ids:t?t.ids:["",0,0],accessCache:null,renderCache:[],components:null,directives:null,propsOptions:Xc(r,s),emitsOptions:Kc(r,s),emit:null,emitted:null,propsDefaults:de,inheritAttrs:r.inheritAttrs,ctx:de,data:de,props:de,attrs:de,slots:de,refs:de,setupState:de,setupContext:null,suspense:n,suspenseId:n?n.pendingId:0,asyncDep:null,asyncResolved:!1,isMounted:!1,isUnmounted:!1,isDeactivated:!1,bc:null,c:null,bm:null,m:null,bu:null,u:null,um:null,bum:null,da:null,a:null,rtg:null,rtc:null,ec:null,sp:null};return i.ctx={_:i},i.root=t?t.root:i,i.emit=jf.bind(null,i),e.ce&&e.ce(i),i}let Pe=null;const Bi=()=>Pe||Ae;let Yr,ai;{const e=us(),t=(n,r)=>{let s;return(s=e[n])||(s=e[n]=[]),s.push(r),i=>{s.length>1?s.forEach(o=>o(i)):s[0](i)}};Yr=t("__VUE_INSTANCE_SETTERS__",n=>Pe=n),ai=t("__VUE_SSR_SETTERS__",n=>fr=n)}const Er=e=>{const t=Pe;return Yr(e),e.scope.on(),()=>{e.scope.off(),Yr(t)}},So=()=>{Pe&&Pe.scope.off(),Yr(null)};function al(e){return e.vnode.shapeFlag&4}let fr=!1;function dd(e,t=!1,n=!1){t&&ai(t);const{props:r,children:s}=e.vnode,i=al(e);qf(e,r,i,t),Qf(e,s,n||t);const o=i?hd(e,t):void 0;return t&&ai(!1),o}function hd(e,t){const n=e.type;e.accessCache=Object.create(null),e.proxy=new Proxy(e.ctx,xf);const{setup:r}=n;if(r){Pt();const s=e.setupContext=r.length>1?gd(e):null,i=Er(e),o=br(r,e,0,[e.props,s]),a=za(o);if(Ot(),i(),(a||e.sp)&&!Cn(e)&&Dc(e),a){if(o.then(So,So),t)return o.then(c=>{To(e,c)}).catch(c=>{ps(c,e,0)});e.asyncDep=o}else To(e,o)}else cl(e)}function To(e,t,n){z(t)?e.type.__ssrInlineRender?e.ssrRender=t:e.render=t:oe(t)&&(e.setupState=yc(t)),cl(e)}function cl(e,t,n){const r=e.type;e.render||(e.render=r.render||ft);{const s=Er(e);Pt();try{Df(e)}finally{Ot(),s()}}}const pd={get(e,t){return Ce(e,"get",""),e[t]}};function gd(e){const t=n=>{e.exposed=n||{}};return{attrs:new Proxy(e.attrs,pd),slots:e.slots,emit:e.emit,expose:t}}function bs(e){return e.exposed?e.exposeProxy||(e.exposeProxy=new Proxy(yc(Ni(e.exposed)),{get(t,n){if(n in t)return t[n];if(n in er)return er[n](e)},has(t,n){return n in t||n in er}})):e.proxy}function md(e,t=!0){return z(e)?e.displayName||e.name:e.name||t&&e.__name}function _d(e){return z(e)&&"__vccOpts"in e}const Fe=(e,t)=>af(e,t,fr);function xn(e,t,n){try{Jr(-1);const r=arguments.length;return r===2?oe(t)&&!U(t)?ur(t)?fe(e,null,[t]):fe(e,t):fe(e,null,t):(r>3?n=Array.prototype.slice.call(arguments,2):r===3&&ur(n)&&(n=[n]),fe(e,t,n))}finally{Jr(1)}}const vd="3.5.33";/**
* @vue/runtime-dom v3.5.33
* (c) 2018-present Yuxi (Evan) You and Vue contributors
* @license MIT
**/let ci;const Ao=typeof window<"u"&&window.trustedTypes;if(Ao)try{ci=Ao.createPolicy("vue",{createHTML:e=>e})}catch{}const ll=ci?e=>ci.createHTML(e):e=>e,yd="http://www.w3.org/2000/svg",bd="http://www.w3.org/1998/Math/MathML",vt=typeof document<"u"?document:null,Co=vt&&vt.createElement("template"),Ed={insert:(e,t,n)=>{t.insertBefore(e,n||null)},remove:e=>{const t=e.parentNode;t&&t.removeChild(e)},createElement:(e,t,n,r)=>{const s=t==="svg"?vt.createElementNS(yd,e):t==="mathml"?vt.createElementNS(bd,e):n?vt.createElement(e,{is:n}):vt.createElement(e);return e==="select"&&r&&r.multiple!=null&&s.setAttribute("multiple",r.multiple),s},createText:e=>vt.createTextNode(e),createComment:e=>vt.createComment(e),setText:(e,t)=>{e.nodeValue=t},setElementText:(e,t)=>{e.textContent=t},parentNode:e=>e.parentNode,nextSibling:e=>e.nextSibling,querySelector:e=>vt.querySelector(e),setScopeId(e,t){e.setAttribute(t,"")},insertStaticContent(e,t,n,r,s,i){const o=n?n.previousSibling:t.lastChild;if(s&&(s===i||s.nextSibling))for(;t.insertBefore(s.cloneNode(!0),n),!(s===i||!(s=s.nextSibling)););else{Co.innerHTML=ll(r==="svg"?`<svg>${e}</svg>`:r==="mathml"?`<math>${e}</math>`:e);const a=Co.content;if(r==="svg"||r==="mathml"){const c=a.firstChild;for(;c.firstChild;)a.appendChild(c.firstChild);a.removeChild(c)}t.insertBefore(a,n)}return[o?o.nextSibling:t.firstChild,n?n.previousSibling:t.lastChild]}},Lt="transition",Wn="animation",dr=Symbol("_vtc"),ul={name:String,type:String,css:{type:Boolean,default:!0},duration:[String,Number,Object],enterFromClass:String,enterActiveClass:String,enterToClass:String,appearFromClass:String,appearActiveClass:String,appearToClass:String,leaveFromClass:String,leaveActiveClass:String,leaveToClass:String},Id=Ee({},Rc,ul),wd=e=>(e.displayName="Transition",e.props=Id,e),fl=wd((e,{slots:t})=>xn(bf,Sd(e),t)),rn=(e,t=[])=>{U(e)?e.forEach(n=>n(...t)):e&&e(...t)},Ro=e=>e?U(e)?e.some(t=>t.length>1):e.length>1:!1;function Sd(e){const t={};for(const O in e)O in ul||(t[O]=e[O]);if(e.css===!1)return t;const{name:n="v",type:r,duration:s,enterFromClass:i=`${n}-enter-from`,enterActiveClass:o=`${n}-enter-active`,enterToClass:a=`${n}-enter-to`,appearFromClass:c=i,appearActiveClass:l=o,appearToClass:u=a,leaveFromClass:f=`${n}-leave-from`,leaveActiveClass:p=`${n}-leave-active`,leaveToClass:g=`${n}-leave-to`}=e,I=Td(s),w=I&&I[0],L=I&&I[1],{onBeforeEnter:M,onEnter:A,onEnterCancelled:x,onLeave:N,onLeaveCancelled:H,onBeforeAppear:te=M,onAppear:J=A,onAppearCancelled:G=x}=t,C=(O,X,ve,Oe)=>{O._enterCancelled=Oe,sn(O,X?u:a),sn(O,X?l:o),ve&&ve()},j=(O,X)=>{O._isLeaving=!1,sn(O,f),sn(O,g),sn(O,p),X&&X()},Z=O=>(X,ve)=>{const Oe=O?J:A,ae=()=>C(X,O,ve);rn(Oe,[X,ae]),Po(()=>{sn(X,O?c:i),mt(X,O?u:a),Ro(Oe)||Oo(X,r,w,ae)})};return Ee(t,{onBeforeEnter(O){rn(M,[O]),mt(O,i),mt(O,o)},onBeforeAppear(O){rn(te,[O]),mt(O,c),mt(O,l)},onEnter:Z(!1),onAppear:Z(!0),onLeave(O,X){O._isLeaving=!0;const ve=()=>j(O,X);mt(O,f),O._enterCancelled?(mt(O,p),xo(O)):(xo(O),mt(O,p)),Po(()=>{O._isLeaving&&(sn(O,f),mt(O,g),Ro(N)||Oo(O,r,L,ve))}),rn(N,[O,ve])},onEnterCancelled(O){C(O,!1,void 0,!0),rn(x,[O])},onAppearCancelled(O){C(O,!0,void 0,!0),rn(G,[O])},onLeaveCancelled(O){j(O),rn(H,[O])}})}function Td(e){if(e==null)return null;if(oe(e))return[Ls(e.enter),Ls(e.leave)];{const t=Ls(e);return[t,t]}}function Ls(e){return Tu(e)}function mt(e,t){t.split(/\s+/).forEach(n=>n&&e.classList.add(n)),(e[dr]||(e[dr]=new Set)).add(t)}function sn(e,t){t.split(/\s+/).forEach(r=>r&&e.classList.remove(r));const n=e[dr];n&&(n.delete(t),n.size||(e[dr]=void 0))}function Po(e){requestAnimationFrame(()=>{requestAnimationFrame(e)})}let Ad=0;function Oo(e,t,n,r){const s=e._endId=++Ad,i=()=>{s===e._endId&&r()};if(n!=null)return setTimeout(i,n);const{type:o,timeout:a,propCount:c}=Cd(e,t);if(!o)return r();const l=o+"end";let u=0;const f=()=>{e.removeEventListener(l,p),i()},p=g=>{g.target===e&&++u>=c&&f()};setTimeout(()=>{u<c&&f()},a+1),e.addEventListener(l,p)}function Cd(e,t){const n=window.getComputedStyle(e),r=I=>(n[I]||"").split(", "),s=r(`${Lt}Delay`),i=r(`${Lt}Duration`),o=ko(s,i),a=r(`${Wn}Delay`),c=r(`${Wn}Duration`),l=ko(a,c);let u=null,f=0,p=0;t===Lt?o>0&&(u=Lt,f=o,p=i.length):t===Wn?l>0&&(u=Wn,f=l,p=c.length):(f=Math.max(o,l),u=f>0?o>l?Lt:Wn:null,p=u?u===Lt?i.length:c.length:0);const g=u===Lt&&/\b(?:transform|all)(?:,|$)/.test(r(`${Lt}Property`).toString());return{type:u,timeout:f,propCount:p,hasTransform:g}}function ko(e,t){for(;e.length<t.length;)e=e.concat(e);return Math.max(...t.map((n,r)=>No(n)+No(e[r])))}function No(e){return e==="auto"?0:Number(e.slice(0,-1).replace(",","."))*1e3}function xo(e){return(e?e.ownerDocument:document).body.offsetHeight}function Rd(e,t,n){const r=e[dr];r&&(t=(t?[t,...r]:[...r]).join(" ")),t==null?e.removeAttribute("class"):n?e.setAttribute("class",t):e.className=t}const Do=Symbol("_vod"),Pd=Symbol("_vsh"),Od=Symbol(""),kd=/(?:^|;)\s*display\s*:/;function Nd(e,t,n){const r=e.style,s=ge(n);let i=!1;if(n&&!s){if(t)if(ge(t))for(const o of t.split(";")){const a=o.slice(0,o.indexOf(":")).trim();n[a]==null&&qn(r,a,"")}else for(const o in t)n[o]==null&&qn(r,o,"");for(const o in n){o==="display"&&(i=!0);const a=n[o];a!=null?Dd(e,o,!ge(t)&&t?t[o]:void 0,a)||qn(r,o,a):qn(r,o,"")}}else if(s){if(t!==n){const o=r[Od];o&&(n+=";"+o),r.cssText=n,i=kd.test(n)}}else t&&e.removeAttribute("style");Do in e&&(e[Do]=i?r.display:"",e[Pd]&&(r.display="none"))}const Mo=/\s*!important$/;function qn(e,t,n){if(U(n))n.forEach(r=>qn(e,t,r));else if(n==null&&(n=""),t.startsWith("--"))e.setProperty(t,n);else{const r=xd(e,t);Mo.test(n)?e.setProperty(mn(r),n.replace(Mo,""),"important"):e[r]=n}}const Lo=["Webkit","Moz","ms"],Us={};function xd(e,t){const n=Us[t];if(n)return n;let r=De(t);if(r!=="filter"&&r in e)return Us[t]=r;r=cs(r);for(let s=0;s<Lo.length;s++){const i=Lo[s]+r;if(i in e)return Us[t]=i}return t}function Dd(e,t,n,r){return e.tagName==="TEXTAREA"&&(t==="width"||t==="height")&&ge(r)&&n===r}const Uo="http://www.w3.org/1999/xlink";function Fo(e,t,n,r,s,i=ku(t)){r&&t.startsWith("xlink:")?n==null?e.removeAttributeNS(Uo,t.slice(6,t.length)):e.setAttributeNS(Uo,t,n):n==null||i&&!Xa(n)?e.removeAttribute(t):e.setAttribute(t,i?"":je(n)?String(n):n)}function Bo(e,t,n,r,s){if(t==="innerHTML"||t==="textContent"){n!=null&&(e[t]=t==="innerHTML"?ll(n):n);return}const i=e.tagName;if(t==="value"&&i!=="PROGRESS"&&!i.includes("-")){const a=i==="OPTION"?e.getAttribute("value")||"":e.value,c=n==null?e.type==="checkbox"?"on":"":String(n);(a!==c||!("_value"in e))&&(e.value=c),n==null&&e.removeAttribute(t),e._value=n;return}let o=!1;if(n===""||n==null){const a=typeof e[t];a==="boolean"?n=Xa(n):n==null&&a==="string"?(n="",o=!0):a==="number"&&(n=0,o=!0)}try{e[t]=n}catch{}o&&e.removeAttribute(s||t)}function It(e,t,n,r){e.addEventListener(t,n,r)}function Md(e,t,n,r){e.removeEventListener(t,n,r)}const Vo=Symbol("_vei");function Ld(e,t,n,r,s=null){const i=e[Vo]||(e[Vo]={}),o=i[t];if(r&&o)o.value=r;else{const[a,c]=Ud(t);if(r){const l=i[t]=Vd(r,s);It(e,a,l,c)}else o&&(Md(e,a,o,c),i[t]=void 0)}}const Ho=/(?:Once|Passive|Capture)$/;function Ud(e){let t;if(Ho.test(e)){t={};let r;for(;r=e.match(Ho);)e=e.slice(0,e.length-r[0].length),t[r[0].toLowerCase()]=!0}return[e[2]===":"?e.slice(3):mn(e.slice(2)),t]}let Fs=0;const Fd=Promise.resolve(),Bd=()=>Fs||(Fd.then(()=>Fs=0),Fs=Date.now());function Vd(e,t){const n=r=>{if(!r._vts)r._vts=Date.now();else if(r._vts<=n.attached)return;Qe(Hd(r,n.value),t,5,[r])};return n.value=e,n.attached=Bd(),n}function Hd(e,t){if(U(t)){const n=e.stopImmediatePropagation;return e.stopImmediatePropagation=()=>{n.call(e),e._stopped=!0},t.map(r=>s=>!s._stopped&&r&&r(s))}else return t}const jo=e=>e.charCodeAt(0)===111&&e.charCodeAt(1)===110&&e.charCodeAt(2)>96&&e.charCodeAt(2)<123,jd=(e,t,n,r,s,i)=>{const o=s==="svg";t==="class"?Rd(e,r,o):t==="style"?Nd(e,n,r):ss(t)?is(t)||Ld(e,t,n,r,i):(t[0]==="."?(t=t.slice(1),!0):t[0]==="^"?(t=t.slice(1),!1):$d(e,t,r,o))?(Bo(e,t,r),!e.tagName.includes("-")&&(t==="value"||t==="checked"||t==="selected")&&Fo(e,t,r,o,i,t!=="value")):e._isVueCE&&(Wd(e,t)||e._def.__asyncLoader&&(/[A-Z]/.test(t)||!ge(r)))?Bo(e,De(t),r,i,t):(t==="true-value"?e._trueValue=r:t==="false-value"&&(e._falseValue=r),Fo(e,t,r,o))};function $d(e,t,n,r){if(r)return!!(t==="innerHTML"||t==="textContent"||t in e&&jo(t)&&z(n));if(t==="spellcheck"||t==="draggable"||t==="translate"||t==="autocorrect"||t==="sandbox"&&e.tagName==="IFRAME"||t==="form"||t==="list"&&e.tagName==="INPUT"||t==="type"&&e.tagName==="TEXTAREA")return!1;if(t==="width"||t==="height"){const s=e.tagName;if(s==="IMG"||s==="VIDEO"||s==="CANVAS"||s==="SOURCE")return!1}return jo(t)&&ge(n)?!1:t in e}function Wd(e,t){const n=e._def.props;if(!n)return!1;const r=De(t);return Array.isArray(n)?n.some(s=>De(s)===r):Object.keys(n).some(s=>De(s)===r)}const Xt=e=>{const t=e.props["onUpdate:modelValue"]||!1;return U(t)?n=>xr(t,n):t};function Kd(e){e.target.composing=!0}function $o(e){const t=e.target;t.composing&&(t.composing=!1,t.dispatchEvent(new Event("input")))}const qe=Symbol("_assign");function Wo(e,t,n){return t&&(e=e.trim()),n&&(e=ls(e)),e}const Qv={created(e,{modifiers:{lazy:t,trim:n,number:r}},s){e[qe]=Xt(s);const i=r||s.props&&s.props.type==="number";It(e,t?"change":"input",o=>{o.target.composing||e[qe](Wo(e.value,n,i))}),(n||i)&&It(e,"change",()=>{e.value=Wo(e.value,n,i)}),t||(It(e,"compositionstart",Kd),It(e,"compositionend",$o),It(e,"change",$o))},mounted(e,{value:t}){e.value=t??""},beforeUpdate(e,{value:t,oldValue:n,modifiers:{lazy:r,trim:s,number:i}},o){if(e[qe]=Xt(o),e.composing)return;const a=(i||e.type==="number")&&!/^0\d/.test(e.value)?ls(e.value):e.value,c=t??"";if(a===c)return;const l=e.getRootNode();(l instanceof Document||l instanceof ShadowRoot)&&l.activeElement===e&&e.type!=="range"&&(r&&t===n||s&&e.value.trim()===c)||(e.value=c)}},Zv={deep:!0,created(e,t,n){e[qe]=Xt(n),It(e,"change",()=>{const r=e._modelValue,s=Dn(e),i=e.checked,o=e[qe];if(U(r)){const a=Ti(r,s),c=a!==-1;if(i&&!c)o(r.concat(s));else if(!i&&c){const l=[...r];l.splice(a,1),o(l)}}else if(Bn(r)){const a=new Set(r);i?a.add(s):a.delete(s),o(a)}else o(dl(e,i))})},mounted:Ko,beforeUpdate(e,t,n){e[qe]=Xt(n),Ko(e,t,n)}};function Ko(e,{value:t,oldValue:n},r){e._modelValue=t;let s;if(U(t))s=Ti(t,r.props.value)>-1;else if(Bn(t))s=t.has(r.props.value);else{if(t===n)return;s=Jt(t,dl(e,!0))}e.checked!==s&&(e.checked=s)}const ey={created(e,{value:t},n){e.checked=Jt(t,n.props.value),e[qe]=Xt(n),It(e,"change",()=>{e[qe](Dn(e))})},beforeUpdate(e,{value:t,oldValue:n},r){e[qe]=Xt(r),t!==n&&(e.checked=Jt(t,r.props.value))}},ty={deep:!0,created(e,{value:t,modifiers:{number:n}},r){const s=Bn(t);It(e,"change",()=>{const i=Array.prototype.filter.call(e.options,o=>o.selected).map(o=>n?ls(Dn(o)):Dn(o));e[qe](e.multiple?s?new Set(i):i:i[0]),e._assigning=!0,gs(()=>{e._assigning=!1})}),e[qe]=Xt(r)},mounted(e,{value:t}){Go(e,t)},beforeUpdate(e,t,n){e[qe]=Xt(n)},updated(e,{value:t}){e._assigning||Go(e,t)}};function Go(e,t){const n=e.multiple,r=U(t);if(!(n&&!r&&!Bn(t))){for(let s=0,i=e.options.length;s<i;s++){const o=e.options[s],a=Dn(o);if(n)if(r){const c=typeof a;c==="string"||c==="number"?o.selected=t.some(l=>String(l)===String(a)):o.selected=Ti(t,a)>-1}else o.selected=t.has(a);else if(Jt(Dn(o),t)){e.selectedIndex!==s&&(e.selectedIndex=s);return}}!n&&e.selectedIndex!==-1&&(e.selectedIndex=-1)}}function Dn(e){return"_value"in e?e._value:e.value}function dl(e,t){const n=t?"_trueValue":"_falseValue";return n in e?e[n]:t}const Gd=["ctrl","shift","alt","meta"],zd={stop:e=>e.stopPropagation(),prevent:e=>e.preventDefault(),self:e=>e.target!==e.currentTarget,ctrl:e=>!e.ctrlKey,shift:e=>!e.shiftKey,alt:e=>!e.altKey,meta:e=>!e.metaKey,left:e=>"button"in e&&e.button!==0,middle:e=>"button"in e&&e.button!==1,right:e=>"button"in e&&e.button!==2,exact:(e,t)=>Gd.some(n=>e[`${n}Key`]&&!t.includes(n))},ny=(e,t)=>{if(!e)return e;const n=e._withMods||(e._withMods={}),r=t.join(".");return n[r]||(n[r]=(s,...i)=>{for(let o=0;o<t.length;o++){const a=zd[t[o]];if(a&&a(s,t))return}return e(s,...i)})},qd=Ee({patchProp:jd},Ed);let zo;function Jd(){return zo||(zo=ed(qd))}const Yd=(...e)=>{const t=Jd().createApp(...e),{mount:n}=t;return t.mount=r=>{const s=Qd(r);if(!s)return;const i=t._component;!z(i)&&!i.render&&!i.template&&(i.template=s.innerHTML),s.nodeType===1&&(s.textContent="");const o=n(s,!1,Xd(s));return s instanceof Element&&(s.removeAttribute("v-cloak"),s.setAttribute("data-v-app","")),o},t};function Xd(e){if(e instanceof SVGElement)return"svg";if(typeof MathMLElement=="function"&&e instanceof MathMLElement)return"mathml"}function Qd(e){return ge(e)?document.querySelector(e):e}/*!
 * pinia v2.3.1
 * (c) 2025 Eduardo San Martin Morote
 * @license MIT
 */let hl;const Es=e=>hl=e,pl=Symbol();function li(e){return e&&typeof e=="object"&&Object.prototype.toString.call(e)==="[object Object]"&&typeof e.toJSON!="function"}var nr;(function(e){e.direct="direct",e.patchObject="patch object",e.patchFunction="patch function"})(nr||(nr={}));function Zd(){const e=tc(!0),t=e.run(()=>$r({}));let n=[],r=[];const s=Ni({install(i){Es(s),s._a=i,i.provide(pl,s),i.config.globalProperties.$pinia=s,r.forEach(o=>n.push(o)),r=[]},use(i){return this._a?n.push(i):r.push(i),this},_p:n,_a:null,_e:e,_s:new Map,state:t});return s}const gl=()=>{};function qo(e,t,n,r=gl){e.push(t);const s=()=>{const i=e.indexOf(t);i>-1&&(e.splice(i,1),r())};return!n&&nc()&&xu(s),s}function bn(e,...t){e.slice().forEach(n=>{n(...t)})}const eh=e=>e(),Jo=Symbol(),Bs=Symbol();function ui(e,t){e instanceof Map&&t instanceof Map?t.forEach((n,r)=>e.set(r,n)):e instanceof Set&&t instanceof Set&&t.forEach(e.add,e);for(const n in t){if(!t.hasOwnProperty(n))continue;const r=t[n],s=e[n];li(s)&&li(r)&&e.hasOwnProperty(n)&&!_e(r)&&!Rt(r)?e[n]=ui(s,r):e[n]=r}return e}const th=Symbol();function nh(e){return!li(e)||!e.hasOwnProperty(th)}const{assign:Vt}=Object;function rh(e){return!!(_e(e)&&e.effect)}function sh(e,t,n,r){const{state:s,actions:i,getters:o}=t,a=n.state.value[e];let c;function l(){a||(n.state.value[e]=s?s():{});const u=nf(n.state.value[e]);return Vt(u,i,Object.keys(o||{}).reduce((f,p)=>(f[p]=Ni(Fe(()=>{Es(n);const g=n._s.get(e);return o[p].call(g,g)})),f),{}))}return c=ml(e,l,t,n,r,!0),c}function ml(e,t,n={},r,s,i){let o;const a=Vt({actions:{}},n),c={deep:!0};let l,u,f=[],p=[],g;const I=r.state.value[e];!i&&!I&&(r.state.value[e]={});let w;function L(G){let C;l=u=!1,typeof G=="function"?(G(r.state.value[e]),C={type:nr.patchFunction,storeId:e,events:g}):(ui(r.state.value[e],G),C={type:nr.patchObject,payload:G,storeId:e,events:g});const j=w=Symbol();gs().then(()=>{w===j&&(l=!0)}),u=!0,bn(f,C,r.state.value[e])}const M=i?function(){const{state:C}=n,j=C?C():{};this.$patch(Z=>{Vt(Z,j)})}:gl;function A(){o.stop(),f=[],p=[],r._s.delete(e)}const x=(G,C="")=>{if(Jo in G)return G[Bs]=C,G;const j=function(){Es(r);const Z=Array.from(arguments),O=[],X=[];function ve(q){O.push(q)}function Oe(q){X.push(q)}bn(p,{args:Z,name:j[Bs],store:H,after:ve,onError:Oe});let ae;try{ae=G.apply(this&&this.$id===e?this:H,Z)}catch(q){throw bn(X,q),q}return ae instanceof Promise?ae.then(q=>(bn(O,q),q)).catch(q=>(bn(X,q),Promise.reject(q))):(bn(O,ae),ae)};return j[Jo]=!0,j[Bs]=C,j},N={_p:r,$id:e,$onAction:qo.bind(null,p),$patch:L,$reset:M,$subscribe(G,C={}){const j=qo(f,G,C.detached,()=>Z()),Z=o.run(()=>Qn(()=>r.state.value[e],O=>{(C.flush==="sync"?u:l)&&G({storeId:e,type:nr.direct,events:g},O)},Vt({},c,C)));return j},$dispose:A},H=yr(N);r._s.set(e,H);const J=(r._a&&r._a.runWithContext||eh)(()=>r._e.run(()=>(o=tc()).run(()=>t({action:x}))));for(const G in J){const C=J[G];if(_e(C)&&!rh(C)||Rt(C))i||(I&&nh(C)&&(_e(C)?C.value=I[G]:ui(C,I[G])),r.state.value[e][G]=C);else if(typeof C=="function"){const j=x(C,G);J[G]=j,a.actions[G]=C}}return Vt(H,J),Vt(ee(H),J),Object.defineProperty(H,"$state",{get:()=>r.state.value[e],set:G=>{L(C=>{Vt(C,G)})}}),r._p.forEach(G=>{Vt(H,o.run(()=>G({store:H,app:r._a,pinia:r,options:a})))}),I&&i&&n.hydrate&&n.hydrate(H.$state,I),l=!0,u=!0,H}/*! #__NO_SIDE_EFFECTS__ */function ih(e,t,n){let r,s;const i=typeof t=="function";typeof e=="string"?(r=e,s=i?n:t):(s=e,r=e.id);function o(a,c){const l=hf();return a=a||(l?ze(pl,null):null),a&&Es(a),a=hl,a._s.has(r)||(i?ml(r,t,s,a):sh(r,s,a)),a._s.get(r)}return o.$id=r,o}/*!
 * vue-router v4.6.4
 * (c) 2025 Eduardo San Martin Morote
 * @license MIT
 */const wn=typeof document<"u";function _l(e){return typeof e=="object"||"displayName"in e||"props"in e||"__vccOpts"in e}function oh(e){return e.__esModule||e[Symbol.toStringTag]==="Module"||e.default&&_l(e.default)}const se=Object.assign;function Vs(e,t){const n={};for(const r in t){const s=t[r];n[r]=Ze(s)?s.map(e):e(s)}return n}const rr=()=>{},Ze=Array.isArray;function Yo(e,t){const n={};for(const r in e)n[r]=r in t?t[r]:e[r];return n}const vl=/#/g,ah=/&/g,ch=/\//g,lh=/=/g,uh=/\?/g,yl=/\+/g,fh=/%5B/g,dh=/%5D/g,bl=/%5E/g,hh=/%60/g,El=/%7B/g,ph=/%7C/g,Il=/%7D/g,gh=/%20/g;function Vi(e){return e==null?"":encodeURI(""+e).replace(ph,"|").replace(fh,"[").replace(dh,"]")}function mh(e){return Vi(e).replace(El,"{").replace(Il,"}").replace(bl,"^")}function fi(e){return Vi(e).replace(yl,"%2B").replace(gh,"+").replace(vl,"%23").replace(ah,"%26").replace(hh,"`").replace(El,"{").replace(Il,"}").replace(bl,"^")}function _h(e){return fi(e).replace(lh,"%3D")}function vh(e){return Vi(e).replace(vl,"%23").replace(uh,"%3F")}function yh(e){return vh(e).replace(ch,"%2F")}function hr(e){if(e==null)return null;try{return decodeURIComponent(""+e)}catch{}return""+e}const bh=/\/$/,Eh=e=>e.replace(bh,"");function Hs(e,t,n="/"){let r,s={},i="",o="";const a=t.indexOf("#");let c=t.indexOf("?");return c=a>=0&&c>a?-1:c,c>=0&&(r=t.slice(0,c),i=t.slice(c,a>0?a:t.length),s=e(i.slice(1))),a>=0&&(r=r||t.slice(0,a),o=t.slice(a,t.length)),r=Th(r??t,n),{fullPath:r+i+o,path:r,query:s,hash:hr(o)}}function Ih(e,t){const n=t.query?e(t.query):"";return t.path+(n&&"?")+n+(t.hash||"")}function Xo(e,t){return!t||!e.toLowerCase().startsWith(t.toLowerCase())?e:e.slice(t.length)||"/"}function wh(e,t,n){const r=t.matched.length-1,s=n.matched.length-1;return r>-1&&r===s&&Mn(t.matched[r],n.matched[s])&&wl(t.params,n.params)&&e(t.query)===e(n.query)&&t.hash===n.hash}function Mn(e,t){return(e.aliasOf||e)===(t.aliasOf||t)}function wl(e,t){if(Object.keys(e).length!==Object.keys(t).length)return!1;for(var n in e)if(!Sh(e[n],t[n]))return!1;return!0}function Sh(e,t){return Ze(e)?Qo(e,t):Ze(t)?Qo(t,e):e?.valueOf()===t?.valueOf()}function Qo(e,t){return Ze(t)?e.length===t.length&&e.every((n,r)=>n===t[r]):e.length===1&&e[0]===t}function Th(e,t){if(e.startsWith("/"))return e;if(!e)return t;const n=t.split("/"),r=e.split("/"),s=r[r.length-1];(s===".."||s===".")&&r.push("");let i=n.length-1,o,a;for(o=0;o<r.length;o++)if(a=r[o],a!==".")if(a==="..")i>1&&i--;else break;return n.slice(0,i).join("/")+"/"+r.slice(o).join("/")}const Ut={path:"/",name:void 0,params:{},query:{},hash:"",fullPath:"/",matched:[],meta:{},redirectedFrom:void 0};let di=function(e){return e.pop="pop",e.push="push",e}({}),js=function(e){return e.back="back",e.forward="forward",e.unknown="",e}({});function Ah(e){if(!e)if(wn){const t=document.querySelector("base");e=t&&t.getAttribute("href")||"/",e=e.replace(/^\w+:\/\/[^\/]+/,"")}else e="/";return e[0]!=="/"&&e[0]!=="#"&&(e="/"+e),Eh(e)}const Ch=/^[^#]+#/;function Rh(e,t){return e.replace(Ch,"#")+t}function Ph(e,t){const n=document.documentElement.getBoundingClientRect(),r=e.getBoundingClientRect();return{behavior:t.behavior,left:r.left-n.left-(t.left||0),top:r.top-n.top-(t.top||0)}}const Is=()=>({left:window.scrollX,top:window.scrollY});function Oh(e){let t;if("el"in e){const n=e.el,r=typeof n=="string"&&n.startsWith("#"),s=typeof n=="string"?r?document.getElementById(n.slice(1)):document.querySelector(n):n;if(!s)return;t=Ph(s,e)}else t=e;"scrollBehavior"in document.documentElement.style?window.scrollTo(t):window.scrollTo(t.left!=null?t.left:window.scrollX,t.top!=null?t.top:window.scrollY)}function Zo(e,t){return(history.state?history.state.position-t:-1)+e}const hi=new Map;function kh(e,t){hi.set(e,t)}function Nh(e){const t=hi.get(e);return hi.delete(e),t}function xh(e){return typeof e=="string"||e&&typeof e=="object"}function Sl(e){return typeof e=="string"||typeof e=="symbol"}let me=function(e){return e[e.MATCHER_NOT_FOUND=1]="MATCHER_NOT_FOUND",e[e.NAVIGATION_GUARD_REDIRECT=2]="NAVIGATION_GUARD_REDIRECT",e[e.NAVIGATION_ABORTED=4]="NAVIGATION_ABORTED",e[e.NAVIGATION_CANCELLED=8]="NAVIGATION_CANCELLED",e[e.NAVIGATION_DUPLICATED=16]="NAVIGATION_DUPLICATED",e}({});const Tl=Symbol("");me.MATCHER_NOT_FOUND+"",me.NAVIGATION_GUARD_REDIRECT+"",me.NAVIGATION_ABORTED+"",me.NAVIGATION_CANCELLED+"",me.NAVIGATION_DUPLICATED+"";function Ln(e,t){return se(new Error,{type:e,[Tl]:!0},t)}function _t(e,t){return e instanceof Error&&Tl in e&&(t==null||!!(e.type&t))}const Dh=["params","query","hash"];function Mh(e){if(typeof e=="string")return e;if(e.path!=null)return e.path;const t={};for(const n of Dh)n in e&&(t[n]=e[n]);return JSON.stringify(t,null,2)}function Lh(e){const t={};if(e===""||e==="?")return t;const n=(e[0]==="?"?e.slice(1):e).split("&");for(let r=0;r<n.length;++r){const s=n[r].replace(yl," "),i=s.indexOf("="),o=hr(i<0?s:s.slice(0,i)),a=i<0?null:hr(s.slice(i+1));if(o in t){let c=t[o];Ze(c)||(c=t[o]=[c]),c.push(a)}else t[o]=a}return t}function ea(e){let t="";for(let n in e){const r=e[n];if(n=_h(n),r==null){r!==void 0&&(t+=(t.length?"&":"")+n);continue}(Ze(r)?r.map(s=>s&&fi(s)):[r&&fi(r)]).forEach(s=>{s!==void 0&&(t+=(t.length?"&":"")+n,s!=null&&(t+="="+s))})}return t}function Uh(e){const t={};for(const n in e){const r=e[n];r!==void 0&&(t[n]=Ze(r)?r.map(s=>s==null?null:""+s):r==null?r:""+r)}return t}const Fh=Symbol(""),ta=Symbol(""),ws=Symbol(""),Hi=Symbol(""),pi=Symbol("");function Kn(){let e=[];function t(r){return e.push(r),()=>{const s=e.indexOf(r);s>-1&&e.splice(s,1)}}function n(){e=[]}return{add:t,list:()=>e.slice(),reset:n}}function jt(e,t,n,r,s,i=o=>o()){const o=r&&(r.enterCallbacks[s]=r.enterCallbacks[s]||[]);return()=>new Promise((a,c)=>{const l=p=>{p===!1?c(Ln(me.NAVIGATION_ABORTED,{from:n,to:t})):p instanceof Error?c(p):xh(p)?c(Ln(me.NAVIGATION_GUARD_REDIRECT,{from:t,to:p})):(o&&r.enterCallbacks[s]===o&&typeof p=="function"&&o.push(p),a())},u=i(()=>e.call(r&&r.instances[s],t,n,l));let f=Promise.resolve(u);e.length<3&&(f=f.then(l)),f.catch(p=>c(p))})}function $s(e,t,n,r,s=i=>i()){const i=[];for(const o of e)for(const a in o.components){let c=o.components[a];if(!(t!=="beforeRouteEnter"&&!o.instances[a]))if(_l(c)){const l=(c.__vccOpts||c)[t];l&&i.push(jt(l,n,r,o,a,s))}else{let l=c();i.push(()=>l.then(u=>{if(!u)throw new Error(`Couldn't resolve component "${a}" at "${o.path}"`);const f=oh(u)?u.default:u;o.mods[a]=u,o.components[a]=f;const p=(f.__vccOpts||f)[t];return p&&jt(p,n,r,o,a,s)()}))}}return i}function Bh(e,t){const n=[],r=[],s=[],i=Math.max(t.matched.length,e.matched.length);for(let o=0;o<i;o++){const a=t.matched[o];a&&(e.matched.find(l=>Mn(l,a))?r.push(a):n.push(a));const c=e.matched[o];c&&(t.matched.find(l=>Mn(l,c))||s.push(c))}return[n,r,s]}/*!
 * vue-router v4.6.4
 * (c) 2025 Eduardo San Martin Morote
 * @license MIT
 */let Vh=()=>location.protocol+"//"+location.host;function Al(e,t){const{pathname:n,search:r,hash:s}=t,i=e.indexOf("#");if(i>-1){let o=s.includes(e.slice(i))?e.slice(i).length:1,a=s.slice(o);return a[0]!=="/"&&(a="/"+a),Xo(a,"")}return Xo(n,e)+r+s}function Hh(e,t,n,r){let s=[],i=[],o=null;const a=({state:p})=>{const g=Al(e,location),I=n.value,w=t.value;let L=0;if(p){if(n.value=g,t.value=p,o&&o===I){o=null;return}L=w?p.position-w.position:0}else r(g);s.forEach(M=>{M(n.value,I,{delta:L,type:di.pop,direction:L?L>0?js.forward:js.back:js.unknown})})};function c(){o=n.value}function l(p){s.push(p);const g=()=>{const I=s.indexOf(p);I>-1&&s.splice(I,1)};return i.push(g),g}function u(){if(document.visibilityState==="hidden"){const{history:p}=window;if(!p.state)return;p.replaceState(se({},p.state,{scroll:Is()}),"")}}function f(){for(const p of i)p();i=[],window.removeEventListener("popstate",a),window.removeEventListener("pagehide",u),document.removeEventListener("visibilitychange",u)}return window.addEventListener("popstate",a),window.addEventListener("pagehide",u),document.addEventListener("visibilitychange",u),{pauseListeners:c,listen:l,destroy:f}}function na(e,t,n,r=!1,s=!1){return{back:e,current:t,forward:n,replaced:r,position:window.history.length,scroll:s?Is():null}}function jh(e){const{history:t,location:n}=window,r={value:Al(e,n)},s={value:t.state};s.value||i(r.value,{back:null,current:r.value,forward:null,position:t.length-1,replaced:!0,scroll:null},!0);function i(c,l,u){const f=e.indexOf("#"),p=f>-1?(n.host&&document.querySelector("base")?e:e.slice(f))+c:Vh()+e+c;try{t[u?"replaceState":"pushState"](l,"",p),s.value=l}catch(g){console.error(g),n[u?"replace":"assign"](p)}}function o(c,l){i(c,se({},t.state,na(s.value.back,c,s.value.forward,!0),l,{position:s.value.position}),!0),r.value=c}function a(c,l){const u=se({},s.value,t.state,{forward:c,scroll:Is()});i(u.current,u,!0),i(c,se({},na(r.value,c,null),{position:u.position+1},l),!1),r.value=c}return{location:r,state:s,push:a,replace:o}}function $h(e){e=Ah(e);const t=jh(e),n=Hh(e,t.state,t.location,t.replace);function r(i,o=!0){o||n.pauseListeners(),history.go(i)}const s=se({location:"",base:e,go:r,createHref:Rh.bind(null,e)},t,n);return Object.defineProperty(s,"location",{enumerable:!0,get:()=>t.location.value}),Object.defineProperty(s,"state",{enumerable:!0,get:()=>t.state.value}),s}let un=function(e){return e[e.Static=0]="Static",e[e.Param=1]="Param",e[e.Group=2]="Group",e}({});var be=function(e){return e[e.Static=0]="Static",e[e.Param=1]="Param",e[e.ParamRegExp=2]="ParamRegExp",e[e.ParamRegExpEnd=3]="ParamRegExpEnd",e[e.EscapeNext=4]="EscapeNext",e}(be||{});const Wh={type:un.Static,value:""},Kh=/[a-zA-Z0-9_]/;function Gh(e){if(!e)return[[]];if(e==="/")return[[Wh]];if(!e.startsWith("/"))throw new Error(`Invalid path "${e}"`);function t(g){throw new Error(`ERR (${n})/"${l}": ${g}`)}let n=be.Static,r=n;const s=[];let i;function o(){i&&s.push(i),i=[]}let a=0,c,l="",u="";function f(){l&&(n===be.Static?i.push({type:un.Static,value:l}):n===be.Param||n===be.ParamRegExp||n===be.ParamRegExpEnd?(i.length>1&&(c==="*"||c==="+")&&t(`A repeatable param (${l}) must be alone in its segment. eg: '/:ids+.`),i.push({type:un.Param,value:l,regexp:u,repeatable:c==="*"||c==="+",optional:c==="*"||c==="?"})):t("Invalid state to consume buffer"),l="")}function p(){l+=c}for(;a<e.length;){if(c=e[a++],c==="\\"&&n!==be.ParamRegExp){r=n,n=be.EscapeNext;continue}switch(n){case be.Static:c==="/"?(l&&f(),o()):c===":"?(f(),n=be.Param):p();break;case be.EscapeNext:p(),n=r;break;case be.Param:c==="("?n=be.ParamRegExp:Kh.test(c)?p():(f(),n=be.Static,c!=="*"&&c!=="?"&&c!=="+"&&a--);break;case be.ParamRegExp:c===")"?u[u.length-1]=="\\"?u=u.slice(0,-1)+c:n=be.ParamRegExpEnd:u+=c;break;case be.ParamRegExpEnd:f(),n=be.Static,c!=="*"&&c!=="?"&&c!=="+"&&a--,u="";break;default:t("Unknown state");break}}return n===be.ParamRegExp&&t(`Unfinished custom RegExp for param "${l}"`),f(),o(),s}const ra="[^/]+?",zh={sensitive:!1,strict:!1,start:!0,end:!0};var Ne=function(e){return e[e._multiplier=10]="_multiplier",e[e.Root=90]="Root",e[e.Segment=40]="Segment",e[e.SubSegment=30]="SubSegment",e[e.Static=40]="Static",e[e.Dynamic=20]="Dynamic",e[e.BonusCustomRegExp=10]="BonusCustomRegExp",e[e.BonusWildcard=-50]="BonusWildcard",e[e.BonusRepeatable=-20]="BonusRepeatable",e[e.BonusOptional=-8]="BonusOptional",e[e.BonusStrict=.7000000000000001]="BonusStrict",e[e.BonusCaseSensitive=.25]="BonusCaseSensitive",e}(Ne||{});const qh=/[.+*?^${}()[\]/\\]/g;function Jh(e,t){const n=se({},zh,t),r=[];let s=n.start?"^":"";const i=[];for(const l of e){const u=l.length?[]:[Ne.Root];n.strict&&!l.length&&(s+="/");for(let f=0;f<l.length;f++){const p=l[f];let g=Ne.Segment+(n.sensitive?Ne.BonusCaseSensitive:0);if(p.type===un.Static)f||(s+="/"),s+=p.value.replace(qh,"\\$&"),g+=Ne.Static;else if(p.type===un.Param){const{value:I,repeatable:w,optional:L,regexp:M}=p;i.push({name:I,repeatable:w,optional:L});const A=M||ra;if(A!==ra){g+=Ne.BonusCustomRegExp;try{`${A}`}catch(N){throw new Error(`Invalid custom RegExp for param "${I}" (${A}): `+N.message)}}let x=w?`((?:${A})(?:/(?:${A}))*)`:`(${A})`;f||(x=L&&l.length<2?`(?:/${x})`:"/"+x),L&&(x+="?"),s+=x,g+=Ne.Dynamic,L&&(g+=Ne.BonusOptional),w&&(g+=Ne.BonusRepeatable),A===".*"&&(g+=Ne.BonusWildcard)}u.push(g)}r.push(u)}if(n.strict&&n.end){const l=r.length-1;r[l][r[l].length-1]+=Ne.BonusStrict}n.strict||(s+="/?"),n.end?s+="$":n.strict&&!s.endsWith("/")&&(s+="(?:/|$)");const o=new RegExp(s,n.sensitive?"":"i");function a(l){const u=l.match(o),f={};if(!u)return null;for(let p=1;p<u.length;p++){const g=u[p]||"",I=i[p-1];f[I.name]=g&&I.repeatable?g.split("/"):g}return f}function c(l){let u="",f=!1;for(const p of e){(!f||!u.endsWith("/"))&&(u+="/"),f=!1;for(const g of p)if(g.type===un.Static)u+=g.value;else if(g.type===un.Param){const{value:I,repeatable:w,optional:L}=g,M=I in l?l[I]:"";if(Ze(M)&&!w)throw new Error(`Provided param "${I}" is an array but it is not repeatable (* or + modifiers)`);const A=Ze(M)?M.join("/"):M;if(!A)if(L)p.length<2&&(u.endsWith("/")?u=u.slice(0,-1):f=!0);else throw new Error(`Missing required param "${I}"`);u+=A}}return u||"/"}return{re:o,score:r,keys:i,parse:a,stringify:c}}function Yh(e,t){let n=0;for(;n<e.length&&n<t.length;){const r=t[n]-e[n];if(r)return r;n++}return e.length<t.length?e.length===1&&e[0]===Ne.Static+Ne.Segment?-1:1:e.length>t.length?t.length===1&&t[0]===Ne.Static+Ne.Segment?1:-1:0}function Cl(e,t){let n=0;const r=e.score,s=t.score;for(;n<r.length&&n<s.length;){const i=Yh(r[n],s[n]);if(i)return i;n++}if(Math.abs(s.length-r.length)===1){if(sa(r))return 1;if(sa(s))return-1}return s.length-r.length}function sa(e){const t=e[e.length-1];return e.length>0&&t[t.length-1]<0}const Xh={strict:!1,end:!0,sensitive:!1};function Qh(e,t,n){const r=Jh(Gh(e.path),n),s=se(r,{record:e,parent:t,children:[],alias:[]});return t&&!s.record.aliasOf==!t.record.aliasOf&&t.children.push(s),s}function Zh(e,t){const n=[],r=new Map;t=Yo(Xh,t);function s(f){return r.get(f)}function i(f,p,g){const I=!g,w=oa(f);w.aliasOf=g&&g.record;const L=Yo(t,f),M=[w];if("alias"in f){const N=typeof f.alias=="string"?[f.alias]:f.alias;for(const H of N)M.push(oa(se({},w,{components:g?g.record.components:w.components,path:H,aliasOf:g?g.record:w})))}let A,x;for(const N of M){const{path:H}=N;if(p&&H[0]!=="/"){const te=p.record.path,J=te[te.length-1]==="/"?"":"/";N.path=p.record.path+(H&&J+H)}if(A=Qh(N,p,L),g?g.alias.push(A):(x=x||A,x!==A&&x.alias.push(A),I&&f.name&&!aa(A)&&o(f.name)),Rl(A)&&c(A),w.children){const te=w.children;for(let J=0;J<te.length;J++)i(te[J],A,g&&g.children[J])}g=g||A}return x?()=>{o(x)}:rr}function o(f){if(Sl(f)){const p=r.get(f);p&&(r.delete(f),n.splice(n.indexOf(p),1),p.children.forEach(o),p.alias.forEach(o))}else{const p=n.indexOf(f);p>-1&&(n.splice(p,1),f.record.name&&r.delete(f.record.name),f.children.forEach(o),f.alias.forEach(o))}}function a(){return n}function c(f){const p=np(f,n);n.splice(p,0,f),f.record.name&&!aa(f)&&r.set(f.record.name,f)}function l(f,p){let g,I={},w,L;if("name"in f&&f.name){if(g=r.get(f.name),!g)throw Ln(me.MATCHER_NOT_FOUND,{location:f});L=g.record.name,I=se(ia(p.params,g.keys.filter(x=>!x.optional).concat(g.parent?g.parent.keys.filter(x=>x.optional):[]).map(x=>x.name)),f.params&&ia(f.params,g.keys.map(x=>x.name))),w=g.stringify(I)}else if(f.path!=null)w=f.path,g=n.find(x=>x.re.test(w)),g&&(I=g.parse(w),L=g.record.name);else{if(g=p.name?r.get(p.name):n.find(x=>x.re.test(p.path)),!g)throw Ln(me.MATCHER_NOT_FOUND,{location:f,currentLocation:p});L=g.record.name,I=se({},p.params,f.params),w=g.stringify(I)}const M=[];let A=g;for(;A;)M.unshift(A.record),A=A.parent;return{name:L,path:w,params:I,matched:M,meta:tp(M)}}e.forEach(f=>i(f));function u(){n.length=0,r.clear()}return{addRoute:i,resolve:l,removeRoute:o,clearRoutes:u,getRoutes:a,getRecordMatcher:s}}function ia(e,t){const n={};for(const r of t)r in e&&(n[r]=e[r]);return n}function oa(e){const t={path:e.path,redirect:e.redirect,name:e.name,meta:e.meta||{},aliasOf:e.aliasOf,beforeEnter:e.beforeEnter,props:ep(e),children:e.children||[],instances:{},leaveGuards:new Set,updateGuards:new Set,enterCallbacks:{},components:"components"in e?e.components||null:e.component&&{default:e.component}};return Object.defineProperty(t,"mods",{value:{}}),t}function ep(e){const t={},n=e.props||!1;if("component"in e)t.default=n;else for(const r in e.components)t[r]=typeof n=="object"?n[r]:n;return t}function aa(e){for(;e;){if(e.record.aliasOf)return!0;e=e.parent}return!1}function tp(e){return e.reduce((t,n)=>se(t,n.meta),{})}function np(e,t){let n=0,r=t.length;for(;n!==r;){const i=n+r>>1;Cl(e,t[i])<0?r=i:n=i+1}const s=rp(e);return s&&(r=t.lastIndexOf(s,r-1)),r}function rp(e){let t=e;for(;t=t.parent;)if(Rl(t)&&Cl(e,t)===0)return t}function Rl({record:e}){return!!(e.name||e.components&&Object.keys(e.components).length||e.redirect)}function ca(e){const t=ze(ws),n=ze(Hi),r=Fe(()=>{const c=Y(e.to);return t.resolve(c)}),s=Fe(()=>{const{matched:c}=r.value,{length:l}=c,u=c[l-1],f=n.matched;if(!u||!f.length)return-1;const p=f.findIndex(Mn.bind(null,u));if(p>-1)return p;const g=la(c[l-2]);return l>1&&la(u)===g&&f[f.length-1].path!==g?f.findIndex(Mn.bind(null,c[l-2])):p}),i=Fe(()=>s.value>-1&&ap(n.params,r.value.params)),o=Fe(()=>s.value>-1&&s.value===n.matched.length-1&&wl(n.params,r.value.params));function a(c={}){if(op(c)){const l=t[Y(e.replace)?"replace":"push"](Y(e.to)).catch(rr);return e.viewTransition&&typeof document<"u"&&"startViewTransition"in document&&document.startViewTransition(()=>l),l}return Promise.resolve()}return{route:r,href:Fe(()=>r.value.href),isActive:i,isExactActive:o,navigate:a}}function sp(e){return e.length===1?e[0]:e}const ip=xc({name:"RouterLink",compatConfig:{MODE:3},props:{to:{type:[String,Object],required:!0},replace:Boolean,activeClass:String,exactActiveClass:String,custom:Boolean,ariaCurrentValue:{type:String,default:"page"},viewTransition:Boolean},useLink:ca,setup(e,{slots:t}){const n=yr(ca(e)),{options:r}=ze(ws),s=Fe(()=>({[ua(e.activeClass,r.linkActiveClass,"router-link-active")]:n.isActive,[ua(e.exactActiveClass,r.linkExactActiveClass,"router-link-exact-active")]:n.isExactActive}));return()=>{const i=t.default&&sp(t.default(n));return e.custom?i:xn("a",{"aria-current":n.isExactActive?e.ariaCurrentValue:null,href:n.href,onClick:n.navigate,class:s.value},i)}}}),Ur=ip;function op(e){if(!(e.metaKey||e.altKey||e.ctrlKey||e.shiftKey)&&!e.defaultPrevented&&!(e.button!==void 0&&e.button!==0)){if(e.currentTarget&&e.currentTarget.getAttribute){const t=e.currentTarget.getAttribute("target");if(/\b_blank\b/i.test(t))return}return e.preventDefault&&e.preventDefault(),!0}}function ap(e,t){for(const n in t){const r=t[n],s=e[n];if(typeof r=="string"){if(r!==s)return!1}else if(!Ze(s)||s.length!==r.length||r.some((i,o)=>i.valueOf()!==s[o].valueOf()))return!1}return!0}function la(e){return e?e.aliasOf?e.aliasOf.path:e.path:""}const ua=(e,t,n)=>e??t??n,cp=xc({name:"RouterView",inheritAttrs:!1,props:{name:{type:String,default:"default"},route:Object},compatConfig:{MODE:3},setup(e,{attrs:t,slots:n}){const r=ze(pi),s=Fe(()=>e.route||r.value),i=ze(ta,0),o=Fe(()=>{let l=Y(i);const{matched:u}=s.value;let f;for(;(f=u[l])&&!f.components;)l++;return l}),a=Fe(()=>s.value.matched[o.value]);Dr(ta,Fe(()=>o.value+1)),Dr(Fh,a),Dr(pi,s);const c=$r();return Qn(()=>[c.value,a.value,e.name],([l,u,f],[p,g,I])=>{u&&(u.instances[f]=l,g&&g!==u&&l&&l===p&&(u.leaveGuards.size||(u.leaveGuards=g.leaveGuards),u.updateGuards.size||(u.updateGuards=g.updateGuards))),l&&u&&(!g||!Mn(u,g)||!p)&&(u.enterCallbacks[f]||[]).forEach(w=>w(l))},{flush:"post"}),()=>{const l=s.value,u=e.name,f=a.value,p=f&&f.components[u];if(!p)return fa(n.default,{Component:p,route:l});const g=f.props[u],I=g?g===!0?l.params:typeof g=="function"?g(l):g:null,L=xn(p,se({},I,t,{onVnodeUnmounted:M=>{M.component.isUnmounted&&(f.instances[u]=null)},ref:c}));return fa(n.default,{Component:L,route:l})||L}}});function fa(e,t){if(!e)return null;const n=e(t);return n.length===1?n[0]:n}const lp=cp;function up(e){const t=Zh(e.routes,e),n=e.parseQuery||Lh,r=e.stringifyQuery||ea,s=e.history,i=Kn(),o=Kn(),a=Kn(),c=Zu(Ut);let l=Ut;wn&&e.scrollBehavior&&"scrollRestoration"in history&&(history.scrollRestoration="manual");const u=Vs.bind(null,y=>""+y),f=Vs.bind(null,yh),p=Vs.bind(null,hr);function g(y,D){let P,F;return Sl(y)?(P=t.getRecordMatcher(y),F=D):F=y,t.addRoute(F,P)}function I(y){const D=t.getRecordMatcher(y);D&&t.removeRoute(D)}function w(){return t.getRoutes().map(y=>y.record)}function L(y){return!!t.getRecordMatcher(y)}function M(y,D){if(D=se({},D||c.value),typeof y=="string"){const m=Hs(n,y,D.path),_=t.resolve({path:m.path},D),b=s.createHref(m.fullPath);return se(m,_,{params:p(_.params),hash:hr(m.hash),redirectedFrom:void 0,href:b})}let P;if(y.path!=null)P=se({},y,{path:Hs(n,y.path,D.path).path});else{const m=se({},y.params);for(const _ in m)m[_]==null&&delete m[_];P=se({},y,{params:f(m)}),D.params=f(D.params)}const F=t.resolve(P,D),Q=y.hash||"";F.params=u(p(F.params));const d=Ih(r,se({},y,{hash:mh(Q),path:F.path})),h=s.createHref(d);return se({fullPath:d,hash:Q,query:r===ea?Uh(y.query):y.query||{}},F,{redirectedFrom:void 0,href:h})}function A(y){return typeof y=="string"?Hs(n,y,c.value.path):se({},y)}function x(y,D){if(l!==y)return Ln(me.NAVIGATION_CANCELLED,{from:D,to:y})}function N(y){return J(y)}function H(y){return N(se(A(y),{replace:!0}))}function te(y,D){const P=y.matched[y.matched.length-1];if(P&&P.redirect){const{redirect:F}=P;let Q=typeof F=="function"?F(y,D):F;return typeof Q=="string"&&(Q=Q.includes("?")||Q.includes("#")?Q=A(Q):{path:Q},Q.params={}),se({query:y.query,hash:y.hash,params:Q.path!=null?{}:y.params},Q)}}function J(y,D){const P=l=M(y),F=c.value,Q=y.state,d=y.force,h=y.replace===!0,m=te(P,F);if(m)return J(se(A(m),{state:typeof m=="object"?se({},Q,m.state):Q,force:d,replace:h}),D||P);const _=P;_.redirectedFrom=D;let b;return!d&&wh(r,F,P)&&(b=Ln(me.NAVIGATION_DUPLICATED,{to:_,from:F}),et(F,F,!0,!1)),(b?Promise.resolve(b):j(_,F)).catch(v=>_t(v)?_t(v,me.NAVIGATION_GUARD_REDIRECT)?v:Mt(v):re(v,_,F)).then(v=>{if(v){if(_t(v,me.NAVIGATION_GUARD_REDIRECT))return J(se({replace:h},A(v.to),{state:typeof v.to=="object"?se({},Q,v.to.state):Q,force:d}),D||_)}else v=O(_,F,!0,h,Q);return Z(_,F,v),v})}function G(y,D){const P=x(y,D);return P?Promise.reject(P):Promise.resolve()}function C(y){const D=vn.values().next().value;return D&&typeof D.runWithContext=="function"?D.runWithContext(y):y()}function j(y,D){let P;const[F,Q,d]=Bh(y,D);P=$s(F.reverse(),"beforeRouteLeave",y,D);for(const m of F)m.leaveGuards.forEach(_=>{P.push(jt(_,y,D))});const h=G.bind(null,y,D);return P.push(h),We(P).then(()=>{P=[];for(const m of i.list())P.push(jt(m,y,D));return P.push(h),We(P)}).then(()=>{P=$s(Q,"beforeRouteUpdate",y,D);for(const m of Q)m.updateGuards.forEach(_=>{P.push(jt(_,y,D))});return P.push(h),We(P)}).then(()=>{P=[];for(const m of d)if(m.beforeEnter)if(Ze(m.beforeEnter))for(const _ of m.beforeEnter)P.push(jt(_,y,D));else P.push(jt(m.beforeEnter,y,D));return P.push(h),We(P)}).then(()=>(y.matched.forEach(m=>m.enterCallbacks={}),P=$s(d,"beforeRouteEnter",y,D,C),P.push(h),We(P))).then(()=>{P=[];for(const m of o.list())P.push(jt(m,y,D));return P.push(h),We(P)}).catch(m=>_t(m,me.NAVIGATION_CANCELLED)?m:Promise.reject(m))}function Z(y,D,P){a.list().forEach(F=>C(()=>F(y,D,P)))}function O(y,D,P,F,Q){const d=x(y,D);if(d)return d;const h=D===Ut,m=wn?history.state:{};P&&(F||h?s.replace(y.fullPath,se({scroll:h&&m&&m.scroll},Q)):s.push(y.fullPath,Q)),c.value=y,et(y,D,P,h),Mt()}let X;function ve(){X||(X=s.listen((y,D,P)=>{if(!en.listening)return;const F=M(y),Q=te(F,en.currentRoute.value);if(Q){J(se(Q,{replace:!0,force:!0}),F).catch(rr);return}l=F;const d=c.value;wn&&kh(Zo(d.fullPath,P.delta),Is()),j(F,d).catch(h=>_t(h,me.NAVIGATION_ABORTED|me.NAVIGATION_CANCELLED)?h:_t(h,me.NAVIGATION_GUARD_REDIRECT)?(J(se(A(h.to),{force:!0}),F).then(m=>{_t(m,me.NAVIGATION_ABORTED|me.NAVIGATION_DUPLICATED)&&!P.delta&&P.type===di.pop&&s.go(-1,!1)}).catch(rr),Promise.reject()):(P.delta&&s.go(-P.delta,!1),re(h,F,d))).then(h=>{h=h||O(F,d,!1),h&&(P.delta&&!_t(h,me.NAVIGATION_CANCELLED)?s.go(-P.delta,!1):P.type===di.pop&&_t(h,me.NAVIGATION_ABORTED|me.NAVIGATION_DUPLICATED)&&s.go(-1,!1)),Z(F,d,h)}).catch(rr)}))}let Oe=Kn(),ae=Kn(),q;function re(y,D,P){Mt(y);const F=ae.list();return F.length?F.forEach(Q=>Q(y,D,P)):console.error(y),Promise.reject(y)}function pt(){return q&&c.value!==Ut?Promise.resolve():new Promise((y,D)=>{Oe.add([y,D])})}function Mt(y){return q||(q=!y,ve(),Oe.list().forEach(([D,P])=>y?P(y):D()),Oe.reset()),y}function et(y,D,P,F){const{scrollBehavior:Q}=e;if(!wn||!Q)return Promise.resolve();const d=!P&&Nh(Zo(y.fullPath,0))||(F||!P)&&history.state&&history.state.scroll||null;return gs().then(()=>Q(y,D,d)).then(h=>h&&Oh(h)).catch(h=>re(h,y,D))}const Le=y=>s.go(y);let _n;const vn=new Set,en={currentRoute:c,listening:!0,addRoute:g,removeRoute:I,clearRoutes:t.clearRoutes,hasRoute:L,getRoutes:w,resolve:M,options:e,push:N,replace:H,go:Le,back:()=>Le(-1),forward:()=>Le(1),beforeEach:i.add,beforeResolve:o.add,afterEach:a.add,onError:ae.add,isReady:pt,install(y){y.component("RouterLink",Ur),y.component("RouterView",lp),y.config.globalProperties.$router=en,Object.defineProperty(y.config.globalProperties,"$route",{enumerable:!0,get:()=>Y(c)}),wn&&!_n&&c.value===Ut&&(_n=!0,N(s.location).catch(F=>{}));const D={};for(const F in Ut)Object.defineProperty(D,F,{get:()=>c.value[F],enumerable:!0});y.provide(ws,en),y.provide(Hi,_c(D)),y.provide(pi,c);const P=y.unmount;vn.add(y),y.unmount=function(){vn.delete(y),vn.size<1&&(l=Ut,X&&X(),X=null,c.value=Ut,_n=!1,q=!1),P()}}};function We(y){return y.reduce((D,P)=>D.then(()=>C(P)),Promise.resolve())}return en}function fp(){return ze(ws)}function Pl(e){return ze(Hi)}var da={};/**
 * @license
 * Copyright 2017 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const Ol=function(e){const t=[];let n=0;for(let r=0;r<e.length;r++){let s=e.charCodeAt(r);s<128?t[n++]=s:s<2048?(t[n++]=s>>6|192,t[n++]=s&63|128):(s&64512)===55296&&r+1<e.length&&(e.charCodeAt(r+1)&64512)===56320?(s=65536+((s&1023)<<10)+(e.charCodeAt(++r)&1023),t[n++]=s>>18|240,t[n++]=s>>12&63|128,t[n++]=s>>6&63|128,t[n++]=s&63|128):(t[n++]=s>>12|224,t[n++]=s>>6&63|128,t[n++]=s&63|128)}return t},dp=function(e){const t=[];let n=0,r=0;for(;n<e.length;){const s=e[n++];if(s<128)t[r++]=String.fromCharCode(s);else if(s>191&&s<224){const i=e[n++];t[r++]=String.fromCharCode((s&31)<<6|i&63)}else if(s>239&&s<365){const i=e[n++],o=e[n++],a=e[n++],c=((s&7)<<18|(i&63)<<12|(o&63)<<6|a&63)-65536;t[r++]=String.fromCharCode(55296+(c>>10)),t[r++]=String.fromCharCode(56320+(c&1023))}else{const i=e[n++],o=e[n++];t[r++]=String.fromCharCode((s&15)<<12|(i&63)<<6|o&63)}}return t.join("")},kl={byteToCharMap_:null,charToByteMap_:null,byteToCharMapWebSafe_:null,charToByteMapWebSafe_:null,ENCODED_VALS_BASE:"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",get ENCODED_VALS(){return this.ENCODED_VALS_BASE+"+/="},get ENCODED_VALS_WEBSAFE(){return this.ENCODED_VALS_BASE+"-_."},HAS_NATIVE_SUPPORT:typeof atob=="function",encodeByteArray(e,t){if(!Array.isArray(e))throw Error("encodeByteArray takes an array as a parameter");this.init_();const n=t?this.byteToCharMapWebSafe_:this.byteToCharMap_,r=[];for(let s=0;s<e.length;s+=3){const i=e[s],o=s+1<e.length,a=o?e[s+1]:0,c=s+2<e.length,l=c?e[s+2]:0,u=i>>2,f=(i&3)<<4|a>>4;let p=(a&15)<<2|l>>6,g=l&63;c||(g=64,o||(p=64)),r.push(n[u],n[f],n[p],n[g])}return r.join("")},encodeString(e,t){return this.HAS_NATIVE_SUPPORT&&!t?btoa(e):this.encodeByteArray(Ol(e),t)},decodeString(e,t){return this.HAS_NATIVE_SUPPORT&&!t?atob(e):dp(this.decodeStringToByteArray(e,t))},decodeStringToByteArray(e,t){this.init_();const n=t?this.charToByteMapWebSafe_:this.charToByteMap_,r=[];for(let s=0;s<e.length;){const i=n[e.charAt(s++)],a=s<e.length?n[e.charAt(s)]:0;++s;const l=s<e.length?n[e.charAt(s)]:64;++s;const f=s<e.length?n[e.charAt(s)]:64;if(++s,i==null||a==null||l==null||f==null)throw new hp;const p=i<<2|a>>4;if(r.push(p),l!==64){const g=a<<4&240|l>>2;if(r.push(g),f!==64){const I=l<<6&192|f;r.push(I)}}}return r},init_(){if(!this.byteToCharMap_){this.byteToCharMap_={},this.charToByteMap_={},this.byteToCharMapWebSafe_={},this.charToByteMapWebSafe_={};for(let e=0;e<this.ENCODED_VALS.length;e++)this.byteToCharMap_[e]=this.ENCODED_VALS.charAt(e),this.charToByteMap_[this.byteToCharMap_[e]]=e,this.byteToCharMapWebSafe_[e]=this.ENCODED_VALS_WEBSAFE.charAt(e),this.charToByteMapWebSafe_[this.byteToCharMapWebSafe_[e]]=e,e>=this.ENCODED_VALS_BASE.length&&(this.charToByteMap_[this.ENCODED_VALS_WEBSAFE.charAt(e)]=e,this.charToByteMapWebSafe_[this.ENCODED_VALS.charAt(e)]=e)}}};class hp extends Error{constructor(){super(...arguments),this.name="DecodeBase64StringError"}}const pp=function(e){const t=Ol(e);return kl.encodeByteArray(t,!0)},Nl=function(e){return pp(e).replace(/\./g,"")},xl=function(e){try{return kl.decodeString(e,!0)}catch(t){console.error("base64Decode failed: ",t)}return null};/**
 * @license
 * Copyright 2022 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function gp(){if(typeof self<"u")return self;if(typeof window<"u")return window;if(typeof global<"u")return global;throw new Error("Unable to locate global object.")}/**
 * @license
 * Copyright 2022 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const mp=()=>gp().__FIREBASE_DEFAULTS__,_p=()=>{if(typeof process>"u"||typeof da>"u")return;const e=da.__FIREBASE_DEFAULTS__;if(e)return JSON.parse(e)},vp=()=>{if(typeof document>"u")return;let e;try{e=document.cookie.match(/__FIREBASE_DEFAULTS__=([^;]+)/)}catch{return}const t=e&&xl(e[1]);return t&&JSON.parse(t)},ji=()=>{try{return mp()||_p()||vp()}catch(e){console.info(`Unable to get __FIREBASE_DEFAULTS__ due to: ${e}`);return}},yp=e=>{var t,n;return(n=(t=ji())===null||t===void 0?void 0:t.emulatorHosts)===null||n===void 0?void 0:n[e]},Dl=()=>{var e;return(e=ji())===null||e===void 0?void 0:e.config},Ml=e=>{var t;return(t=ji())===null||t===void 0?void 0:t[`_${e}`]};/**
 * @license
 * Copyright 2017 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class bp{constructor(){this.reject=()=>{},this.resolve=()=>{},this.promise=new Promise((t,n)=>{this.resolve=t,this.reject=n})}wrapCallback(t){return(n,r)=>{n?this.reject(n):this.resolve(r),typeof t=="function"&&(this.promise.catch(()=>{}),t.length===1?t(n):t(n,r))}}}/**
 * @license
 * Copyright 2017 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function Me(){return typeof navigator<"u"&&typeof navigator.userAgent=="string"?navigator.userAgent:""}function Ep(){return typeof window<"u"&&!!(window.cordova||window.phonegap||window.PhoneGap)&&/ios|iphone|ipod|ipad|android|blackberry|iemobile/i.test(Me())}function Ip(){return typeof navigator<"u"&&navigator.userAgent==="Cloudflare-Workers"}function wp(){const e=typeof chrome=="object"?chrome.runtime:typeof browser=="object"?browser.runtime:void 0;return typeof e=="object"&&e.id!==void 0}function Sp(){return typeof navigator=="object"&&navigator.product==="ReactNative"}function Tp(){const e=Me();return e.indexOf("MSIE ")>=0||e.indexOf("Trident/")>=0}function Ap(){try{return typeof indexedDB=="object"}catch{return!1}}function Cp(){return new Promise((e,t)=>{try{let n=!0;const r="validate-browser-context-for-indexeddb-analytics-module",s=self.indexedDB.open(r);s.onsuccess=()=>{s.result.close(),n||self.indexedDB.deleteDatabase(r),e(!0)},s.onupgradeneeded=()=>{n=!1},s.onerror=()=>{var i;t(((i=s.error)===null||i===void 0?void 0:i.message)||"")}}catch(n){t(n)}})}/**
 * @license
 * Copyright 2017 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const Rp="FirebaseError";class Qt extends Error{constructor(t,n,r){super(n),this.code=t,this.customData=r,this.name=Rp,Object.setPrototypeOf(this,Qt.prototype),Error.captureStackTrace&&Error.captureStackTrace(this,Ir.prototype.create)}}class Ir{constructor(t,n,r){this.service=t,this.serviceName=n,this.errors=r}create(t,...n){const r=n[0]||{},s=`${this.service}/${t}`,i=this.errors[t],o=i?Pp(i,r):"Error",a=`${this.serviceName}: ${o} (${s}).`;return new Qt(s,a,r)}}function Pp(e,t){return e.replace(Op,(n,r)=>{const s=t[r];return s!=null?String(s):`<${r}?>`})}const Op=/\{\$([^}]+)}/g;function kp(e){for(const t in e)if(Object.prototype.hasOwnProperty.call(e,t))return!1;return!0}function Xr(e,t){if(e===t)return!0;const n=Object.keys(e),r=Object.keys(t);for(const s of n){if(!r.includes(s))return!1;const i=e[s],o=t[s];if(ha(i)&&ha(o)){if(!Xr(i,o))return!1}else if(i!==o)return!1}for(const s of r)if(!n.includes(s))return!1;return!0}function ha(e){return e!==null&&typeof e=="object"}/**
 * @license
 * Copyright 2017 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function wr(e){const t=[];for(const[n,r]of Object.entries(e))Array.isArray(r)?r.forEach(s=>{t.push(encodeURIComponent(n)+"="+encodeURIComponent(s))}):t.push(encodeURIComponent(n)+"="+encodeURIComponent(r));return t.length?"&"+t.join("&"):""}function Np(e,t){const n=new xp(e,t);return n.subscribe.bind(n)}class xp{constructor(t,n){this.observers=[],this.unsubscribes=[],this.observerCount=0,this.task=Promise.resolve(),this.finalized=!1,this.onNoObservers=n,this.task.then(()=>{t(this)}).catch(r=>{this.error(r)})}next(t){this.forEachObserver(n=>{n.next(t)})}error(t){this.forEachObserver(n=>{n.error(t)}),this.close(t)}complete(){this.forEachObserver(t=>{t.complete()}),this.close()}subscribe(t,n,r){let s;if(t===void 0&&n===void 0&&r===void 0)throw new Error("Missing Observer.");Dp(t,["next","error","complete"])?s=t:s={next:t,error:n,complete:r},s.next===void 0&&(s.next=Ws),s.error===void 0&&(s.error=Ws),s.complete===void 0&&(s.complete=Ws);const i=this.unsubscribeOne.bind(this,this.observers.length);return this.finalized&&this.task.then(()=>{try{this.finalError?s.error(this.finalError):s.complete()}catch{}}),this.observers.push(s),i}unsubscribeOne(t){this.observers===void 0||this.observers[t]===void 0||(delete this.observers[t],this.observerCount-=1,this.observerCount===0&&this.onNoObservers!==void 0&&this.onNoObservers(this))}forEachObserver(t){if(!this.finalized)for(let n=0;n<this.observers.length;n++)this.sendOne(n,t)}sendOne(t,n){this.task.then(()=>{if(this.observers!==void 0&&this.observers[t]!==void 0)try{n(this.observers[t])}catch(r){typeof console<"u"&&console.error&&console.error(r)}})}close(t){this.finalized||(this.finalized=!0,t!==void 0&&(this.finalError=t),this.task.then(()=>{this.observers=void 0,this.onNoObservers=void 0}))}}function Dp(e,t){if(typeof e!="object"||e===null)return!1;for(const n of t)if(n in e&&typeof e[n]=="function")return!0;return!1}function Ws(){}/**
 * @license
 * Copyright 2021 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function Zt(e){return e&&e._delegate?e._delegate:e}class Un{constructor(t,n,r){this.name=t,this.instanceFactory=n,this.type=r,this.multipleInstances=!1,this.serviceProps={},this.instantiationMode="LAZY",this.onInstanceCreated=null}setInstantiationMode(t){return this.instantiationMode=t,this}setMultipleInstances(t){return this.multipleInstances=t,this}setServiceProps(t){return this.serviceProps=t,this}setInstanceCreatedCallback(t){return this.onInstanceCreated=t,this}}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const an="[DEFAULT]";/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class Mp{constructor(t,n){this.name=t,this.container=n,this.component=null,this.instances=new Map,this.instancesDeferred=new Map,this.instancesOptions=new Map,this.onInitCallbacks=new Map}get(t){const n=this.normalizeInstanceIdentifier(t);if(!this.instancesDeferred.has(n)){const r=new bp;if(this.instancesDeferred.set(n,r),this.isInitialized(n)||this.shouldAutoInitialize())try{const s=this.getOrInitializeService({instanceIdentifier:n});s&&r.resolve(s)}catch{}}return this.instancesDeferred.get(n).promise}getImmediate(t){var n;const r=this.normalizeInstanceIdentifier(t?.identifier),s=(n=t?.optional)!==null&&n!==void 0?n:!1;if(this.isInitialized(r)||this.shouldAutoInitialize())try{return this.getOrInitializeService({instanceIdentifier:r})}catch(i){if(s)return null;throw i}else{if(s)return null;throw Error(`Service ${this.name} is not available`)}}getComponent(){return this.component}setComponent(t){if(t.name!==this.name)throw Error(`Mismatching Component ${t.name} for Provider ${this.name}.`);if(this.component)throw Error(`Component for ${this.name} has already been provided`);if(this.component=t,!!this.shouldAutoInitialize()){if(Up(t))try{this.getOrInitializeService({instanceIdentifier:an})}catch{}for(const[n,r]of this.instancesDeferred.entries()){const s=this.normalizeInstanceIdentifier(n);try{const i=this.getOrInitializeService({instanceIdentifier:s});r.resolve(i)}catch{}}}}clearInstance(t=an){this.instancesDeferred.delete(t),this.instancesOptions.delete(t),this.instances.delete(t)}async delete(){const t=Array.from(this.instances.values());await Promise.all([...t.filter(n=>"INTERNAL"in n).map(n=>n.INTERNAL.delete()),...t.filter(n=>"_delete"in n).map(n=>n._delete())])}isComponentSet(){return this.component!=null}isInitialized(t=an){return this.instances.has(t)}getOptions(t=an){return this.instancesOptions.get(t)||{}}initialize(t={}){const{options:n={}}=t,r=this.normalizeInstanceIdentifier(t.instanceIdentifier);if(this.isInitialized(r))throw Error(`${this.name}(${r}) has already been initialized`);if(!this.isComponentSet())throw Error(`Component ${this.name} has not been registered yet`);const s=this.getOrInitializeService({instanceIdentifier:r,options:n});for(const[i,o]of this.instancesDeferred.entries()){const a=this.normalizeInstanceIdentifier(i);r===a&&o.resolve(s)}return s}onInit(t,n){var r;const s=this.normalizeInstanceIdentifier(n),i=(r=this.onInitCallbacks.get(s))!==null&&r!==void 0?r:new Set;i.add(t),this.onInitCallbacks.set(s,i);const o=this.instances.get(s);return o&&t(o,s),()=>{i.delete(t)}}invokeOnInitCallbacks(t,n){const r=this.onInitCallbacks.get(n);if(r)for(const s of r)try{s(t,n)}catch{}}getOrInitializeService({instanceIdentifier:t,options:n={}}){let r=this.instances.get(t);if(!r&&this.component&&(r=this.component.instanceFactory(this.container,{instanceIdentifier:Lp(t),options:n}),this.instances.set(t,r),this.instancesOptions.set(t,n),this.invokeOnInitCallbacks(r,t),this.component.onInstanceCreated))try{this.component.onInstanceCreated(this.container,t,r)}catch{}return r||null}normalizeInstanceIdentifier(t=an){return this.component?this.component.multipleInstances?t:an:t}shouldAutoInitialize(){return!!this.component&&this.component.instantiationMode!=="EXPLICIT"}}function Lp(e){return e===an?void 0:e}function Up(e){return e.instantiationMode==="EAGER"}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class Fp{constructor(t){this.name=t,this.providers=new Map}addComponent(t){const n=this.getProvider(t.name);if(n.isComponentSet())throw new Error(`Component ${t.name} has already been registered with ${this.name}`);n.setComponent(t)}addOrOverwriteComponent(t){this.getProvider(t.name).isComponentSet()&&this.providers.delete(t.name),this.addComponent(t)}getProvider(t){if(this.providers.has(t))return this.providers.get(t);const n=new Mp(t,this);return this.providers.set(t,n),n}getProviders(){return Array.from(this.providers.values())}}/**
 * @license
 * Copyright 2017 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */var ue;(function(e){e[e.DEBUG=0]="DEBUG",e[e.VERBOSE=1]="VERBOSE",e[e.INFO=2]="INFO",e[e.WARN=3]="WARN",e[e.ERROR=4]="ERROR",e[e.SILENT=5]="SILENT"})(ue||(ue={}));const Bp={debug:ue.DEBUG,verbose:ue.VERBOSE,info:ue.INFO,warn:ue.WARN,error:ue.ERROR,silent:ue.SILENT},Vp=ue.INFO,Hp={[ue.DEBUG]:"log",[ue.VERBOSE]:"log",[ue.INFO]:"info",[ue.WARN]:"warn",[ue.ERROR]:"error"},jp=(e,t,...n)=>{if(t<e.logLevel)return;const r=new Date().toISOString(),s=Hp[t];if(s)console[s](`[${r}]  ${e.name}:`,...n);else throw new Error(`Attempted to log a message with an invalid logType (value: ${t})`)};class Ll{constructor(t){this.name=t,this._logLevel=Vp,this._logHandler=jp,this._userLogHandler=null}get logLevel(){return this._logLevel}set logLevel(t){if(!(t in ue))throw new TypeError(`Invalid value "${t}" assigned to \`logLevel\``);this._logLevel=t}setLogLevel(t){this._logLevel=typeof t=="string"?Bp[t]:t}get logHandler(){return this._logHandler}set logHandler(t){if(typeof t!="function")throw new TypeError("Value assigned to `logHandler` must be a function");this._logHandler=t}get userLogHandler(){return this._userLogHandler}set userLogHandler(t){this._userLogHandler=t}debug(...t){this._userLogHandler&&this._userLogHandler(this,ue.DEBUG,...t),this._logHandler(this,ue.DEBUG,...t)}log(...t){this._userLogHandler&&this._userLogHandler(this,ue.VERBOSE,...t),this._logHandler(this,ue.VERBOSE,...t)}info(...t){this._userLogHandler&&this._userLogHandler(this,ue.INFO,...t),this._logHandler(this,ue.INFO,...t)}warn(...t){this._userLogHandler&&this._userLogHandler(this,ue.WARN,...t),this._logHandler(this,ue.WARN,...t)}error(...t){this._userLogHandler&&this._userLogHandler(this,ue.ERROR,...t),this._logHandler(this,ue.ERROR,...t)}}const $p=(e,t)=>t.some(n=>e instanceof n);let pa,ga;function Wp(){return pa||(pa=[IDBDatabase,IDBObjectStore,IDBIndex,IDBCursor,IDBTransaction])}function Kp(){return ga||(ga=[IDBCursor.prototype.advance,IDBCursor.prototype.continue,IDBCursor.prototype.continuePrimaryKey])}const Ul=new WeakMap,gi=new WeakMap,Fl=new WeakMap,Ks=new WeakMap,$i=new WeakMap;function Gp(e){const t=new Promise((n,r)=>{const s=()=>{e.removeEventListener("success",i),e.removeEventListener("error",o)},i=()=>{n(zt(e.result)),s()},o=()=>{r(e.error),s()};e.addEventListener("success",i),e.addEventListener("error",o)});return t.then(n=>{n instanceof IDBCursor&&Ul.set(n,e)}).catch(()=>{}),$i.set(t,e),t}function zp(e){if(gi.has(e))return;const t=new Promise((n,r)=>{const s=()=>{e.removeEventListener("complete",i),e.removeEventListener("error",o),e.removeEventListener("abort",o)},i=()=>{n(),s()},o=()=>{r(e.error||new DOMException("AbortError","AbortError")),s()};e.addEventListener("complete",i),e.addEventListener("error",o),e.addEventListener("abort",o)});gi.set(e,t)}let mi={get(e,t,n){if(e instanceof IDBTransaction){if(t==="done")return gi.get(e);if(t==="objectStoreNames")return e.objectStoreNames||Fl.get(e);if(t==="store")return n.objectStoreNames[1]?void 0:n.objectStore(n.objectStoreNames[0])}return zt(e[t])},set(e,t,n){return e[t]=n,!0},has(e,t){return e instanceof IDBTransaction&&(t==="done"||t==="store")?!0:t in e}};function qp(e){mi=e(mi)}function Jp(e){return e===IDBDatabase.prototype.transaction&&!("objectStoreNames"in IDBTransaction.prototype)?function(t,...n){const r=e.call(Gs(this),t,...n);return Fl.set(r,t.sort?t.sort():[t]),zt(r)}:Kp().includes(e)?function(...t){return e.apply(Gs(this),t),zt(Ul.get(this))}:function(...t){return zt(e.apply(Gs(this),t))}}function Yp(e){return typeof e=="function"?Jp(e):(e instanceof IDBTransaction&&zp(e),$p(e,Wp())?new Proxy(e,mi):e)}function zt(e){if(e instanceof IDBRequest)return Gp(e);if(Ks.has(e))return Ks.get(e);const t=Yp(e);return t!==e&&(Ks.set(e,t),$i.set(t,e)),t}const Gs=e=>$i.get(e);function Xp(e,t,{blocked:n,upgrade:r,blocking:s,terminated:i}={}){const o=indexedDB.open(e,t),a=zt(o);return r&&o.addEventListener("upgradeneeded",c=>{r(zt(o.result),c.oldVersion,c.newVersion,zt(o.transaction),c)}),n&&o.addEventListener("blocked",c=>n(c.oldVersion,c.newVersion,c)),a.then(c=>{i&&c.addEventListener("close",()=>i()),s&&c.addEventListener("versionchange",l=>s(l.oldVersion,l.newVersion,l))}).catch(()=>{}),a}const Qp=["get","getKey","getAll","getAllKeys","count"],Zp=["put","add","delete","clear"],zs=new Map;function ma(e,t){if(!(e instanceof IDBDatabase&&!(t in e)&&typeof t=="string"))return;if(zs.get(t))return zs.get(t);const n=t.replace(/FromIndex$/,""),r=t!==n,s=Zp.includes(n);if(!(n in(r?IDBIndex:IDBObjectStore).prototype)||!(s||Qp.includes(n)))return;const i=async function(o,...a){const c=this.transaction(o,s?"readwrite":"readonly");let l=c.store;return r&&(l=l.index(a.shift())),(await Promise.all([l[n](...a),s&&c.done]))[0]};return zs.set(t,i),i}qp(e=>({...e,get:(t,n,r)=>ma(t,n)||e.get(t,n,r),has:(t,n)=>!!ma(t,n)||e.has(t,n)}));/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class eg{constructor(t){this.container=t}getPlatformInfoString(){return this.container.getProviders().map(n=>{if(tg(n)){const r=n.getImmediate();return`${r.library}/${r.version}`}else return null}).filter(n=>n).join(" ")}}function tg(e){const t=e.getComponent();return t?.type==="VERSION"}const _i="@firebase/app",_a="0.10.13";/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const Nt=new Ll("@firebase/app"),ng="@firebase/app-compat",rg="@firebase/analytics-compat",sg="@firebase/analytics",ig="@firebase/app-check-compat",og="@firebase/app-check",ag="@firebase/auth",cg="@firebase/auth-compat",lg="@firebase/database",ug="@firebase/data-connect",fg="@firebase/database-compat",dg="@firebase/functions",hg="@firebase/functions-compat",pg="@firebase/installations",gg="@firebase/installations-compat",mg="@firebase/messaging",_g="@firebase/messaging-compat",vg="@firebase/performance",yg="@firebase/performance-compat",bg="@firebase/remote-config",Eg="@firebase/remote-config-compat",Ig="@firebase/storage",wg="@firebase/storage-compat",Sg="@firebase/firestore",Tg="@firebase/vertexai-preview",Ag="@firebase/firestore-compat",Cg="firebase",Rg="10.14.1";/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const vi="[DEFAULT]",Pg={[_i]:"fire-core",[ng]:"fire-core-compat",[sg]:"fire-analytics",[rg]:"fire-analytics-compat",[og]:"fire-app-check",[ig]:"fire-app-check-compat",[ag]:"fire-auth",[cg]:"fire-auth-compat",[lg]:"fire-rtdb",[ug]:"fire-data-connect",[fg]:"fire-rtdb-compat",[dg]:"fire-fn",[hg]:"fire-fn-compat",[pg]:"fire-iid",[gg]:"fire-iid-compat",[mg]:"fire-fcm",[_g]:"fire-fcm-compat",[vg]:"fire-perf",[yg]:"fire-perf-compat",[bg]:"fire-rc",[Eg]:"fire-rc-compat",[Ig]:"fire-gcs",[wg]:"fire-gcs-compat",[Sg]:"fire-fst",[Ag]:"fire-fst-compat",[Tg]:"fire-vertex","fire-js":"fire-js",[Cg]:"fire-js-all"};/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const Qr=new Map,Og=new Map,yi=new Map;function va(e,t){try{e.container.addComponent(t)}catch(n){Nt.debug(`Component ${t.name} failed to register with FirebaseApp ${e.name}`,n)}}function pr(e){const t=e.name;if(yi.has(t))return Nt.debug(`There were multiple attempts to register component ${t}.`),!1;yi.set(t,e);for(const n of Qr.values())va(n,e);for(const n of Og.values())va(n,e);return!0}function Bl(e,t){const n=e.container.getProvider("heartbeat").getImmediate({optional:!0});return n&&n.triggerHeartbeat(),e.container.getProvider(t)}function St(e){return e.settings!==void 0}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const kg={"no-app":"No Firebase App '{$appName}' has been created - call initializeApp() first","bad-app-name":"Illegal App name: '{$appName}'","duplicate-app":"Firebase App named '{$appName}' already exists with different options or config","app-deleted":"Firebase App named '{$appName}' already deleted","server-app-deleted":"Firebase Server App has been deleted","no-options":"Need to provide options, when not being deployed to hosting via source.","invalid-app-argument":"firebase.{$appName}() takes either no argument or a Firebase App instance.","invalid-log-argument":"First argument to `onLog` must be null or a function.","idb-open":"Error thrown when opening IndexedDB. Original error: {$originalErrorMessage}.","idb-get":"Error thrown when reading from IndexedDB. Original error: {$originalErrorMessage}.","idb-set":"Error thrown when writing to IndexedDB. Original error: {$originalErrorMessage}.","idb-delete":"Error thrown when deleting from IndexedDB. Original error: {$originalErrorMessage}.","finalization-registry-not-supported":"FirebaseServerApp deleteOnDeref field defined but the JS runtime does not support FinalizationRegistry.","invalid-server-app-environment":"FirebaseServerApp is not for use in browser environments."},qt=new Ir("app","Firebase",kg);/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class Ng{constructor(t,n,r){this._isDeleted=!1,this._options=Object.assign({},t),this._config=Object.assign({},n),this._name=n.name,this._automaticDataCollectionEnabled=n.automaticDataCollectionEnabled,this._container=r,this.container.addComponent(new Un("app",()=>this,"PUBLIC"))}get automaticDataCollectionEnabled(){return this.checkDestroyed(),this._automaticDataCollectionEnabled}set automaticDataCollectionEnabled(t){this.checkDestroyed(),this._automaticDataCollectionEnabled=t}get name(){return this.checkDestroyed(),this._name}get options(){return this.checkDestroyed(),this._options}get config(){return this.checkDestroyed(),this._config}get container(){return this._container}get isDeleted(){return this._isDeleted}set isDeleted(t){this._isDeleted=t}checkDestroyed(){if(this.isDeleted)throw qt.create("app-deleted",{appName:this._name})}}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const Sr=Rg;function Vl(e,t={}){let n=e;typeof t!="object"&&(t={name:t});const r=Object.assign({name:vi,automaticDataCollectionEnabled:!1},t),s=r.name;if(typeof s!="string"||!s)throw qt.create("bad-app-name",{appName:String(s)});if(n||(n=Dl()),!n)throw qt.create("no-options");const i=Qr.get(s);if(i){if(Xr(n,i.options)&&Xr(r,i.config))return i;throw qt.create("duplicate-app",{appName:s})}const o=new Fp(s);for(const c of yi.values())o.addComponent(c);const a=new Ng(n,r,o);return Qr.set(s,a),a}function xg(e=vi){const t=Qr.get(e);if(!t&&e===vi&&Dl())return Vl();if(!t)throw qt.create("no-app",{appName:e});return t}function Rn(e,t,n){var r;let s=(r=Pg[e])!==null&&r!==void 0?r:e;n&&(s+=`-${n}`);const i=s.match(/\s|\//),o=t.match(/\s|\//);if(i||o){const a=[`Unable to register library "${s}" with version "${t}":`];i&&a.push(`library name "${s}" contains illegal characters (whitespace or "/")`),i&&o&&a.push("and"),o&&a.push(`version name "${t}" contains illegal characters (whitespace or "/")`),Nt.warn(a.join(" "));return}pr(new Un(`${s}-version`,()=>({library:s,version:t}),"VERSION"))}/**
 * @license
 * Copyright 2021 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const Dg="firebase-heartbeat-database",Mg=1,gr="firebase-heartbeat-store";let qs=null;function Hl(){return qs||(qs=Xp(Dg,Mg,{upgrade:(e,t)=>{switch(t){case 0:try{e.createObjectStore(gr)}catch(n){console.warn(n)}}}}).catch(e=>{throw qt.create("idb-open",{originalErrorMessage:e.message})})),qs}async function Lg(e){try{const n=(await Hl()).transaction(gr),r=await n.objectStore(gr).get(jl(e));return await n.done,r}catch(t){if(t instanceof Qt)Nt.warn(t.message);else{const n=qt.create("idb-get",{originalErrorMessage:t?.message});Nt.warn(n.message)}}}async function ya(e,t){try{const r=(await Hl()).transaction(gr,"readwrite");await r.objectStore(gr).put(t,jl(e)),await r.done}catch(n){if(n instanceof Qt)Nt.warn(n.message);else{const r=qt.create("idb-set",{originalErrorMessage:n?.message});Nt.warn(r.message)}}}function jl(e){return`${e.name}!${e.options.appId}`}/**
 * @license
 * Copyright 2021 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const Ug=1024,Fg=30*24*60*60*1e3;class Bg{constructor(t){this.container=t,this._heartbeatsCache=null;const n=this.container.getProvider("app").getImmediate();this._storage=new Hg(n),this._heartbeatsCachePromise=this._storage.read().then(r=>(this._heartbeatsCache=r,r))}async triggerHeartbeat(){var t,n;try{const s=this.container.getProvider("platform-logger").getImmediate().getPlatformInfoString(),i=ba();return((t=this._heartbeatsCache)===null||t===void 0?void 0:t.heartbeats)==null&&(this._heartbeatsCache=await this._heartbeatsCachePromise,((n=this._heartbeatsCache)===null||n===void 0?void 0:n.heartbeats)==null)||this._heartbeatsCache.lastSentHeartbeatDate===i||this._heartbeatsCache.heartbeats.some(o=>o.date===i)?void 0:(this._heartbeatsCache.heartbeats.push({date:i,agent:s}),this._heartbeatsCache.heartbeats=this._heartbeatsCache.heartbeats.filter(o=>{const a=new Date(o.date).valueOf();return Date.now()-a<=Fg}),this._storage.overwrite(this._heartbeatsCache))}catch(r){Nt.warn(r)}}async getHeartbeatsHeader(){var t;try{if(this._heartbeatsCache===null&&await this._heartbeatsCachePromise,((t=this._heartbeatsCache)===null||t===void 0?void 0:t.heartbeats)==null||this._heartbeatsCache.heartbeats.length===0)return"";const n=ba(),{heartbeatsToSend:r,unsentEntries:s}=Vg(this._heartbeatsCache.heartbeats),i=Nl(JSON.stringify({version:2,heartbeats:r}));return this._heartbeatsCache.lastSentHeartbeatDate=n,s.length>0?(this._heartbeatsCache.heartbeats=s,await this._storage.overwrite(this._heartbeatsCache)):(this._heartbeatsCache.heartbeats=[],this._storage.overwrite(this._heartbeatsCache)),i}catch(n){return Nt.warn(n),""}}}function ba(){return new Date().toISOString().substring(0,10)}function Vg(e,t=Ug){const n=[];let r=e.slice();for(const s of e){const i=n.find(o=>o.agent===s.agent);if(i){if(i.dates.push(s.date),Ea(n)>t){i.dates.pop();break}}else if(n.push({agent:s.agent,dates:[s.date]}),Ea(n)>t){n.pop();break}r=r.slice(1)}return{heartbeatsToSend:n,unsentEntries:r}}class Hg{constructor(t){this.app=t,this._canUseIndexedDBPromise=this.runIndexedDBEnvironmentCheck()}async runIndexedDBEnvironmentCheck(){return Ap()?Cp().then(()=>!0).catch(()=>!1):!1}async read(){if(await this._canUseIndexedDBPromise){const n=await Lg(this.app);return n?.heartbeats?n:{heartbeats:[]}}else return{heartbeats:[]}}async overwrite(t){var n;if(await this._canUseIndexedDBPromise){const s=await this.read();return ya(this.app,{lastSentHeartbeatDate:(n=t.lastSentHeartbeatDate)!==null&&n!==void 0?n:s.lastSentHeartbeatDate,heartbeats:t.heartbeats})}else return}async add(t){var n;if(await this._canUseIndexedDBPromise){const s=await this.read();return ya(this.app,{lastSentHeartbeatDate:(n=t.lastSentHeartbeatDate)!==null&&n!==void 0?n:s.lastSentHeartbeatDate,heartbeats:[...s.heartbeats,...t.heartbeats]})}else return}}function Ea(e){return Nl(JSON.stringify({version:2,heartbeats:e})).length}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function jg(e){pr(new Un("platform-logger",t=>new eg(t),"PRIVATE")),pr(new Un("heartbeat",t=>new Bg(t),"PRIVATE")),Rn(_i,_a,e),Rn(_i,_a,"esm2017"),Rn("fire-js","")}jg("");var $g="firebase",Wg="10.14.1";/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */Rn($g,Wg,"app");function Wi(e,t){var n={};for(var r in e)Object.prototype.hasOwnProperty.call(e,r)&&t.indexOf(r)<0&&(n[r]=e[r]);if(e!=null&&typeof Object.getOwnPropertySymbols=="function")for(var s=0,r=Object.getOwnPropertySymbols(e);s<r.length;s++)t.indexOf(r[s])<0&&Object.prototype.propertyIsEnumerable.call(e,r[s])&&(n[r[s]]=e[r[s]]);return n}function $l(){return{"dependent-sdk-initialized-before-auth":"Another Firebase SDK was initialized and is trying to use Auth before Auth is initialized. Please be sure to call `initializeAuth` or `getAuth` before starting any other Firebase SDK."}}const Kg=$l,Wl=new Ir("auth","Firebase",$l());/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const Zr=new Ll("@firebase/auth");function Gg(e,...t){Zr.logLevel<=ue.WARN&&Zr.warn(`Auth (${Sr}): ${e}`,...t)}function Fr(e,...t){Zr.logLevel<=ue.ERROR&&Zr.error(`Auth (${Sr}): ${e}`,...t)}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function ht(e,...t){throw Gi(e,...t)}function Ye(e,...t){return Gi(e,...t)}function Ki(e,t,n){const r=Object.assign(Object.assign({},Kg()),{[t]:n});return new Ir("auth","Firebase",r).create(t,{appName:e.name})}function pn(e){return Ki(e,"operation-not-supported-in-this-environment","Operations that alter the current user are not supported in conjunction with FirebaseServerApp")}function zg(e,t,n){const r=n;if(!(t instanceof r))throw r.name!==t.constructor.name&&ht(e,"argument-error"),Ki(e,"argument-error",`Type of ${t.constructor.name} does not match expected instance.Did you pass a reference from a different Auth SDK?`)}function Gi(e,...t){if(typeof e!="string"){const n=t[0],r=[...t.slice(1)];return r[0]&&(r[0].appName=e.name),e._errorFactory.create(n,...r)}return Wl.create(e,...t)}function K(e,t,...n){if(!e)throw Gi(t,...n)}function Tt(e){const t="INTERNAL ASSERTION FAILED: "+e;throw Fr(t),new Error(t)}function xt(e,t){e||Tt(t)}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function bi(){var e;return typeof self<"u"&&((e=self.location)===null||e===void 0?void 0:e.href)||""}function qg(){return Ia()==="http:"||Ia()==="https:"}function Ia(){var e;return typeof self<"u"&&((e=self.location)===null||e===void 0?void 0:e.protocol)||null}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function Jg(){return typeof navigator<"u"&&navigator&&"onLine"in navigator&&typeof navigator.onLine=="boolean"&&(qg()||wp()||"connection"in navigator)?navigator.onLine:!0}function Yg(){if(typeof navigator>"u")return null;const e=navigator;return e.languages&&e.languages[0]||e.language||null}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class Tr{constructor(t,n){this.shortDelay=t,this.longDelay=n,xt(n>t,"Short delay should be less than long delay!"),this.isMobile=Ep()||Sp()}get(){return Jg()?this.isMobile?this.longDelay:this.shortDelay:Math.min(5e3,this.shortDelay)}}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function zi(e,t){xt(e.emulator,"Emulator should always be set here");const{url:n}=e.emulator;return t?`${n}${t.startsWith("/")?t.slice(1):t}`:n}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class Kl{static initialize(t,n,r){this.fetchImpl=t,n&&(this.headersImpl=n),r&&(this.responseImpl=r)}static fetch(){if(this.fetchImpl)return this.fetchImpl;if(typeof self<"u"&&"fetch"in self)return self.fetch;if(typeof globalThis<"u"&&globalThis.fetch)return globalThis.fetch;if(typeof fetch<"u")return fetch;Tt("Could not find fetch implementation, make sure you call FetchProvider.initialize() with an appropriate polyfill")}static headers(){if(this.headersImpl)return this.headersImpl;if(typeof self<"u"&&"Headers"in self)return self.Headers;if(typeof globalThis<"u"&&globalThis.Headers)return globalThis.Headers;if(typeof Headers<"u")return Headers;Tt("Could not find Headers implementation, make sure you call FetchProvider.initialize() with an appropriate polyfill")}static response(){if(this.responseImpl)return this.responseImpl;if(typeof self<"u"&&"Response"in self)return self.Response;if(typeof globalThis<"u"&&globalThis.Response)return globalThis.Response;if(typeof Response<"u")return Response;Tt("Could not find Response implementation, make sure you call FetchProvider.initialize() with an appropriate polyfill")}}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const Xg={CREDENTIAL_MISMATCH:"custom-token-mismatch",MISSING_CUSTOM_TOKEN:"internal-error",INVALID_IDENTIFIER:"invalid-email",MISSING_CONTINUE_URI:"internal-error",INVALID_PASSWORD:"wrong-password",MISSING_PASSWORD:"missing-password",INVALID_LOGIN_CREDENTIALS:"invalid-credential",EMAIL_EXISTS:"email-already-in-use",PASSWORD_LOGIN_DISABLED:"operation-not-allowed",INVALID_IDP_RESPONSE:"invalid-credential",INVALID_PENDING_TOKEN:"invalid-credential",FEDERATED_USER_ID_ALREADY_LINKED:"credential-already-in-use",MISSING_REQ_TYPE:"internal-error",EMAIL_NOT_FOUND:"user-not-found",RESET_PASSWORD_EXCEED_LIMIT:"too-many-requests",EXPIRED_OOB_CODE:"expired-action-code",INVALID_OOB_CODE:"invalid-action-code",MISSING_OOB_CODE:"internal-error",CREDENTIAL_TOO_OLD_LOGIN_AGAIN:"requires-recent-login",INVALID_ID_TOKEN:"invalid-user-token",TOKEN_EXPIRED:"user-token-expired",USER_NOT_FOUND:"user-token-expired",TOO_MANY_ATTEMPTS_TRY_LATER:"too-many-requests",PASSWORD_DOES_NOT_MEET_REQUIREMENTS:"password-does-not-meet-requirements",INVALID_CODE:"invalid-verification-code",INVALID_SESSION_INFO:"invalid-verification-id",INVALID_TEMPORARY_PROOF:"invalid-credential",MISSING_SESSION_INFO:"missing-verification-id",SESSION_EXPIRED:"code-expired",MISSING_ANDROID_PACKAGE_NAME:"missing-android-pkg-name",UNAUTHORIZED_DOMAIN:"unauthorized-continue-uri",INVALID_OAUTH_CLIENT_ID:"invalid-oauth-client-id",ADMIN_ONLY_OPERATION:"admin-restricted-operation",INVALID_MFA_PENDING_CREDENTIAL:"invalid-multi-factor-session",MFA_ENROLLMENT_NOT_FOUND:"multi-factor-info-not-found",MISSING_MFA_ENROLLMENT_ID:"missing-multi-factor-info",MISSING_MFA_PENDING_CREDENTIAL:"missing-multi-factor-session",SECOND_FACTOR_EXISTS:"second-factor-already-in-use",SECOND_FACTOR_LIMIT_EXCEEDED:"maximum-second-factor-count-exceeded",BLOCKING_FUNCTION_ERROR_RESPONSE:"internal-error",RECAPTCHA_NOT_ENABLED:"recaptcha-not-enabled",MISSING_RECAPTCHA_TOKEN:"missing-recaptcha-token",INVALID_RECAPTCHA_TOKEN:"invalid-recaptcha-token",INVALID_RECAPTCHA_ACTION:"invalid-recaptcha-action",MISSING_CLIENT_TYPE:"missing-client-type",MISSING_RECAPTCHA_VERSION:"missing-recaptcha-version",INVALID_RECAPTCHA_VERSION:"invalid-recaptcha-version",INVALID_REQ_TYPE:"invalid-req-type"};/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const Qg=new Tr(3e4,6e4);function qi(e,t){return e.tenantId&&!t.tenantId?Object.assign(Object.assign({},t),{tenantId:e.tenantId}):t}async function Vn(e,t,n,r,s={}){return Gl(e,s,async()=>{let i={},o={};r&&(t==="GET"?o=r:i={body:JSON.stringify(r)});const a=wr(Object.assign({key:e.config.apiKey},o)).slice(1),c=await e._getAdditionalHeaders();c["Content-Type"]="application/json",e.languageCode&&(c["X-Firebase-Locale"]=e.languageCode);const l=Object.assign({method:t,headers:c},i);return Ip()||(l.referrerPolicy="no-referrer"),Kl.fetch()(zl(e,e.config.apiHost,n,a),l)})}async function Gl(e,t,n){e._canInitEmulator=!1;const r=Object.assign(Object.assign({},Xg),t);try{const s=new em(e),i=await Promise.race([n(),s.promise]);s.clearNetworkTimeout();const o=await i.json();if("needConfirmation"in o)throw kr(e,"account-exists-with-different-credential",o);if(i.ok&&!("errorMessage"in o))return o;{const a=i.ok?o.errorMessage:o.error.message,[c,l]=a.split(" : ");if(c==="FEDERATED_USER_ID_ALREADY_LINKED")throw kr(e,"credential-already-in-use",o);if(c==="EMAIL_EXISTS")throw kr(e,"email-already-in-use",o);if(c==="USER_DISABLED")throw kr(e,"user-disabled",o);const u=r[c]||c.toLowerCase().replace(/[_\s]+/g,"-");if(l)throw Ki(e,u,l);ht(e,u)}}catch(s){if(s instanceof Qt)throw s;ht(e,"network-request-failed",{message:String(s)})}}async function Zg(e,t,n,r,s={}){const i=await Vn(e,t,n,r,s);return"mfaPendingCredential"in i&&ht(e,"multi-factor-auth-required",{_serverResponse:i}),i}function zl(e,t,n,r){const s=`${t}${n}?${r}`;return e.config.emulator?zi(e.config,s):`${e.config.apiScheme}://${s}`}class em{constructor(t){this.auth=t,this.timer=null,this.promise=new Promise((n,r)=>{this.timer=setTimeout(()=>r(Ye(this.auth,"network-request-failed")),Qg.get())})}clearNetworkTimeout(){clearTimeout(this.timer)}}function kr(e,t,n){const r={appName:e.name};n.email&&(r.email=n.email),n.phoneNumber&&(r.phoneNumber=n.phoneNumber);const s=Ye(e,t,r);return s.customData._tokenResponse=n,s}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */async function tm(e,t){return Vn(e,"POST","/v1/accounts:delete",t)}async function ql(e,t){return Vn(e,"POST","/v1/accounts:lookup",t)}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function sr(e){if(e)try{const t=new Date(Number(e));if(!isNaN(t.getTime()))return t.toUTCString()}catch{}}async function nm(e,t=!1){const n=Zt(e),r=await n.getIdToken(t),s=Ji(r);K(s&&s.exp&&s.auth_time&&s.iat,n.auth,"internal-error");const i=typeof s.firebase=="object"?s.firebase:void 0,o=i?.sign_in_provider;return{claims:s,token:r,authTime:sr(Js(s.auth_time)),issuedAtTime:sr(Js(s.iat)),expirationTime:sr(Js(s.exp)),signInProvider:o||null,signInSecondFactor:i?.sign_in_second_factor||null}}function Js(e){return Number(e)*1e3}function Ji(e){const[t,n,r]=e.split(".");if(t===void 0||n===void 0||r===void 0)return Fr("JWT malformed, contained fewer than 3 sections"),null;try{const s=xl(n);return s?JSON.parse(s):(Fr("Failed to decode base64 JWT payload"),null)}catch(s){return Fr("Caught error parsing JWT payload as JSON",s?.toString()),null}}function wa(e){const t=Ji(e);return K(t,"internal-error"),K(typeof t.exp<"u","internal-error"),K(typeof t.iat<"u","internal-error"),Number(t.exp)-Number(t.iat)}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */async function mr(e,t,n=!1){if(n)return t;try{return await t}catch(r){throw r instanceof Qt&&rm(r)&&e.auth.currentUser===e&&await e.auth.signOut(),r}}function rm({code:e}){return e==="auth/user-disabled"||e==="auth/user-token-expired"}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class sm{constructor(t){this.user=t,this.isRunning=!1,this.timerId=null,this.errorBackoff=3e4}_start(){this.isRunning||(this.isRunning=!0,this.schedule())}_stop(){this.isRunning&&(this.isRunning=!1,this.timerId!==null&&clearTimeout(this.timerId))}getInterval(t){var n;if(t){const r=this.errorBackoff;return this.errorBackoff=Math.min(this.errorBackoff*2,96e4),r}else{this.errorBackoff=3e4;const s=((n=this.user.stsTokenManager.expirationTime)!==null&&n!==void 0?n:0)-Date.now()-3e5;return Math.max(0,s)}}schedule(t=!1){if(!this.isRunning)return;const n=this.getInterval(t);this.timerId=setTimeout(async()=>{await this.iteration()},n)}async iteration(){try{await this.user.getIdToken(!0)}catch(t){t?.code==="auth/network-request-failed"&&this.schedule(!0);return}this.schedule()}}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class Ei{constructor(t,n){this.createdAt=t,this.lastLoginAt=n,this._initializeTime()}_initializeTime(){this.lastSignInTime=sr(this.lastLoginAt),this.creationTime=sr(this.createdAt)}_copy(t){this.createdAt=t.createdAt,this.lastLoginAt=t.lastLoginAt,this._initializeTime()}toJSON(){return{createdAt:this.createdAt,lastLoginAt:this.lastLoginAt}}}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */async function es(e){var t;const n=e.auth,r=await e.getIdToken(),s=await mr(e,ql(n,{idToken:r}));K(s?.users.length,n,"internal-error");const i=s.users[0];e._notifyReloadListener(i);const o=!((t=i.providerUserInfo)===null||t===void 0)&&t.length?Jl(i.providerUserInfo):[],a=om(e.providerData,o),c=e.isAnonymous,l=!(e.email&&i.passwordHash)&&!a?.length,u=c?l:!1,f={uid:i.localId,displayName:i.displayName||null,photoURL:i.photoUrl||null,email:i.email||null,emailVerified:i.emailVerified||!1,phoneNumber:i.phoneNumber||null,tenantId:i.tenantId||null,providerData:a,metadata:new Ei(i.createdAt,i.lastLoginAt),isAnonymous:u};Object.assign(e,f)}async function im(e){const t=Zt(e);await es(t),await t.auth._persistUserIfCurrent(t),t.auth._notifyListenersIfCurrent(t)}function om(e,t){return[...e.filter(r=>!t.some(s=>s.providerId===r.providerId)),...t]}function Jl(e){return e.map(t=>{var{providerId:n}=t,r=Wi(t,["providerId"]);return{providerId:n,uid:r.rawId||"",displayName:r.displayName||null,email:r.email||null,phoneNumber:r.phoneNumber||null,photoURL:r.photoUrl||null}})}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */async function am(e,t){const n=await Gl(e,{},async()=>{const r=wr({grant_type:"refresh_token",refresh_token:t}).slice(1),{tokenApiHost:s,apiKey:i}=e.config,o=zl(e,s,"/v1/token",`key=${i}`),a=await e._getAdditionalHeaders();return a["Content-Type"]="application/x-www-form-urlencoded",Kl.fetch()(o,{method:"POST",headers:a,body:r})});return{accessToken:n.access_token,expiresIn:n.expires_in,refreshToken:n.refresh_token}}async function cm(e,t){return Vn(e,"POST","/v2/accounts:revokeToken",qi(e,t))}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class Pn{constructor(){this.refreshToken=null,this.accessToken=null,this.expirationTime=null}get isExpired(){return!this.expirationTime||Date.now()>this.expirationTime-3e4}updateFromServerResponse(t){K(t.idToken,"internal-error"),K(typeof t.idToken<"u","internal-error"),K(typeof t.refreshToken<"u","internal-error");const n="expiresIn"in t&&typeof t.expiresIn<"u"?Number(t.expiresIn):wa(t.idToken);this.updateTokensAndExpiration(t.idToken,t.refreshToken,n)}updateFromIdToken(t){K(t.length!==0,"internal-error");const n=wa(t);this.updateTokensAndExpiration(t,null,n)}async getToken(t,n=!1){return!n&&this.accessToken&&!this.isExpired?this.accessToken:(K(this.refreshToken,t,"user-token-expired"),this.refreshToken?(await this.refresh(t,this.refreshToken),this.accessToken):null)}clearRefreshToken(){this.refreshToken=null}async refresh(t,n){const{accessToken:r,refreshToken:s,expiresIn:i}=await am(t,n);this.updateTokensAndExpiration(r,s,Number(i))}updateTokensAndExpiration(t,n,r){this.refreshToken=n||null,this.accessToken=t||null,this.expirationTime=Date.now()+r*1e3}static fromJSON(t,n){const{refreshToken:r,accessToken:s,expirationTime:i}=n,o=new Pn;return r&&(K(typeof r=="string","internal-error",{appName:t}),o.refreshToken=r),s&&(K(typeof s=="string","internal-error",{appName:t}),o.accessToken=s),i&&(K(typeof i=="number","internal-error",{appName:t}),o.expirationTime=i),o}toJSON(){return{refreshToken:this.refreshToken,accessToken:this.accessToken,expirationTime:this.expirationTime}}_assign(t){this.accessToken=t.accessToken,this.refreshToken=t.refreshToken,this.expirationTime=t.expirationTime}_clone(){return Object.assign(new Pn,this.toJSON())}_performRefresh(){return Tt("not implemented")}}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function Ft(e,t){K(typeof e=="string"||typeof e>"u","internal-error",{appName:t})}class At{constructor(t){var{uid:n,auth:r,stsTokenManager:s}=t,i=Wi(t,["uid","auth","stsTokenManager"]);this.providerId="firebase",this.proactiveRefresh=new sm(this),this.reloadUserInfo=null,this.reloadListener=null,this.uid=n,this.auth=r,this.stsTokenManager=s,this.accessToken=s.accessToken,this.displayName=i.displayName||null,this.email=i.email||null,this.emailVerified=i.emailVerified||!1,this.phoneNumber=i.phoneNumber||null,this.photoURL=i.photoURL||null,this.isAnonymous=i.isAnonymous||!1,this.tenantId=i.tenantId||null,this.providerData=i.providerData?[...i.providerData]:[],this.metadata=new Ei(i.createdAt||void 0,i.lastLoginAt||void 0)}async getIdToken(t){const n=await mr(this,this.stsTokenManager.getToken(this.auth,t));return K(n,this.auth,"internal-error"),this.accessToken!==n&&(this.accessToken=n,await this.auth._persistUserIfCurrent(this),this.auth._notifyListenersIfCurrent(this)),n}getIdTokenResult(t){return nm(this,t)}reload(){return im(this)}_assign(t){this!==t&&(K(this.uid===t.uid,this.auth,"internal-error"),this.displayName=t.displayName,this.photoURL=t.photoURL,this.email=t.email,this.emailVerified=t.emailVerified,this.phoneNumber=t.phoneNumber,this.isAnonymous=t.isAnonymous,this.tenantId=t.tenantId,this.providerData=t.providerData.map(n=>Object.assign({},n)),this.metadata._copy(t.metadata),this.stsTokenManager._assign(t.stsTokenManager))}_clone(t){const n=new At(Object.assign(Object.assign({},this),{auth:t,stsTokenManager:this.stsTokenManager._clone()}));return n.metadata._copy(this.metadata),n}_onReload(t){K(!this.reloadListener,this.auth,"internal-error"),this.reloadListener=t,this.reloadUserInfo&&(this._notifyReloadListener(this.reloadUserInfo),this.reloadUserInfo=null)}_notifyReloadListener(t){this.reloadListener?this.reloadListener(t):this.reloadUserInfo=t}_startProactiveRefresh(){this.proactiveRefresh._start()}_stopProactiveRefresh(){this.proactiveRefresh._stop()}async _updateTokensIfNecessary(t,n=!1){let r=!1;t.idToken&&t.idToken!==this.stsTokenManager.accessToken&&(this.stsTokenManager.updateFromServerResponse(t),r=!0),n&&await es(this),await this.auth._persistUserIfCurrent(this),r&&this.auth._notifyListenersIfCurrent(this)}async delete(){if(St(this.auth.app))return Promise.reject(pn(this.auth));const t=await this.getIdToken();return await mr(this,tm(this.auth,{idToken:t})),this.stsTokenManager.clearRefreshToken(),this.auth.signOut()}toJSON(){return Object.assign(Object.assign({uid:this.uid,email:this.email||void 0,emailVerified:this.emailVerified,displayName:this.displayName||void 0,isAnonymous:this.isAnonymous,photoURL:this.photoURL||void 0,phoneNumber:this.phoneNumber||void 0,tenantId:this.tenantId||void 0,providerData:this.providerData.map(t=>Object.assign({},t)),stsTokenManager:this.stsTokenManager.toJSON(),_redirectEventId:this._redirectEventId},this.metadata.toJSON()),{apiKey:this.auth.config.apiKey,appName:this.auth.name})}get refreshToken(){return this.stsTokenManager.refreshToken||""}static _fromJSON(t,n){var r,s,i,o,a,c,l,u;const f=(r=n.displayName)!==null&&r!==void 0?r:void 0,p=(s=n.email)!==null&&s!==void 0?s:void 0,g=(i=n.phoneNumber)!==null&&i!==void 0?i:void 0,I=(o=n.photoURL)!==null&&o!==void 0?o:void 0,w=(a=n.tenantId)!==null&&a!==void 0?a:void 0,L=(c=n._redirectEventId)!==null&&c!==void 0?c:void 0,M=(l=n.createdAt)!==null&&l!==void 0?l:void 0,A=(u=n.lastLoginAt)!==null&&u!==void 0?u:void 0,{uid:x,emailVerified:N,isAnonymous:H,providerData:te,stsTokenManager:J}=n;K(x&&J,t,"internal-error");const G=Pn.fromJSON(this.name,J);K(typeof x=="string",t,"internal-error"),Ft(f,t.name),Ft(p,t.name),K(typeof N=="boolean",t,"internal-error"),K(typeof H=="boolean",t,"internal-error"),Ft(g,t.name),Ft(I,t.name),Ft(w,t.name),Ft(L,t.name),Ft(M,t.name),Ft(A,t.name);const C=new At({uid:x,auth:t,email:p,emailVerified:N,displayName:f,isAnonymous:H,photoURL:I,phoneNumber:g,tenantId:w,stsTokenManager:G,createdAt:M,lastLoginAt:A});return te&&Array.isArray(te)&&(C.providerData=te.map(j=>Object.assign({},j))),L&&(C._redirectEventId=L),C}static async _fromIdTokenResponse(t,n,r=!1){const s=new Pn;s.updateFromServerResponse(n);const i=new At({uid:n.localId,auth:t,stsTokenManager:s,isAnonymous:r});return await es(i),i}static async _fromGetAccountInfoResponse(t,n,r){const s=n.users[0];K(s.localId!==void 0,"internal-error");const i=s.providerUserInfo!==void 0?Jl(s.providerUserInfo):[],o=!(s.email&&s.passwordHash)&&!i?.length,a=new Pn;a.updateFromIdToken(r);const c=new At({uid:s.localId,auth:t,stsTokenManager:a,isAnonymous:o}),l={uid:s.localId,displayName:s.displayName||null,photoURL:s.photoUrl||null,email:s.email||null,emailVerified:s.emailVerified||!1,phoneNumber:s.phoneNumber||null,tenantId:s.tenantId||null,providerData:i,metadata:new Ei(s.createdAt,s.lastLoginAt),isAnonymous:!(s.email&&s.passwordHash)&&!i?.length};return Object.assign(c,l),c}}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const Sa=new Map;function Ct(e){xt(e instanceof Function,"Expected a class definition");let t=Sa.get(e);return t?(xt(t instanceof e,"Instance stored in cache mismatched with class"),t):(t=new e,Sa.set(e,t),t)}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class Yl{constructor(){this.type="NONE",this.storage={}}async _isAvailable(){return!0}async _set(t,n){this.storage[t]=n}async _get(t){const n=this.storage[t];return n===void 0?null:n}async _remove(t){delete this.storage[t]}_addListener(t,n){}_removeListener(t,n){}}Yl.type="NONE";const Ta=Yl;/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function Br(e,t,n){return`firebase:${e}:${t}:${n}`}class On{constructor(t,n,r){this.persistence=t,this.auth=n,this.userKey=r;const{config:s,name:i}=this.auth;this.fullUserKey=Br(this.userKey,s.apiKey,i),this.fullPersistenceKey=Br("persistence",s.apiKey,i),this.boundEventHandler=n._onStorageEvent.bind(n),this.persistence._addListener(this.fullUserKey,this.boundEventHandler)}setCurrentUser(t){return this.persistence._set(this.fullUserKey,t.toJSON())}async getCurrentUser(){const t=await this.persistence._get(this.fullUserKey);return t?At._fromJSON(this.auth,t):null}removeCurrentUser(){return this.persistence._remove(this.fullUserKey)}savePersistenceForRedirect(){return this.persistence._set(this.fullPersistenceKey,this.persistence.type)}async setPersistence(t){if(this.persistence===t)return;const n=await this.getCurrentUser();if(await this.removeCurrentUser(),this.persistence=t,n)return this.setCurrentUser(n)}delete(){this.persistence._removeListener(this.fullUserKey,this.boundEventHandler)}static async create(t,n,r="authUser"){if(!n.length)return new On(Ct(Ta),t,r);const s=(await Promise.all(n.map(async l=>{if(await l._isAvailable())return l}))).filter(l=>l);let i=s[0]||Ct(Ta);const o=Br(r,t.config.apiKey,t.name);let a=null;for(const l of n)try{const u=await l._get(o);if(u){const f=At._fromJSON(t,u);l!==i&&(a=f),i=l;break}}catch{}const c=s.filter(l=>l._shouldAllowMigration);return!i._shouldAllowMigration||!c.length?new On(i,t,r):(i=c[0],a&&await i._set(o,a.toJSON()),await Promise.all(n.map(async l=>{if(l!==i)try{await l._remove(o)}catch{}})),new On(i,t,r))}}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function Aa(e){const t=e.toLowerCase();if(t.includes("opera/")||t.includes("opr/")||t.includes("opios/"))return"Opera";if(eu(t))return"IEMobile";if(t.includes("msie")||t.includes("trident/"))return"IE";if(t.includes("edge/"))return"Edge";if(Xl(t))return"Firefox";if(t.includes("silk/"))return"Silk";if(nu(t))return"Blackberry";if(ru(t))return"Webos";if(Ql(t))return"Safari";if((t.includes("chrome/")||Zl(t))&&!t.includes("edge/"))return"Chrome";if(tu(t))return"Android";{const n=/([a-zA-Z\d\.]+)\/[a-zA-Z\d\.]*$/,r=e.match(n);if(r?.length===2)return r[1]}return"Other"}function Xl(e=Me()){return/firefox\//i.test(e)}function Ql(e=Me()){const t=e.toLowerCase();return t.includes("safari/")&&!t.includes("chrome/")&&!t.includes("crios/")&&!t.includes("android")}function Zl(e=Me()){return/crios\//i.test(e)}function eu(e=Me()){return/iemobile/i.test(e)}function tu(e=Me()){return/android/i.test(e)}function nu(e=Me()){return/blackberry/i.test(e)}function ru(e=Me()){return/webos/i.test(e)}function Yi(e=Me()){return/iphone|ipad|ipod/i.test(e)||/macintosh/i.test(e)&&/mobile/i.test(e)}function lm(e=Me()){var t;return Yi(e)&&!!(!((t=window.navigator)===null||t===void 0)&&t.standalone)}function um(){return Tp()&&document.documentMode===10}function su(e=Me()){return Yi(e)||tu(e)||ru(e)||nu(e)||/windows phone/i.test(e)||eu(e)}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function iu(e,t=[]){let n;switch(e){case"Browser":n=Aa(Me());break;case"Worker":n=`${Aa(Me())}-${e}`;break;default:n=e}const r=t.length?t.join(","):"FirebaseCore-web";return`${n}/JsCore/${Sr}/${r}`}/**
 * @license
 * Copyright 2022 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class fm{constructor(t){this.auth=t,this.queue=[]}pushCallback(t,n){const r=i=>new Promise((o,a)=>{try{const c=t(i);o(c)}catch(c){a(c)}});r.onAbort=n,this.queue.push(r);const s=this.queue.length-1;return()=>{this.queue[s]=()=>Promise.resolve()}}async runMiddleware(t){if(this.auth.currentUser===t)return;const n=[];try{for(const r of this.queue)await r(t),r.onAbort&&n.push(r.onAbort)}catch(r){n.reverse();for(const s of n)try{s()}catch{}throw this.auth._errorFactory.create("login-blocked",{originalMessage:r?.message})}}}/**
 * @license
 * Copyright 2023 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */async function dm(e,t={}){return Vn(e,"GET","/v2/passwordPolicy",qi(e,t))}/**
 * @license
 * Copyright 2023 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const hm=6;class pm{constructor(t){var n,r,s,i;const o=t.customStrengthOptions;this.customStrengthOptions={},this.customStrengthOptions.minPasswordLength=(n=o.minPasswordLength)!==null&&n!==void 0?n:hm,o.maxPasswordLength&&(this.customStrengthOptions.maxPasswordLength=o.maxPasswordLength),o.containsLowercaseCharacter!==void 0&&(this.customStrengthOptions.containsLowercaseLetter=o.containsLowercaseCharacter),o.containsUppercaseCharacter!==void 0&&(this.customStrengthOptions.containsUppercaseLetter=o.containsUppercaseCharacter),o.containsNumericCharacter!==void 0&&(this.customStrengthOptions.containsNumericCharacter=o.containsNumericCharacter),o.containsNonAlphanumericCharacter!==void 0&&(this.customStrengthOptions.containsNonAlphanumericCharacter=o.containsNonAlphanumericCharacter),this.enforcementState=t.enforcementState,this.enforcementState==="ENFORCEMENT_STATE_UNSPECIFIED"&&(this.enforcementState="OFF"),this.allowedNonAlphanumericCharacters=(s=(r=t.allowedNonAlphanumericCharacters)===null||r===void 0?void 0:r.join(""))!==null&&s!==void 0?s:"",this.forceUpgradeOnSignin=(i=t.forceUpgradeOnSignin)!==null&&i!==void 0?i:!1,this.schemaVersion=t.schemaVersion}validatePassword(t){var n,r,s,i,o,a;const c={isValid:!0,passwordPolicy:this};return this.validatePasswordLengthOptions(t,c),this.validatePasswordCharacterOptions(t,c),c.isValid&&(c.isValid=(n=c.meetsMinPasswordLength)!==null&&n!==void 0?n:!0),c.isValid&&(c.isValid=(r=c.meetsMaxPasswordLength)!==null&&r!==void 0?r:!0),c.isValid&&(c.isValid=(s=c.containsLowercaseLetter)!==null&&s!==void 0?s:!0),c.isValid&&(c.isValid=(i=c.containsUppercaseLetter)!==null&&i!==void 0?i:!0),c.isValid&&(c.isValid=(o=c.containsNumericCharacter)!==null&&o!==void 0?o:!0),c.isValid&&(c.isValid=(a=c.containsNonAlphanumericCharacter)!==null&&a!==void 0?a:!0),c}validatePasswordLengthOptions(t,n){const r=this.customStrengthOptions.minPasswordLength,s=this.customStrengthOptions.maxPasswordLength;r&&(n.meetsMinPasswordLength=t.length>=r),s&&(n.meetsMaxPasswordLength=t.length<=s)}validatePasswordCharacterOptions(t,n){this.updatePasswordCharacterOptionsStatuses(n,!1,!1,!1,!1);let r;for(let s=0;s<t.length;s++)r=t.charAt(s),this.updatePasswordCharacterOptionsStatuses(n,r>="a"&&r<="z",r>="A"&&r<="Z",r>="0"&&r<="9",this.allowedNonAlphanumericCharacters.includes(r))}updatePasswordCharacterOptionsStatuses(t,n,r,s,i){this.customStrengthOptions.containsLowercaseLetter&&(t.containsLowercaseLetter||(t.containsLowercaseLetter=n)),this.customStrengthOptions.containsUppercaseLetter&&(t.containsUppercaseLetter||(t.containsUppercaseLetter=r)),this.customStrengthOptions.containsNumericCharacter&&(t.containsNumericCharacter||(t.containsNumericCharacter=s)),this.customStrengthOptions.containsNonAlphanumericCharacter&&(t.containsNonAlphanumericCharacter||(t.containsNonAlphanumericCharacter=i))}}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class gm{constructor(t,n,r,s){this.app=t,this.heartbeatServiceProvider=n,this.appCheckServiceProvider=r,this.config=s,this.currentUser=null,this.emulatorConfig=null,this.operations=Promise.resolve(),this.authStateSubscription=new Ca(this),this.idTokenSubscription=new Ca(this),this.beforeStateQueue=new fm(this),this.redirectUser=null,this.isProactiveRefreshEnabled=!1,this.EXPECTED_PASSWORD_POLICY_SCHEMA_VERSION=1,this._canInitEmulator=!0,this._isInitialized=!1,this._deleted=!1,this._initializationPromise=null,this._popupRedirectResolver=null,this._errorFactory=Wl,this._agentRecaptchaConfig=null,this._tenantRecaptchaConfigs={},this._projectPasswordPolicy=null,this._tenantPasswordPolicies={},this.lastNotifiedUid=void 0,this.languageCode=null,this.tenantId=null,this.settings={appVerificationDisabledForTesting:!1},this.frameworks=[],this.name=t.name,this.clientVersion=s.sdkClientVersion}_initializeWithPersistence(t,n){return n&&(this._popupRedirectResolver=Ct(n)),this._initializationPromise=this.queue(async()=>{var r,s;if(!this._deleted&&(this.persistenceManager=await On.create(this,t),!this._deleted)){if(!((r=this._popupRedirectResolver)===null||r===void 0)&&r._shouldInitProactively)try{await this._popupRedirectResolver._initialize(this)}catch{}await this.initializeCurrentUser(n),this.lastNotifiedUid=((s=this.currentUser)===null||s===void 0?void 0:s.uid)||null,!this._deleted&&(this._isInitialized=!0)}}),this._initializationPromise}async _onStorageEvent(){if(this._deleted)return;const t=await this.assertedPersistence.getCurrentUser();if(!(!this.currentUser&&!t)){if(this.currentUser&&t&&this.currentUser.uid===t.uid){this._currentUser._assign(t),await this.currentUser.getIdToken();return}await this._updateCurrentUser(t,!0)}}async initializeCurrentUserFromIdToken(t){try{const n=await ql(this,{idToken:t}),r=await At._fromGetAccountInfoResponse(this,n,t);await this.directlySetCurrentUser(r)}catch(n){console.warn("FirebaseServerApp could not login user with provided authIdToken: ",n),await this.directlySetCurrentUser(null)}}async initializeCurrentUser(t){var n;if(St(this.app)){const o=this.app.settings.authIdToken;return o?new Promise(a=>{setTimeout(()=>this.initializeCurrentUserFromIdToken(o).then(a,a))}):this.directlySetCurrentUser(null)}const r=await this.assertedPersistence.getCurrentUser();let s=r,i=!1;if(t&&this.config.authDomain){await this.getOrInitRedirectPersistenceManager();const o=(n=this.redirectUser)===null||n===void 0?void 0:n._redirectEventId,a=s?._redirectEventId,c=await this.tryRedirectSignIn(t);(!o||o===a)&&c?.user&&(s=c.user,i=!0)}if(!s)return this.directlySetCurrentUser(null);if(!s._redirectEventId){if(i)try{await this.beforeStateQueue.runMiddleware(s)}catch(o){s=r,this._popupRedirectResolver._overrideRedirectResult(this,()=>Promise.reject(o))}return s?this.reloadAndSetCurrentUserOrClear(s):this.directlySetCurrentUser(null)}return K(this._popupRedirectResolver,this,"argument-error"),await this.getOrInitRedirectPersistenceManager(),this.redirectUser&&this.redirectUser._redirectEventId===s._redirectEventId?this.directlySetCurrentUser(s):this.reloadAndSetCurrentUserOrClear(s)}async tryRedirectSignIn(t){let n=null;try{n=await this._popupRedirectResolver._completeRedirectFn(this,t,!0)}catch{await this._setRedirectUser(null)}return n}async reloadAndSetCurrentUserOrClear(t){try{await es(t)}catch(n){if(n?.code!=="auth/network-request-failed")return this.directlySetCurrentUser(null)}return this.directlySetCurrentUser(t)}useDeviceLanguage(){this.languageCode=Yg()}async _delete(){this._deleted=!0}async updateCurrentUser(t){if(St(this.app))return Promise.reject(pn(this));const n=t?Zt(t):null;return n&&K(n.auth.config.apiKey===this.config.apiKey,this,"invalid-user-token"),this._updateCurrentUser(n&&n._clone(this))}async _updateCurrentUser(t,n=!1){if(!this._deleted)return t&&K(this.tenantId===t.tenantId,this,"tenant-id-mismatch"),n||await this.beforeStateQueue.runMiddleware(t),this.queue(async()=>{await this.directlySetCurrentUser(t),this.notifyAuthListeners()})}async signOut(){return St(this.app)?Promise.reject(pn(this)):(await this.beforeStateQueue.runMiddleware(null),(this.redirectPersistenceManager||this._popupRedirectResolver)&&await this._setRedirectUser(null),this._updateCurrentUser(null,!0))}setPersistence(t){return St(this.app)?Promise.reject(pn(this)):this.queue(async()=>{await this.assertedPersistence.setPersistence(Ct(t))})}_getRecaptchaConfig(){return this.tenantId==null?this._agentRecaptchaConfig:this._tenantRecaptchaConfigs[this.tenantId]}async validatePassword(t){this._getPasswordPolicyInternal()||await this._updatePasswordPolicy();const n=this._getPasswordPolicyInternal();return n.schemaVersion!==this.EXPECTED_PASSWORD_POLICY_SCHEMA_VERSION?Promise.reject(this._errorFactory.create("unsupported-password-policy-schema-version",{})):n.validatePassword(t)}_getPasswordPolicyInternal(){return this.tenantId===null?this._projectPasswordPolicy:this._tenantPasswordPolicies[this.tenantId]}async _updatePasswordPolicy(){const t=await dm(this),n=new pm(t);this.tenantId===null?this._projectPasswordPolicy=n:this._tenantPasswordPolicies[this.tenantId]=n}_getPersistence(){return this.assertedPersistence.persistence.type}_updateErrorMap(t){this._errorFactory=new Ir("auth","Firebase",t())}onAuthStateChanged(t,n,r){return this.registerStateListener(this.authStateSubscription,t,n,r)}beforeAuthStateChanged(t,n){return this.beforeStateQueue.pushCallback(t,n)}onIdTokenChanged(t,n,r){return this.registerStateListener(this.idTokenSubscription,t,n,r)}authStateReady(){return new Promise((t,n)=>{if(this.currentUser)t();else{const r=this.onAuthStateChanged(()=>{r(),t()},n)}})}async revokeAccessToken(t){if(this.currentUser){const n=await this.currentUser.getIdToken(),r={providerId:"apple.com",tokenType:"ACCESS_TOKEN",token:t,idToken:n};this.tenantId!=null&&(r.tenantId=this.tenantId),await cm(this,r)}}toJSON(){var t;return{apiKey:this.config.apiKey,authDomain:this.config.authDomain,appName:this.name,currentUser:(t=this._currentUser)===null||t===void 0?void 0:t.toJSON()}}async _setRedirectUser(t,n){const r=await this.getOrInitRedirectPersistenceManager(n);return t===null?r.removeCurrentUser():r.setCurrentUser(t)}async getOrInitRedirectPersistenceManager(t){if(!this.redirectPersistenceManager){const n=t&&Ct(t)||this._popupRedirectResolver;K(n,this,"argument-error"),this.redirectPersistenceManager=await On.create(this,[Ct(n._redirectPersistence)],"redirectUser"),this.redirectUser=await this.redirectPersistenceManager.getCurrentUser()}return this.redirectPersistenceManager}async _redirectUserForId(t){var n,r;return this._isInitialized&&await this.queue(async()=>{}),((n=this._currentUser)===null||n===void 0?void 0:n._redirectEventId)===t?this._currentUser:((r=this.redirectUser)===null||r===void 0?void 0:r._redirectEventId)===t?this.redirectUser:null}async _persistUserIfCurrent(t){if(t===this.currentUser)return this.queue(async()=>this.directlySetCurrentUser(t))}_notifyListenersIfCurrent(t){t===this.currentUser&&this.notifyAuthListeners()}_key(){return`${this.config.authDomain}:${this.config.apiKey}:${this.name}`}_startProactiveRefresh(){this.isProactiveRefreshEnabled=!0,this.currentUser&&this._currentUser._startProactiveRefresh()}_stopProactiveRefresh(){this.isProactiveRefreshEnabled=!1,this.currentUser&&this._currentUser._stopProactiveRefresh()}get _currentUser(){return this.currentUser}notifyAuthListeners(){var t,n;if(!this._isInitialized)return;this.idTokenSubscription.next(this.currentUser);const r=(n=(t=this.currentUser)===null||t===void 0?void 0:t.uid)!==null&&n!==void 0?n:null;this.lastNotifiedUid!==r&&(this.lastNotifiedUid=r,this.authStateSubscription.next(this.currentUser))}registerStateListener(t,n,r,s){if(this._deleted)return()=>{};const i=typeof n=="function"?n:n.next.bind(n);let o=!1;const a=this._isInitialized?Promise.resolve():this._initializationPromise;if(K(a,this,"internal-error"),a.then(()=>{o||i(this.currentUser)}),typeof n=="function"){const c=t.addObserver(n,r,s);return()=>{o=!0,c()}}else{const c=t.addObserver(n);return()=>{o=!0,c()}}}async directlySetCurrentUser(t){this.currentUser&&this.currentUser!==t&&this._currentUser._stopProactiveRefresh(),t&&this.isProactiveRefreshEnabled&&t._startProactiveRefresh(),this.currentUser=t,t?await this.assertedPersistence.setCurrentUser(t):await this.assertedPersistence.removeCurrentUser()}queue(t){return this.operations=this.operations.then(t,t),this.operations}get assertedPersistence(){return K(this.persistenceManager,this,"internal-error"),this.persistenceManager}_logFramework(t){!t||this.frameworks.includes(t)||(this.frameworks.push(t),this.frameworks.sort(),this.clientVersion=iu(this.config.clientPlatform,this._getFrameworks()))}_getFrameworks(){return this.frameworks}async _getAdditionalHeaders(){var t;const n={"X-Client-Version":this.clientVersion};this.app.options.appId&&(n["X-Firebase-gmpid"]=this.app.options.appId);const r=await((t=this.heartbeatServiceProvider.getImmediate({optional:!0}))===null||t===void 0?void 0:t.getHeartbeatsHeader());r&&(n["X-Firebase-Client"]=r);const s=await this._getAppCheckToken();return s&&(n["X-Firebase-AppCheck"]=s),n}async _getAppCheckToken(){var t;const n=await((t=this.appCheckServiceProvider.getImmediate({optional:!0}))===null||t===void 0?void 0:t.getToken());return n?.error&&Gg(`Error while retrieving App Check token: ${n.error}`),n?.token}}function Ss(e){return Zt(e)}class Ca{constructor(t){this.auth=t,this.observer=null,this.addObserver=Np(n=>this.observer=n)}get next(){return K(this.observer,this.auth,"internal-error"),this.observer.next.bind(this.observer)}}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */let Xi={async loadJS(){throw new Error("Unable to load external scripts")},recaptchaV2Script:"",recaptchaEnterpriseScript:"",gapiScript:""};function mm(e){Xi=e}function _m(e){return Xi.loadJS(e)}function vm(){return Xi.gapiScript}function ym(e){return`__${e}${Math.floor(Math.random()*1e6)}`}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function bm(e,t){const n=Bl(e,"auth");if(n.isInitialized()){const s=n.getImmediate(),i=n.getOptions();if(Xr(i,t??{}))return s;ht(s,"already-initialized")}return n.initialize({options:t})}function Em(e,t){const n=t?.persistence||[],r=(Array.isArray(n)?n:[n]).map(Ct);t?.errorMap&&e._updateErrorMap(t.errorMap),e._initializeWithPersistence(r,t?.popupRedirectResolver)}function Im(e,t,n){const r=Ss(e);K(r._canInitEmulator,r,"emulator-config-failed"),K(/^https?:\/\//.test(t),r,"invalid-emulator-scheme");const s=!1,i=ou(t),{host:o,port:a}=wm(t),c=a===null?"":`:${a}`;r.config.emulator={url:`${i}//${o}${c}/`},r.settings.appVerificationDisabledForTesting=!0,r.emulatorConfig=Object.freeze({host:o,port:a,protocol:i.replace(":",""),options:Object.freeze({disableWarnings:s})}),Sm()}function ou(e){const t=e.indexOf(":");return t<0?"":e.substr(0,t+1)}function wm(e){const t=ou(e),n=/(\/\/)?([^?#/]+)/.exec(e.substr(t.length));if(!n)return{host:"",port:null};const r=n[2].split("@").pop()||"",s=/^(\[[^\]]+\])(:|$)/.exec(r);if(s){const i=s[1];return{host:i,port:Ra(r.substr(i.length+1))}}else{const[i,o]=r.split(":");return{host:i,port:Ra(o)}}}function Ra(e){if(!e)return null;const t=Number(e);return isNaN(t)?null:t}function Sm(){function e(){const t=document.createElement("p"),n=t.style;t.innerText="Running in emulator mode. Do not use with production credentials.",n.position="fixed",n.width="100%",n.backgroundColor="#ffffff",n.border=".1em solid #000000",n.color="#b50000",n.bottom="0px",n.left="0px",n.margin="0px",n.zIndex="10000",n.textAlign="center",t.classList.add("firebase-emulator-warning"),document.body.appendChild(t)}typeof console<"u"&&typeof console.info=="function"&&console.info("WARNING: You are using the Auth Emulator, which is intended for local testing only.  Do not use with production credentials."),typeof window<"u"&&typeof document<"u"&&(document.readyState==="loading"?window.addEventListener("DOMContentLoaded",e):e())}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class au{constructor(t,n){this.providerId=t,this.signInMethod=n}toJSON(){return Tt("not implemented")}_getIdTokenResponse(t){return Tt("not implemented")}_linkToIdToken(t,n){return Tt("not implemented")}_getReauthenticationResolver(t){return Tt("not implemented")}}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */async function kn(e,t){return Zg(e,"POST","/v1/accounts:signInWithIdp",qi(e,t))}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const Tm="http://localhost";class gn extends au{constructor(){super(...arguments),this.pendingToken=null}static _fromParams(t){const n=new gn(t.providerId,t.signInMethod);return t.idToken||t.accessToken?(t.idToken&&(n.idToken=t.idToken),t.accessToken&&(n.accessToken=t.accessToken),t.nonce&&!t.pendingToken&&(n.nonce=t.nonce),t.pendingToken&&(n.pendingToken=t.pendingToken)):t.oauthToken&&t.oauthTokenSecret?(n.accessToken=t.oauthToken,n.secret=t.oauthTokenSecret):ht("argument-error"),n}toJSON(){return{idToken:this.idToken,accessToken:this.accessToken,secret:this.secret,nonce:this.nonce,pendingToken:this.pendingToken,providerId:this.providerId,signInMethod:this.signInMethod}}static fromJSON(t){const n=typeof t=="string"?JSON.parse(t):t,{providerId:r,signInMethod:s}=n,i=Wi(n,["providerId","signInMethod"]);if(!r||!s)return null;const o=new gn(r,s);return o.idToken=i.idToken||void 0,o.accessToken=i.accessToken||void 0,o.secret=i.secret,o.nonce=i.nonce,o.pendingToken=i.pendingToken||null,o}_getIdTokenResponse(t){const n=this.buildRequest();return kn(t,n)}_linkToIdToken(t,n){const r=this.buildRequest();return r.idToken=n,kn(t,r)}_getReauthenticationResolver(t){const n=this.buildRequest();return n.autoCreate=!1,kn(t,n)}buildRequest(){const t={requestUri:Tm,returnSecureToken:!0};if(this.pendingToken)t.pendingToken=this.pendingToken;else{const n={};this.idToken&&(n.id_token=this.idToken),this.accessToken&&(n.access_token=this.accessToken),this.secret&&(n.oauth_token_secret=this.secret),n.providerId=this.providerId,this.nonce&&!this.pendingToken&&(n.nonce=this.nonce),t.postBody=wr(n)}return t}}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class Qi{constructor(t){this.providerId=t,this.defaultLanguageCode=null,this.customParameters={}}setDefaultLanguage(t){this.defaultLanguageCode=t}setCustomParameters(t){return this.customParameters=t,this}getCustomParameters(){return this.customParameters}}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class Ar extends Qi{constructor(){super(...arguments),this.scopes=[]}addScope(t){return this.scopes.includes(t)||this.scopes.push(t),this}getScopes(){return[...this.scopes]}}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class $t extends Ar{constructor(){super("facebook.com")}static credential(t){return gn._fromParams({providerId:$t.PROVIDER_ID,signInMethod:$t.FACEBOOK_SIGN_IN_METHOD,accessToken:t})}static credentialFromResult(t){return $t.credentialFromTaggedObject(t)}static credentialFromError(t){return $t.credentialFromTaggedObject(t.customData||{})}static credentialFromTaggedObject({_tokenResponse:t}){if(!t||!("oauthAccessToken"in t)||!t.oauthAccessToken)return null;try{return $t.credential(t.oauthAccessToken)}catch{return null}}}$t.FACEBOOK_SIGN_IN_METHOD="facebook.com";$t.PROVIDER_ID="facebook.com";/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class wt extends Ar{constructor(){super("google.com"),this.addScope("profile")}static credential(t,n){return gn._fromParams({providerId:wt.PROVIDER_ID,signInMethod:wt.GOOGLE_SIGN_IN_METHOD,idToken:t,accessToken:n})}static credentialFromResult(t){return wt.credentialFromTaggedObject(t)}static credentialFromError(t){return wt.credentialFromTaggedObject(t.customData||{})}static credentialFromTaggedObject({_tokenResponse:t}){if(!t)return null;const{oauthIdToken:n,oauthAccessToken:r}=t;if(!n&&!r)return null;try{return wt.credential(n,r)}catch{return null}}}wt.GOOGLE_SIGN_IN_METHOD="google.com";wt.PROVIDER_ID="google.com";/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class Wt extends Ar{constructor(){super("github.com")}static credential(t){return gn._fromParams({providerId:Wt.PROVIDER_ID,signInMethod:Wt.GITHUB_SIGN_IN_METHOD,accessToken:t})}static credentialFromResult(t){return Wt.credentialFromTaggedObject(t)}static credentialFromError(t){return Wt.credentialFromTaggedObject(t.customData||{})}static credentialFromTaggedObject({_tokenResponse:t}){if(!t||!("oauthAccessToken"in t)||!t.oauthAccessToken)return null;try{return Wt.credential(t.oauthAccessToken)}catch{return null}}}Wt.GITHUB_SIGN_IN_METHOD="github.com";Wt.PROVIDER_ID="github.com";/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class Kt extends Ar{constructor(){super("twitter.com")}static credential(t,n){return gn._fromParams({providerId:Kt.PROVIDER_ID,signInMethod:Kt.TWITTER_SIGN_IN_METHOD,oauthToken:t,oauthTokenSecret:n})}static credentialFromResult(t){return Kt.credentialFromTaggedObject(t)}static credentialFromError(t){return Kt.credentialFromTaggedObject(t.customData||{})}static credentialFromTaggedObject({_tokenResponse:t}){if(!t)return null;const{oauthAccessToken:n,oauthTokenSecret:r}=t;if(!n||!r)return null;try{return Kt.credential(n,r)}catch{return null}}}Kt.TWITTER_SIGN_IN_METHOD="twitter.com";Kt.PROVIDER_ID="twitter.com";/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class Fn{constructor(t){this.user=t.user,this.providerId=t.providerId,this._tokenResponse=t._tokenResponse,this.operationType=t.operationType}static async _fromIdTokenResponse(t,n,r,s=!1){const i=await At._fromIdTokenResponse(t,r,s),o=Pa(r);return new Fn({user:i,providerId:o,_tokenResponse:r,operationType:n})}static async _forOperation(t,n,r){await t._updateTokensIfNecessary(r,!0);const s=Pa(r);return new Fn({user:t,providerId:s,_tokenResponse:r,operationType:n})}}function Pa(e){return e.providerId?e.providerId:"phoneNumber"in e?"phone":null}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class ts extends Qt{constructor(t,n,r,s){var i;super(n.code,n.message),this.operationType=r,this.user=s,Object.setPrototypeOf(this,ts.prototype),this.customData={appName:t.name,tenantId:(i=t.tenantId)!==null&&i!==void 0?i:void 0,_serverResponse:n.customData._serverResponse,operationType:r}}static _fromErrorAndOperation(t,n,r,s){return new ts(t,n,r,s)}}function cu(e,t,n,r){return(t==="reauthenticate"?n._getReauthenticationResolver(e):n._getIdTokenResponse(e)).catch(i=>{throw i.code==="auth/multi-factor-auth-required"?ts._fromErrorAndOperation(e,i,t,r):i})}async function Am(e,t,n=!1){const r=await mr(e,t._linkToIdToken(e.auth,await e.getIdToken()),n);return Fn._forOperation(e,"link",r)}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */async function Cm(e,t,n=!1){const{auth:r}=e;if(St(r.app))return Promise.reject(pn(r));const s="reauthenticate";try{const i=await mr(e,cu(r,s,t,e),n);K(i.idToken,r,"internal-error");const o=Ji(i.idToken);K(o,r,"internal-error");const{sub:a}=o;return K(e.uid===a,r,"user-mismatch"),Fn._forOperation(e,s,i)}catch(i){throw i?.code==="auth/user-not-found"&&ht(r,"user-mismatch"),i}}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */async function Rm(e,t,n=!1){if(St(e.app))return Promise.reject(pn(e));const r="signIn",s=await cu(e,r,t),i=await Fn._fromIdTokenResponse(e,r,s);return n||await e._updateCurrentUser(i.user),i}function Pm(e,t,n,r){return Zt(e).onIdTokenChanged(t,n,r)}function Om(e,t,n){return Zt(e).beforeAuthStateChanged(t,n)}function km(e,t,n,r){return Zt(e).onAuthStateChanged(t,n,r)}function Nm(e){return Zt(e).signOut()}const ns="__sak";/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class lu{constructor(t,n){this.storageRetriever=t,this.type=n}_isAvailable(){try{return this.storage?(this.storage.setItem(ns,"1"),this.storage.removeItem(ns),Promise.resolve(!0)):Promise.resolve(!1)}catch{return Promise.resolve(!1)}}_set(t,n){return this.storage.setItem(t,JSON.stringify(n)),Promise.resolve()}_get(t){const n=this.storage.getItem(t);return Promise.resolve(n?JSON.parse(n):null)}_remove(t){return this.storage.removeItem(t),Promise.resolve()}get storage(){return this.storageRetriever()}}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const xm=1e3,Dm=10;class uu extends lu{constructor(){super(()=>window.localStorage,"LOCAL"),this.boundEventHandler=(t,n)=>this.onStorageEvent(t,n),this.listeners={},this.localCache={},this.pollTimer=null,this.fallbackToPolling=su(),this._shouldAllowMigration=!0}forAllChangedKeys(t){for(const n of Object.keys(this.listeners)){const r=this.storage.getItem(n),s=this.localCache[n];r!==s&&t(n,s,r)}}onStorageEvent(t,n=!1){if(!t.key){this.forAllChangedKeys((o,a,c)=>{this.notifyListeners(o,c)});return}const r=t.key;n?this.detachListener():this.stopPolling();const s=()=>{const o=this.storage.getItem(r);!n&&this.localCache[r]===o||this.notifyListeners(r,o)},i=this.storage.getItem(r);um()&&i!==t.newValue&&t.newValue!==t.oldValue?setTimeout(s,Dm):s()}notifyListeners(t,n){this.localCache[t]=n;const r=this.listeners[t];if(r)for(const s of Array.from(r))s(n&&JSON.parse(n))}startPolling(){this.stopPolling(),this.pollTimer=setInterval(()=>{this.forAllChangedKeys((t,n,r)=>{this.onStorageEvent(new StorageEvent("storage",{key:t,oldValue:n,newValue:r}),!0)})},xm)}stopPolling(){this.pollTimer&&(clearInterval(this.pollTimer),this.pollTimer=null)}attachListener(){window.addEventListener("storage",this.boundEventHandler)}detachListener(){window.removeEventListener("storage",this.boundEventHandler)}_addListener(t,n){Object.keys(this.listeners).length===0&&(this.fallbackToPolling?this.startPolling():this.attachListener()),this.listeners[t]||(this.listeners[t]=new Set,this.localCache[t]=this.storage.getItem(t)),this.listeners[t].add(n)}_removeListener(t,n){this.listeners[t]&&(this.listeners[t].delete(n),this.listeners[t].size===0&&delete this.listeners[t]),Object.keys(this.listeners).length===0&&(this.detachListener(),this.stopPolling())}async _set(t,n){await super._set(t,n),this.localCache[t]=JSON.stringify(n)}async _get(t){const n=await super._get(t);return this.localCache[t]=JSON.stringify(n),n}async _remove(t){await super._remove(t),delete this.localCache[t]}}uu.type="LOCAL";const Mm=uu;/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class fu extends lu{constructor(){super(()=>window.sessionStorage,"SESSION")}_addListener(t,n){}_removeListener(t,n){}}fu.type="SESSION";const du=fu;/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function Lm(e){return Promise.all(e.map(async t=>{try{return{fulfilled:!0,value:await t}}catch(n){return{fulfilled:!1,reason:n}}}))}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class Ts{constructor(t){this.eventTarget=t,this.handlersMap={},this.boundEventHandler=this.handleEvent.bind(this)}static _getInstance(t){const n=this.receivers.find(s=>s.isListeningto(t));if(n)return n;const r=new Ts(t);return this.receivers.push(r),r}isListeningto(t){return this.eventTarget===t}async handleEvent(t){const n=t,{eventId:r,eventType:s,data:i}=n.data,o=this.handlersMap[s];if(!o?.size)return;n.ports[0].postMessage({status:"ack",eventId:r,eventType:s});const a=Array.from(o).map(async l=>l(n.origin,i)),c=await Lm(a);n.ports[0].postMessage({status:"done",eventId:r,eventType:s,response:c})}_subscribe(t,n){Object.keys(this.handlersMap).length===0&&this.eventTarget.addEventListener("message",this.boundEventHandler),this.handlersMap[t]||(this.handlersMap[t]=new Set),this.handlersMap[t].add(n)}_unsubscribe(t,n){this.handlersMap[t]&&n&&this.handlersMap[t].delete(n),(!n||this.handlersMap[t].size===0)&&delete this.handlersMap[t],Object.keys(this.handlersMap).length===0&&this.eventTarget.removeEventListener("message",this.boundEventHandler)}}Ts.receivers=[];/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function Zi(e="",t=10){let n="";for(let r=0;r<t;r++)n+=Math.floor(Math.random()*10);return e+n}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class Um{constructor(t){this.target=t,this.handlers=new Set}removeMessageHandler(t){t.messageChannel&&(t.messageChannel.port1.removeEventListener("message",t.onMessage),t.messageChannel.port1.close()),this.handlers.delete(t)}async _send(t,n,r=50){const s=typeof MessageChannel<"u"?new MessageChannel:null;if(!s)throw new Error("connection_unavailable");let i,o;return new Promise((a,c)=>{const l=Zi("",20);s.port1.start();const u=setTimeout(()=>{c(new Error("unsupported_event"))},r);o={messageChannel:s,onMessage(f){const p=f;if(p.data.eventId===l)switch(p.data.status){case"ack":clearTimeout(u),i=setTimeout(()=>{c(new Error("timeout"))},3e3);break;case"done":clearTimeout(i),a(p.data.response);break;default:clearTimeout(u),clearTimeout(i),c(new Error("invalid_response"));break}}},this.handlers.add(o),s.port1.addEventListener("message",o.onMessage),this.target.postMessage({eventType:t,eventId:l,data:n},[s.port2])}).finally(()=>{o&&this.removeMessageHandler(o)})}}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function dt(){return window}function Fm(e){dt().location.href=e}/**
 * @license
 * Copyright 2020 Google LLC.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function hu(){return typeof dt().WorkerGlobalScope<"u"&&typeof dt().importScripts=="function"}async function Bm(){if(!navigator?.serviceWorker)return null;try{return(await navigator.serviceWorker.ready).active}catch{return null}}function Vm(){var e;return((e=navigator?.serviceWorker)===null||e===void 0?void 0:e.controller)||null}function Hm(){return hu()?self:null}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const pu="firebaseLocalStorageDb",jm=1,rs="firebaseLocalStorage",gu="fbase_key";class Cr{constructor(t){this.request=t}toPromise(){return new Promise((t,n)=>{this.request.addEventListener("success",()=>{t(this.request.result)}),this.request.addEventListener("error",()=>{n(this.request.error)})})}}function As(e,t){return e.transaction([rs],t?"readwrite":"readonly").objectStore(rs)}function $m(){const e=indexedDB.deleteDatabase(pu);return new Cr(e).toPromise()}function Ii(){const e=indexedDB.open(pu,jm);return new Promise((t,n)=>{e.addEventListener("error",()=>{n(e.error)}),e.addEventListener("upgradeneeded",()=>{const r=e.result;try{r.createObjectStore(rs,{keyPath:gu})}catch(s){n(s)}}),e.addEventListener("success",async()=>{const r=e.result;r.objectStoreNames.contains(rs)?t(r):(r.close(),await $m(),t(await Ii()))})})}async function Oa(e,t,n){const r=As(e,!0).put({[gu]:t,value:n});return new Cr(r).toPromise()}async function Wm(e,t){const n=As(e,!1).get(t),r=await new Cr(n).toPromise();return r===void 0?null:r.value}function ka(e,t){const n=As(e,!0).delete(t);return new Cr(n).toPromise()}const Km=800,Gm=3;class mu{constructor(){this.type="LOCAL",this._shouldAllowMigration=!0,this.listeners={},this.localCache={},this.pollTimer=null,this.pendingWrites=0,this.receiver=null,this.sender=null,this.serviceWorkerReceiverAvailable=!1,this.activeServiceWorker=null,this._workerInitializationPromise=this.initializeServiceWorkerMessaging().then(()=>{},()=>{})}async _openDb(){return this.db?this.db:(this.db=await Ii(),this.db)}async _withRetries(t){let n=0;for(;;)try{const r=await this._openDb();return await t(r)}catch(r){if(n++>Gm)throw r;this.db&&(this.db.close(),this.db=void 0)}}async initializeServiceWorkerMessaging(){return hu()?this.initializeReceiver():this.initializeSender()}async initializeReceiver(){this.receiver=Ts._getInstance(Hm()),this.receiver._subscribe("keyChanged",async(t,n)=>({keyProcessed:(await this._poll()).includes(n.key)})),this.receiver._subscribe("ping",async(t,n)=>["keyChanged"])}async initializeSender(){var t,n;if(this.activeServiceWorker=await Bm(),!this.activeServiceWorker)return;this.sender=new Um(this.activeServiceWorker);const r=await this.sender._send("ping",{},800);r&&!((t=r[0])===null||t===void 0)&&t.fulfilled&&!((n=r[0])===null||n===void 0)&&n.value.includes("keyChanged")&&(this.serviceWorkerReceiverAvailable=!0)}async notifyServiceWorker(t){if(!(!this.sender||!this.activeServiceWorker||Vm()!==this.activeServiceWorker))try{await this.sender._send("keyChanged",{key:t},this.serviceWorkerReceiverAvailable?800:50)}catch{}}async _isAvailable(){try{if(!indexedDB)return!1;const t=await Ii();return await Oa(t,ns,"1"),await ka(t,ns),!0}catch{}return!1}async _withPendingWrite(t){this.pendingWrites++;try{await t()}finally{this.pendingWrites--}}async _set(t,n){return this._withPendingWrite(async()=>(await this._withRetries(r=>Oa(r,t,n)),this.localCache[t]=n,this.notifyServiceWorker(t)))}async _get(t){const n=await this._withRetries(r=>Wm(r,t));return this.localCache[t]=n,n}async _remove(t){return this._withPendingWrite(async()=>(await this._withRetries(n=>ka(n,t)),delete this.localCache[t],this.notifyServiceWorker(t)))}async _poll(){const t=await this._withRetries(s=>{const i=As(s,!1).getAll();return new Cr(i).toPromise()});if(!t)return[];if(this.pendingWrites!==0)return[];const n=[],r=new Set;if(t.length!==0)for(const{fbase_key:s,value:i}of t)r.add(s),JSON.stringify(this.localCache[s])!==JSON.stringify(i)&&(this.notifyListeners(s,i),n.push(s));for(const s of Object.keys(this.localCache))this.localCache[s]&&!r.has(s)&&(this.notifyListeners(s,null),n.push(s));return n}notifyListeners(t,n){this.localCache[t]=n;const r=this.listeners[t];if(r)for(const s of Array.from(r))s(n)}startPolling(){this.stopPolling(),this.pollTimer=setInterval(async()=>this._poll(),Km)}stopPolling(){this.pollTimer&&(clearInterval(this.pollTimer),this.pollTimer=null)}_addListener(t,n){Object.keys(this.listeners).length===0&&this.startPolling(),this.listeners[t]||(this.listeners[t]=new Set,this._get(t)),this.listeners[t].add(n)}_removeListener(t,n){this.listeners[t]&&(this.listeners[t].delete(n),this.listeners[t].size===0&&delete this.listeners[t]),Object.keys(this.listeners).length===0&&this.stopPolling()}}mu.type="LOCAL";const zm=mu;new Tr(3e4,6e4);/**
 * @license
 * Copyright 2021 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function _u(e,t){return t?Ct(t):(K(e._popupRedirectResolver,e,"argument-error"),e._popupRedirectResolver)}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class eo extends au{constructor(t){super("custom","custom"),this.params=t}_getIdTokenResponse(t){return kn(t,this._buildIdpRequest())}_linkToIdToken(t,n){return kn(t,this._buildIdpRequest(n))}_getReauthenticationResolver(t){return kn(t,this._buildIdpRequest())}_buildIdpRequest(t){const n={requestUri:this.params.requestUri,sessionId:this.params.sessionId,postBody:this.params.postBody,tenantId:this.params.tenantId,pendingToken:this.params.pendingToken,returnSecureToken:!0,returnIdpCredential:!0};return t&&(n.idToken=t),n}}function qm(e){return Rm(e.auth,new eo(e),e.bypassAuthState)}function Jm(e){const{auth:t,user:n}=e;return K(n,t,"internal-error"),Cm(n,new eo(e),e.bypassAuthState)}async function Ym(e){const{auth:t,user:n}=e;return K(n,t,"internal-error"),Am(n,new eo(e),e.bypassAuthState)}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class vu{constructor(t,n,r,s,i=!1){this.auth=t,this.resolver=r,this.user=s,this.bypassAuthState=i,this.pendingPromise=null,this.eventManager=null,this.filter=Array.isArray(n)?n:[n]}execute(){return new Promise(async(t,n)=>{this.pendingPromise={resolve:t,reject:n};try{this.eventManager=await this.resolver._initialize(this.auth),await this.onExecution(),this.eventManager.registerConsumer(this)}catch(r){this.reject(r)}})}async onAuthEvent(t){const{urlResponse:n,sessionId:r,postBody:s,tenantId:i,error:o,type:a}=t;if(o){this.reject(o);return}const c={auth:this.auth,requestUri:n,sessionId:r,tenantId:i||void 0,postBody:s||void 0,user:this.user,bypassAuthState:this.bypassAuthState};try{this.resolve(await this.getIdpTask(a)(c))}catch(l){this.reject(l)}}onError(t){this.reject(t)}getIdpTask(t){switch(t){case"signInViaPopup":case"signInViaRedirect":return qm;case"linkViaPopup":case"linkViaRedirect":return Ym;case"reauthViaPopup":case"reauthViaRedirect":return Jm;default:ht(this.auth,"internal-error")}}resolve(t){xt(this.pendingPromise,"Pending promise was never set"),this.pendingPromise.resolve(t),this.unregisterAndCleanUp()}reject(t){xt(this.pendingPromise,"Pending promise was never set"),this.pendingPromise.reject(t),this.unregisterAndCleanUp()}unregisterAndCleanUp(){this.eventManager&&this.eventManager.unregisterConsumer(this),this.pendingPromise=null,this.cleanUp()}}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const Xm=new Tr(2e3,1e4);async function Qm(e,t,n){if(St(e.app))return Promise.reject(Ye(e,"operation-not-supported-in-this-environment"));const r=Ss(e);zg(e,t,Qi);const s=_u(r,n);return new fn(r,"signInViaPopup",t,s).executeNotNull()}class fn extends vu{constructor(t,n,r,s,i){super(t,n,s,i),this.provider=r,this.authWindow=null,this.pollId=null,fn.currentPopupAction&&fn.currentPopupAction.cancel(),fn.currentPopupAction=this}async executeNotNull(){const t=await this.execute();return K(t,this.auth,"internal-error"),t}async onExecution(){xt(this.filter.length===1,"Popup operations only handle one event");const t=Zi();this.authWindow=await this.resolver._openPopup(this.auth,this.provider,this.filter[0],t),this.authWindow.associatedEvent=t,this.resolver._originValidation(this.auth).catch(n=>{this.reject(n)}),this.resolver._isIframeWebStorageSupported(this.auth,n=>{n||this.reject(Ye(this.auth,"web-storage-unsupported"))}),this.pollUserCancellation()}get eventId(){var t;return((t=this.authWindow)===null||t===void 0?void 0:t.associatedEvent)||null}cancel(){this.reject(Ye(this.auth,"cancelled-popup-request"))}cleanUp(){this.authWindow&&this.authWindow.close(),this.pollId&&window.clearTimeout(this.pollId),this.authWindow=null,this.pollId=null,fn.currentPopupAction=null}pollUserCancellation(){const t=()=>{var n,r;if(!((r=(n=this.authWindow)===null||n===void 0?void 0:n.window)===null||r===void 0)&&r.closed){this.pollId=window.setTimeout(()=>{this.pollId=null,this.reject(Ye(this.auth,"popup-closed-by-user"))},8e3);return}this.pollId=window.setTimeout(t,Xm.get())};t()}}fn.currentPopupAction=null;/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const Zm="pendingRedirect",Vr=new Map;class e_ extends vu{constructor(t,n,r=!1){super(t,["signInViaRedirect","linkViaRedirect","reauthViaRedirect","unknown"],n,void 0,r),this.eventId=null}async execute(){let t=Vr.get(this.auth._key());if(!t){try{const r=await t_(this.resolver,this.auth)?await super.execute():null;t=()=>Promise.resolve(r)}catch(n){t=()=>Promise.reject(n)}Vr.set(this.auth._key(),t)}return this.bypassAuthState||Vr.set(this.auth._key(),()=>Promise.resolve(null)),t()}async onAuthEvent(t){if(t.type==="signInViaRedirect")return super.onAuthEvent(t);if(t.type==="unknown"){this.resolve(null);return}if(t.eventId){const n=await this.auth._redirectUserForId(t.eventId);if(n)return this.user=n,super.onAuthEvent(t);this.resolve(null)}}async onExecution(){}cleanUp(){}}async function t_(e,t){const n=s_(t),r=r_(e);if(!await r._isAvailable())return!1;const s=await r._get(n)==="true";return await r._remove(n),s}function n_(e,t){Vr.set(e._key(),t)}function r_(e){return Ct(e._redirectPersistence)}function s_(e){return Br(Zm,e.config.apiKey,e.name)}async function i_(e,t,n=!1){if(St(e.app))return Promise.reject(pn(e));const r=Ss(e),s=_u(r,t),o=await new e_(r,s,n).execute();return o&&!n&&(delete o.user._redirectEventId,await r._persistUserIfCurrent(o.user),await r._setRedirectUser(null,t)),o}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const o_=10*60*1e3;class a_{constructor(t){this.auth=t,this.cachedEventUids=new Set,this.consumers=new Set,this.queuedRedirectEvent=null,this.hasHandledPotentialRedirect=!1,this.lastProcessedEventTime=Date.now()}registerConsumer(t){this.consumers.add(t),this.queuedRedirectEvent&&this.isEventForConsumer(this.queuedRedirectEvent,t)&&(this.sendToConsumer(this.queuedRedirectEvent,t),this.saveEventToCache(this.queuedRedirectEvent),this.queuedRedirectEvent=null)}unregisterConsumer(t){this.consumers.delete(t)}onEvent(t){if(this.hasEventBeenHandled(t))return!1;let n=!1;return this.consumers.forEach(r=>{this.isEventForConsumer(t,r)&&(n=!0,this.sendToConsumer(t,r),this.saveEventToCache(t))}),this.hasHandledPotentialRedirect||!c_(t)||(this.hasHandledPotentialRedirect=!0,n||(this.queuedRedirectEvent=t,n=!0)),n}sendToConsumer(t,n){var r;if(t.error&&!yu(t)){const s=((r=t.error.code)===null||r===void 0?void 0:r.split("auth/")[1])||"internal-error";n.onError(Ye(this.auth,s))}else n.onAuthEvent(t)}isEventForConsumer(t,n){const r=n.eventId===null||!!t.eventId&&t.eventId===n.eventId;return n.filter.includes(t.type)&&r}hasEventBeenHandled(t){return Date.now()-this.lastProcessedEventTime>=o_&&this.cachedEventUids.clear(),this.cachedEventUids.has(Na(t))}saveEventToCache(t){this.cachedEventUids.add(Na(t)),this.lastProcessedEventTime=Date.now()}}function Na(e){return[e.type,e.eventId,e.sessionId,e.tenantId].filter(t=>t).join("-")}function yu({type:e,error:t}){return e==="unknown"&&t?.code==="auth/no-auth-event"}function c_(e){switch(e.type){case"signInViaRedirect":case"linkViaRedirect":case"reauthViaRedirect":return!0;case"unknown":return yu(e);default:return!1}}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */async function l_(e,t={}){return Vn(e,"GET","/v1/projects",t)}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const u_=/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/,f_=/^https?/;async function d_(e){if(e.config.emulator)return;const{authorizedDomains:t}=await l_(e);for(const n of t)try{if(h_(n))return}catch{}ht(e,"unauthorized-domain")}function h_(e){const t=bi(),{protocol:n,hostname:r}=new URL(t);if(e.startsWith("chrome-extension://")){const o=new URL(e);return o.hostname===""&&r===""?n==="chrome-extension:"&&e.replace("chrome-extension://","")===t.replace("chrome-extension://",""):n==="chrome-extension:"&&o.hostname===r}if(!f_.test(n))return!1;if(u_.test(e))return r===e;const s=e.replace(/\./g,"\\.");return new RegExp("^(.+\\."+s+"|"+s+")$","i").test(r)}/**
 * @license
 * Copyright 2020 Google LLC.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const p_=new Tr(3e4,6e4);function xa(){const e=dt().___jsl;if(e?.H){for(const t of Object.keys(e.H))if(e.H[t].r=e.H[t].r||[],e.H[t].L=e.H[t].L||[],e.H[t].r=[...e.H[t].L],e.CP)for(let n=0;n<e.CP.length;n++)e.CP[n]=null}}function g_(e){return new Promise((t,n)=>{var r,s,i;function o(){xa(),gapi.load("gapi.iframes",{callback:()=>{t(gapi.iframes.getContext())},ontimeout:()=>{xa(),n(Ye(e,"network-request-failed"))},timeout:p_.get()})}if(!((s=(r=dt().gapi)===null||r===void 0?void 0:r.iframes)===null||s===void 0)&&s.Iframe)t(gapi.iframes.getContext());else if(!((i=dt().gapi)===null||i===void 0)&&i.load)o();else{const a=ym("iframefcb");return dt()[a]=()=>{gapi.load?o():n(Ye(e,"network-request-failed"))},_m(`${vm()}?onload=${a}`).catch(c=>n(c))}}).catch(t=>{throw Hr=null,t})}let Hr=null;function m_(e){return Hr=Hr||g_(e),Hr}/**
 * @license
 * Copyright 2020 Google LLC.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const __=new Tr(5e3,15e3),v_="__/auth/iframe",y_="emulator/auth/iframe",b_={style:{position:"absolute",top:"-100px",width:"1px",height:"1px"},"aria-hidden":"true",tabindex:"-1"},E_=new Map([["identitytoolkit.googleapis.com","p"],["staging-identitytoolkit.sandbox.googleapis.com","s"],["test-identitytoolkit.sandbox.googleapis.com","t"]]);function I_(e){const t=e.config;K(t.authDomain,e,"auth-domain-config-required");const n=t.emulator?zi(t,y_):`https://${e.config.authDomain}/${v_}`,r={apiKey:t.apiKey,appName:e.name,v:Sr},s=E_.get(e.config.apiHost);s&&(r.eid=s);const i=e._getFrameworks();return i.length&&(r.fw=i.join(",")),`${n}?${wr(r).slice(1)}`}async function w_(e){const t=await m_(e),n=dt().gapi;return K(n,e,"internal-error"),t.open({where:document.body,url:I_(e),messageHandlersFilter:n.iframes.CROSS_ORIGIN_IFRAMES_FILTER,attributes:b_,dontclear:!0},r=>new Promise(async(s,i)=>{await r.restyle({setHideOnLeave:!1});const o=Ye(e,"network-request-failed"),a=dt().setTimeout(()=>{i(o)},__.get());function c(){dt().clearTimeout(a),s(r)}r.ping(c).then(c,()=>{i(o)})}))}/**
 * @license
 * Copyright 2020 Google LLC.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const S_={location:"yes",resizable:"yes",statusbar:"yes",toolbar:"no"},T_=500,A_=600,C_="_blank",R_="http://localhost";class Da{constructor(t){this.window=t,this.associatedEvent=null}close(){if(this.window)try{this.window.close()}catch{}}}function P_(e,t,n,r=T_,s=A_){const i=Math.max((window.screen.availHeight-s)/2,0).toString(),o=Math.max((window.screen.availWidth-r)/2,0).toString();let a="";const c=Object.assign(Object.assign({},S_),{width:r.toString(),height:s.toString(),top:i,left:o}),l=Me().toLowerCase();n&&(a=Zl(l)?C_:n),Xl(l)&&(t=t||R_,c.scrollbars="yes");const u=Object.entries(c).reduce((p,[g,I])=>`${p}${g}=${I},`,"");if(lm(l)&&a!=="_self")return O_(t||"",a),new Da(null);const f=window.open(t||"",a,u);K(f,e,"popup-blocked");try{f.focus()}catch{}return new Da(f)}function O_(e,t){const n=document.createElement("a");n.href=e,n.target=t;const r=document.createEvent("MouseEvent");r.initMouseEvent("click",!0,!0,window,1,0,0,0,0,!1,!1,!1,!1,1,null),n.dispatchEvent(r)}/**
 * @license
 * Copyright 2021 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const k_="__/auth/handler",N_="emulator/auth/handler",x_=encodeURIComponent("fac");async function Ma(e,t,n,r,s,i){K(e.config.authDomain,e,"auth-domain-config-required"),K(e.config.apiKey,e,"invalid-api-key");const o={apiKey:e.config.apiKey,appName:e.name,authType:n,redirectUrl:r,v:Sr,eventId:s};if(t instanceof Qi){t.setDefaultLanguage(e.languageCode),o.providerId=t.providerId||"",kp(t.getCustomParameters())||(o.customParameters=JSON.stringify(t.getCustomParameters()));for(const[u,f]of Object.entries({}))o[u]=f}if(t instanceof Ar){const u=t.getScopes().filter(f=>f!=="");u.length>0&&(o.scopes=u.join(","))}e.tenantId&&(o.tid=e.tenantId);const a=o;for(const u of Object.keys(a))a[u]===void 0&&delete a[u];const c=await e._getAppCheckToken(),l=c?`#${x_}=${encodeURIComponent(c)}`:"";return`${D_(e)}?${wr(a).slice(1)}${l}`}function D_({config:e}){return e.emulator?zi(e,N_):`https://${e.authDomain}/${k_}`}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const Ys="webStorageSupport";class M_{constructor(){this.eventManagers={},this.iframes={},this.originValidationPromises={},this._redirectPersistence=du,this._completeRedirectFn=i_,this._overrideRedirectResult=n_}async _openPopup(t,n,r,s){var i;xt((i=this.eventManagers[t._key()])===null||i===void 0?void 0:i.manager,"_initialize() not called before _openPopup()");const o=await Ma(t,n,r,bi(),s);return P_(t,o,Zi())}async _openRedirect(t,n,r,s){await this._originValidation(t);const i=await Ma(t,n,r,bi(),s);return Fm(i),new Promise(()=>{})}_initialize(t){const n=t._key();if(this.eventManagers[n]){const{manager:s,promise:i}=this.eventManagers[n];return s?Promise.resolve(s):(xt(i,"If manager is not set, promise should be"),i)}const r=this.initAndGetManager(t);return this.eventManagers[n]={promise:r},r.catch(()=>{delete this.eventManagers[n]}),r}async initAndGetManager(t){const n=await w_(t),r=new a_(t);return n.register("authEvent",s=>(K(s?.authEvent,t,"invalid-auth-event"),{status:r.onEvent(s.authEvent)?"ACK":"ERROR"}),gapi.iframes.CROSS_ORIGIN_IFRAMES_FILTER),this.eventManagers[t._key()]={manager:r},this.iframes[t._key()]=n,r}_isIframeWebStorageSupported(t,n){this.iframes[t._key()].send(Ys,{type:Ys},s=>{var i;const o=(i=s?.[0])===null||i===void 0?void 0:i[Ys];o!==void 0&&n(!!o),ht(t,"internal-error")},gapi.iframes.CROSS_ORIGIN_IFRAMES_FILTER)}_originValidation(t){const n=t._key();return this.originValidationPromises[n]||(this.originValidationPromises[n]=d_(t)),this.originValidationPromises[n]}get _shouldInitProactively(){return su()||Ql()||Yi()}}const L_=M_;var La="@firebase/auth",Ua="1.7.9";/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class U_{constructor(t){this.auth=t,this.internalListeners=new Map}getUid(){var t;return this.assertAuthConfigured(),((t=this.auth.currentUser)===null||t===void 0?void 0:t.uid)||null}async getToken(t){return this.assertAuthConfigured(),await this.auth._initializationPromise,this.auth.currentUser?{accessToken:await this.auth.currentUser.getIdToken(t)}:null}addAuthTokenListener(t){if(this.assertAuthConfigured(),this.internalListeners.has(t))return;const n=this.auth.onIdTokenChanged(r=>{t(r?.stsTokenManager.accessToken||null)});this.internalListeners.set(t,n),this.updateProactiveRefresh()}removeAuthTokenListener(t){this.assertAuthConfigured();const n=this.internalListeners.get(t);n&&(this.internalListeners.delete(t),n(),this.updateProactiveRefresh())}assertAuthConfigured(){K(this.auth._initializationPromise,"dependent-sdk-initialized-before-auth")}updateProactiveRefresh(){this.internalListeners.size>0?this.auth._startProactiveRefresh():this.auth._stopProactiveRefresh()}}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function F_(e){switch(e){case"Node":return"node";case"ReactNative":return"rn";case"Worker":return"webworker";case"Cordova":return"cordova";case"WebExtension":return"web-extension";default:return}}function B_(e){pr(new Un("auth",(t,{options:n})=>{const r=t.getProvider("app").getImmediate(),s=t.getProvider("heartbeat"),i=t.getProvider("app-check-internal"),{apiKey:o,authDomain:a}=r.options;K(o&&!o.includes(":"),"invalid-api-key",{appName:r.name});const c={apiKey:o,authDomain:a,clientPlatform:e,apiHost:"identitytoolkit.googleapis.com",tokenApiHost:"securetoken.googleapis.com",apiScheme:"https",sdkClientVersion:iu(e)},l=new gm(r,s,i,c);return Em(l,n),l},"PUBLIC").setInstantiationMode("EXPLICIT").setInstanceCreatedCallback((t,n,r)=>{t.getProvider("auth-internal").initialize()})),pr(new Un("auth-internal",t=>{const n=Ss(t.getProvider("auth").getImmediate());return(r=>new U_(r))(n)},"PRIVATE").setInstantiationMode("EXPLICIT")),Rn(La,Ua,F_(e)),Rn(La,Ua,"esm2017")}/**
 * @license
 * Copyright 2021 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const V_=5*60,H_=Ml("authIdTokenMaxAge")||V_;let Fa=null;const j_=e=>async t=>{const n=t&&await t.getIdTokenResult(),r=n&&(new Date().getTime()-Date.parse(n.issuedAtTime))/1e3;if(r&&r>H_)return;const s=n?.token;Fa!==s&&(Fa=s,await fetch(e,{method:s?"POST":"DELETE",headers:s?{Authorization:`Bearer ${s}`}:{}}))};function $_(e=xg()){const t=Bl(e,"auth");if(t.isInitialized())return t.getImmediate();const n=bm(e,{popupRedirectResolver:L_,persistence:[zm,Mm,du]}),r=Ml("authTokenSyncURL");if(r&&typeof isSecureContext=="boolean"&&isSecureContext){const i=new URL(r,location.origin);if(location.origin===i.origin){const o=j_(i.toString());Om(n,o,()=>o(n.currentUser)),Pm(n,a=>o(a))}}const s=yp("auth");return s&&Im(n,`http://${s}`),n}function W_(){var e,t;return(t=(e=document.getElementsByTagName("head"))===null||e===void 0?void 0:e[0])!==null&&t!==void 0?t:document}mm({loadJS(e){return new Promise((t,n)=>{const r=document.createElement("script");r.setAttribute("src",e),r.onload=t,r.onerror=s=>{const i=Ye("internal-error");i.customData=s,n(i)},r.type="text/javascript",r.charset="UTF-8",W_().appendChild(r)})},gapiScript:"https://apis.google.com/js/api.js",recaptchaV2Script:"https://www.google.com/recaptcha/api.js",recaptchaEnterpriseScript:"https://www.google.com/recaptcha/enterprise.js?render="});B_("Browser");const K_={apiKey:"REDACTED_FIREBASE_WEB_KEY",authDomain:"ai.revealiq.in",projectId:"jarvis-a6e18",storageBucket:"jarvis-a6e18.firebasestorage.app",messagingSenderId:"872168972424",appId:"1:872168972424:web:2b0b9b82922860a52c3f3d",measurementId:"G-H2FB26YQ9R"},G_=Vl(K_),_r=$_(G_);function z_(){return Qm(_r,new wt)}function q_(){return Nm(_r)}function J_(e){return km(_r,e)}const to=ih("auth",{state:()=>({user:null,ready:!1}),getters:{isAuthed:e=>!!e.user,displayName:e=>e.user?.displayName||e.user?.email||"Guest",email:e=>e.user?.email||"",photo:e=>e.user?.photoURL||""},actions:{bootstrap(){return new Promise(e=>{J_(t=>{this.user=t,this.ready=!0,e(t)})})},signIn(){return z_()},signOut(){return q_()},async getToken(){return _r.currentUser?await _r.currentUser.getIdToken():null}}});/**
 * @license lucide-vue-next v0.453.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const Y_=e=>e.replace(/([a-z0-9])([A-Z])/g,"$1-$2").toLowerCase();/**
 * @license lucide-vue-next v0.453.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */var Nr={xmlns:"http://www.w3.org/2000/svg",width:24,height:24,viewBox:"0 0 24 24",fill:"none",stroke:"currentColor","stroke-width":2,"stroke-linecap":"round","stroke-linejoin":"round"};/**
 * @license lucide-vue-next v0.453.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const X_=({size:e,strokeWidth:t=2,absoluteStrokeWidth:n,color:r,iconNode:s,name:i,class:o,...a},{slots:c})=>xn("svg",{...Nr,width:e||Nr.width,height:e||Nr.height,stroke:r||Nr.stroke,"stroke-width":n?Number(t)*24/Number(e):t,class:["lucide",`lucide-${Y_(i??"icon")}`],...a},[...s.map(l=>xn(...l)),...c.default?[c.default()]:[]]);/**
 * @license lucide-vue-next v0.453.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const $e=(e,t)=>(n,{slots:r})=>xn(X_,{...n,iconNode:t,name:e},r);/**
 * @license lucide-vue-next v0.453.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const Ba=$e("BotIcon",[["path",{d:"M12 8V4H8",key:"hb8ula"}],["rect",{width:"16",height:"12",x:"4",y:"8",rx:"2",key:"enze0r"}],["path",{d:"M2 14h2",key:"vft8re"}],["path",{d:"M20 14h2",key:"4cs60a"}],["path",{d:"M15 13v2",key:"1xurst"}],["path",{d:"M9 13v2",key:"rq6x2g"}]]);/**
 * @license lucide-vue-next v0.453.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const Q_=$e("ChevronsLeftIcon",[["path",{d:"m11 17-5-5 5-5",key:"13zhaf"}],["path",{d:"m18 17-5-5 5-5",key:"h8a8et"}]]);/**
 * @license lucide-vue-next v0.453.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const Z_=$e("ChevronsRightIcon",[["path",{d:"m6 17 5-5-5-5",key:"xnjwq"}],["path",{d:"m13 17 5-5-5-5",key:"17xmmf"}]]);/**
 * @license lucide-vue-next v0.453.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const Va=$e("LayoutDashboardIcon",[["rect",{width:"7",height:"9",x:"3",y:"3",rx:"1",key:"10lvy0"}],["rect",{width:"7",height:"5",x:"14",y:"3",rx:"1",key:"16une8"}],["rect",{width:"7",height:"9",x:"14",y:"12",rx:"1",key:"1hutg5"}],["rect",{width:"7",height:"5",x:"3",y:"16",rx:"1",key:"ldoo1y"}]]);/**
 * @license lucide-vue-next v0.453.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const Ha=$e("LogOutIcon",[["path",{d:"M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4",key:"1uf3rs"}],["polyline",{points:"16 17 21 12 16 7",key:"1gabdz"}],["line",{x1:"21",x2:"9",y1:"12",y2:"12",key:"1uyos4"}]]);/**
 * @license lucide-vue-next v0.453.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const ev=$e("MenuIcon",[["line",{x1:"4",x2:"20",y1:"12",y2:"12",key:"1e0a9i"}],["line",{x1:"4",x2:"20",y1:"6",y2:"6",key:"1owob3"}],["line",{x1:"4",x2:"20",y1:"18",y2:"18",key:"yk5zj1"}]]);/**
 * @license lucide-vue-next v0.453.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const ja=$e("PhoneIcon",[["path",{d:"M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z",key:"foiqr5"}]]);/**
 * @license lucide-vue-next v0.453.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const tv=$e("PlusIcon",[["path",{d:"M5 12h14",key:"1ays0h"}],["path",{d:"M12 5v14",key:"s699le"}]]);/**
 * @license lucide-vue-next v0.453.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const $a=$e("RadioIcon",[["path",{d:"M4.9 19.1C1 15.2 1 8.8 4.9 4.9",key:"1vaf9d"}],["path",{d:"M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5",key:"u1ii0m"}],["circle",{cx:"12",cy:"12",r:"2",key:"1c9p78"}],["path",{d:"M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5",key:"1j5fej"}],["path",{d:"M19.1 4.9C23 8.8 23 15.1 19.1 19",key:"10b0cb"}]]);/**
 * @license lucide-vue-next v0.453.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const nv=$e("SearchIcon",[["circle",{cx:"11",cy:"11",r:"8",key:"4ej97u"}],["path",{d:"m21 21-4.3-4.3",key:"1qie3q"}]]);/**
 * @license lucide-vue-next v0.453.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const Wa=$e("SettingsIcon",[["path",{d:"M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z",key:"1qme2f"}],["circle",{cx:"12",cy:"12",r:"3",key:"1v7zrd"}]]);/**
 * @license lucide-vue-next v0.453.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const rv=$e("WalletIcon",[["path",{d:"M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1",key:"18etb6"}],["path",{d:"M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4",key:"xoc0q4"}]]);/**
 * @license lucide-vue-next v0.453.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const sv=$e("XIcon",[["path",{d:"M18 6 6 18",key:"1bl5f8"}],["path",{d:"m6 6 12 12",key:"d8bk6v"}]]);function ry(e){const t=Math.max(0,Math.round(Number(e)||0)),n=Math.floor(t/60),r=t%60;return`${n}:${r.toString().padStart(2,"0")}`}function sy(e){const t=iv(e);if(!t)return"";const n=(Date.now()-t.getTime())/1e3;return n<60?"just now":n<3600?`${Math.floor(n/60)}m ago`:n<86400?`${Math.floor(n/3600)}h ago`:n<86400*7?`${Math.floor(n/86400)}d ago`:t.toLocaleDateString()}function iv(e){if(!e)return null;if(e instanceof Date)return e;if(typeof e=="object"&&typeof e.seconds=="number")return new Date(e.seconds*1e3);if(typeof e=="number")return new Date(e>1e12?e:e*1e3);if(typeof e=="string"){const t=Number(e);if(!Number.isNaN(t))return new Date(t>1e12?t:t*1e3);const n=new Date(e);if(!Number.isNaN(n.getTime()))return n}return null}function iy(e){const t=typeof e=="string"?e.toLowerCase():"";return t.includes("pos")?{label:"Positive",cls:"pill-success",icon:"smile"}:t.includes("neg")?{label:"Negative",cls:"pill-danger",icon:"frown"}:{label:"Neutral",cls:"pill-info",icon:"meh"}}function oy(e){const t=String(e?.channel||e?.type||"").toLowerCase();return t.includes("chat")?{label:"Chat",icon:"message-square",tone:"pill-info"}:t.includes("sip")||t.includes("phone")?{label:"Phone",icon:"phone-call",tone:"pill-accent"}:{label:"Web",icon:"globe",tone:"pill-info"}}function Xs(e=""){return String(e).trim().split(/\s+/).slice(0,2).map(n=>n[0]||"").join("").toUpperCase()||"U"}const ov=(e,t)=>{const n=e.__vccOpts||e;for(const[r,s]of t)n[r]=s;return n},av={class:"min-h-screen flex w-full"},cv={class:"h-14 flex items-center gap-2 px-4 border-b border-line"},lv={key:0,class:"flex flex-col leading-tight"},uv={class:"flex-1 px-3 py-4 flex flex-col gap-1"},fv={key:0},dv={class:"p-3 border-t border-line"},hv={class:"avatar"},pv=["src"],gv={key:1},mv={key:0,class:"flex-1 min-w-0"},_v={class:"text-sm font-medium truncate"},vv={class:"text-[11px] text-ink-muted truncate"},yv=["title"],bv={key:0,class:"md:hidden fixed inset-0 z-40"},Ev={class:"absolute inset-y-0 left-0 w-[78%] max-w-[300px] bg-bg-elev border-r border-line flex flex-col"},Iv={class:"h-14 flex items-center justify-between px-4 border-b border-line"},wv={class:"flex-1 px-3 py-4 flex flex-col gap-1 overflow-y-auto"},Sv={class:"p-3 border-t border-line"},Tv={class:"flex items-center gap-2.5"},Av={class:"avatar"},Cv=["src"],Rv={key:1},Pv={class:"flex-1 min-w-0"},Ov={class:"text-sm font-medium truncate"},kv={class:"text-[11px] text-ink-muted truncate"},Nv={class:"flex-1 min-w-0 flex flex-col"},xv={class:"topbar sticky top-0 z-10"},Dv={class:"flex flex-col flex-1 min-w-0"},Mv={class:"text-base sm:text-lg font-semibold truncate"},Lv={class:"hidden md:flex items-center gap-2 max-w-[320px] flex-1 min-w-0"},Uv={class:"relative w-full"},Fv={class:"avatar md:hidden"},Bv=["src"],Vv={key:1},Hv={class:"flex-1 px-4 sm:px-6 lg:px-8 py-6 pb-24 md:pb-10 max-w-[1400px] w-full mx-auto"},jv={class:"bottom-nav"},$v={__name:"AppShell",setup(e){const t=to(),n=Pl(),r=fp(),s=$r(!1),i=$r(!1),o=[{to:"/overview",label:"Overview",icon:Va},{to:"/agents",label:"Agents",icon:Ba},{to:"/calls",label:"Calls",icon:ja},{to:"/telephony",label:"Telephony",icon:$a},{to:"/billing",label:"Billing",icon:rv},{to:"/settings",label:"Settings",icon:Wa}],a=[{to:"/overview",label:"Home",icon:Va},{to:"/agents",label:"Agents",icon:Ba},{to:"/calls",label:"Calls",icon:ja},{to:"/telephony",label:"Phone",icon:$a},{to:"/settings",label:"More",icon:Wa}],c=Fe(()=>n.meta.title||"");function l(f){return n.path===f||n.path.startsWith(f+"/")}async function u(){await t.signOut(),r.replace({name:"login"})}return(f,p)=>(le(),Se("div",av,[W("aside",{class:"hidden md:flex flex-col border-r border-line bg-bg-elev/60 backdrop-blur-md sticky top-0 h-screen transition-[width] duration-200 z-20",style:fs({width:i.value?"var(--sidebar-w-collapsed)":"var(--sidebar-w)"})},[W("div",cv,[p[7]||(p[7]=W("div",{class:"h-8 w-8 rounded-lg bg-gradient-to-br from-accent to-accent-strong flex items-center justify-center text-[#00211D] font-extrabold text-sm shadow-glow"}," K ",-1)),i.value?In("",!0):(le(),Se("div",lv,[...p[6]||(p[6]=[W("span",{class:"text-sm font-semibold text-ink"},"Kautilya",-1),W("span",{class:"text-[10px] text-ink-muted uppercase tracking-wider"},"RevealIQ Studio",-1)])]))]),W("nav",uv,[(le(),Se(Te,null,xs(o,g=>fe(Y(Ur),{key:g.to,to:g.to,class:ln(["nav-item",{active:l(g.to)}]),title:i.value?g.label:""},{default:Gt(()=>[(le(),ut(Gn(g.icon),{size:18})),i.value?In("",!0):(le(),Se("span",fv,Ge(g.label),1))]),_:2},1032,["to","class","title"])),64))]),W("div",dv,[W("div",{class:ln(["flex items-center gap-2.5",{"justify-center":i.value}])},[W("div",hv,[Y(t).photo?(le(),Se("img",{key:0,src:Y(t).photo,referrerpolicy:"no-referrer"},null,8,pv)):(le(),Se("span",gv,Ge(Y(Xs)(Y(t).displayName)),1))]),i.value?In("",!0):(le(),Se("div",mv,[W("div",_v,Ge(Y(t).displayName),1),W("div",vv,Ge(Y(t).email),1)])),i.value?In("",!0):(le(),Se("button",{key:1,onClick:u,class:"btn-icon",title:"Sign out"},[fe(Y(Ha),{size:14})]))],2),W("button",{onClick:p[0]||(p[0]=g=>i.value=!i.value),class:"mt-3 w-full btn-icon !justify-center",title:i.value?"Expand":"Collapse"},[(le(),ut(Gn(i.value?Y(Z_):Y(Q_)),{size:14}))],8,yv)])],4),fe(fl,{name:"drawer"},{default:Gt(()=>[s.value?(le(),Se("div",bv,[W("div",{class:"absolute inset-0 bg-black/60 backdrop-blur-sm",onClick:p[1]||(p[1]=g=>s.value=!1)}),W("aside",Ev,[W("div",Iv,[p[8]||(p[8]=W("div",{class:"flex items-center gap-2"},[W("div",{class:"h-8 w-8 rounded-lg bg-gradient-to-br from-accent to-accent-strong flex items-center justify-center text-[#00211D] font-extrabold text-sm"},"K"),W("span",{class:"text-sm font-semibold"},"Kautilya")],-1)),W("button",{class:"btn-icon",onClick:p[2]||(p[2]=g=>s.value=!1)},[fe(Y(sv),{size:16})])]),W("nav",wv,[(le(),Se(Te,null,xs(o,g=>fe(Y(Ur),{key:g.to,to:g.to,class:ln(["nav-item",{active:l(g.to)}]),onClick:p[3]||(p[3]=I=>s.value=!1)},{default:Gt(()=>[(le(),ut(Gn(g.icon),{size:18})),W("span",null,Ge(g.label),1)]),_:2},1032,["to","class"])),64))]),W("div",Sv,[W("div",Tv,[W("div",Av,[Y(t).photo?(le(),Se("img",{key:0,src:Y(t).photo,referrerpolicy:"no-referrer"},null,8,Cv)):(le(),Se("span",Rv,Ge(Y(Xs)(Y(t).displayName)),1))]),W("div",Pv,[W("div",Ov,Ge(Y(t).displayName),1),W("div",kv,Ge(Y(t).email),1)]),W("button",{onClick:u,class:"btn-icon",title:"Sign out"},[fe(Y(Ha),{size:14})])])])])])):In("",!0)]),_:1}),W("div",Nv,[W("header",xv,[W("button",{class:"btn-icon md:hidden",onClick:p[4]||(p[4]=g=>s.value=!0)},[fe(Y(ev),{size:18})]),W("div",Dv,[W("h1",Mv,Ge(c.value),1)]),W("div",Lv,[W("div",Uv,[fe(Y(nv),{size:14,class:"absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-dim"}),p[9]||(p[9]=W("input",{class:"input pl-8 h-9 text-sm",placeholder:"Search agents, calls…"},null,-1)),p[10]||(p[10]=W("span",{class:"kbd absolute right-2 top-1/2 -translate-y-1/2 hidden lg:inline"},"⌘K",-1))])]),W("button",{class:"btn btn-primary btn-sm hidden sm:inline-flex",onClick:p[5]||(p[5]=g=>Y(r).push("/agents?new=1"))},[fe(Y(tv),{size:14}),p[11]||(p[11]=Ui(" New Agent ",-1))]),W("div",Fv,[Y(t).photo?(le(),Se("img",{key:0,src:Y(t).photo,referrerpolicy:"no-referrer"},null,8,Bv)):(le(),Se("span",Vv,Ge(Y(Xs)(Y(t).displayName)),1))])]),W("main",Hv,[Nf(f.$slots,"default",{},void 0)])]),W("nav",jv,[(le(),Se(Te,null,xs(a,g=>fe(Y(Ur),{key:g.to,to:g.to,class:ln(["bottom-nav-item",{active:l(g.to)}])},{default:Gt(()=>[(le(),ut(Gn(g.icon),{size:20})),W("span",null,Ge(g.label),1)]),_:2},1032,["to","class"])),64))])]))}},Wv=ov($v,[["__scopeId","data-v-5f48e51a"]]),Kv={key:0,class:"h-screen w-screen flex items-center justify-center"},Gv={__name:"App",setup(e){const t=Pl(),n=to(),r=Fe(()=>t.meta.layout!=="blank");return Di(()=>{n.ready||n.bootstrap()}),(s,i)=>{const o=kf("router-view");return Y(n).ready?(le(),Se(Te,{key:1},[r.value?(le(),ut(Wv,{key:0},{default:Gt(()=>[fe(o,null,{default:Gt(({Component:a})=>[fe(fl,{name:"fade",mode:"out-in"},{default:Gt(()=>[(le(),ut(Gn(a)))]),_:2},1024)]),_:1})]),_:1})):(le(),ut(o,{key:1}))],64)):(le(),Se("div",Kv,[...i[0]||(i[0]=[W("div",{class:"flex items-center gap-3 text-ink-muted text-sm"},[W("span",{class:"inline-block w-4 h-4 rounded-full border-2 border-accent border-t-transparent animate-spin"}),Ui(" Loading workspace… ")],-1)])]))}}},zv="modulepreload",qv=function(e){return"/static/dashboard-v2/"+e},Ka={},Bt=function(t,n,r){let s=Promise.resolve();if(n&&n.length>0){document.getElementsByTagName("link");const o=document.querySelector("meta[property=csp-nonce]"),a=o?.nonce||o?.getAttribute("nonce");s=Promise.allSettled(n.map(c=>{if(c=qv(c),c in Ka)return;Ka[c]=!0;const l=c.endsWith(".css"),u=l?'[rel="stylesheet"]':"";if(document.querySelector(`link[href="${c}"]${u}`))return;const f=document.createElement("link");if(f.rel=l?"stylesheet":zv,l||(f.as="script"),f.crossOrigin="",f.href=c,a&&f.setAttribute("nonce",a),document.head.appendChild(f),l)return new Promise((p,g)=>{f.addEventListener("load",p),f.addEventListener("error",()=>g(new Error(`Unable to preload CSS for ${c}`)))})}))}function i(o){const a=new Event("vite:preloadError",{cancelable:!0});if(a.payload=o,window.dispatchEvent(a),!a.defaultPrevented)throw o}return s.then(o=>{for(const a of o||[])a.status==="rejected"&&i(a.reason);return t().catch(i)})},Jv=[{path:"/",redirect:"/overview"},{path:"/login",name:"login",component:()=>Bt(()=>import("./LoginView-C35571ZD.js"),__vite__mapDeps([0,1])),meta:{layout:"blank"}},{path:"/overview",name:"overview",component:()=>Bt(()=>import("./OverviewView-D2DWiSy5.js"),__vite__mapDeps([2,3,4,5,1])),meta:{auth:!0,title:"Overview"}},{path:"/agents",name:"agents",component:()=>Bt(()=>import("./AgentsView-az14nKQK.js"),__vite__mapDeps([6,3,7,8])),meta:{auth:!0,title:"Agents"}},{path:"/agents/:id",name:"agent-detail",component:()=>Bt(()=>import("./AgentDetailView-GaC-XYQe.js"),__vite__mapDeps([9,3,7,4,1,10])),meta:{auth:!0,title:"Agent Studio"}},{path:"/calls",name:"calls",component:()=>Bt(()=>import("./CallsView-cWFjsZi3.js"),__vite__mapDeps([11,3,5,10,4])),meta:{auth:!0,title:"Recent Calls"}},{path:"/telephony",name:"telephony",component:()=>Bt(()=>import("./PlaceholderView-BMhHtPde.js"),[]),meta:{auth:!0,title:"Telephony",placeholder:"Telephony providers (Vobiz / Exotel) — coming in next migration step."}},{path:"/billing",name:"billing",component:()=>Bt(()=>import("./PlaceholderView-BMhHtPde.js"),[]),meta:{auth:!0,title:"Billing",placeholder:"Billing & usage — coming in next migration step."}},{path:"/settings",name:"settings",component:()=>Bt(()=>import("./PlaceholderView-BMhHtPde.js"),[]),meta:{auth:!0,title:"Settings",placeholder:"API keys, profile, preferences — coming in next migration step."}},{path:"/:pathMatch(.*)*",redirect:"/overview"}],bu=up({history:$h("/dashboard/"),routes:Jv,scrollBehavior(){return{top:0}}});bu.beforeEach(async e=>{const t=to();return t.ready||await t.bootstrap(),e.meta.auth&&!t.isAuthed?{name:"login",query:{next:e.fullPath}}:e.name==="login"&&t.isAuthed?{path:"/overview"}:!0});const no=Yd(Gv);no.use(Zd());no.use(bu);no.mount("#app");export{ty as A,Ba as B,ey as C,Qn as D,tv as E,Te as F,Zv as G,Wa as H,oy as I,iy as J,ry as K,_r as L,ih as M,ja as P,nv as S,fl as T,sv as X,ov as _,Se as a,W as b,$e as c,Xv as d,Ui as e,fe as f,Y as g,In as h,fp as i,Pl as j,Di as k,xs as l,Fe as m,kf as n,le as o,ut as p,ln as q,$r as r,Gn as s,Ge as t,to as u,sy as v,Gt as w,ny as x,Yv as y,Qv as z};

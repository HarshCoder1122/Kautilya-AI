import{_ as K,k as A,o,a as i,b as e,f as R,g as c,e as x,q as v,t as y,h as U,z as P,C as S,F as T,l as Y,n as _,r as l,m as C}from"./index-WInTOwDQ.js";import{U as I}from"./api-DUjZMk6u.js";import{u as z}from"./agents-DdJlf9qR.js";import{K as L,C as N}from"./key-k6XaeYcS.js";import{L as B}from"./loader-circle-9LXwudTO.js";import{R as E}from"./refresh-cw-DkF2pVAQ.js";import{C as V}from"./circle-check-CJod_h6t.js";const $={class:"space-y-6 animate-fadein"},j={class:"card p-5 sm:p-6 space-y-4"},O={class:"flex items-center justify-between"},D={class:"text-base font-semibold flex items-center gap-2"},G=["disabled"],q={key:0,class:"skeleton h-10 w-full"},F={key:1,class:"p-4 bg-bg-subtle border border-line rounded-lg text-center"},M={key:2,class:"flex gap-2"},J=["value"],Q={key:3,class:"text-red-400 text-xs"},W={class:"card p-5 sm:p-6 space-y-4"},H={class:"space-y-3 pt-2"},X=["value"],Z={class:"border border-line rounded-lg overflow-hidden mt-4"},ee={class:"flex items-center border-b border-line bg-bg-subtle"},te={class:"p-4 text-xs overflow-x-auto font-mono bg-[#1e1e1e] text-[#d4d4d4]"},se={__name:"EmbedView",setup(oe){const u=z(),d=l(null),a=l(""),f=l(!0),m=l(!1),b=l(!1),p=l(null),r=l("react");A(async()=>{u.loaded||await u.fetch(),u.items.length&&(d.value=u.items[0]);try{const s=await I.account();s.api_key&&(a.value=s.api_key)}catch(s){console.error(s)}finally{f.value=!1}});const k=C(()=>`import { LiveKitRoom } from '@livekit/components-react';

// 1. Fetch token from RevealIQ using your API Key
const response = await fetch('https://ai.revealiq.in/api/agents/${d.value?.id||"YOUR_AGENT_ID"}/livekit-token', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer ${a.value||"YOUR_API_KEY"}',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ participantName: "Web User" })
});
const { token, wsUrl } = await response.json();

// 2. Connect your UI
return (
  <LiveKitRoom
    video={false}
    audio={true}
    token={token}
    serverUrl={wsUrl}
    connect={true}
  >
    {/* Your custom UI here */}
  </LiveKitRoom>
);`),g=C(()=>`import { Room } from 'livekit-client';

// 1. Fetch token
const response = await fetch('https://ai.revealiq.in/api/agents/${d.value?.id||"YOUR_AGENT_ID"}/livekit-token', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer ${a.value||"YOUR_API_KEY"}',
    'Content-Type': 'application/json'
  }
});
const { token, wsUrl } = await response.json();

// 2. Connect to Room
const room = new Room({ adaptiveStream: true, dynacast: true });
await room.connect(wsUrl, token);

// 3. Publish Microphone
await room.localParticipant.setMicrophoneEnabled(true);
console.log('Connected to agent!');`);async function h(){if(confirm(a.value?"Are you sure? This will invalidate your existing API key.":"Generate a new API key?")){m.value=!0,p.value=null;try{const s=await I.generateApiKey();a.value=s.api_key}catch(s){p.value=s.message}finally{m.value=!1}}}async function w(s){try{await navigator.clipboard.writeText(s),b.value=!0,setTimeout(()=>b.value=!1,1500)}catch{}}return(s,t)=>(o(),i("div",$,[t[13]||(t[13]=e("header",null,[e("p",{class:"text-xs uppercase tracking-widest text-ink-muted mb-1"},"Developer"),e("h1",{class:"text-2xl sm:text-3xl font-bold"},"API & Integrations"),e("p",{class:"text-sm text-ink-muted mt-1"}," Integrate RevealIQ agents directly into your own web or mobile applications using the LiveKit SDK. ")],-1)),e("section",j,[e("div",O,[e("div",null,[e("h2",D,[R(c(L),{size:16}),t[5]||(t[5]=x(" Your API Key",-1))]),t[6]||(t[6]=e("p",{class:"text-xs text-ink-muted mt-0.5"},"Use this key to authenticate server-side API requests.",-1))]),e("button",{class:"btn btn-ghost text-xs",onClick:h,disabled:m.value},[m.value?(o(),v(c(B),{key:0,size:14,class:"animate-spin"})):(o(),v(c(E),{key:1,size:14})),x(" "+y(a.value?"Regenerate":"Generate Key"),1)],8,G)]),f.value?(o(),i("div",q)):a.value?(o(),i("div",M,[e("input",{type:"text",readonly:"",value:a.value,class:"input flex-1 font-mono text-sm"},null,8,J),e("button",{class:"btn btn-subtle",onClick:t[0]||(t[0]=n=>w(a.value))},"Copy")])):(o(),i("div",F,[t[7]||(t[7]=e("p",{class:"text-sm text-ink-muted mb-3"},"You don't have an API key yet.",-1)),e("button",{class:"btn btn-primary",onClick:h},"Generate API Key")])),p.value?(o(),i("p",Q,y(p.value),1)):U("",!0)]),e("section",W,[t[11]||(t[11]=e("div",null,[e("h2",{class:"text-base font-semibold"},"LiveKit Integration Guide"),e("p",{class:"text-xs text-ink-muted mt-0.5"},"Build a completely custom UI by connecting your app directly to the agent's WebRTC room.")],-1)),e("div",H,[e("div",null,[t[8]||(t[8]=e("label",{class:"text-xs text-ink-muted font-medium mb-1 block"},"Select Agent to generate snippet for:",-1)),P(e("select",{"onUpdate:modelValue":t[1]||(t[1]=n=>d.value=n),class:"select max-w-sm"},[(o(!0),i(T,null,Y(c(u).items,n=>(o(),i("option",{key:n.id,value:n},y(n.name||n.id),9,X))),128))],512),[[S,d.value]])]),e("div",Z,[e("div",ee,[e("button",{class:_(["px-4 py-2 text-sm font-medium hover:bg-white/5 transition-colors",r.value==="react"?"text-accent border-b-2 border-accent":"text-ink-muted"]),onClick:t[2]||(t[2]=n=>r.value="react")},"React",2),e("button",{class:_(["px-4 py-2 text-sm font-medium hover:bg-white/5 transition-colors",r.value==="js"?"text-accent border-b-2 border-accent":"text-ink-muted"]),onClick:t[3]||(t[3]=n=>r.value="js")},"Vanilla JS",2),t[10]||(t[10]=e("div",{class:"flex-1"},null,-1)),e("button",{class:"btn btn-ghost btn-sm mr-2",onClick:t[4]||(t[4]=n=>w(r.value==="react"?k.value:g.value))},[b.value?(o(),v(c(V),{key:0,size:14,class:"text-emerald-400"})):(o(),v(c(N),{key:1,size:14})),t[9]||(t[9]=x(" Copy ",-1))])]),e("pre",te,[e("code",null,y(r.value==="react"?k.value:g.value),1)])])]),t[12]||(t[12]=e("div",{class:"mt-4 p-4 bg-accent/10 border border-accent/20 rounded-lg"},[e("h3",{class:"text-sm font-semibold text-accent mb-1"},"Security Best Practice"),e("p",{class:"text-xs text-ink-muted"}," Never expose your API Key in your frontend code. You should proxy the token request through your own backend server to securely fetch the LiveKit token. ")],-1))])]))}},de=K(se,[["__scopeId","data-v-6c2655de"]]);export{de as default};

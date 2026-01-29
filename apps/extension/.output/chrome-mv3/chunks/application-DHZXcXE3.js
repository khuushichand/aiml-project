import{G as u}from"./react-instance-check-Bx4cImxR.js";const e=u(),P=`Provide a concise summary of the following text, capturing its main ideas and key points:

Text:
---------
{text}
---------

Summarize the text in no more than 3-4 sentences.

Response:`,y=`Rewrite the following text in a different way, maintaining its original meaning but using alternative vocabulary and sentence structures:

Text:
---------
{text}
---------

Ensure that your rephrased version conveys the same information and intent as the original.

Response:`,g=`Translate the following text from its original language into "english". Maintain the tone and style of the original text as much as possible:

Text:
---------
{text}
---------

Response:`,h=`Provide a detailed explanation of the following text, breaking down its key concepts, implications, and context:

Text:
---------
{text}
---------

Your explanation should:

Clarify any complex terms or ideas
Provide relevant background information
Discuss the significance or implications of the content
Address any potential questions a reader might have
Use examples or analogies to illustrate points when appropriate

Aim for a comprehensive explanation that would help someone with little prior knowledge fully understand the text.

Response:`,w="{text}",s=(t,o)=>typeof t=="string"?t:o,n=async()=>s(await e.get("copilotSummaryPrompt"),P),x=async t=>{await e.set("copilotSummaryPrompt",t)},r=async()=>s(await e.get("copilotRephrasePrompt"),y),d=async t=>{await e.set("copilotRephrasePrompt",t)},i=async()=>s(await e.get("copilotTranslatePrompt"),g),f=async t=>{await e.set("copilotTranslatePrompt",t)},p=async()=>s(await e.get("copilotExplainPrompt"),h),T=async t=>{await e.set("copilotExplainPrompt",t)},m=async()=>s(await e.get("copilotCustomPrompt"),w),R=async t=>{await e.set("copilotCustomPrompt",t)},A=async()=>{const[t,o,a,c,l]=await Promise.all([n(),r(),i(),p(),m()]);return[{key:"summary",prompt:t},{key:"rephrase",prompt:o},{key:"translate",prompt:a},{key:"explain",prompt:c},{key:"custom",prompt:l}]},E=async t=>{for(const{key:o,prompt:a}of t)switch(o){case"summary":await x(a);break;case"rephrase":await d(a);break;case"translate":await f(a);break;case"explain":await T(a);break;case"custom":await R(a);break}},S=async t=>{switch(t){case"summary":return await n();case"rephrase":return await r();case"translate":return await i();case"explain":return await p();case"custom":return await m();default:return""}};export{S as a,A as g,E as s};

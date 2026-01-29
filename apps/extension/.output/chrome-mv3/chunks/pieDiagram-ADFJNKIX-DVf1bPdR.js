import{P as S,S as F,aA as j,g as q,s as Z,a as H,b as J,q as K,p as Q,_ as p,l as z,c as X,E as Y,I as tt,a3 as et,d as at,y as rt,F as nt}from"./mermaid.core-D0Kms7Y8.js";import{p as it}from"./chunk-4BX2VUAB-BAu-esdl.js";import{p as st}from"./treemap-KMMF4GRG-CiLJHioB.js";import"./transform-BUod4zOz.js";import{d as R}from"./arc-Cy5ftiUU.js";import{o as lt}from"./ordinal-Cboi1Yqb.js";import"./react-instance-check-Bx4cImxR.js";import"./purify.es-A66Cw1IH.js";import"./min-COqo6sTI.js";import"./_baseUniq-DCk3JkDd.js";import"./init-Gi6I4Gst.js";function ot(t,a){return a<t?-1:a>t?1:a>=t?0:NaN}function ct(t){return t}function ut(){var t=ct,a=ot,f=null,y=S(0),s=S(F),o=S(0);function l(e){var n,c=(e=j(e)).length,g,x,h=0,u=new Array(c),i=new Array(c),v=+y.apply(this,arguments),A=Math.min(F,Math.max(-F,s.apply(this,arguments)-v)),m,C=Math.min(Math.abs(A)/c,o.apply(this,arguments)),$=C*(A<0?-1:1),d;for(n=0;n<c;++n)(d=i[u[n]=n]=+t(e[n],n,e))>0&&(h+=d);for(a!=null?u.sort(function(w,D){return a(i[w],i[D])}):f!=null&&u.sort(function(w,D){return f(e[w],e[D])}),n=0,x=h?(A-c*$)/h:0;n<c;++n,v=m)g=u[n],d=i[g],m=v+(d>0?d*x:0)+$,i[g]={data:e[g],index:n,value:d,startAngle:v,endAngle:m,padAngle:C};return i}return l.value=function(e){return arguments.length?(t=typeof e=="function"?e:S(+e),l):t},l.sortValues=function(e){return arguments.length?(a=e,f=null,l):a},l.sort=function(e){return arguments.length?(f=e,a=null,l):f},l.startAngle=function(e){return arguments.length?(y=typeof e=="function"?e:S(+e),l):y},l.endAngle=function(e){return arguments.length?(s=typeof e=="function"?e:S(+e),l):s},l.padAngle=function(e){return arguments.length?(o=typeof e=="function"?e:S(+e),l):o},l}var pt=nt.pie,G={sections:new Map,showData:!1},T=G.sections,N=G.showData,gt=structuredClone(pt),dt=p(()=>structuredClone(gt),"getConfig"),ft=p(()=>{T=new Map,N=G.showData,rt()},"clear"),mt=p(({label:t,value:a})=>{if(a<0)throw new Error(`"${t}" has invalid value: ${a}. Negative values are not allowed in pie charts. All slice values must be >= 0.`);T.has(t)||(T.set(t,a),z.debug(`added new section: ${t}, with value: ${a}`))},"addSection"),ht=p(()=>T,"getSections"),vt=p(t=>{N=t},"setShowData"),St=p(()=>N,"getShowData"),L={getConfig:dt,clear:ft,setDiagramTitle:Q,getDiagramTitle:K,setAccTitle:J,getAccTitle:H,setAccDescription:Z,getAccDescription:q,addSection:mt,getSections:ht,setShowData:vt,getShowData:St},yt=p((t,a)=>{it(t,a),a.setShowData(t.showData),t.sections.map(a.addSection)},"populateDb"),xt={parse:p(async t=>{const a=await st("pie",t);z.debug(a),yt(a,L)},"parse")},At=p(t=>`
  .pieCircle{
    stroke: ${t.pieStrokeColor};
    stroke-width : ${t.pieStrokeWidth};
    opacity : ${t.pieOpacity};
  }
  .pieOuterCircle{
    stroke: ${t.pieOuterStrokeColor};
    stroke-width: ${t.pieOuterStrokeWidth};
    fill: none;
  }
  .pieTitleText {
    text-anchor: middle;
    font-size: ${t.pieTitleTextSize};
    fill: ${t.pieTitleTextColor};
    font-family: ${t.fontFamily};
  }
  .slice {
    font-family: ${t.fontFamily};
    fill: ${t.pieSectionTextColor};
    font-size:${t.pieSectionTextSize};
    // fill: white;
  }
  .legend text {
    fill: ${t.pieLegendTextColor};
    font-family: ${t.fontFamily};
    font-size: ${t.pieLegendTextSize};
  }
`,"getStyles"),wt=At,Dt=p(t=>{const a=[...t.values()].reduce((s,o)=>s+o,0),f=[...t.entries()].map(([s,o])=>({label:s,value:o})).filter(s=>s.value/a*100>=1).sort((s,o)=>o.value-s.value);return ut().value(s=>s.value)(f)},"createPieArcs"),Ct=p((t,a,f,y)=>{z.debug(`rendering pie chart
`+t);const s=y.db,o=X(),l=Y(s.getConfig(),o.pie),e=40,n=18,c=4,g=450,x=g,h=tt(a),u=h.append("g");u.attr("transform","translate("+x/2+","+g/2+")");const{themeVariables:i}=o;let[v]=et(i.pieOuterStrokeWidth);v??(v=2);const A=l.textPosition,m=Math.min(x,g)/2-e,C=R().innerRadius(0).outerRadius(m),$=R().innerRadius(m*A).outerRadius(m*A);u.append("circle").attr("cx",0).attr("cy",0).attr("r",m+v/2).attr("class","pieOuterCircle");const d=s.getSections(),w=Dt(d),D=[i.pie1,i.pie2,i.pie3,i.pie4,i.pie5,i.pie6,i.pie7,i.pie8,i.pie9,i.pie10,i.pie11,i.pie12];let E=0;d.forEach(r=>{E+=r});const P=w.filter(r=>(r.data.value/E*100).toFixed(0)!=="0"),b=lt(D);u.selectAll("mySlices").data(P).enter().append("path").attr("d",C).attr("fill",r=>b(r.data.label)).attr("class","pieCircle"),u.selectAll("mySlices").data(P).enter().append("text").text(r=>(r.data.value/E*100).toFixed(0)+"%").attr("transform",r=>"translate("+$.centroid(r)+")").style("text-anchor","middle").attr("class","slice"),u.append("text").text(s.getDiagramTitle()).attr("x",0).attr("y",-400/2).attr("class","pieTitleText");const W=[...d.entries()].map(([r,M])=>({label:r,value:M})),k=u.selectAll(".legend").data(W).enter().append("g").attr("class","legend").attr("transform",(r,M)=>{const O=n+c,B=O*W.length/2,V=12*n,U=M*O-B;return"translate("+V+","+U+")"});k.append("rect").attr("width",n).attr("height",n).style("fill",r=>b(r.label)).style("stroke",r=>b(r.label)),k.append("text").attr("x",n+c).attr("y",n-c).text(r=>s.getShowData()?`${r.label} [${r.value}]`:r.label);const _=Math.max(...k.selectAll("text").nodes().map(r=>(r==null?void 0:r.getBoundingClientRect().width)??0)),I=x+e+n+c+_;h.attr("viewBox",`0 0 ${I} ${g}`),at(h,g,I,l.useMaxWidth)},"draw"),$t={draw:Ct},It={parser:xt,db:L,renderer:$t,styles:wt};export{It as diagram};

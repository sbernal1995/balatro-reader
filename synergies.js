'use strict';
let buildCatalog=null,synergyText='',synergyTarget='auto';
try{synergyTarget=localStorage.getItem('balatro-build')||'auto';}catch{}
function jokerName(key){return buildCatalog?.jokers?.[key]?.name||key;}
function sourceLinks(ids,sources){const links=element('div',undefined,'sources');for(const id of ids||[]){const source=sources?.[id];if(!source)continue;const a=element('a',source.title);a.href=source.url;a.target='_blank';a.rel='noopener noreferrer';links.append(a);}return links;}
function pieceTags(build){const tags=element('div',undefined,'build-pieces');for(const key of build.core){const owned=build.core_owned?.includes(key);tags.append(element('span',(owned?'✓ ':'○ ')+jokerName(key),'build-piece'+(owned?' owned':'')));}return tags;}
function selectBuild(id){synergyTarget=id;try{localStorage.setItem('balatro-build',id);}catch{}$('build-select').value=id;synergyText='';pollSynergies(true);}
async function loadBuilds(){try{const response=await fetch('/builds');if(!response.ok)throw Error('No se pudo cargar la biblioteca');buildCatalog=await response.json();const select=$('build-select');select.replaceChildren(element('option','Detectar con mis comodines'));select.firstChild.value='auto';for(const b of buildCatalog.builds){const option=element('option',b.icon+' '+b.name);option.value=b.id;select.append(option);}if(!buildCatalog.builds.some(b=>b.id===synergyTarget))synergyTarget='auto';select.value=synergyTarget;select.disabled=false;$('build-date').textContent=`${buildCatalog.builds.length} builds investigadas · ${buildCatalog.researched_on}`;renderBuildLibrary();}catch(e){$('synergy-status').textContent=e.message;}}
function renderBuildLibrary(profiles=[]){const library=$('build-library');library.replaceChildren();for(const b of buildCatalog.builds){const p=profiles.find(x=>x.id===b.id),box=element('article',undefined,'library-card');box.append(element('strong',b.icon+' '+b.name),pieceTags(p||b),element('p',b.note));const button=element('button','Elegir objetivo');button.type='button';button.addEventListener('click',()=>selectBuild(b.id));box.append(button,sourceLinks(b.sources,buildCatalog.sources));library.append(box);}}
function renderSynergies(data){
 const signature=JSON.stringify(data);if(signature===synergyText)return;synergyText=signature;
 const panel=$('shop-panel'),column=panel.parentElement;if(data.in_shop)column.prepend(panel);else column.insertBefore(panel,$('jokers').closest('section'));
 $('build-warnings').replaceChildren(...(data.warnings||[]).map(x=>element('p',x)));
 const focus=$('build-focus');focus.replaceChildren();const selected=data.builds.find(b=>b.id===data.selected_id);
 if(selected){focus.append(element('div',synergyTarget==='auto'?'Estrategia detectada':'Build objetivo','eyebrow'),element('h3',selected.icon+' '+selected.name),pieceTags(selected),element('p',selected.note),element('p',selected.deck_detail));
 const details=element('details');details.append(element('summary','Piezas de apoyo y referencias'),element('p','Apoyo: '+selected.support.map(jokerName).join(' · ')),sourceLinks(selected.sources,data.sources));focus.append(details);
 }else focus.append(element('p','Aún no se detecta un núcleo de la biblioteca. Podés elegir una build objetivo para ver sus piezas y requisitos.'));
 const root=$('shop-synergies');root.replaceChildren();$('synergy-status').textContent=data.in_shop?'Se recalcula al cambiar la tienda, tus comodines o la baraja.':'Entrá a la tienda para evaluar sus cartas.';
 if(!data.in_shop||!data.shop.length)root.append(element('div',data.in_shop?'No hay cartas en la tienda.':'Las afinidades de compra aparecerán aquí al entrar a la tienda.','empty'));
 for(const item of data.shop){const box=element('article',undefined,'shop-card'),c=item.card;box.append(element('div',c.key?.startsWith('j_')?'✦ Comodín':'☽ Consumible','eyebrow'),element('strong',c.state?.hidden?'Carta oculta':c.label||jokerName(c.key)),element('p',c.value?.effect||''));
 const score=element('div',undefined,'score-line');score.append(element('span','Afinidad con tu partida','muted'),element('span',item.percent==null?'—':item.percent+'%','affinity'+(item.percent==null||item.percent<40?' low':item.percent<70?' medium':'')));box.append(score);
 const meter=element('div',undefined,'meter'),fill=element('i');fill.style.width=(item.percent||0)+'%';fill.style.background=item.percent<40?'var(--muted)':item.percent<70?'var(--gold)':'var(--green)';meter.append(fill);box.append(meter);
 if(item.build_name)box.append(element('p',item.build_name));
 if(synergyTarget!=='auto')box.append(element('p',item.target_piece?'✓ Pieza de tu build objetivo':'Sin pieza específica para tu build objetivo',item.target_piece?'goal-piece':'muted'));
 box.append(element('p',item.purchase.price==null?'Precio no informado':`Precio: $${num(item.purchase.price)} · ${item.purchase.can_buy_now?'Dinero y espacio disponibles':item.purchase.affordable===false?'No alcanza el dinero':item.purchase.space_available===false?'Necesitás espacio':'Revisá los espacios'}`));
 for(const note of [...item.warnings,...item.purchase.notes])box.append(element('p',note,'caution'));
 const list=element('ul');for(const reason of item.reasons)list.append(element('li',reason));box.append(list);
 if(item.components){const details=element('details');details.append(element('summary','Cómo se calculó'));for(const [key,label] of [['partners','Compañeros'],['deck','Baraja'],['alignment','Núcleo presente'],['development','Desarrollo']])details.append(element('p',`${label}: ${item.components[key]??'sin datos'} / ${data.weights[key]}`));if(item.penalty)details.append(element('p',`Conflictos: −${item.penalty} puntos`));box.append(details);}
 box.append(sourceLinks(item.sources,data.sources));root.append(box);
 }
 renderBuildLibrary(data.builds);
 $('synergy-method').textContent=data.method;
}
let synergyBusy=false;
async function pollSynergies(once=false){if(synergyBusy){if(!once)setTimeout(pollSynergies,1000);return;}synergyBusy=true;const target=synergyTarget;try{if(!buildCatalog)await loadBuilds();const response=await fetch('/synergies?build='+encodeURIComponent(target)),data=await response.json();if(target!==synergyTarget){synergyText='';return;}if(!response.ok)throw Error(data.reason||'Sin lectura de la tienda');renderSynergies(data);}catch(e){$('synergy-status').textContent=e.message;const marker='offline:'+target;if(synergyText===marker)return;synergyText=marker;$('shop-synergies').replaceChildren(element('div','Esperando conexión con Balatro para calcular afinidades.','empty'));const focus=$('build-focus');focus.replaceChildren();const chosen=buildCatalog?.builds.find(b=>b.id===synergyTarget);if(chosen)focus.append(element('div','Build objetivo · Sin lectura de la partida','eyebrow'),element('h3',chosen.icon+' '+chosen.name),element('p',chosen.note),sourceLinks(chosen.sources,buildCatalog.sources));$('build-warnings').replaceChildren();if(buildCatalog)renderBuildLibrary();}finally{synergyBusy=false;if(!once)setTimeout(pollSynergies,1100);}}
$('build-select').addEventListener('change',()=>selectBuild($('build-select').value));
pollSynergies();

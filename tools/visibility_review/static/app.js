'use strict';
const $ = id => document.getElementById(id);
let token, ids=[], current=null, record=null, data=null, busy=false, dirty=false, timer=null, filterTimer=null, generation=0, editVersion=0;
const layers=['building','road','flooded_building','flooded_road'];
const slotNames={pre:'灾前影像',post1:'灾后影像1',post2:'灾后影像2'};
const decisionNames={accepted:'已接受',rejected:'已拒绝',needs_review:'需复核',pending:'待审'};
const flagNames={CLOUD:'云遮挡',BLACK_BORDER:'黑边',NO_DATA:'无数据',INVALID_AREA:'无效区域',TEMPORAL_MISMATCH:'时相不匹配',ALIGNMENT_ERROR:'空间错位',LABEL_ERROR:'标签错误',CORRUPTED_IMAGE:'影像损坏',OTHER:'其他'};
const metricNames={valid_fraction:'有效像元比例',mean_brightness:'平均亮度',near_white_fraction:'近白像元比例',mean_channel_spread:'平均通道差',mean_gradient:'平均梯度',review_priority_score:'审查优先级分数',column:'来源列',path:'路径',sha256:'SHA256'};
async function api(url, body) {
  const r=await fetch(url,body?{method:'POST',headers:{'Content-Type':'application/json','X-Review-Token':token},body:JSON.stringify(body)}:{});
  if(!r.ok){let e=await r.json();throw Error(typeof e.detail==='string'?e.detail:JSON.stringify(e.detail));}
  return r.json();
}
function zhError(value){return String(value).replace('Rejected requires a reason flag or notes','拒绝样本时必须勾选原因或填写备注').replace('Record changed in another tab. Reload before saving.','该记录已在另一个页面修改，请刷新后再保存').replace('Sample Load Error','样本加载错误').replace('POST2 unavailable','灾后影像2不可用').replace('POST1 unavailable','灾后影像1不可用').replace('Preview unavailable','预览图不可用').replace('Unknown sample','未知样本').replace('Accepted requires post1 or post2','接受样本时必须选择灾后影像1或灾后影像2');}
function error(e){$('error').textContent=zhError(e.message||String(e));}
function stats(s){$('stats').replaceChildren();for(const [label,value] of [['审查进度',`${s.total-s.pending} / ${s.total}`],['已接受',s.accepted],['已拒绝',s.rejected],['需复核',s.needs_review],['待审',s.pending],['已选灾后影像1',s.selected_post1],['已选灾后影像2',s.selected_post2]]){const d=document.createElement('div');d.className='stat';const v=document.createElement('strong');v.textContent=value;const l=document.createElement('span');l.textContent=label;d.append(l,v);$('stats').append(d);}}
function overlay(){document.querySelectorAll('.layer').forEach(img=>{const k=img.dataset.layer;img.hidden=k.startsWith('flooded_')?!$('flood').checked:!$(k).checked;});}
function labelControls(){const available=Object.values(data.images).find(im=>im.available&&!im.error&&im.label_feature_counts);const counts=available?.label_feature_counts||{};const values={building:counts.building||0,road:counts.road||0,flood:(counts.flooded_building||0)+(counts.flooded_road||0)};for(const key of ['building','road','flood']){const control=$(key);control.disabled=values[key]===0;if(control.disabled)control.checked=false;$(key+'-label').textContent=key==='building'?`显示建筑标签（${values[key]}）`:key==='road'?`显示道路标签（${values[key]}）`:`显示受淹标签（${values[key]}）`;}const missing=[];if(!values.building)missing.push('建筑');if(!values.road)missing.push('道路');if(!values.flood)missing.push('受淹');$('overlay-note').textContent=missing.length?`本样本没有${missing.join('、')}标签，对应开关已禁用。点击图片可放大。`:'粉色：受淹建筑 · 橙色：受淹道路 · 点击图片放大';}
function picture(slot, im){const d=document.createElement('div');d.className='picture';const base=document.createElement('img');base.className='base';base.alt=slotNames[slot]+' '+current;base.src=`/preview/${encodeURIComponent(current)}/${slot}/rgb.png`;base.onerror=()=>error(Error(`${slotNames[slot]}预览图加载失败`));d.append(base);for(const layer of layers){if(!im.files.includes(layer+'.png'))continue;const img=document.createElement('img');img.className='layer';img.dataset.layer=layer;img.alt='';img.src=`/preview/${encodeURIComponent(current)}/${slot}/${layer}.png`;d.append(img);}return d;}
function metricValue(value){return {'post-event image 1':'灾后影像1','post-event image 2':'灾后影像2'}[value]||value;}
function metadataText(slot,im){if(!im.available)return `${slotNames[slot]}\n状态：不可用`;if(im.error)return `${slotNames[slot]}\n错误：${zhError(im.error)}`;const lines=[slotNames[slot],`文件名：${im.filename}`,`原始尺寸：${im.width} × ${im.height}`,`预览尺寸：${im.preview_width} × ${im.preview_height}`,`坐标参考系：${im.crs}`,`仿射变换：${(im.transform||[]).join(', ')}`,`源文件：${im.source}`,`预期 SHA256：${im.stamp?.expected_sha256||'无'}`,`标签 SHA256：${im.stamp?.label_sha256||'无'}`];if(im.metrics){lines.push('自动指标（仅供排序）：');for(const [k,v] of Object.entries(im.metrics)){if(metricNames[k])lines.push(`  ${metricNames[k]}：${metricValue(v)}`);}}if(im.label_feature_counts){lines.push('标签要素数：');for(const [k,v] of Object.entries(im.label_feature_counts))lines.push(`  ${{building:'建筑',road:'道路',flooded_building:'受淹建筑',flooded_road:'受淹道路'}[k]||k}：${v}`);}return lines.join('\n');}
function render(){
  $('sample-id').textContent='样本：'+current;$('decision-state').textContent=decisionNames[record.decision]+(record.selected_post?' · '+slotNames[record.selected_post]:'');$('position').textContent=`当前筛选结果第 ${ids.indexOf(current)+1} 项，共 ${ids.length} 项`;
  $('images').replaceChildren();$('metadata').replaceChildren();
  for(const slot of ['pre','post1','post2']){const im=data.images[slot],panel=document.createElement('article'),title=document.createElement('h3');panel.className='panel';title.textContent=slotNames[slot];panel.append(title);
    if(!im.available||im.error){const d=document.createElement('div');d.className='unavailable';d.textContent=im.error?zhError(im.error):(slotNames[slot]+'不可用');panel.append(d);}else{const pic=picture(slot,im);pic.onclick=()=>{$('zoom-title').textContent=slotNames[slot]+' · '+current;$('zoom-image').replaceChildren(pic.cloneNode(true));$('zoom').showModal();};panel.append(pic);}
    const name=document.createElement('div');name.className='filename';name.textContent=im.filename?`${im.filename} · ${im.width} × ${im.height} · ${im.crs}`:'';panel.append(name);$('images').append(panel);
    if(im.overlay_error)error(Error(slotNames[slot]+'标签叠加错误：'+im.overlay_error));const meta=document.createElement('pre');meta.textContent=metadataText(slot,im);$('metadata').append(meta);
  }
  const candidates=Object.entries(data.sample.images).filter(([k,v])=>k!=='pre'&&v).sort((a,b)=>(a[1].review_priority_score||0)-(b[1].review_priority_score||0));
  $('recommendation').textContent='仅辅助排序，不代表人工结论。较低风险候选顺序：'+candidates.map(([k,v])=>`${slotNames[k]}（${v.review_priority_score.toFixed(3)}）`).join(' → ');
  $('notes').value=record.notes;$('reviewer').value=(localStorage.getItem('visibility-reviewer')||'人工审查').replace(/^manual$/,'人工审查');
  document.querySelectorAll('[data-flag]').forEach(el=>el.checked=record.flags[el.dataset.flag]);
  $('accept2').disabled=!data.images.post2.available||Boolean(data.images.post2.error);$('accept1').disabled=!data.images.post1.available||Boolean(data.images.post1.error);
  $('review').hidden=false;labelControls();overlay();
}
async function load(sid){
  const gen=++generation;current=sid;record=null;dirty=false;$('error').textContent='';
  if(!sid){$('sample-id').textContent=ids.length?'审查已完成':'没有符合条件的样本';$('images').replaceChildren();$('metadata').replaceChildren();$('review').hidden=true;$('position').textContent='';$('decision-state').textContent='';return;}
  busy=true;$('sample-id').textContent='正在加载 '+sid+'…';
  try{const result=await api('/api/sample/'+encodeURIComponent(sid));if(gen!==generation)return;data=result;record=result.record;render();$('save-status').textContent='已加载 · 所有决定立即保存';}catch(e){error(e);}finally{if(gen===generation)busy=false;}
}
async function refreshList(){const q=new URLSearchParams({kind:$('filter').value,search:$('search').value,risk:$('risk').checked});const r=await api('/api/samples?'+q);ids=r.ids;stats(r.summary);return r;}
async function flush(decision=null,post=null,advance=false){
  clearTimeout(timer);if(!record||busy)return false;if(!dirty&&!decision)return true;
  busy=true;$('error').textContent='';$('save-status').textContent='正在落盘…';
  const savedVersion=editVersion,sid=current,payload={revision:record.revision,decision:decision||record.decision,selected_post:decision?post:record.selected_post,flags:{},notes:$('notes').value,reviewer:$('reviewer').value};
  document.querySelectorAll('[data-flag]').forEach(el=>payload.flags[el.dataset.flag]=el.checked);
  try{const r=await api('/api/review/'+encodeURIComponent(sid),payload);record=r.record;dirty=editVersion!==savedVersion;stats(r.summary);$('save-status').textContent=dirty?'正在保存后续编辑…':'已持久化 ✓';$('decision-state').textContent=decisionNames[record.decision]+(record.selected_post?' · '+slotNames[record.selected_post]:'');localStorage.setItem('visibility-reviewer',payload.reviewer);busy=false;
    if(dirty&&!(await flush()))return false;
    if(advance){$('filter').value='all';$('search').value='';const list=await refreshList();await load(list.resume);if(!list.resume)$('sample-id').textContent='审查已完成';}
    return true;
  }catch(e){error(e);$('save-status').textContent='保存失败 · 请处理后重试';return false;}finally{busy=false;}
}
async function navigate(delta){if(busy||!(await flush()))return;await refreshList();const i=ids.indexOf(current);await load(ids[Math.max(0,Math.min(ids.length-1,i+delta))]||null);}
async function decide(d,p=null){if(busy||!record)return;if(p==='post2'&&$('accept2').disabled)return;if(p==='post1'&&$('accept1').disabled)return;await flush(d,p,true);}
function edited(){dirty=true;editVersion++;clearTimeout(timer);timer=setTimeout(()=>flush(),450);}
async function filters(){clearTimeout(filterTimer);if(busy){filterTimer=setTimeout(filters,100);return;}if(!(await flush()))return;try{await refreshList();await load(ids.includes(current)?current:ids[0]||null);}catch(e){error(e);}}
$('notes').addEventListener('input',edited);$('reviewer').addEventListener('change',edited);
$('accept1').onclick=()=>decide('accepted','post1');$('accept2').onclick=()=>decide('accepted','post2');$('reject').onclick=()=>decide('rejected');$('uncertain').onclick=()=>decide('needs_review');$('pending').onclick=()=>decide('pending');
$('previous').onclick=()=>navigate(-1);$('next').onclick=()=>navigate(1);
for(const id of ['filter','risk'])$(id).onchange=filters;$('search').onchange=filters;$('search').oninput=()=>{clearTimeout(filterTimer);filterTimer=setTimeout(filters,250);};
$('resume').onclick=async()=>{if(busy||!(await flush()))return;$('filter').value='all';$('search').value='';const list=await refreshList();await load(list.resume);if(!list.resume)$('sample-id').textContent='审查已完成';};
for(const id of ['building','road','flood'])$(id).onchange=overlay;
function toggle(){const enabled=['building','road','flood'].filter(id=>!$(id).disabled);const on=!enabled.some(id=>$(id).checked);for(const id of enabled)$(id).checked=on;overlay();}
$('hide-labels').onclick=toggle;$('close-zoom').onclick=()=>$('zoom').close();
document.addEventListener('keydown',e=>{if(e.ctrlKey||e.altKey||e.metaKey||e.repeat||e.target.closest('input,textarea,select,[contenteditable=true]')||$('zoom').open)return;const key=e.key.toLowerCase();const actions={'1':()=>decide('accepted','post1'),'2':()=>decide('accepted','post2'),'r':()=>decide('rejected'),'u':()=>decide('needs_review'),'n':()=>navigate(1),'p':()=>navigate(-1),'o':toggle};if(actions[key]){e.preventDefault();actions[key]();}});
window.addEventListener('beforeunload',e=>{if(dirty||busy){e.preventDefault();e.returnValue='';}});
(async()=>{try{const b=await api('/api/bootstrap');token=b.token;$('mode').textContent=b.sandbox?'沙盒 · 测试审查库':'本机 · 正式审查库';for(const flag of b.flags){const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.dataset.flag=flag;input.onchange=edited;label.append(input,document.createTextNode(flagNames[flag]||flag));$('flags').append(label);}stats(b.summary);await refreshList();await load(b.resume);if(!b.resume)$('sample-id').textContent='审查已完成';}catch(e){error(e);}})();

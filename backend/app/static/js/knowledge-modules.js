/* S2 module workspace. Evidence is selected from server-owned chunks. */
(() => {
  const id = new URLSearchParams(location.search).get('material');
  const root = document.querySelector('#knowledge-panel');
  const status = root.querySelector('[role=status]');
  const list = document.querySelector('#knowledge-list');
  const form = document.querySelector('#knowledge-form');
  const source = document.querySelector('#knowledge-source');
  const dialog = document.querySelector('#knowledge-extract-dialog');
  let busy = false, sources = [], editId = null;
  const message = (text, error=false) => { status.textContent=text; status.className='notice'+(error?' warn':''); };
  const api = (path, options={}) => sbApi.json('/api/knowledge-modules'+path, options);
  const el = (tag,text,cls) => Object.assign(document.createElement(tag), {textContent:text,className:cls||''});
  const button = (label, action) => { const b=el('button',label,'btn'); b.type='button'; b.title=label; b.onclick=action; return b; };
  document.querySelectorAll('#knowledge-panel button, #knowledge-tab, #knowledge-content-tab').forEach(b=>b.title=b.textContent);
  const change = async (action, text) => {
    if(busy)return;
    busy=true; root.querySelectorAll('button').forEach(b=>b.disabled=true);
    try { await action(); await load(); message(text); }
    catch(error) { message(({knowledge_source_invalid:'来源已变更，请重新选择片段。',provider_not_configured:'AI 服务未配置，可使用手动添加。',knowledge_generation_invalid:'AI 返回格式无效，可重试或手动添加。'})[error.code]||'知识模块操作失败，可重试。', true); }
    finally {busy=false;root.querySelectorAll('button').forEach(b=>b.disabled=false);document.querySelector('#knowledge-save').disabled=!sources.length&&!editId;document.querySelector('#knowledge-extract').disabled=!sources.length;}
  };
  function reset(){editId=null;form.reset();source.disabled=false;document.querySelector('#knowledge-save').textContent='手动添加模块';}
  function render(module) {
    const row=el('article','', 'card stack'); row.dataset.moduleId=module.id;
    row.append(el('h3',module.title),el('p',module.description));
    const labels={draft:'AI 草稿，待确认',confirmed:'已确认',rejected:'已拒绝'};
    row.append(el('p',(labels[module.lifecycle]||module.lifecycle)+' · 重要性 '+module.importance+' · 难度 '+module.difficulty+' · '+Math.round(module.mastery_level*100)+'%（基于已评分练习）'));
    const sourceLabels={valid:'来源可用',source_deleted:'来源已删除',source_unavailable:'来源不可用',stale:'来源已变更'};
    row.append(el('p',sourceLabels[module.source_status]||'来源不可用'));
    if(module.source_status==='valid') {
      const a=el('a','查看来源片段','btn'); a.href='#body';
      a.onclick=() => {
        document.querySelector('#knowledge-content-tab').click();
        const body=document.querySelector('#body');
        const quote=module.source_evidence.context||'';
        const text=body.textContent, start=text.indexOf(quote);
        if(start>=0&&quote){body.replaceChildren(document.createTextNode(text.slice(0,start)));const mark=el('mark',quote);body.append(mark,document.createTextNode(text.slice(start+quote.length)));}
        body.scrollIntoView({block:'center'});
      };
      row.append(a);
    }
    if(module.lifecycle!=='rejected') {
      row.append(button('编辑模块',() => {
        editId=module.id;
        document.querySelector('#knowledge-title').value=module.title;
        document.querySelector('#knowledge-description').value=module.description;
        document.querySelector('#knowledge-importance').value=module.importance;
        document.querySelector('#knowledge-difficulty').value=module.difficulty;
        source.disabled=true;
        document.querySelector('#knowledge-save').textContent='保存模块编辑';
        document.querySelector('#knowledge-title').focus();
      }));
    }
    if(module.lifecycle==='draft'){
      row.append(button('确认模块',()=>change(()=>api('/'+module.id+'/confirm',{method:'POST'}),'模块已确认。')),
                 button('拒绝草稿',()=>change(()=>api('/'+module.id+'/reject',{method:'POST'}),'草稿已拒绝。')));
    }
    if(module.lifecycle==='confirmed'&&module.source_status==='valid'&&module.status==='active'){
      const a=el('a','按此模块练习','btn btn-primary');
      a.href='/app/exercises.html?knowledge_module='+encodeURIComponent(module.id);row.append(a);
    }
    row.append(button('删除模块',()=>{if(window.confirm('删除此模块？已有练习记录将保留。'))change(()=>api('/'+module.id,{method:'DELETE'}),'模块已删除。');}));
    return row;
  }
  async function load(){
    const q=document.querySelector('#knowledge-query').value;
    const data=await api('?material_id='+encodeURIComponent(id)+(q?'&q='+encodeURIComponent(q):''));
    list.replaceChildren(...data.modules.map(render));
    if(!data.modules.length)list.append(el('p','暂无知识模块，可手动添加或 AI 辅助抽取。'));
  }
  document.querySelector('#knowledge-tab').onclick=()=>{
    root.hidden=false;document.querySelector('#material-content-panel').hidden=true;
    document.querySelector('#knowledge-tab').setAttribute('aria-selected','true');
    document.querySelector('#knowledge-content-tab').setAttribute('aria-selected','false');
  };
  document.querySelector('#knowledge-content-tab').onclick=()=>{
    root.hidden=true;document.querySelector('#material-content-panel').hidden=false;
    document.querySelector('#knowledge-tab').setAttribute('aria-selected','false');
    document.querySelector('#knowledge-content-tab').setAttribute('aria-selected','true');
  };
  const tabs=[document.querySelector('#knowledge-content-tab'),document.querySelector('#knowledge-tab')];
  if(new URLSearchParams(location.search).get('tab')==='knowledge')tabs[1].click();
  tabs.forEach((tab,index)=>tab.addEventListener('keydown',event=>{
    if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
    event.preventDefault();const target=event.key==='Home'?tabs[0]:event.key==='End'?tabs[1]:tabs[1-index];target.click();target.focus();
  }));
  form.onsubmit=event=>{
    event.preventDefault();
    const payload={title:document.querySelector('#knowledge-title').value,description:document.querySelector('#knowledge-description').value,
      importance:Number(document.querySelector('#knowledge-importance').value),difficulty:Number(document.querySelector('#knowledge-difficulty').value)};
    change(async()=>{
      if(editId)await api('/'+editId,{method:'PATCH',body:JSON.stringify(payload)});
      else await api('',{method:'POST',body:JSON.stringify({...payload,material_id:id,chunk_ids:[source.value]})});
      reset();
    },'模块已保存。');
  };
  document.querySelector('#knowledge-cancel').onclick=reset;
  document.querySelector('#knowledge-search').onsubmit=event=>{event.preventDefault();change(load,'模块列表已刷新。');};
  document.querySelector('#knowledge-refresh').onclick=()=>change(load,'模块列表已刷新。');
  document.querySelector('#knowledge-extract').onclick=()=>dialog.showModal();
  document.querySelector('#knowledge-extract-cancel').onclick=()=>dialog.close();
  document.querySelector('#knowledge-extract-form').onsubmit=event=>{
    event.preventDefault();
    const count=Number(document.querySelector('#knowledge-count').value);
    dialog.close();
    change(()=>api('/extract',{method:'POST',body:JSON.stringify({material_id:id,max_modules:count})}),'AI 草稿已生成，请逐项编辑、确认或拒绝。');
  };
  if(!id){message('请先从资料库选择材料。');root.querySelectorAll('button,input,select,textarea').forEach(b=>b.disabled=true);return;}
  async function init(){
    try{
      sources=await api('/sources?material_id='+encodeURIComponent(id));
      source.replaceChildren(...sources.map((s,i)=>new Option('来源片段 '+(i+1),s.chunk_id)));
      await load();
      const ready=sources.length>0;
      document.querySelector('#knowledge-save').disabled=!ready;
      document.querySelector('#knowledge-extract').disabled=!ready;
      message(ready?'请选择来源片段添加模块，或生成 AI 草稿。':'材料尚未建立索引。请先在内容页建立 AI 索引，再刷新本页。');
    }catch(error){message('模块或来源加载失败，请刷新重试。',true);}
  }
  document.addEventListener('sb-index-updated',init);
  document.addEventListener('sb-material-error',()=>{root.querySelectorAll('button,input,select,textarea').forEach(b=>b.disabled=true);message('材料不可用，模块操作已停用。',true);});
  init();
})();

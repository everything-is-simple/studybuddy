/* S1: bounded, evidence-backed actions; completion uses existing domain events. */
(() => {
  const list=document.querySelector('#pending-items'),status=document.querySelector('#pending-status');
  const refresh=document.querySelector('#refresh-pending'),errorBox=document.querySelector('#pending-error');
  const overflow=document.querySelector('#pending-overflow'),emptyActions=document.querySelector('#pending-empty-actions');
  let generation=0;
  const busyItems=new Set();
  const el=(tag,text,cls='')=>Object.assign(document.createElement(tag),{textContent:text,className:cls});
  const labels=['紧急 · P0','重要 · P1','建议 · P2'];
  const categories={tomorrow_prep:'明日准备',due_task:'到期安排',quality_check:'待核对',mistake_review:'错题复习',plan_schedule:'待安排',cram_countdown:'冲刺倒计时',next_step:'下一步'};
  function error(error){errorBox.hidden=false;errorBox.textContent=sbApi.safeError(error);}
  async function progress(item,button){
    if(busyItems.has(item.id))return;
    busyItems.add(item.id);button.disabled=true;errorBox.hidden=true;
    const evidence=item.evidence,eventType=evidence.status==='in_progress'?'completed':'started';
    try{
      await sbSubmit.once('s1-'+item.id,()=>sbApi.json(`/api/study/plans/${encodeURIComponent(evidence.plan_id)}/items/${encodeURIComponent(evidence.item_id)}/progress`,{
        method:'POST',body:JSON.stringify({event_type:eventType,metadata:{local_date:evidence.local_date}})
      }));
      await load();document.dispatchEvent(new CustomEvent('sb-today-progress'));
    }catch(e){error(e);}finally{busyItems.delete(item.id);button.disabled=false;}
  }
  function render(item){
    const row=el('li','','pending-item-card stack');row.dataset.pendingId=item.id;row.dataset.category=item.category;row.dataset.priority=item.priority;
    row.append(el('span',labels[item.priority],'priority-badge priority-p'+item.priority),el('h3',item.title),el('p',item.description));
    const evidence=item.evidence;
    row.append(el('p',categories[item.category]+(evidence.local_date?' · '+evidence.local_date:'')+(evidence.mistake_count?' · '+evidence.mistake_count+' 道':'')+(evidence.draft_count?' · '+evidence.draft_count+' 个草稿':''),'muted'));
    const actions=el('div','','stack-actions');
    if(item.category==='due_task'&&!evidence.blocked_count){
      const button=el('button',item.action_label,'btn btn-primary');button.type='button';button.onclick=()=>progress(item,button);actions.append(button);
      const details=el('a','查看计划详情','btn');details.href=item.action_url;actions.append(details);
    }else{
      const link=el('a',item.action_label,'btn btn-primary');link.href=item.action_url;actions.append(link);
    }
    row.append(actions);return row;
  }
  async function load(){
    const run=++generation;refresh.disabled=true;errorBox.hidden=true;emptyActions.hidden=true;overflow.hidden=true;
    status.hidden=false;status.textContent='正在整理今日待办…';list.replaceChildren();
    try{
      const data=await sbApi.json('/api/today/pending-items');
      if(run!==generation)return;
      list.replaceChildren(...data.pending_items.map(render));
      status.hidden=data.total>0;
      if(!data.total){status.textContent='今天没有紧急待办。可以休息，也可以安排一次学习。';emptyActions.hidden=false;}
      if(data.remaining_count){
        overflow.hidden=false;overflow.replaceChildren(document.createTextNode(`还有 ${data.remaining_count} 项未显示${data.remaining_p0_count?'，其中 '+data.remaining_p0_count+' 项紧急':''}。`));
        const more=el('button','查看更多任务','btn');more.type='button';more.onclick=()=>{const details=document.querySelector('#more-tasks');details.open=true;details.scrollIntoView({block:'start'});};overflow.append(more);
        [['全部计划','/app/plans.html'],['资料','/app/materials.html'],['错题','/app/review.html'],['备考与练习','/app/practice.html']].forEach(([label,url])=>{const link=el('a',label,'btn');link.href=url;overflow.append(link);});
      }
    }catch(e){if(run!==generation)return;status.hidden=true;error(e);}
    finally{if(run===generation)refresh.disabled=false;}
  }
  refresh.onclick=load;
  document.addEventListener('sb-today-reload',load);
  load();
})();

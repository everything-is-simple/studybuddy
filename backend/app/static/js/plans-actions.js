(function(){
document.querySelector('#refresh-all')?.setAttribute('data-control','plans-reload');
const refresh=document.querySelector('#refresh-all');
const notices=['#plan-status','#goal-status','#module-status','#source-status'].map(s=>document.querySelector(s)).filter(Boolean);
function add(element){
  if(element.dataset.actionReady==='1')return;
  const value=element.textContent||'';
  if(!/失败|错误|冲突|重复|不可用|没有完成|目标已经归档|模块已经归档/.test(value))return;
  let code='request_failed';
  if(value.includes('先后顺序')||value.includes('依赖'))code='study_plan_dependency_cycle';
  else if(value.includes('当天已经安排')||value.includes('重复安排'))code='study_rhythm_allocation_duplicate';
  else if(value.includes('目标已经归档'))code='learning_goal_archived';
  else if(value.includes('模块已经归档'))code='knowledge_module_archived';
  const info=sbApi.errorInfo({code});
  const action=document.createElement('button');
  action.type='button';action.className='btn mt-12';action.dataset.control=info.action.control;
  action.textContent=info.action.type==='focus'?'前往修改':'重新加载';
  action.onclick=()=>{const target=document.querySelector(`[data-control="${info.action.control}"]`);if(info.action.type==='focus'&&target){target.focus();target.scrollIntoView({block:'center'});return}(refresh||document.querySelector('#source-refresh'))?.click()};
  element.append(document.createTextNode(` ${info.message}。怎么办：${info.advice}`),action);
  element.dataset.actionReady='1';
}
const observer=new MutationObserver(records=>records.forEach(record=>add(record.target.nodeType===3?record.target.parentElement:record.target)));
notices.forEach(element=>observer.observe(element,{childList:true,characterData:true,subtree:true}));
notices.forEach(add);
})();

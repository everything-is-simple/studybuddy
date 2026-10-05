/* TTS browser skill: audio playback stays in the page; the server owns synthesis and cache. */
(() => {
  const player=document.querySelector('#tts-player');
  if(!player)return;
  const audio=new Audio(),status=player.querySelector('[data-tts-status]');
  const speakButton=player.querySelector('[data-tts-speak]'),playButton=player.querySelector('[data-tts-play]');
  const stopButton=player.querySelector('[data-tts-stop]'),retryButton=player.querySelector('[data-tts-retry]');
  let current=null,busy=false;
  const message=(text,kind='')=>{status.textContent=text;status.className='notice'+(kind?' '+kind:'');};
  const setButtons=()=>{playButton.disabled=!current||busy;stopButton.disabled=!current||busy;retryButton.disabled=!current||busy;};
  async function speak(text,title='知识模块'){
    const value=(text||'').trim();if(!value||busy)return;
    busy=true;setButtons();message('正在准备语音…');
    try{audio.pause();audio.currentTime=0;const result=await sbApi.json('/api/tts/speak',{method:'POST',body:JSON.stringify({text:value})});
      current={...result,text:value,title};player.querySelector('[data-tts-title]').textContent=title;audio.src=result.audio_url;audio.load();await audio.play();
      message(result.fallback_used?'正在播放（已切换本地引擎）':'正在播放');
    }catch(error){current=null;message(sbApi.safeError(error)+' 可重试。','warn');}
    finally{busy=false;setButtons();}
  }
  async function control(action){if(!current||busy)return;try{
    if(action==='pause')audio.paused?await audio.play():audio.pause();if(action==='stop'){audio.pause();audio.currentTime=0;}
    await sbApi.json('/api/tts/control',{method:'POST',body:JSON.stringify({playback_id:current.playback_id,action})});
    message(action==='pause'?(audio.paused?'已暂停':'正在播放'):action==='stop'?'已停止':'正在播放');
  }catch(error){message(sbApi.safeError(error)+' 可重试。','warn');}}
  audio.onended=()=>{if(current)message('播放完成');};
  speakButton.onclick=()=>speak(speakButton.dataset.ttsText,speakButton.dataset.ttsTitle||'知识模块');
  playButton.onclick=()=>control('pause');stopButton.onclick=()=>control('stop');retryButton.onclick=()=>current&&speak(current.text,current.title);setButtons();
  window.sbTts={speak,setTarget(text,title){speakButton.dataset.ttsText=text;speakButton.dataset.ttsTitle=title;speakButton.disabled=!text;},capabilities:()=>sbApi.json('/api/tts/capabilities')};
  sbApi.json('/api/tts/capabilities').then(data=>{const enabled=data.status==='configured'||data.status==='demo';
    player.querySelector('[data-tts-engine]').textContent=enabled?(data.provider_id||'local'):'未配置';
    if(!enabled){message('TTS 未配置；可在启动环境中显式启用。','warn');speakButton.disabled=true;}
  }).catch(()=>message('TTS 状态不可用，可刷新重试。','warn'));
})();

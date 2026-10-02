(function () {
  const routes = Object.freeze({
    today: { label: '今天', path: '/app/today.html' },
    student: { label: '学生', path: '/app/student.html' },
    parent: { label: '家长', path: '/app/parent.html' },
  });
  let frame = document.querySelector('#buddy-frame');
  const status = document.querySelector('#buddy-status');
  const fallback = document.querySelector('#buddy-fallback-link');
  const links = [...document.querySelectorAll('[data-view]')];
  const switches = [...document.querySelectorAll('[data-switch-view]')];
  const mobileToggle = document.querySelector('[data-mobile-nav-toggle]');
  const nav = document.querySelector('#buddy-navigation');
  const storageKey = 'studybuddy-buddy-view';
  let currentView = '';
  let frameReady = false;

  function viewFromUrl() {
    const value = new URLSearchParams(location.search).get('view');
    if (Object.prototype.hasOwnProperty.call(routes, value)) return value;
    const stored = localStorage.getItem(storageKey);
    return stored === 'student' || stored === 'parent' ? stored : 'student';
  }
  function updateChrome(view) {
    const route = routes[view];
    links.forEach(link => link.setAttribute('aria-current', link.dataset.view === view ? 'page' : 'false'));
    switches.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.switchView === view)));
    document.querySelectorAll('[data-management-link]').forEach(link => { link.hidden = view === 'student'; });
    document.title = `StudyBuddy · ${route.label}`;
    fallback.href = route.path;
    fallback.textContent = `直接打开${route.label}页面`;
    status.textContent = frameReady ? `${route.label}页面已打开` : `正在打开${route.label}页面…`;
  }
  function onFrameLoad(event) {
    if (event.currentTarget !== frame) return;
    frameReady = true;
    status.textContent = `${routes[currentView].label}页面已打开`;
  }
  function load(view, replace) {
    const route = routes[view];
    if (replace) history.replaceState({ view }, '', `/app/buddy.html?view=${view}`);
    else if (currentView !== view) history.pushState({ view }, '', `/app/buddy.html?view=${view}`);
    const changed = currentView !== view || frame.getAttribute('src') !== route.path;
    if (changed) frameReady = false;
    updateChrome(view);
    if (view === 'student' || view === 'parent') localStorage.setItem(storageKey, view);
    if (changed) {
      currentView = view;
      // A fresh child context keeps shell view changes out of iframe history.
      const nextFrame = frame.cloneNode(false);
      nextFrame.setAttribute('src', route.path);
      nextFrame.addEventListener('load', onFrameLoad);
      const previousFrame = frame;
      frame = nextFrame;
      previousFrame.replaceWith(nextFrame);
    }
  }
  links.forEach(link => link.addEventListener('click', event => {
    event.preventDefault();
    load(link.dataset.view, false);
    nav.classList.remove('is-open');
    mobileToggle?.setAttribute('aria-expanded', 'false');
  }));
  switches.forEach(button => button.addEventListener('click', () => load(button.dataset.switchView, false)));
  mobileToggle?.addEventListener('click', () => {
    const open = nav.classList.toggle('is-open');
    mobileToggle.setAttribute('aria-expanded', String(open));
  });
  window.addEventListener('popstate', () => load(viewFromUrl(), true));
  load(viewFromUrl(), true);
  document.querySelector('#buddy-script-help')?.remove();
}());

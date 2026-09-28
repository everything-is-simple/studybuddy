(function () {
  const routes = Object.freeze({
    today: { label: '今天', path: '/app/today.html' },
    student: { label: '学生', path: '/app/student.html' },
    parent: { label: '家长', path: '/app/parent.html' },
  });
  const frame = document.querySelector('#buddy-frame');
  const status = document.querySelector('#buddy-status');
  const fallback = document.querySelector('#buddy-fallback-link');
  const links = [...document.querySelectorAll('[data-view]')];
  const switches = [...document.querySelectorAll('[data-switch-view]')];
  const storageKey = 'studybuddy-buddy-view';
  let currentView = '';

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
    status.textContent = `正在打开${route.label}页面…`;
  }
  function load(view, replace) {
    const route = routes[view];
    if (replace) history.replaceState({ view }, '', `/app/buddy.html?view=${view}`);
    else history.pushState({ view }, '', `/app/buddy.html?view=${view}`);
    updateChrome(view);
    if (view === 'student' || view === 'parent') localStorage.setItem(storageKey, view);
    if (currentView !== view || frame.getAttribute('src') !== route.path) {
      currentView = view;
      frame.src = route.path;
    }
  }
  links.forEach(link => link.addEventListener('click', event => {
    event.preventDefault();
    load(link.dataset.view, false);
  }));
  switches.forEach(button => button.addEventListener('click', () => load(button.dataset.switchView, false)));
  frame.addEventListener('load', () => {
    const route = routes[currentView] || routes.today;
    status.textContent = `${route.label}页面已打开`;
  });
  window.addEventListener('popstate', () => load(viewFromUrl(), true));
  load(viewFromUrl(), true);
}());

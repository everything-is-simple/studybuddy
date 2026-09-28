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
  let currentView = '';

  function viewFromUrl() {
    const value = new URLSearchParams(location.search).get('view');
    return Object.prototype.hasOwnProperty.call(routes, value) ? value : 'today';
  }
  function updateChrome(view) {
    const route = routes[view];
    links.forEach(link => link.setAttribute('aria-current', link.dataset.view === view ? 'page' : 'false'));
    document.title = `StudyBuddy · ${route.label}`;
    fallback.href = route.path;
    status.textContent = `正在打开${route.label}页面…`;
  }
  function load(view, replace) {
    const route = routes[view];
    if (replace) history.replaceState({ view }, '', `/app/buddy.html?view=${view}`);
    else history.pushState({ view }, '', `/app/buddy.html?view=${view}`);
    updateChrome(view);
    if (currentView !== view || frame.getAttribute('src') !== route.path) {
      currentView = view;
      frame.src = route.path;
    }
  }
  links.forEach(link => link.addEventListener('click', event => {
    event.preventDefault();
    load(link.dataset.view, false);
  }));
  frame.addEventListener('load', () => {
    const route = routes[currentView] || routes.today;
    status.textContent = `${route.label}页面已打开`;
  });
  window.addEventListener('popstate', () => load(viewFromUrl(), true));
  load(viewFromUrl(), true);
}());

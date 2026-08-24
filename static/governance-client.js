(async () => {
  const css = document.createElement('link');
  css.rel = 'stylesheet';
  css.href = '/static/governance-client.css';
  document.head.appendChild(css);

  const response = await fetch('/api/v1/auth/me');
  if (!response.ok) return;
  const user = await response.json();

  const nav = document.createElement('nav');
  nav.className = 'global-governance-nav';
  nav.innerHTML = `<b>RI</b>
    <a href="/">Início</a>
    <a class="optional" href="/monitoring">Monitoria 360°</a>
    <a class="optional" href="/journey">Jornada</a>
    <a class="optional" href="/explainability">Explicabilidade</a>
    ${user.role === 'admin' ? '<a href="/admin/governance">Governança</a>' : ''}
    <span class="spacer"></span>
    <small>${user.username} · ${user.role}</small>
    <select id="global-product" aria-label="Produto ativo">
      ${user.products.map(product => `<option value="${product.slug}" ${product.slug === user.product_scope ? 'selected' : ''}>${product.name}</option>`).join('')}
    </select>
    <button id="global-logout">Sair</button>`;
  document.body.prepend(nav);

  // Product scope is an HttpOnly security cookie, so only the server may
  // change it. Navigating with a validated query lets the middleware update
  // that cookie before this page's API requests are issued.
  nav.querySelector('#global-product').addEventListener('change', event => {
    const target = new URL(window.location.href);
    target.searchParams.set('product_scope', event.target.value);
    window.location.assign(target.toString());
  });

  nav.querySelector('#global-logout').addEventListener('click', async () => {
    await fetch('/api/v1/auth/logout', {method: 'POST'});
    window.location.assign('/login');
  });

  // Keep URLs clean after the server has persisted the selected scope.
  if (new URL(window.location.href).searchParams.has('product_scope')) {
    const clean = new URL(window.location.href);
    clean.searchParams.delete('product_scope');
    window.history.replaceState({}, '', clean.toString());
  }
})();

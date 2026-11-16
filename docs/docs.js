(() => {
  const theme = document.querySelector('#theme');
  const systemTheme = matchMedia('(prefers-color-scheme: dark)');
  try { theme.value = localStorage.getItem('marslab-theme') || 'auto'; } catch (_) {}
  function applyTheme() {
    document.documentElement.dataset.theme = theme.value === 'auto'
      ? (systemTheme.matches ? 'dark' : 'light') : theme.value;
  }
  theme.addEventListener('change', () => {
    applyTheme();
    try { localStorage.setItem('marslab-theme', theme.value); } catch (_) {}
  });
  systemTheme.addEventListener('change', applyTheme);
  applyTheme();

  const menu = document.querySelector('.menu-toggle');
  menu.addEventListener('click', () => {
    const open = document.body.classList.toggle('menu-open');
    menu.setAttribute('aria-expanded', String(open));
    menu.textContent = open ? 'Close menu' : 'Menu';
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && document.body.classList.contains('menu-open')) {
      menu.click();
      menu.focus();
    }
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      document.querySelector('#header-query').focus();
    }
  });

  const toc = document.querySelector('#page-toc');
  document.querySelectorAll('.doc-content h2[id], .doc-content h3[id]').forEach((heading) => {
    const item = document.createElement('li');
    const link = document.createElement('a');
    link.href = `#${heading.id}`;
    link.textContent = heading.textContent;
    if (heading.tagName === 'H3') item.classList.add('subheading');
    item.append(link);
    toc.append(item);
  });
  if (toc.children.length) toc.closest('aside').hidden = false;

  document.querySelectorAll('.doc-content pre').forEach((pre) => {
    const wrapper = document.createElement('div');
    wrapper.className = 'code-block';
    pre.before(wrapper);
    wrapper.append(pre);
    const button = document.createElement('button');
    button.className = 'copy-code';
    button.type = 'button';
    button.textContent = 'Copy';
    button.setAttribute('aria-label', 'Copy code');
    button.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(pre.textContent.replace(/\n$/, ''));
        button.textContent = 'Copied';
      } catch (_) {
        button.textContent = 'Select to copy';
        const selection = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(pre);
        selection.removeAllRanges();
        selection.addRange(range);
      }
      setTimeout(() => { button.textContent = 'Copy'; }, 1800);
    });
    wrapper.append(button);
  });
})();

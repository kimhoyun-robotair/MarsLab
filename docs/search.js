(() => {
  const container = document.querySelector('#doc-search');
  if (!container) return;
  const input = document.querySelector('#search-query');
  const status = document.querySelector('#search-status');
  const results = document.querySelector('#search-results');
  let indexPromise;
  let sequence = 0;
  let timer;

  function loadIndex() {
    if (!indexPromise) {
      indexPromise = fetch(container.dataset.index).then((response) => {
        if (!response.ok) throw new Error('Search index unavailable');
        return response.json();
      }).catch((error) => {
        indexPromise = undefined;
        throw error;
      });
    }
    return indexPromise;
  }

  async function search() {
    const request = ++sequence;
    const query = input.value.trim();
    const terms = [...new Set(query.toLowerCase().match(/[\p{L}\p{N}_]+/gu) || [])];
    results.replaceChildren();
    const url = new URL(location.href);
    if (query) url.searchParams.set('q', query);
    else url.searchParams.delete('q');
    history.replaceState(null, '', url);
    document.querySelector('#header-query').value = query;
    if (query.length < 2 || !terms.length) {
      status.textContent = 'Enter at least two characters to search the documentation.';
      return;
    }
    status.textContent = 'Searching…';
    try {
      const documents = await loadIndex();
      if (request !== sequence) return;
      const matches = documents.map((document) => {
        const title = document.title.toLowerCase();
        const body = `${document.description || ''} ${document.content || ''}`.toLowerCase();
        const all = `${title} ${body}`;
        const score = terms.every((term) => all.includes(term))
          ? terms.reduce((sum, term) => sum + (title.includes(term) ? 10 : 1), 0) + (title === query.toLowerCase() ? 20 : 0) : 0;
        return { document, score };
      }).filter((match) => match.score > 0).sort((a, b) => b.score - a.score || a.document.title.localeCompare(b.document.title));
      status.textContent = matches.length
        ? `${matches.length} matching ${matches.length === 1 ? 'page' : 'pages'}.${matches.length > 12 ? ' Showing the first 12.' : ''}`
        : 'No matching pages. Try a robot name, a shorter phrase, or a configuration key.';
      for (const { document: entry } of matches.slice(0, 12)) {
        const item = document.createElement('li');
        const heading = document.createElement('h2');
        const link = document.createElement('a');
        link.href = entry.url;
        link.textContent = entry.title;
        heading.append(link);
        const excerpt = document.createElement('p');
        const content = entry.content || entry.description || '';
        const firstMatch = terms.map((term) => content.toLowerCase().indexOf(term)).filter((index) => index >= 0);
        const start = firstMatch.length ? Math.max(0, Math.min(...firstMatch) - 65) : 0;
        excerpt.textContent = `${start ? '…' : ''}${content.slice(start, start + 230)}${content.length > start + 230 ? '…' : ''}`;
        item.append(heading, excerpt);
        results.append(item);
      }
    } catch (_) {
      if (request === sequence) status.textContent = 'Search could not load. Try again, or use the documentation sidebar.';
    }
  }
  document.querySelector('#search-form').addEventListener('submit', (event) => {
    event.preventDefault();
    clearTimeout(timer);
    search();
  });
  input.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(search, 200);
  });
  input.value = new URLSearchParams(location.search).get('q') || '';
  if (input.value) search();
})();

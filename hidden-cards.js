'use strict';
(() => {
  const panel = document.getElementById('hidden-identification');
  const status = document.getElementById('hidden-status');
  const results = document.getElementById('hidden-results');
  let current = null, busy = false, previous = '', message = '';
  const buttons = [...panel.querySelectorAll('button[data-sort]')];
  const updateButtons = () => {
    for (const button of buttons) {
      const mode = button.dataset.sort;
      button.disabled = busy || !current?.hand_id || (mode === 'clear' && !current.observations?.length);
      button.classList.toggle('recorded', mode !== 'clear' && current?.observations?.includes(mode));
      if (mode !== 'clear') button.setAttribute('aria-pressed', String(!!current?.observations?.includes(mode)));
    }
  };
  window.renderHiddenInference = state => {
    const hasHidden = state?.hand?.cards?.some(card => card.state?.hidden);
    panel.hidden = !hasHidden;
    const next = hasHidden ? state.hidden_inference : null;
    if (next?.hand_id !== current?.hand_id) message = '';
    current = next;
    updateButtons();
    if (!hasHidden) { previous = ''; results.replaceChildren(); return; }
    const modes = current?.observations || [];
    status.textContent = message || current?.reason || (modes.length === 2
      ? 'Categoría y Palo registrados · posibilidades cruzadas'
      : modes.length === 1 ? `${modes[0] === 'rank' ? 'Categoría registrada' : 'Palo registrado'} · falta el otro orden para afinar`
      : 'Registrá uno de los órdenes para empezar.');
    // Keep expanded candidate lists open while the live reader polls.
    const key = JSON.stringify(current);
    if (key !== previous) {
      previous = key;
      results.replaceChildren();
      for (const inferred of current?.cards || []) {
        const box = element('article', undefined, 'hidden-result');
        const header = element('div', undefined, 'hidden-result-head');
        header.append(element('strong', `Oculta ${inferred.label}`), element('span',
          !modes.length ? 'Sin observaciones' : inferred.identified ? 'Una combinación compatible' : 'Posibilidades',
          'badge' + (inferred.identified ? ' final' : '')));
        box.append(header);
        if (!modes.length) {
          box.append(element('p', 'Su posición al ordenar ayudará a acotar el valor y el palo.', 'muted'));
        } else {
          const ranks = element('div', undefined, 'hidden-values');
          ranks.append(element('span', 'Valores', 'muted'));
          for (const rank of inferred.ranks) ranks.append(element('span', rank === 'A' ? 'As' : rank === 'T' ? '10' : rank, 'value-chip'));
          if (!inferred.ranks.length) ranks.append(element('span', 'Sin valor para jugar', 'muted'));
          const suitRow = element('div', undefined, 'hidden-values');
          suitRow.append(element('span', 'Palos', 'muted'));
          for (const suit of inferred.suits) {
            const chip = element('span', suits[suit], 'suit-chip' + (['H', 'D'].includes(suit) ? ' red' : ''));
            chip.title = {S:'Picas',H:'Corazones',C:'Tréboles',D:'Diamantes'}[suit];
            chip.setAttribute('aria-label', {S:'Picas',H:'Corazones',C:'Tréboles',D:'Diamantes'}[suit]);
            suitRow.append(chip);
          }
          if (!inferred.suits.length) suitRow.append(element('span', 'Sin palo para jugar', 'muted'));
          box.append(ranks, suitRow);
          if (inferred.stone_possible) box.append(element('p', 'También podría ser una carta Piedra, cuyo orden funciona de otra manera.', 'small-note'));
          const candidates = inferred.candidates || [];
          if (candidates.length) {
            const list = element('details');
            list.open = candidates.length <= 6;
            list.append(element('summary', `${candidates.length} ${candidates.length === 1 ? 'carta compatible' : 'cartas compatibles'}`));
            const cards = element('div', undefined, 'cards compact');
            renderCards(cards, candidates.map(value => ({value})), null, true);
            list.append(cards);
            box.append(list);
          }
        }
        results.append(box);
      }
    }
    // Track the same hidden card after either sort, without changing its face.
    for (const wrapper of document.querySelectorAll('#hand .card-wrapper')) {
      const inferred = current?.cards?.find(card => card.token === wrapper.dataset.token);
      if (!inferred) continue;
      wrapper.querySelector('.card-label').textContent = `Oculta ${inferred.label}`;
      const card = wrapper.querySelector('.playing-card');
      let badge = card.querySelector('.hidden-count');
      if (!badge) { badge = element('span', undefined, 'hidden-count'); card.append(badge); }
      badge.textContent = modes.length ? `${inferred.candidates.length}${inferred.stone_possible ? ' + ◇' : ''} posibles` : `Oculta ${inferred.label}`;
      card.setAttribute('aria-label', `Carta oculta ${inferred.label}`);
    }
  };
  for (const button of buttons) button.addEventListener('click', async () => {
    if (button.disabled) return;
    busy = true;
    message = '';
    updateButtons();
    status.textContent = 'Registrando el orden actual de la mano…';
    try {
      const response = await fetch('/hidden-observation', {method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({mode:button.dataset.sort, hand_id:current?.hand_id})});
      const data = await response.json();
      if (!response.ok) throw Error(data.reason || 'No se pudo registrar el orden.');
      if (liveState) window.renderHiddenInference({...liveState, hidden_inference:data.inference});
    } catch (error) { message = error.message; status.textContent = message; }
    finally { busy = false; updateButtons(); }
  });
})();

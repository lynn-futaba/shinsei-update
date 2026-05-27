/* app/static/js/pallet-supply.js
 * Requires: jQuery 3.7+, Bootstrap 5 bundle
 * Aligned with api_response_format.py:
 *   Success: { status, message, data }
 *   Error   : { status, message, error: { code, details } }
 */
// ===== Auto refresh (polling) =====
let pollTimerId = null;
let isPolling = false;
const POLL_INTERVAL_MS = 1000;
let selectedPattern = null;
let isCountdownActive = false;
// Track which pairIds already have active countdowns
const countdownPairIds = new Set();

(function ($) {
  'use strict';

  console.log('[pallet-supply] boot');

  // ===== API (underscore) =====
  const API_BASE = '/worker/api/v1/pallet_supply';

  /**
   * Parse API response aligned with api_response_format.py.
   * - On non-2xx or presence of error payload, throws Error(message [CODE])
   * - On success returns the parsed JSON (expecting {status, message, data, ...})
   */
  async function parseApi(res) {
    let js = null;
    try {
      js = await res.json();
    } catch (e) {
      // If server sent no/invalid JSON, keep js=null and rely on res.ok below
    }

    const status = res.status;
    const message = (js && typeof js === 'object' && typeof js.message === 'string')
      ? js.message
      : (res.statusText || 'Request failed');

    const errorCode = (js && js.error && js.error.code) ? js.error.code : null;
    const details = (js && js.error) ? js.error.details : undefined;

    // Treat either HTTP error OR a structured error payload as failure
    if (!res.ok || (js && js.error)) {
      const err = new Error(errorCode ? `${message} [${errorCode}]` : message);
      err.code = errorCode || `HTTP_${status}`;
      err.status = status;
      err.details = details;
      throw err;
    }

    // Success path: expect an object and "data" key (could be null for 204 shape)
    if (!js || typeof js !== 'object') {
      const err = new Error('Invalid JSON payload');
      err.code = 'INVALID_JSON';
      err.status = status;
      throw err;
    }
    return js; // { status, message, data, ... }
  }

  async function apiList() {
    const res = await fetch(API_BASE, { headers: { 'Accept': 'application/json' } });
    const js = await parseApi(res);
    const data = js.data;
    if (!data || !Array.isArray(data.lines)) {
      throw new Error('Invalid payload: data.lines must be an array');
    }
    const maxPairs = Number(data.max_pairs);
    return { lines: data.lines, max_pairs: Number.isFinite(maxPairs) ? maxPairs : 10 };
  }

  async function apiGetLine(lineId) {
    const res = await fetch(`${API_BASE}/${encodeURIComponent(lineId)}`, { headers: { 'Accept': 'application/json' } });
    const js = await parseApi(res);
    const data = js.data;
    if (!data || !data.line) throw new Error('Invalid payload: data.line missing');
    return data.line;
  }

  async function apiNames(lineName) {
    const res = await fetch(`${API_BASE}/${encodeURIComponent(lineName)}/names`, {
      headers: { 'Accept': 'application/json' }
    });
    const js = await parseApi(res);
    const data = js.data;
    if (!data || !Array.isArray(data.names)) {
      throw new Error('Invalid payload: data.names must be an array');
    }
    // Ensure shape: [{ pallet_type, pallet_name }]
    return data.names.map(n => {
      if (n && typeof n === 'object' && 'pallet_type' in n) return n;
      // fallback if backend ever sends just strings
      return { pallet_type: null, pallet_name: String(n || '') };
    });
  }

  async function apiAdd(lineId, beforeIndex, palletType, count) {
    const body = {
      before_index: Number.isInteger(beforeIndex) ? beforeIndex : null,
      pallet_type : Number(palletType),   // ← use type (INT)
      count       : Number(count),
    };
    const res = await fetch(`${API_BASE}/${encodeURIComponent(lineId)}/pair`, {
      method : 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body   : JSON.stringify(body)
    });
    const js = await parseApi(res);
    const data = js.data;
    if (!data || !data.line) throw new Error('Invalid payload: data.line missing');
    return data.line;
  }
  
  async function apiUpdate(lineId, pairId, palletType, count) {
    const res = await fetch(`${API_BASE}/${encodeURIComponent(lineId)}/pair/${Number(pairId)}`, {
      method : 'PUT',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body   : JSON.stringify({
        pallet_type: Number(palletType),
        count      : Number(count),
      })
    });
    const js = await parseApi(res);
    const data = js.data;
    if (!data || !data.line) throw new Error('Invalid payload: data.line missing');
    return data.line;
  }

  async function apiDelete(lineId, pairId) {
    const res = await fetch(`${API_BASE}/${encodeURIComponent(lineId)}/pair/${Number(pairId)}`, {
      method : 'DELETE',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      // body   : JSON.stringify({ rev: Number(rev) })
    });
    const js = await parseApi(res);
    const data = js.data;
    if (!data || !data.line) throw new Error('Invalid payload: data.line missing');
    return data.line;
  }

  async function apiMoveToGroup0(lineId, pairIndex) {
    const res = await fetch(`${API_BASE}/${encodeURIComponent(lineId)}/move_to_group0`, {
      method : 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body   : JSON.stringify({ pair_index: Number(pairIndex) })
    });
    const js = await parseApi(res);
    return js.data.line;
  }

  // ✅ Lock if any lift is WORK or COMP
  async function isLineLocked(lineName) {
    try {
      if (!lineName) return false; // ✅ prevent empty line bug
  
      const res = await fetch('/worker/api/v1/lift_entrance', {
        headers: { 'Accept': 'application/json' }
      });
  
      const js = await res.json();
      const rows = js.data || [];
  
      const lineRows = rows.filter(r => r.line_name === lineName);
  
      return lineRows.some(r =>
        ['COMP'].includes((r.transport_status || '').toUpperCase())
      );
  
    } catch (e) {
      console.error('[line-lock-check] failed:', e);
      return false;
    }
  }


  // ===== Elements =====
  const $tbody = $('#line-state-body');
  const $thead = $('#line-table thead');

  const $btnRead   = $('#btn-read');
  const $btnEdit   = $('#btn-edit');
  const $btnAdd    = $('#btn-add');
  const $btnDelete = $('#btn-delete');

  // ===== Modals: create ONCE (reused) =====
  const deleteModalEl  = document.getElementById('deleteConfirmModal');
  const deleteModal    = deleteModalEl ? bootstrap.Modal.getOrCreateInstance(deleteModalEl) : null;

  const readModalEl    = document.getElementById('readModal');
  const readModal      = readModalEl ? bootstrap.Modal.getOrCreateInstance(readModalEl) : null;

  const editAddModalEl = document.getElementById('editAddModal');
  const editAddModal   = editAddModalEl ? bootstrap.Modal.getOrCreateInstance(editAddModalEl) : null;

  const $deleteExecBtn = $('#deleteExecuteBtn');
  // const $readTableBody = $('#readTableBody');
  const $palletList    = $('#palletList');
  const $supplyInput   = $('#supplyInput');
  const $modalSaveBtn  = $('#modalSaveBtn');

  function setButtonsDisabled(disabled) {
    $('#btn-edit, #btn-add, #btn-delete')
      .prop('disabled', disabled)
      .toggleClass('opacity-50', disabled);
  
    if (disabled) {
      $('#btn-edit, #btn-add, #btn-delete')
        .attr('title', 'リフト作業中のため操作できません');
    } else {
      $('#btn-edit, #btn-add, #btn-delete')
        .removeAttr('title');
    }
  }

  // ---- Focus-safe modal hide helpers ----
  function moveFocusOutOf(modalEl) {
    try {
      const active = document.activeElement;
      if (active && modalEl.contains(active)) {
        // Blur focused control inside modal
        active.blur();

        // Temporarily focus body (so aria-hidden can be applied safely)
        const body = document.body;
        const prevTabIndex = body.getAttribute('tabindex');
        body.setAttribute('tabindex', '-1');
        body.focus({ preventScroll: true });
        // Restore tabindex
        if (prevTabIndex === null) body.removeAttribute('tabindex');
        else body.setAttribute('tabindex', prevTabIndex);
      }
    } catch (e) {
      console.warn('[pallet-supply] moveFocusOutOf error:', e);
    }
  }
  /** Call this instead of modal.hide() */
  function safeHideModal(modalInstance, modalEl) {
    if (!modalInstance || !modalEl) return;
    moveFocusOutOf(modalEl);
    // Defer to ensure focus moves before hide
    setTimeout(() => {
      modalInstance.hide();
    }, 0);
  }
  // Also protect attribute-dismissed buttons (rare edge case)
  document.querySelectorAll('[data-bs-dismiss="modal"]').forEach(btn => {
    btn.addEventListener('mousedown', () => {
      const modalEl = btn.closest('.modal');
      if (modalEl) moveFocusOutOf(modalEl);
    });
  });

  // Cache names per line to reduce requests (keys are lineName strings)
  const namesCache = new Map();

  function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => (
    {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]
  ));
  }

  /**
   * Loads list from /names and filters to the selected line:
   * - If pallet_name contains "(T63)" and lineName === "T63", keep it.
   * - If the server already filters, this is a harmless no-op.
   */
  async function loadNamesForLine(lineName) {
  if (namesCache.has(lineName)) return namesCache.get(lineName);

  const list = await apiNames(lineName); // [{pallet_type, pallet_name}, ...]
  const tag = `(${lineName})`;

  // Filter to items that clearly belong to this line (fallback to keep all if name missing)
  const filtered = list.filter(({ pallet_name }) => {
    const name = (pallet_name || '').toString();
    return name.includes(tag); // simple and robust with your current data
  });

  const finalList = filtered.length ? filtered : list; // fallback if no tagged names found
  namesCache.set(lineName, finalList);
  return finalList;
  }

  function populateModalList($listEl, names, selectedType = null) {
    $listEl.empty();
    if (!names || !names.length) {
      $listEl.append('<div class="text-muted text-center py-2">データがありません</div>');
      return;
    }
    names.forEach(({ pallet_type, pallet_name }) => {
      const active = (selectedType != null && Number(pallet_type) === Number(selectedType)) ? ' active' : '';
      const label = escapeHtml(pallet_name ?? '');
      const typeAttr = (pallet_type != null) ? ` data-type="${String(pallet_type)}"` : '';
      $listEl.append(
        `<button type="button" class="list-group-item list-group-item-action${active}"${typeAttr}>${label}</button>`
      );
    });
  }

  // ===== Selection state =====
  const RESET_SELECTION = () => ({
    $row: null,
    lineId: 0,
    lineName: '',
    pairIndex: -1,
    pairId: null,  
    $palletCell: null,
    $countCell: null,
    palletText: '',
    palletType: null
  });
  
  let selection = RESET_SELECTION();
  let modalMode = 'edit'; // or 'add'

  // Cache for max pairs from API (used when re-rendering one row)
  let maxPairsCache = 10;

  // ===== Sticky scrolling helpers =====
  function ensureScrollable() {
    const scroller = document.querySelector('.table-scroll-both');
    const table = document.getElementById('line-table');
    if (!scroller || !table) return;
    scroller.style.overflow = 'auto';
    table.style.width = 'max-content';
    table.style.whiteSpace = 'nowrap';
  }

  // ===== Header builder (2-row header) =====
  function rebuildHeader(maxPairs) {
    const row1 = document.createElement('tr');
    const row2 = document.createElement('tr');

    const thLeft = document.createElement('th');
    thLeft.scope = 'col';
    thLeft.rowSpan = 2;
    thLeft.className = 'text-center align-middle sticky-left bg-light';
    thLeft.style.minWidth = '120px';
    thLeft.textContent = 'ライン名';
    row1.appendChild(thLeft);

    for (let i = 0; i < maxPairs; i++) {
      const gth = document.createElement('th');
      gth.colSpan = 10;
      gth.className = 'text-center';
      gth.textContent = (i === 0) ? '現在生産中' : String(i);
      
      if (i === 0) {
        gth.innerHTML = `<span class="inline-pointer">👉</span>現在生産中`;
        gth.classList.add('current-header');  // ✅ ONLY HERE
      } else {
        gth.textContent = String(i);
      }

      row1.appendChild(gth);

      const thP = document.createElement('th');
      thP.colSpan = 6;
      thP.className = 'text-center';
      thP.textContent = (i === 0) ? '供給パレット' : '次供給パレット';
      
      row2.appendChild(thP);

      const thC = document.createElement('th');
      thC.colSpan = 4;
      thC.className = 'text-center';
      thC.textContent = '供給数';
      row2.appendChild(thC);
    }

    $thead.empty().append(row1, row2);
    ensureScrollable();
  }

  // ===== Render one line row =====
  function renderLineRow(line, maxPairs) {
    const tr = document.createElement('tr');
    
    tr.dataset.lineId = line.line_id;
  
    const th = document.createElement('th');  
    th.scope = 'row';
    th.className = 'text-center fw-semibold sticky-left bg-white';
    th.textContent = line.line_name || '-';
    tr.appendChild(th);
  
    // const pairs = Array.isArray(line.pairs) ? line.pairs : [];
    let pairs = Array.isArray(line.pairs) ? line.pairs : [];

    // ✅ UI fallback only (DO NOT insert in DB)
    if (pairs.length === 0) {
      pairs = [{
        pair_id: null,
        pallet_type: null,
        pallet_name: "",   // or "未設定"
        count: ""
      }];
    }

    const n = Math.min(pairs.length, maxPairs);
  
    for (let i = 0; i < n; i++) {
      const p = pairs[i] || {};

      const tdP = document.createElement('td');
      tdP.colSpan = 6;
      tdP.className = 'text-center';
      tdP.textContent = p.pallet_name ?? '';
      
      const tdC = document.createElement('td');
      tdC.colSpan = 4;
      tdC.className = 'text-center';
      tdC.textContent = Number.isFinite(Number(p.count)) ? String(p.count) : '';
      

      if (p.pair_id != null) {
        tdP.dataset.pairId = String(p.pair_id);
      }

      // >>> NEW: keep current type for preselecting in Edit
      if (p.pallet_type !== undefined && p.pallet_type !== null) {
        tdP.setAttribute('data-pallet-type', String(p.pallet_type));
      }
      
      tr.appendChild(tdP);
      tr.appendChild(tdC);
    }
    // (rest unchanged)
    for (let i = n; i < maxPairs; i++) {
      const tdP = document.createElement('td');
      tdP.colSpan = 6; tdP.className = 'text-center';
      const tdC = document.createElement('td');
      tdC.colSpan = 4; tdC.className = 'text-center';
      tr.appendChild(tdP);
      tr.appendChild(tdC);
    }
    return tr;
  }

  function replaceRowWithFreshLine($oldRow, lineDto) {
    const $newRow = $(renderLineRow(lineDto, maxPairsCache || 10));
  
    $oldRow.replaceWith($newRow);
  
    // ✅ Avoid stale selection
    selection = RESET_SELECTION();
    ensureScrollable();
  
    return $newRow;
  }

  // ===== Render full table =====
  async function loadAndRender() {
    try {
      const { lines, max_pairs } = await apiList();

      maxPairsCache = Math.max(1, Number(max_pairs) || 10);
      rebuildHeader(maxPairsCache);

      $tbody.empty();
      const frag = document.createDocumentFragment();
      lines.forEach(line => frag.appendChild(renderLineRow(line, maxPairsCache)));
      $tbody.get(0).appendChild(frag);
      ensureScrollable();
      autoDetectZeroCountAndStartCountdown();
      restoreSelectionHighlight();   // ✅ ADD
    } catch (err) {
      console.error('[pallet-supply] list failed:', err);
      $tbody.html('<tr><td colspan="2" class="text-center text-muted">データ取得に失敗しました</td></tr>');
    }
  }

  async function loadAndRenderSafe() {
    if (isPolling || isCountdownActive) return;
    isPolling = true;
    try {
      await loadAndRender();
    } catch (e) {
      console.warn('[pallet-supply] polling failed:', e);
    } finally {
      isPolling = false;
    }
  }

  function restoreSelectionHighlight() {
    if (
      persistedSelection.lineId == null ||
      persistedSelection.pairIndex == null
    ) return;
  
    const $row = $tbody.find(
      `tr[data-line-id="${persistedSelection.lineId}"]`
    );
    if (!$row.length) return;
  
    const cells = getPairCells($row, persistedSelection.pairIndex);
    if (!cells.$palletTd.length || !cells.$countTd.length) return;
  
    clearCellSelection();
  
    cells.$palletTd.addClass('bg-info text-white selected-cell');
    cells.$countTd.addClass('bg-info text-white selected-cell');
  
    // ✅ rebuild live selection object
    selection.$row        = $row;
    selection.$palletCell = cells.$palletTd;
    selection.$countCell  = cells.$countTd;
  }

  // ===== Utilities for selection and pair index math =====
  function clearCellSelection() {
    $tbody.find('td').removeClass('bg-info text-white selected-cell');
  }
  function getPairBaseRelIndex(cellIndexAbs) {
    const rel = cellIndexAbs - 1; // after row header th
    return rel % 2 === 0 ? rel : rel - 1;
  }
  function computePairIndexFromCell(tdEl) {
    const abs = tdEl?.cellIndex ?? 1;
    const baseRel = getPairBaseRelIndex(abs);
    return Math.floor(baseRel / 2);
  }
  function getPairCells($tr, pairIndex) {
    const $tds = $tr.children('td');
    const base = pairIndex * 2;
    return {
      $palletTd: $tds.eq(base),
      $countTd : $tds.eq(base + 1)
    };
  }

  // ===== Countdown helpers (3s) =====
  function cancelCountdown($countTd, restoreTextTo = null) {
    if (!$countTd || !$countTd.length) return;
    const timeoutId  = $countTd.data('delTimeoutId');
    const intervalId = $countTd.data('delIntervalId');
    if (intervalId) clearInterval(intervalId);
    if (timeoutId)  clearTimeout(timeoutId);

    const origText = $countTd.data('delOriginalText');
    if (restoreTextTo !== null && restoreTextTo !== undefined) {
      $countTd.text(restoreTextTo);
    } else if (origText !== undefined) {
      $countTd.text(origText);
    }

    $countTd.removeData('delTimeoutId delIntervalId delOriginalText');
    $countTd.removeClass('bg-warning');
  }

  async function startDeletionCountdown3s(lineId, pairId, $row, seconds = 3) {
    isCountdownActive = true;
  
    const $palletTd = $row.find(`td[data-pair-id="${pairId}"]`);
    if (!$palletTd.length) {
      console.error('[auto-delete] target pair not found:', pairId);
      isCountdownActive = false;
      return;
    }
  
    const $countTd = $palletTd.next('td');
    cancelCountdown($countTd);
  
    let remaining = seconds;
    const originalText = $countTd.text();
  
    $countTd
      .data('delOriginalText', originalText)
      .addClass('bg-warning')
      .text(`削除まで ${remaining}秒`);
  
    const intervalId = setInterval(() => {
      remaining -= 1;
      if (remaining > 0) {
        $countTd.text(`削除まで ${remaining}秒`);
      }
    }, 1000);
  
    const timeoutId = setTimeout(async () => {
      clearInterval(intervalId);
      try {
        const updatedLine = await apiDelete(lineId, pairId);
        replaceRowWithFreshLine($row, updatedLine);
      } catch (err) {
        // ✅ STALE_WRITE = already deleted → safe to ignore
        if (err?.code === 'STALE_WRITE') {
          console.warn('[auto-delete] already deleted by another process:', pairId);
      
          // Just refresh the row to sync UI
          try {
            const refreshed = await apiGetLine(lineId);
            const $oldRow = $tbody.find(`tr[data-line-id="${lineId}"]`);
            replaceRowWithFreshLine($oldRow, refreshed);
          } catch (_) {
            // ignore secondary refresh failure
          }
          return; // ✅ NOT an error
        }
      
        // ❌ Real failure
        console.error('[pallet-supply] auto-delete failed:', err);
        $countTd.text(originalText).removeClass('bg-warning');
        alert(`自動削除に失敗しました。\n${err.message || err}`);
      } finally {
        countdownPairIds.delete(pairId);
        isCountdownActive = false;
      }
    }, seconds * 1000);
  
    $countTd.data('delTimeoutId', timeoutId);
  }

  async function autoDetectZeroCountAndStartCountdown() {
    if (isCountdownActive) return; // do not race
  
    $tbody.find('tr').each(async function () {
      const $row = $(this);
      const lineId = Number($row.data('lineId'));
      if (!Number.isFinite(lineId)) return;
  
      // Find all pallet cells in this row
      $row.find('td[data-pair-id]').each(async function () {
        const $palletTd = $(this);
        const pairId = Number($palletTd.data('pairId'));
        if (!Number.isFinite(pairId)) return;
  
        // Prevent duplicate countdowns
        if (countdownPairIds.has(pairId)) return;
  
        const $countTd = $palletTd.next('td');
        const countVal = Number(($countTd.text() || '').trim());
  
        if (countVal !== 0) return;
  
        // ✅ Mark countdown as started
        countdownPairIds.add(pairId);
  
        try {
          // ✅ Move THIS pair to group 0
          const pairIndex = computePairIndexFromCell($palletTd.get(0));
          
          // 1. Move to group 0
          const movedLine = await apiMoveToGroup0(lineId, pairIndex);

          // 2. Replace the row with backend response
          const $oldRow = $tbody.find(`tr[data-line-id="${lineId}"]`);
          replaceRowWithFreshLine($oldRow, movedLine);

          // 3. Re-find the fresh DOM row
          const $updatedRow = $tbody.find(`tr[data-line-id="${lineId}"]`);

          // 4. Start countdown on correct pallet
          await startDeletionCountdown3s(
            lineId,
            pairId,
            $updatedRow,
            3
          );
  
        } catch (err) {
          console.error('[auto-detect-0] failed:', err);
          countdownPairIds.delete(pairId); // allow retry
        }
      });
    });
  }

  async function apiApplyPattern(patternNo) {
    const res = await fetch(
      `${API_BASE}/pattern/${Number(patternNo)}/apply`,
      {
        method: 'POST',
        headers: { 'Accept': 'application/json' }
      }
    );
    const js = await parseApi(res);
  
    const data = js.data;
    if (!data || !Array.isArray(data.lines)) {
      throw new Error('Invalid payload: data.lines must be an array');
    }
    return data.lines;
  }

  function rebuildTableFromLines(lines) {
    $tbody.empty();
    const frag = document.createDocumentFragment();
    lines.forEach(line => {
      frag.appendChild(renderLineRow(line, maxPairsCache || 10));
    });
    $tbody.get(0).appendChild(frag);
    ensureScrollable();
  
    // Clear selection to avoid inconsistent state
    selection = RESET_SELECTION();

    autoDetectZeroCountAndStartCountdown();
    restoreSelectionHighlight();   // ✅ ADD
  }

  let persistedSelection = {
    lineId: null,
    pairIndex: null
  };

  // ===== Click selection on any TD in tbody (skip first column) =====
  $tbody.on('click', 'td', function () {
    const $td = $(this);
    const $tr = $td.closest('tr');
    const abs = this.cellIndex;
    if (abs <= 0) return; // ignore sticky line-name column
  
    clearCellSelection();
  
    const baseRel = getPairBaseRelIndex(abs);
    const $cells = $tr.children('td');
    const $palletCell = $cells.eq(baseRel);
    const $countCell  = $cells.eq(baseRel + 1);
  
    $palletCell.addClass('bg-info text-white selected-cell');
    $countCell.addClass('bg-info text-white selected-cell');
  
    // Parse the visible count in the selected row/cell
    const parsedCount = Number(($countCell.text() || '').trim());
    const countValue = Number.isFinite(parsedCount) ? parsedCount : 0;
  
    selection = {
      $row      : $tr,
      lineId: Number($tr.data('lineId')),
      lineName  : ($tr.children('th').first().text() || '').trim(),
      pairIndex : Math.floor(baseRel / 2),
      
      pairId    : (() => {
        const id = $palletCell.data('pairId');
        const n  = Number(id);
        return Number.isFinite(n) ? n : null;
      })(),

      $palletCell,
      $countCell,
      palletText: ($palletCell.text() || '').trim(),
      palletType: (() => {
        const t = $palletCell.attr('data-pallet-type');
        const n = Number(t);
        return Number.isFinite(n) ? n : null;
      })(),
      countValue // <-- NEW
    };
    
    // ✅ persist stable identifiers
    persistedSelection.lineId = selection.lineId;
    persistedSelection.pairIndex = selection.pairIndex;

  });

  // ===== Clear selection when clicking outside selectable cells =====
  $(document).on('mousedown', function (e) {
    const $target = $(e.target);

    // If clicking on a selected pallet/count cell → keep selection
    if ($target.closest('#line-state-body td').length) return;

    // If clicking inside modals or buttons → keep selection
    if ($target.closest('.modal, button').length) return;

    clearCellSelection();
    selection = RESET_SELECTION();
    // auto-reselect after update so comment out
    // persistedSelection.lineId = null;
    // persistedSelection.pairIndex = null;
  });


  // ===== 読出 =====
  $btnRead.on('click', function () {
    selectedPattern = null;
    $('.read-pattern').removeClass('active');
    readModal?.show();
  });
  

  // ===== 変更 =====
  $btnEdit.on('click', async function () {
    if (!selection.$row) {
       alert('編集するセルを選択してください。'); 
      return; 
    }

    if (selection.pairIndex === 0) {
      const locked = await isLineLocked(selection.lineName);
      if (locked) {
        showModalLockedState('編集');
        return;
      }
    }

    try {
      const names = await loadNamesForLine(selection.lineName);
      // Preselect the current type in the list
      populateModalList($palletList, names, selection.palletType);
    } catch (err) {
      console.error('[pallet-supply] names(load) failed:', err);
      alert(`選択候補の取得に失敗しました。\n${err.message || err}`);
      return;
    }
    $('#editAddModalLabel').text(`編集 — ${selection.lineName}（${selection.palletText || ''}）`);
    // Use actual current value (not hardcoded 10)
    $supplyInput.val(String(
      Number.isFinite(selection.countValue) && selection.countValue > 0
        ? selection.countValue
        : 1
    ));
    
// ✅ RESTORE button (IMPORTANT)
$('#modalSaveBtn')
.prop('disabled', false)
.text('実行');


    modalMode = 'edit';
    editAddModal?.show();
  });

  // ===== 追加 =====
  $btnAdd.on('click', async function () {
    if (!selection.$row) { 
      alert('「追加」する位置のセルを選択してください。'); 
      return; 
    }
    
  if (selection.pairIndex === 0) {
    const locked = await isLineLocked(selection.lineName);
    if (locked) {
      showModalLockedState('追加');
      return;
    }
  }
  
    try {
      const names = await loadNamesForLine(selection.lineName);
      // For Add: no preselect in the list
      populateModalList($palletList, names, null);
    } catch (err) {
      console.error('[pallet-supply] names(load) failed:', err);
      alert(`選択候補の取得に失敗しました。\n${err.message || err}`);
      return;
    }
    $('#editAddModalLabel').text(`追加 — ${selection.lineName}（${selection.palletText || ''}）`);
    // Use actual current value in the clicked column as a friendly default
    $supplyInput.val(String(
      Number.isFinite(selection.countValue) && selection.countValue > 0
        ? selection.countValue
        : 1
    ));
    
// ✅ RESTORE button (IMPORTANT)
$('#modalSaveBtn')
.prop('disabled', false)
.text('実行');

    modalMode = 'add';
    editAddModal?.show();
  });

  // Pallet select in modal
  $palletList.on('click', '.list-group-item', function () {
    $palletList.find('.list-group-item').removeClass('active');
    $(this).addClass('active');
  });

  // Keypad
  $(document).on('click', '.keypad', function () {
    const txt = $(this).text().trim();
    if (txt === 'C') { $supplyInput.val(''); return; }
    $supplyInput.val(($supplyInput.val() || '') + txt);
  });

  // ===== 実行（Save） with zero→leftmost→3s→delete flow =====
  $modalSaveBtn.on('click', async function () {
    if (!selection.$row) {
      safeHideModal(editAddModal, editAddModalEl);
      return;
    }
  
    // ---- pallet type ----
    let chosenType = NaN;
    const $active = $palletList.find('.list-group-item.active');
    if ($active.length) {
      chosenType = Number($active.data('type'));
    }
    if (!Number.isFinite(chosenType) && modalMode === 'edit') {
      chosenType = Number(selection.palletType);
    }
    if (!Number.isFinite(chosenType)) {
      alert('パレットを選択してください。');
      return;
    }
  
    // ---- count ----
    let v = String($supplyInput.val() || '').trim();
    if (!/^\d+$/.test(v)) v = '0';
  
    const lineName = selection.lineName;
    const lineId = selection.lineId;

    try {
      let updatedLine;
  
      if (modalMode === 'edit') {
        updatedLine = await apiUpdate(
          lineId,
          selection.pairId,
          chosenType,
          Number(v)
        );
      } else {
        const beforeIndex =
          selection.pairIndex >= 0 ? selection.pairIndex : null;
  
        updatedLine = await apiAdd(
          lineId,
          beforeIndex,
          chosenType,
          Number(v)
        );
      }
  
      // ✅ Capture BEFORE row replacement
      const targetPairId = selection.pairId;
      const targetPairIndex = selection.pairIndex;

      let $newRow = replaceRowWithFreshLine(selection.$row, updatedLine);

      if (v === '0') {
        // 1. Move the SAME pair to group 0
        const movedLine = await apiMoveToGroup0(
          lineId,
          targetPairIndex
        );

        replaceRowWithFreshLine($newRow, movedLine);

        // 2. Re-find updated row
        const $movedRow = $tbody.find(`tr[data-line-id="${lineId}"]`);

        // 3. Countdown delete EXACT pair
        await startDeletionCountdown3s(
          lineId,
          targetPairId, // ✅ preserved correctly
          $movedRow,
          3
        );
      }
  
      safeHideModal(editAddModal, editAddModalEl);
  
    } catch (err) {
      console.error('[pallet-supply] save failed:', err);
      alert(`実行に失敗しました。\n${err.message || err}`);
    }
  });
  

  // ===== 削除 =====
  $btnDelete.on('click', async function () {
    if (!selection.$row) {
      alert('削除するセルを選択してください。');
      return;
    }
  
    let locked = false;
  
    // ✅ ✅ ONLY CHECK LOCK for group 0
    if (selection.pairIndex === 0) {
      locked = await isLineLocked(selection.lineName);
    }
  
    if (locked) {
  
      // $deleteExecBtn
      //   .prop('disabled', true)
      //   .text('作業中');
  
      // $('#deleteConfirmModal .modal-body').html(`
      //   <div class="text-danger text-center fw-bold py-3">
      //     ⚠ 現在生産中のため削除できません
      //   </div>
      // `);

      
    $('#deleteConfirmModal .modal-body').html(`
      <div class="text-danger text-center fw-bold py-3">
        ⚠ ${selection.lineName} はリフト画面で「完了」状態のため操作できません
      </div>
    `);

    $deleteExecBtn
      .prop('disabled', true)
      .text('操作不可');

  
    } else {
  
      $deleteExecBtn
        .prop('disabled', false)
        .text('実行');
  
      $('#deleteConfirmModal .modal-body').html(`
        <div class="text-center">
          ${selection.lineName} のデータを削除しますか？
        </div>
      `);
    }
  
    // clearCellSelection();
    // deleteModal?.show();
    
    deleteModal?.show();
    setTimeout(() => {
      clearCellSelection();
    }, 0);

  });

  $deleteExecBtn.on('click', async function () {

    if (!selection.$row) { 
      safeHideModal(deleteModal, deleteModalEl);
      return; 
    }
    
    let locked = false;
    // ✅ ONLY check for group 0
    if (selection.pairIndex === 0) {
      locked = await isLineLocked(selection.lineName);
    }

    if (locked) {
      // alert('現在生産中のため削除できません');
      alert('リフト画面で「完了」状態のため削除できません');

      return;
    }


    const lineId = selection.lineId;

    try {
      
      // if (selection.pairId == null) {
      //   alert('pair_id が取得できません');
      //   return;
      // }

      const updatedLine = await apiDelete(lineId, selection.pairId);

      replaceRowWithFreshLine(selection.$row, updatedLine);

      // ✅ HARD RESET selection to avoid reuse
      selection = RESET_SELECTION();
      persistedSelection.lineId = null;
      persistedSelection.pairIndex = null;
      clearCellSelection();

      safeHideModal(deleteModal, deleteModalEl); // ✅ focus-safe close
    } catch (err) {
      console.error('[pallet-supply] delete failed:', err);
      alert(`削除に失敗しました。\n${err.message || err}`);
    }
  });

  // ===== 読出 =====
  $(document).on('click', '.read-pattern', function () {
    const patternNo = Number($(this).data('pattern'));
  
    // Store selected pattern
    selectedPattern = patternNo;
  
    // UI highlight
    $('.read-pattern').removeClass('active');
    $(this).addClass('active');
  
    console.log('[READ] Pattern selected:', selectedPattern);
  });

  $('#btn-apply-pattern').on('click', async function () {
    if (!Number.isFinite(selectedPattern)) {
      alert('パターンを選択してください。');
      return;
    }
  
    console.log('[READ] Applying pattern:', selectedPattern);
  
    // Stop polling to prevent race condition
    if (pollTimerId) {
      clearInterval(pollTimerId);
      pollTimerId = null;
    }
  
    try {
      const lines = await apiApplyPattern(selectedPattern);
  
      // Rebuild table using backend result
      rebuildTableFromLines(lines);
  
      // Close modal
      safeHideModal(readModal, readModalEl);
  
    } catch (err) {
      console.error('[pallet-supply] apply pattern failed:', err);
      alert(`パターン適用に失敗しました。\n${err.message || err}`);
  
    } finally {
      // Resume polling
      pollTimerId = setInterval(loadAndRenderSafe, POLL_INTERVAL_MS);
    }
  });

  // function showModalLockedState(actionName) {

  //   // ✅ Change title
  //   $('#editAddModalLabel').text(`${actionName}不可`);
  
  //   // ✅ Clear list and show warning
  //   $palletList.empty().append(
  //     `<div class="text-danger text-center fw-bold py-4">
  //       現在リフト作業中のため操作できません
  //     </div>`
  //   );
  
  //   // ✅ clear input
  //   $supplyInput.val('');
  
  //   // ✅ DISABLE execute button
  //   $('#modalSaveBtn')
  //     .prop('disabled', true)
  //     .text('作業中');
  
  //   // ✅ KEEP cancel button enabled
  //   editAddModal?.show();
  // }

  function showModalLockedState(actionName) {

    $('#editAddModalLabel').text(`${actionName}不可`);
  
    $palletList.empty().append(
      `<div class="text-danger text-center fw-bold py-4">
        ⚠ ${selection.lineName} はリフト画面で「完了」状態のため操作できません
      </div>`
    );
  
    $supplyInput.val('');
  
    $('#modalSaveBtn')
      .prop('disabled', true)
      .text('操作不可');
  
    editAddModal?.show();
  }

  // ===== Init =====
  $(function () {
    loadAndRender(); // initial GET
    
    // start auto refresh
    pollTimerId = setInterval(loadAndRenderSafe, POLL_INTERVAL_MS);

    });

})(jQuery);


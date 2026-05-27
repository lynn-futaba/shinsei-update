/* ======================================================================
   admin.js — Ordered to mirror HTML structure for easy cross-reading
   Layout mapping to HTML:
   - Header: Clock (#current-time)
   - Left column:
       A) Map (#map) + map → inputs (INDV only)
       B) Error list (エラー表示) (#error-table-body)
   - Right column:
       1) Controls (RMS Lamp #tab-rms, Mode gauge #lever-mode / radios, Run btn #tab-ab)
       2) 各個操作 (accordion #opsAccordion + buttons)
       3) ライン状態表示 (#line-state-body, click-to-toggle)
       4) リフト間口表示 (#lift-state-body)
       5) ステータス表示 (#task-status-body)
   - DOM Ready: wires in the above order
====================================================================== */
'use strict';

/* ======================================================================
   0) Config & Diagnostics
====================================================================== */
const API = {
  base: '/manage/api/v1',
  path(p) { return `${this.base}${p}`; }
};
console.info('[admin.js] Loaded. API base =', API.base);

/* Expose helpers for DevTools debugging */
window.API = API;

/* ======================================================================
   1) Core Helpers (apiFetch, showConfirm, time)
====================================================================== */
/**
 * Envelope-aware fetch:
 *   - Accepts JSON; returns only `data` on success.
 *   - Parses JSON even for non-2xx responses if possible.
 *   - Throws Error with best-possible message on failures.
 */
async function apiFetch(url, options = {}) {

  // const res = await fetch(url, {
  //   headers: { 'Accept': 'application/json', ...(options.headers || {}) },
  //   ...options
  // });

  let res;
  try {
    res = await fetch(url, {
      headers: { 'Accept': 'application/json', ...(options.headers || {}) },
      ...options
    });
  } catch (err) {
    console.error("Network error:", err);
    throw new Error("API接続エラー（サーバーに接続できません）");
  }


  let json = null;
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) {
    json = await res.json().catch(() => null);
  } else {
    // Try anyway; could still be JSON from proxies
    json = await res.json().catch(() => null);
  }

  if (!res.ok) {
    const msg = json?.message || res.statusText || `HTTP ${res.status}`;
    const code = json?.error?.code || '';
    const details = json?.error?.details;
    const suffix = details ? ` - ${typeof details === 'string' ? details : JSON.stringify(details)}` : '';
    throw new Error(code ? `[${code}] ${msg}${suffix}` : `${msg}${suffix}`);
  }

  // Envelope validation
  const s = Number(json?.status ?? res.status);
  if (!Number.isFinite(s) || s < 200 || s >= 300) {
    const code = json?.error?.code || 'ERROR';
    const msg = json?.message || 'Unexpected API response';
    const details = json?.error?.details;
    const suffix = details ? ` - ${typeof details === 'string' ? details : JSON.stringify(details)}` : '';
    throw new Error(`[${code}] ${msg}${suffix}`);
  }

  return json?.data;
}
window.apiFetch = apiFetch; // for console usage

/**
 * Bootstrap Confirm Modal
 */
function showConfirm(message /* string */) {
  return new Promise((resolve) => {
    let modalEl = document.getElementById('confirmModal');
    if (!modalEl) {
      modalEl = document.createElement('div');
      modalEl.className = 'modal fade';
      modalEl.id = 'confirmModal';
      modalEl.tabIndex = -1;
      modalEl.setAttribute('aria-hidden', 'true');
      modalEl.innerHTML = `
        <div class="modal-dialog modal-lg modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title fs-1">確認</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="閉じる"></button>
            </div>
            <div class="modal-body">
              <p class="fs-1 mb-4"></p>
              <div class="d-flex justify-content-end" style="gap:.5rem;">
                <button type="button" class="btn btn-danger btn-lg fs-1 btn-ok">実行</button>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
                <button type="button" class="btn btn-secondary btn-lg fs-1 btn-cancel">キャンセル</button>
              </div>
            </div>
          </div>
        </div>
      `;
      document.body.appendChild(modalEl);
    }

    const p = modalEl.querySelector('.modal-body p');
    if (p) p.textContent = message ?? 'よろしいですか？';

    const bs = new bootstrap.Modal(modalEl, { backdrop: true, keyboard: false, focus: true });
    const okBtn = modalEl.querySelector('.btn-ok');
    const cancelBtn = modalEl.querySelector('.btn-cancel');

    let resolved = false;

    const onOk = () => { if (resolved) return; resolved = true; bs.hide(); cleanup(); resolve(true); };
    const onCancel = () => { if (resolved) return; resolved = true; bs.hide(); cleanup(); resolve(false); };
    const onHidden = () => { if (!resolved) { resolved = true; cleanup(); resolve(false); } };
    const cleanup = () => {
      modalEl.removeEventListener('hidden.bs.modal', onHidden);
      okBtn?.removeEventListener('click', onOk);
      cancelBtn?.removeEventListener('click', onCancel);
    };

    modalEl.addEventListener('hidden.bs.modal', onHidden, { once: true });
    okBtn?.addEventListener('click', onOk);
    cancelBtn?.addEventListener('click', onCancel);

    bs.show();
  });
}

/** Time util: updates #current-time once per second (Header) */
function getCurrentTime() {
  const now = new Date();
  const formatted = now.toLocaleString("ja-JP", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
  const timeEl = document.getElementById("current-time");
  if (timeEl) timeEl.textContent = `現在時刻: ${formatted}`;
}

/* ======================================================================
   2) LEFT COLUMN: Map (#map) → inputs (INDV only)
====================================================================== */
/**
 * Map selection → fill inputs (INDV mode only) [HTML: 左カラム 地図]
 * - Listens to:
 *   - map:selected (preferred, {kind, id, ...})
 *   - map:cellSelected, map:amrSelected, map:shelfSelected (compat)
 */
function wireMapSelectionToInputs() {
  const mapRoot = document.getElementById('map');
  if (!mapRoot) return;

  const isIndv = () => document.getElementById('mode-indv')?.checked === true;

  function expandAccordion() {
    const collapse = document.getElementById('opsCollapse');
    if (collapse && !collapse.classList.contains('show')) {
      const c = new bootstrap.Collapse(collapse, { toggle: false });
      c.show();
    }
  }

  function fill(id, value) {
    const el = document.getElementById(id);
    if (!el || value == null || String(value).trim() === '') return;
    el.value = String(value).trim();
    expandAccordion();
    try { el.focus({ preventScroll: false }); } catch {}
  }

  // Generic combined event
  mapRoot.addEventListener('map:selected', (e) => {
    if (!isIndv()) return;
    const d = e.detail || {};
    switch (d.kind) {
      case 'cell':
        fill('cellNumber',   d.code || d.cellCode || d.id);
        break;
      case 'amr':
        fill('amrNumber',    d.id   || d.robotId   || d.code);
        break;
      case 'shelf':
      case 'kotatsu':
        fill('kotatsuNumber', d.shelfCode || d.id || d.code);
        break;
    }
  });

  // Kind-specific back-compat events
  mapRoot.addEventListener('map:cellSelected',   (e) => { if (!isIndv()) return; const d = e.detail || {}; fill('cellNumber',    d.code || d.cellCode || d.id); });
  mapRoot.addEventListener('map:amrSelected',    (e) => { if (!isIndv()) return; const d = e.detail || {}; fill('amrNumber',     d.id   || d.robotId   || d.code); });
  mapRoot.addEventListener('map:shelfSelected',  (e) => { if (!isIndv()) return; const d = e.detail || {}; fill('kotatsuNumber', d.shelfCode || d.id || d.code); });

  console.debug('[wire] wireMapSelectionToInputs');
}

/**
 * jQuery-based compat: wire map:select → inputs (INDV only)
 */
function wireMapAutoFill() {
  $(document).on('map:select', function(e, data) {
    const isIndv = document.getElementById('mode-indv')?.checked;
    if (!isIndv) return;

    console.log(`[AutoFill] Selected ${data.type}: ${data.id}`);

    switch(data.type) {
      case 'amr':   $('#amrNumber').val(data.id).addClass('is-valid');   setTimeout(() => $('#amrNumber').removeClass('is-valid'), 1000); break;
      case 'shelf': $('#kotatsuNumber').val(data.id).addClass('is-valid'); setTimeout(() => $('#kotatsuNumber').removeClass('is-valid'), 1000); break;
      case 'cell':  $('#cellNumber').val(data.id).addClass('is-valid');  setTimeout(() => $('#cellNumber').removeClass('is-valid'), 1000); break;
    }
  });

  // Also fill optional form names if present
  $(document).on('map:select', function(e, selection) {
    if (selection.type === 'shelf') {
      $('input[name="shelfCode"]').val(selection.id);
    } else if (selection.type === 'amr') {
      $('input[name="robotId"]').val(selection.id);
    } else if (selection.type === 'cell') {
      $('input[name="cellCode"], input[name="location"]').val(selection.id);
    }
  });
}

/* ======================================================================
   3) LEFT COLUMN: エラー表示 (Error list) [HTML: #error-table-body]
====================================================================== */
function loadAndRenderErrors() {
  console.debug('[wire] loadAndRenderErrors');
  const tbody = document.getElementById('error-table-body');
  const refreshBtn = document.getElementById('error-refresh-btn');
  if (!tbody) return;

  function levelToBadge(level, isCompleted) {
    if (isCompleted) return 'bg-light text-muted border';
    const v = String(level || '').toUpperCase();
    if (v === 'ERROR') return 'bg-danger';
    if (v === 'WARN' || v === 'WARNING') return 'bg-warning text-dark';
    if (v === 'INFO') return 'bg-info text-dark';
    return 'bg-secondary';
  }

  function buildRow(item) {
    const isDone = item.is_completed === true || item.is_completed === 1 || item.is_completed === "true";
    const tr = document.createElement('tr');
    if (isDone) { tr.style.opacity = '0.6'; tr.classList.add('table-light'); }

    // datasets for modal
    tr.dataset.errorNum = item.error_num || '';
    tr.dataset.errorCode  = item.error_code || ''; 
    tr.dataset.errorLevel = item.error_level || 'High';
    tr.dataset.errorCategory = item.source || 'RMS→';
    tr.dataset.errorSummary = item.error_summary || '';
    tr.dataset.errorOperation = item.error_operation || '';
    tr.dataset.errorDescription = item.error_description || '';


    // 1) 詳細ボタン
    const tdNo = document.createElement('td');
    const btn = document.createElement('button');
    btn.className = "btn btn-lg btn-outline-secondary";
    btn.textContent = "詳細";
    btn.onclick = (e) => { e.stopPropagation(); openDetailFromRow(tr); };
    tdNo.appendChild(btn);

    // 2) エラーコード（クリック可）
    const tdCode = document.createElement('td');
    tdCode.className = "cursor-pointer text-primary";

    // tdCode.innerHTML = `<code>${item.error_code || item.error_num}</code>`;
    // const codeValue =
    //   item.source === 'RMS'
    //     ? item.error_num
    //     : item.error_code;
    
    const codeValue = item.error_code || '-';
    tdCode.innerHTML = `<code>${codeValue ?? '-'}</code>`;

    // 3) バッジ + サマリ
    const tdContent = document.createElement('td');

    const sourceSpan = document.createElement('span');
    sourceSpan.className = `badge ${item.source === 'RMS' ? 'bg-dark' : 'bg-primary'} me-2`;
    sourceSpan.textContent = item.source;
    
    const summarySpan = document.createElement('span');
    summarySpan.className = `badge ${levelToBadge(item.error_level, isDone)}`;
    summarySpan.textContent = item.error_summary || '-';
    
    tdContent.appendChild(sourceSpan);
    tdContent.appendChild(summarySpan);

    // 4) 時刻
    const tdTime = document.createElement('td');
    tdTime.className = 'small font-monospace';
    tdTime.textContent = item.error_datetime || '-';

    tr.appendChild(tdNo);
    tr.appendChild(tdCode);
    tr.appendChild(tdContent);
    tr.appendChild(tdTime);
    return tr;
  }

  async function fetchErrors() {
    try {
      const response = await apiFetch(API.path('/get_error_list'), { method: 'GET' });
      console.log("Response received:", response);
      const payload = response?.data ? response.data : response;
      if (!payload?.athena && !payload?.local) {
        console.warn("Payload does not contain expected keys:", payload);
        return [];
      }
      const local = (payload.local || []).map(i => ({ ...i, source: 'WCS' }));
      const athena = (payload.athena || []).map(i => ({ ...i, source: 'RMS' }));
      return [...local, ...athena];
    } catch (e) {
      console.error("Fetch failed", e);
      throw e;
    }
  }

  async function render() {
    try {
      tbody.innerHTML = '<tr><td colspan="4" class="text-center">読み込み中...</td></tr>';
      const items = await fetchErrors();
      // items.sort((a, b) => (b.error_datetime || '').localeCompare(a.error_datetime || ''));
      items.sort((a, b) => {
        // WCS first, then RMS
        if (a.source !== b.source) {
          return a.source === 'WCS' ? -1 : 1;
        }
      
        // Newest first inside same source
        return (b.error_datetime || '').localeCompare(a.error_datetime || '');
      });
      tbody.innerHTML = '';
      if (items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">現在、表示できるエラーはありません</td></tr>';
        return;
      }
      const frag = document.createDocumentFragment();
      items.forEach(it => frag.appendChild(buildRow(it)));
      tbody.appendChild(frag);
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="4" class="text-center text-danger">取得エラー: ${err.message}</td></tr>`;
    }
  }

  // Modal wiring scoped here
  (function () {
    const modalEl = document.getElementById('errorDetailModal');
    if (!modalEl) return;
    const modal = new bootstrap.Modal(modalEl, { backdrop: true, keyboard: true });

    (function tuneErrorDetailFooter() {
      const footer = modalEl.querySelector('.modal-footer');
      if (footer) {
        footer.classList.remove('justify-content-start');
        footer.classList.add('justify-content-end');
        footer.style.gap = '.5rem';
      }
      modalEl.querySelectorAll('.modal-footer .btn, .modal-body .btn').forEach(btn => {
        btn.classList.add('btn-lg');
      });
    })();

    function setText(id, value) {
      const el = document.getElementById(id);
      if (el) el.textContent = value ?? '-';
    }

    function openDetailFromRow(row) {

      console.log("Row in Error Dialog >>>", row)
      
      const codeDisplay = (row.cells[1]?.textContent || '').trim();
      const errorCode = row.dataset.errorCode || '—';

      const content = (row.cells[2]?.innerText || '').trim();
      const time = (row.cells[3]?.textContent || '').trim();
      console.log("Dataset in Error Dialog >>>", row.dataset);

      const no = row.dataset.errorNum || '—';
      const level = row.dataset.errorLevel || '—';
      const type = row.dataset.errorCategory || '—';
      const detail = row.dataset.errorDescription || content || '—';
      const summary = row.dataset.errorSummary || '—';
      const operation = row.dataset.errorOperation || '—';

      setText('err-no', no);
      // ✅ Show both error_num + error_code (clean format)
      const combinedCode = errorCode && errorCode !== '—'
      ? `${errorCode}`
      : codeDisplay;

      setText('err-code', combinedCode);

      setText('err-level', level);
      setText('err-type', type);
      setText('err-content', summary);
      setText('err-detail', detail);
      setText('err-action', operation);
      setText('err-time', time || '—');

      modal.show();
    }
    
    // ✅ ADD THIS LINE (GLOBAL EXPORT)
    window.openDetailFromRow = openDetailFromRow;

    tbody?.addEventListener('click', (e) => {
      const cell = e.target.closest('td');
      const row = e.target.closest('tr');
      if (!cell || !row) return;
      if (cell.cellIndex !== 1) return; // 2nd column only
      openDetailFromRow(row);
    });

    tbody?.addEventListener('keydown', (e) => {
      const cell = e.target.closest('td');
      const row = e.target.closest('tr');
      if (!cell || !row) return;
      if (cell.cellIndex !== 1) return;
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openDetailFromRow(row);
      }
    });

    Array.from(tbody?.rows || []).forEach(tr => {
      const codeCell = tr.cells[1];
      if (codeCell) codeCell.tabIndex = 0;
    });
    
    modalEl.addEventListener('click', async (e) => {
      const btn = e.target.closest('#err-reset-btn');
      if (!btn) return;
    
      const source = document.getElementById('err-type')?.textContent?.trim();
    
      const errorNumText = document
        .getElementById('err-no')
        ?.textContent
        ?.trim();
    
      // ✅ strong validation
      if (!source || !errorNumText || errorNumText === '—') {
        alert('エラーIDが取得できません');
        return;
      }
    
      const errorNum = Number(errorNumText);
      if (!Number.isInteger(errorNum)) {
        alert('エラーIDが不正です');
        return;
      }
    
      btn.disabled = true;
    
      try {
        await apiFetch(API.path('/error/reset'), {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            source,
            error_num: errorNum
          })
        });
      
        // btn.textContent = 'リセット';
      
        // ✅ Re-fetch & re-render list
        await loadAndRenderErrors();
      
        // ✅ Close modal
        modal.hide();
      
      } catch (err) {
        console.error(err);
        alert('リセット失敗');
      } finally {
        btn.disabled = false;
      }
    });

  })();

  // Initial load + manual refresh
  render();
  refreshBtn?.addEventListener('click', () => {
    refreshBtn.disabled = true;
    const prev = refreshBtn.textContent;
    refreshBtn.textContent = '更新中...';
    (async () => await render())().finally(() => {
      refreshBtn.disabled = false;
      refreshBtn.textContent = prev;
    });
  });
}

/* ======================================================================
   4) RIGHT COLUMN (1/5): Controls
     - Mode gauge (自動/各個)
     - Run button (自動 3-step)
     - RMS Lamp (orange/red)
     - RMS polling control: stop in 各個, start in 自動
====================================================================== */
/* ----- Utilities for Mode/Run button ----- */
const AUTO_STATE_SEQ = [
  { key: 'ready',   label: '起動準備', add: ['btn-warning'],                      remove: ['btn-secondary','btn-success','btn-light'], inlineBg: null,                textClass: 'text-dark'  },
  { key: 'start',   label: '起動',     add: ['btn-success','text-white'],         remove: ['btn-secondary','btn-warning','btn-light'], inlineBg: null,                textClass: 'text-white' },
  { key: 'running', label: '運転中',   add: ['btn-light','text-white'],           remove: ['btn-secondary','btn-warning','btn-success'], inlineBg: 'rgb(255, 94, 0)', textClass: 'text-white' },
];

function getRunBtn() { return document.getElementById('tab-ab'); }

function stripBtnVariants(btn) {
  btn.classList.remove('btn-primary','btn-secondary','btn-success','btn-danger',
                       'btn-warning','btn-info','btn-light','btn-dark','text-white','text-dark');
  btn.style.removeProperty('background-color');
}

function setAutoStateOnRunBtn(stateIndex) {
  const btn = getRunBtn();
  if (!btn) return;
  const idx = Math.max(0, Math.min(AUTO_STATE_SEQ.length - 1, stateIndex));
  const st  = AUTO_STATE_SEQ[idx];

  btn.dataset.autoStateIndex = String(idx);
  stripBtnVariants(btn);
  st.remove?.forEach(c => btn.classList.remove(c));
  st.add?.forEach(c => btn.classList.add(c));

  if (st.inlineBg) btn.style.setProperty('background-color', st.inlineBg, 'important');
  if (st.textClass === 'text-white') btn.classList.add('text-white');
  else { btn.classList.remove('text-white'); btn.classList.add('text-dark'); }
  btn.textContent = st.label;
  btn.setAttribute('aria-checked', 'false');

  const isRunning = (st.key === 'running');
  if (isRunning) { btn.dataset.autoLocked = '1'; btn.classList.add('pe-none'); }
  else { btn.dataset.autoLocked = '0'; btn.classList.remove('pe-none'); }

}

function updateGaugeUI() {
  const autoRadio = document.getElementById('mode-auto');
  const indvRadio = document.getElementById('mode-indv');
  const autoLabel = document.querySelector('label[for="mode-auto"]');
  const indvLabel = document.querySelector('label[for="mode-indv"]');
  const gauge = document.getElementById('lever-mode');
  if (!autoLabel || !indvLabel || !gauge) return;

  const GREEN = '#198754';
  const GREY  = '#d4dfe9';

  autoLabel.classList.remove('bg-success', 'bg-secondary');
  indvLabel.classList.remove('bg-success', 'bg-secondary');

  const isIndv = (indvRadio && indvRadio.checked);
  if (isIndv) {
    indvLabel.classList.add('bg-success');
    autoLabel.classList.add('bg-secondary');
    gauge.style.setProperty('--clr-arc-grad-left', GREY);
    gauge.style.setProperty('--clr-arc-grad-right', GREEN);
  } else {
    autoLabel.classList.add('bg-success');
    indvLabel.classList.add('bg-secondary');
    gauge.style.setProperty('--clr-arc-grad-left', GREEN);
    gauge.style.setProperty('--clr-arc-grad-right', GREY);
  }
}

function preventIndvGreyToggle() {
  const btn = document.getElementById('tab-ab');
  if (!btn) return;
  btn.addEventListener('click', (e) => {
    const indv = document.getElementById('mode-indv');
    if (indv && indv.checked && btn.classList.contains('btn-secondary')) {
      e.preventDefault();
      e.stopPropagation();
    }
  }, true);
}

/* ----- RMS Lamp + Poll control (stop in 各個 mode) ----- */
let __rmsPollTimer = null;

function stopRmsPolling() {
  if (__rmsPollTimer) { clearInterval(__rmsPollTimer); __rmsPollTimer = null; console.debug('[RMS] Polling stopped'); }
}

function startRmsPolling() {
  stopRmsPolling();
  syncRMSFromAPI(); // guard will bail in 各個
  __rmsPollTimer = setInterval(syncRMSFromAPI, 5000);
  console.debug('[RMS] Polling started (5s)');
}

function setRMSState(state /* 'on' | 'off' */) {
  const rmsBtn = document.getElementById('tab-rms');
  if (!rmsBtn) return;
  const s = (state === 'on') ? 'on' : 'off';
  rmsBtn.dataset.rmsState = s;

  rmsBtn.classList.remove('btn-primary','btn-secondary','btn-success','btn-danger',
                          'btn-warning','btn-info','btn-light','btn-dark','text-white','text-dark');
  rmsBtn.classList.add('btn-lg','fw-bold','btn-fat','text-white');

  rmsBtn.style.removeProperty('background-color');
  rmsBtn.style.removeProperty('box-shadow');
  rmsBtn.style.borderRadius = '9999px';

  if (s === 'on') {
    const ORANGE = 'rgb(255, 94, 0)';
    rmsBtn.style.setProperty('background-color', ORANGE, 'important');
    rmsBtn.style.boxShadow = '0 0 0.5rem rgba(255,94,0,0.6), 0 0 1.25rem rgba(255,94,0,0.45)';
  } else {
    const RED = 'rgb(220, 53, 69)';
    rmsBtn.style.setProperty('background-color', RED, 'important');
    rmsBtn.style.boxShadow = '0 0 0.4rem rgba(220,53,69,0.45)';
  }
  rmsBtn.setAttribute('aria-checked', (s === 'on') ? 'true' : 'false');
}

async function syncRMSFromAPI() {
  // Guard: if current mode is 各個, do nothing
  const isIndv = document.getElementById('mode-indv')?.checked === true;
  if (isIndv) return;
  try {
    const data = await apiGetRmsStatus(); // { system_status, job_status }
    const sys = String(data?.system_status || '').toUpperCase();
    const job = String(data?.job_status || '').toUpperCase();
    const lampOn = (sys === 'RUNNING' && job === 'RUNNING');
    setRMSState(lampOn ? 'on' : 'off');
  } catch (err) {
    console.error('[RMS Lamp] sync failed:', err);
    setRMSState('off'); // fail-safe
  }
}

/* ----- Controls: Mode wiring & Run button wiring ----- */
function applyModeUI(mode) {

  const isIndv = (mode === 'indv');


  // 1) Accordion enable/disable
  setAccordionDisabled(!isIndv);

  // 2) Run button style/content
  const runBtn = document.getElementById('tab-ab');
  if (runBtn) {
    if (isIndv) {
      stripBtnVariants(runBtn);
      runBtn.classList.add('btn-secondary','text-white');
      runBtn.textContent = '停止';
      runBtn.style.removeProperty('background-color');
      runBtn.setAttribute('aria-checked', 'false');
    } else {
      setAutoStateOnRunBtn(0);  // 起動準備
    }
  }

  // 3) RMS polling control
  if (isIndv) stopRmsPolling();
  else startRmsPolling();
}

function wireModeToggle() {
  console.debug('[wire] wireModeToggle');
  const auto = document.getElementById('mode-auto');
  const indv = document.getElementById('mode-indv');

  async function initFromAPI() {
    try {
      const mode = await apiGetRmsMode(); // 1=auto, 0=indv
      if (mode === 1) {
        if (auto) auto.checked = true; if (indv) indv.checked = false; applyModeUI('auto');
      } else {
        if (auto) auto.checked = false; if (indv) indv.checked = true; applyModeUI('indv');
      }
      updateGaugeUI();
    } catch (err) {
      console.error('RMS mode init failed:', err);
      const fallbackIsIndv = (indv && indv.checked);
      applyModeUI(fallbackIsIndv ? 'indv' : 'auto');
      updateGaugeUI();
    }
  }

  async function onChange(targetMode /* 'auto' | 'indv' */) {
    const want = (targetMode === 'auto') ? 1 : 0;
    auto && (auto.disabled = true);
    indv && (indv.disabled = true);
    try {
      const newMode = await apiSetRmsMode(want);
      const isAuto = (newMode === 1);
      if (auto) auto.checked = isAuto;
      if (indv) indv.checked = !isAuto;
      applyModeUI(isAuto ? 'auto' : 'indv');
      updateGaugeUI();
    } catch (err) {
      console.error('Set RMS mode failed:', err);
      alert('モード切替に失敗しました。もう一度お試しください。');
      try {
        const mode = await apiGetRmsMode();
        const isAuto = (mode === 1);
        if (auto) auto.checked = isAuto;
        if (indv) indv.checked = !isAuto;
        applyModeUI(isAuto ? 'auto' : 'indv');
        updateGaugeUI();
      } catch (_) { /* ignore */ }
    } finally {
      auto && (auto.disabled = false);
      indv && (indv.disabled = false);
    }
  }

  auto?.addEventListener('change', () => { if (auto.checked) onChange('auto'); });
  indv?.addEventListener('change', () => { if (indv.checked) onChange('indv'); });

  initFromAPI();
}

let __wasAutoRunning = false;

function wireRunButtonAdvance() {

  console.debug('[wire] wireRunButtonAdvance');
  const btn = document.getElementById('tab-ab');
  if (!btn) return;

  btn.addEventListener('click', async (e) => {
    const indv = document.getElementById('mode-indv');
    if (indv && indv.checked) return;
    if (btn.dataset.autoLocked === '1') return;

    e.preventDefault();
    e.stopPropagation();

    const cur = Number(btn.dataset.autoStateIndex ?? '0');

    try {
      // 起動準備
      if (cur === 0) {
        await apiRmsAutoPrepare();
      }
      // 起動
      else if (cur === 1) {
        await apiRmsAutoStart();
      }
      // 運転中（idempotent）
      else {
        // await apiRmsAutoRun();
      }

      // ✅ After any action → refresh actual status
      await syncAutoStateFromAPI();

    } catch (err) {
      console.error('自動ステップ失敗:', err);
      alert('自動モードの実行に失敗しました。');
    }
  }, true);
}

async function syncAutoStateFromAPI() {
  /**
   * Backend response example:
   * {
   *   mode: 1,
   *   preparation_ok: 1|0,
   *   auto_running: 1|0
   * }
   */
  const data = await apiFetch(API.path('/get_rms_current_mode'), { method: 'GET' });
  const item = Array.isArray(data) ? data[0] : data;
  if (!item) return;

  const isAuto = Number(item.mode) === 1;
  if (!isAuto) {
    __wasAutoRunning = false; // reset when leaving auto mode
    return;
  }

  const isRunningNow = Number(item.auto_running) === 1;

  // ---- UI state decision (unchanged behavior) ----
  let stateIndex = 0; // 起動準備
  if (isRunningNow) {
    stateIndex = 2; // 運転中
  } else if (Number(item.preparation_ok) === 1) {
    stateIndex = 1; // 起動
  }

  setAutoStateOnRunBtn(stateIndex);

  // ---- ✅ ONE‑TIME CALL WHEN ENTERING 運転中 ----
  if (isRunningNow && !__wasAutoRunning) {
    console.debug('[AUTO] Entered 運転中 → call apiRmsAutoRun once');
    try {
      await apiRmsAutoRun();
    } catch (err) {
      console.error('[AUTO] auto_run failed:', err);
    }
  }

  __wasAutoRunning = isRunningNow;
}


function wireRmsLamp() {
  console.debug('[wire] wireRmsLamp');
  const rmsBtn = document.getElementById('tab-rms');
  if (!rmsBtn) return;

  // RMS lamp is API-driven; block manual toggles
  rmsBtn.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); }, true);

  // Initial paint; do not start polling here — applyModeUI() handles it.
  if (!rmsBtn.dataset.rmsState) setRMSState('off');
}

/* ======================================================================
   5) RIGHT COLUMN (2/5): 各個操作 (accordion) [HTML: #opsAccordion]
====================================================================== */
function setAccordionDisabled(disabled) {
  const acc = document.getElementById('opsAccordion');
  const headerBtn = document.querySelector('#opsHeader .accordion-button');
  const collapse = document.getElementById('opsCollapse');
  if (!acc) return;

  acc.classList.toggle('pe-none', disabled);
  acc.classList.toggle('opacity-50', disabled);
  acc.setAttribute('aria-disabled', String(disabled));

  acc.querySelectorAll('button, input, select, textarea, a').forEach(el => {
    if (disabled) {
      if (!el.dataset.prevDisabled) el.dataset.prevDisabled = String(el.disabled || false);
      if (!el.dataset.prevTabindex) el.dataset.prevTabindex = String(el.tabIndex || 0);
      el.disabled = true; el.tabIndex = -1; el.setAttribute('aria-disabled', 'true');
    } else {
      if (el.dataset.prevDisabled !== undefined) { el.disabled = (el.dataset.prevDisabled === 'true'); delete el.dataset.prevDisabled; } else { el.disabled = false; }
      if (el.dataset.prevTabindex !== undefined) { el.tabIndex = Number(el.dataset.prevTabindex); delete el.dataset.prevTabindex; } else { el.tabIndex = 0; }
      el.removeAttribute('aria-disabled');
    }
  });

  if (collapse && disabled) { collapse.classList.remove('show'); collapse.setAttribute('aria-expanded', 'false'); }
  if (headerBtn) {
    if (disabled) { headerBtn.classList.add('disabled'); headerBtn.setAttribute('tabindex', '-1'); headerBtn.setAttribute('aria-disabled', 'true'); }
    else { headerBtn.classList.remove('disabled'); headerBtn.removeAttribute('aria-disabled'); headerBtn.removeAttribute('tabindex'); }
  }
}

function wireManualOps() {
  console.debug('[wire] wireManualOps');

  // ✅ ADD THIS ONE LINE (GLOBAL MANUAL LOCK) TODO: 0509
  let manualInFlight = false;

  // DOM elements
  const $amr    = document.getElementById('amrNumber');
  const $shelf  = document.getElementById('kotatsuNumber');  // "shelf"
  const $cell   = document.getElementById('cellNumber');
  const $angle  = document.getElementById('rotationAngle');

  const $btnMove   = document.getElementById('btnSingleMove');    // 単体移動
  const $btnLoad   = document.getElementById('btnShelfTransport'); // 棚搬送
  const $btnFetch  = document.getElementById('btnLoadedMove');     // 積載移動
  const $btnCancel = document.getElementById('btnCancel');         // キャンセル

  if (!$amr || !$cell || !$btnMove || !$btnLoad || !$btnFetch || !$btnCancel) {
    console.warn('[manual-ops] Required elements not found; skipping wire-up.');
    return;
  }

  function normalizeStr(v) { return String(v ?? '').trim(); }
  function readAngle() {
    const raw = normalizeStr($angle?.value ?? ''); if (!raw) return 0;
    const num = Number(raw); return Number.isFinite(num) ? num : 0;
  }
  function readForm() {
    return {
      robot_id:  normalizeStr($amr.value),
      shelf_id:  normalizeStr($shelf?.value ?? ''),
      cell_code: normalizeStr($cell.value),
      angle:     readAngle(),
    };
  }
  function setBusy(btn, busy) {
    if (!btn) return;
    btn.disabled = !!busy;
    const prev = btn.dataset.prevText || btn.textContent;
    if (!btn.dataset.prevText) btn.dataset.prevText = prev;
    btn.textContent = busy ? `${prev}…` : prev;
  }
  function endpointFor(action) {
    switch (action) {
      case 'move':   return API.path('/rms_manual_move');
      case 'cancel': return API.path('/rms_manual_cancel');
      case 'load':   return API.path('/rms_manual_load');
      case 'fetch':  return API.path('/rms_manual_fetch');
      default: throw new Error(`Unknown action: ${action}`);
    }
  }
  function payloadFor(action, form) {
    switch (action) {
      case 'move':   return ({ robot_id: form.robot_id, cell_code: form.cell_code });
      case 'cancel': return ({ robot_id: form.robot_id, cell_code: form.cell_code });
      case 'load':   return ({ robot_id: form.robot_id, shelf_id: form.shelf_id, cell_code: form.cell_code, angle: form.angle });
      case 'fetch':  return ({ robot_id: form.robot_id, shelf_id: form.shelf_id, cell_code: form.cell_code, angle: form.angle });
    }
  }
  function validate(action, form) {
    const missing = [];
    if (!form.robot_id) missing.push('AMR番号');
    if (!form.cell_code && (action === 'move' || action === 'cancel' || action === 'load' || action === 'fetch')) missing.push('セル番号');
    if (!form.shelf_id && (action === 'load' || action === 'fetch')) missing.push('コタツ番号');
    if (missing.length) return `必須項目が不足しています: ${missing.join('、')}`;
    return null;
  }
  async function callApi(action, form, btn) {
    const url = endpointFor(action);
    const body = payloadFor(action, form);
    setBusy(btn, true);
    try {
      const data = await apiFetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify(body),
      });
      alert('実行しました（サーバー応答: OK）');
      return data;
    } finally {
      setBusy(btn, false);
    }
  }

  async function handleAction(action, btn) {

    // ✅ BLOCK DUPLICATE MANUAL COMMANDS
    if (manualInFlight) {
      console.warn('[manual-ops] duplicate action blocked:', action);
      return;
    }

    manualInFlight = true;

    try {
      const form = readForm();
      const errMsg = validate(action, form);
      if (errMsg) { alert(errMsg); return; }
      const ok = await showConfirm((() => {
        switch (action) {
          case 'move':   return `AMR ${form.robot_id} を セル ${form.cell_code} へ単体移動します。よろしいですか？`;
          case 'cancel': return `AMR ${form.robot_id} のタスクを（セル ${form.cell_code}）でキャンセルします。よろしいですか？`;
          case 'load':   return `AMR ${form.robot_id} で 棚 ${form.shelf_id} を セル ${form.cell_code} へ搬送（角度 ${form.angle}°）します。よろしいですか？`;
          case 'fetch':  return `AMR ${form.robot_id} で 棚 ${form.shelf_id} を セル ${form.cell_code} へ積載移動（角度 ${form.angle}°）します。よろしいですか？`;
          default:       return '実行しますか？';
        }
      })());
      if (!ok) return;
      await callApi(action, form, btn);
    } catch (err) {
      console.error(`[manual-ops] ${action} failed:`, err);
      alert(`操作に失敗しました。\n${String(err?.message || err)}`);
    } finally {
      manualInFlight = false; // ✅ ALWAYS RELEASE LOCK
    }
  }

  // Bind buttons
  document.getElementById('btnSingleMove')    ?.addEventListener('click', () => handleAction('move',   $btnMove));
  document.getElementById('btnShelfTransport')?.addEventListener('click', () => handleAction('load',   $btnLoad));
  document.getElementById('btnLoadedMove')    ?.addEventListener('click', () => handleAction('fetch',  $btnFetch));
  document.getElementById('btnCancel')        ?.addEventListener('click', () => handleAction('cancel', $btnCancel));
}

/* ======================================================================
   6) RIGHT COLUMN (3/5): ライン状態表示 (#line-state-body)
====================================================================== */
function loadAndRenderLineStates() {
  console.debug('[wire] loadAndRenderLineStates started');

  const GREEN_HEX = '#ace1af';
  const setCellToGreen = (td) => { td.classList.remove('bg-secondary','text-white'); td.classList.add('bg-light','text-dark'); td.style.setProperty('background-color', GREEN_HEX, 'important'); };
  const setCellToGrey  = (td) => { td.classList.remove('bg-light','text-dark'); td.classList.add('bg-secondary','text-white'); td.style.removeProperty('background-color'); };

  async function fetchLineStates() {
    const response = await apiFetch(API.path('/get_line_state_list'), { method: 'GET' });
    const items = response?.data || response || [];
    if (!Array.isArray(items)) { console.error('Data is not an array:', items); return []; }
    return items.map(e => ({
      line_id: String(e.line_id ?? '').trim(),
      line_name: String(e.line_name ?? '').trim(),
      transport_permission: Boolean(e.transport_permission),
      pallets: Array.isArray(e.pallets) ? e.pallets : []
    }));
  }

  function buildRow(item) {
    const tr = document.createElement('tr');
    tr.dataset.lineId = item.line_id;
    tr.dataset.lineName = item.line_name;

    const tdCell = document.createElement('td');
    tdCell.textContent = item.line_name || '-';
    item.transport_permission ? setCellToGreen(tdCell) : setCellToGrey(tdCell);
    tr.appendChild(tdCell);

    for (let i = 0; i < 2; i++) {
      const tdPallet = document.createElement('td');
      let pName = (item.pallets && item.pallets[i]) ? item.pallets[i] : '—';
      if (pName === 'None' || pName === '') pName = '—';
      tdPallet.textContent = pName;
      tr.appendChild(tdPallet);
    }
    
    return tr;
  }

  async function render() {
    const targetBody = document.getElementById('line-state-body');
    if (!targetBody) { console.warn('Target <tbody> not found yet.'); return; }

    try {
      const items = await fetchLineStates();
      targetBody.innerHTML = '';
      if (items.length === 0) {
        targetBody.innerHTML = '<tr><td colspan="3" class="text-center">No data found</td></tr>';
        return;
      }
      items.sort((a, b) => a.line_name.localeCompare(b.line_name, 'ja'));
      const frag = document.createDocumentFragment();
      items.forEach(item => frag.appendChild(buildRow(item)));
      targetBody.appendChild(frag);
    } catch (err) {
      console.error('Render failed:', err);
      targetBody.innerHTML = '<tr><td colspan="3" class="text-center text-danger">Fetch Error</td></tr>';
    }
  }

  render();
}

/**
 * ライン状態表示: click-to-toggle (1st column) → /line_state/permission
 */
function wireLineStateCellClick() {
  console.debug('[wire] wireLineStateCellClick');
  const tbody = document.querySelector('#line-state-body');
  if (!tbody) return;

  const GREEN_HEX = '#ace1af';
  const TARGET_LINE_NAMES = new Set(['T63', 'T64', 'T65', 'T66']); // optional filter

  async function toggleRequestFlag(lineID) {
    const normalized = /^\d+$/.test(String(lineID)) ? Number(lineID) : String(lineID);
    const result = await apiFetch(API.path('/line_state/permission'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ line_id: normalized })
    });
    return Boolean(result.transport_permission);
  }

  const setCellToGreen = (td) => { td.classList.remove('bg-secondary','text-white'); td.classList.add('bg-light','text-dark'); td.style.setProperty('background-color', GREEN_HEX, 'important'); };
  const setCellToGrey  = (td) => { td.classList.remove('bg-light','text-dark'); td.classList.add('bg-secondary','text-white'); td.style.removeProperty('background-color'); };

  function setBusy(td, busy) {
    if (busy) {
      td.dataset.prevText = td.textContent.trim();
      td.textContent = `${td.dataset.prevText} …`;
      td.style.opacity = '0.8';
      td.style.cursor = 'wait';
    } else {
      if (td.dataset.prevText) { td.textContent = td.dataset.prevText; delete td.dataset.prevText; }
      td.style.opacity = ''; td.style.cursor = '';
    }
  }

  tbody.addEventListener('click', async (e) => {
    const td = e.target.closest('td');
    const tr = e.target.closest('tr');
    if (!td || !tr) return;
    if (td.cellIndex !== 0) return; // Only first column clickable

    const lineId   = tr.dataset.lineId;
    const lineName = tr.dataset.lineName;
    if (!lineId) return;
    if (TARGET_LINE_NAMES.size > 0 && !TARGET_LINE_NAMES.has(lineName)) return;

    try {
      setBusy(td, true);
      const requestFlag = await toggleRequestFlag(lineId);
      requestFlag ? setCellToGreen(td) : setCellToGrey(td);
    } catch (err) {
      console.error('permission toggle 失敗:', err);
      alert('更新に失敗しました。ネットワークまたはサーバーをご確認ください。');
    } finally {
      setBusy(td, false);
    }
  });
}

/* -------------------------
    Lift Entrance - View Only
    WORK state shows 3 columns (line/pallet/status) with bg-info
------------------------- */

let liftLoading = false;

function loadAndRenderLiftEntrance() {

  if (liftLoading) return; // ✅ prevent overlapping calls

  const tbody = document.getElementById('lift-state-body');
  if (!tbody) return;

  liftLoading = true;

  async function render() {

    try {
      const response = await apiFetch(API.path('/get_lift_entrance'), { method: 'GET' });
      const items = Array.isArray(response?.data) ? response.data : response;

      console.log("LiftData >> items", items);

      tbody.innerHTML = '';

      items.forEach(item => {
        const tr = document.createElement('tr');
        const status = String(item.transport_status || '').toUpperCase();

        // 1. Maguchi column (always)
        const tdMaguchi = document.createElement('td');
        tdMaguchi.textContent = item.maguchi_name || '-';
        tdMaguchi.className = "bg-light fw-bold text-center align-middle";
        tr.appendChild(tdMaguchi);

        /* ---------------------------------------------------------
            STATUS : WAIT
            → 3 columns merged, centered message, bg-secondary white text
        ---------------------------------------------------------- */
        if (status === 'WAIT') {
          const tdWait = document.createElement('td');
          tdWait.colSpan = 3;
          tdWait.textContent = '完成品搬入待ち';
          tdWait.className = "text-center align-middle bg-secondary text-white fw-bold";
          tr.appendChild(tdWait);
        }

        /* ---------------------------------------------------------
            STATUS : WORK (view-only)
            → 3 split columns (line/pallet/status)
            → bg-info text-white on all three
            → Status label: 「投入完了」
        ---------------------------------------------------------- */
        else if (status === 'WORK') {

          const tdLine   = document.createElement('td');
          const tdPallet = document.createElement('td');
          const tdStatus = document.createElement('td');

          tdLine.textContent   = item.line_name   || '';
          tdPallet.textContent = item.pallet_name || '';
          tdStatus.textContent = '投入完了';

          tdLine.className   = "text-center align-middle bg-info text-white fw-bold";
          tdPallet.className = "text-center align-middle bg-info text-white fw-bold";
          tdStatus.className = "text-center align-middle bg-info text-white fw-bold";

          tr.appendChild(tdLine);
          tr.appendChild(tdPallet);
          tr.appendChild(tdStatus);
        }

        /* ---------------------------------------------------------
            STATUS : READY / REDY
            → Orange background, split columns
        ---------------------------------------------------------- */
        else if (status === 'READY' || status === 'REDY') {
          const ORANGE = 'rgb(250, 96, 0)';

          const tdLine = document.createElement('td');
          const tdPallet = document.createElement('td');
          const tdStatus = document.createElement('td');

          tdLine.textContent = item.line_name || '';
          tdPallet.textContent = item.pallet_name || '';
          tdStatus.textContent = '取出開始';

          [tdLine, tdPallet, tdStatus].forEach(td => {
            td.style.backgroundColor = ORANGE;
            td.style.color = 'white';
            td.className = "text-center align-middle";
          });

          tr.appendChild(tdLine);
          tr.appendChild(tdPallet);
          tr.appendChild(tdStatus);
        }

        /* ---------------------------------------------------------
            STATUS : COMP / COMPLETE
            → Green + Grey (existing logic)
        ---------------------------------------------------------- */
        else if (status === 'COMP' || status === 'COMPLETE') {
          const GREEN = '#ace1af';

          const tdLine = document.createElement('td');
          const tdPallet = document.createElement('td');
          const tdStatus = document.createElement('td');

          tdLine.textContent = item.line_name || '';
          tdPallet.textContent = item.pallet_name || '';
          tdStatus.textContent = '完了';

          tdLine.style.backgroundColor = GREEN;
          tdPallet.style.backgroundColor = GREEN;

          tdStatus.style.backgroundColor = '#6c757d'; // grey
          tdStatus.style.color = 'white';

          tdLine.className = tdPallet.className = "text-center align-middle";
          tdStatus.className = "text-center align-middle";

          tr.appendChild(tdLine);
          tr.appendChild(tdPallet);
          tr.appendChild(tdStatus);
        }

        /* ---------------------------------------------------------
            DEFAULT — Show raw status with 3 columns
        ---------------------------------------------------------- */
        else {
          const tdLine = document.createElement('td');
          const tdPallet = document.createElement('td');
          const tdStatus = document.createElement('td');

          tdLine.textContent = item.line_name || '';
          tdPallet.textContent = item.pallet_name || '';
          tdStatus.textContent = item.transport_status;

          tdLine.className = tdPallet.className = tdStatus.className = "text-center align-middle";

          tr.appendChild(tdLine);
          tr.appendChild(tdPallet);
          tr.appendChild(tdStatus);
        }

        tbody.appendChild(tr);
      });

    } catch (err) {
      console.error(err);
    } finally {
      liftLoading = false;
    }
   
  }

  render();
}

/* ======================================================================
   1.5) Small Utilities
====================================================================== */
function normalizePositiveInt(value, fallback = 1) {
  const n = Number(value);
  return Number.isInteger(n) && n > 0 ? n : fallback;
}

let currentPage = 1;
let __taskStatusTimer = null;

function startTaskStatusPolling(intervalMs = 5000) {
  stopTaskStatusPolling();

  // initial load
  loadAndRenderTaskStatus(currentPage);

  __taskStatusTimer = setInterval(() => {
    loadAndRenderTaskStatus(currentPage);
  }, intervalMs);

  console.debug('[TaskStatus] Polling started (5s)');
}

function stopTaskStatusPolling() {
  if (__taskStatusTimer) {
    clearInterval(__taskStatusTimer);
    __taskStatusTimer = null;
    console.debug('[TaskStatus] Polling stopped');
  }
}

function loadAndRenderTaskStatus(page) {
  const tbody = document.getElementById('task-status-body');
  if (!tbody) return;

  currentPage = normalizePositiveInt(page, 1);

  async function render() {
    try {
      const items = await apiFetch(
        API.path(`/get_task_status?minutes=10&limit=100&page=${currentPage}`)
      );

      tbody.innerHTML = '';

      if (!Array.isArray(items) || items.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="6" class="text-center text-muted">
              直近10分以内のタスクはありません
            </td>
          </tr>`;
        return;
      }

      const frag = document.createDocumentFragment();

      items.forEach(task => {
        const tr = document.createElement('tr');
        const td = v => { const el = document.createElement('td'); el.textContent = v ?? '-'; return el; };

        tr.appendChild(td(task.task_id));
        tr.appendChild(td(task.robot_id));
        const statusTd = document.createElement('td');
        const badge = document.createElement('span');
        badge.classList.add('badge', 'fs-4', 'px-3', 'py-2');

        switch (task.status) {
          case 'EXECUTING':
            badge.classList.add('bg-primary');
            badge.textContent = 'EXECUTING';
            break;
          case 'COMPLETED':
            badge.classList.add('bg-success');
            badge.textContent = 'COMPLETED';
            break;
          case 'ERROR':
            badge.classList.add('bg-danger');
            badge.textContent = 'ERROR';
            break;
          default:
            badge.classList.add('bg-secondary');
            badge.textContent = task.status || '-';
        }

        statusTd.appendChild(badge);
        tr.appendChild(statusTd);
        tr.appendChild(td(task.task_type));
        tr.appendChild(td(task.destination));
        tr.appendChild(td(task.instruction));

        frag.appendChild(tr);
      });

      tbody.appendChild(frag);
    } catch (err) {
      console.error(err);
    }
  }

  render();
}

/* ======================================================================
   9) Backend API Wrappers (RMS endpoints)
====================================================================== */
async function apiGetRmsStatus() { return await apiFetch(API.path('/rms_status'), { method: 'GET' }); }

async function apiGetRmsMode() {
  const arr = await apiFetch(API.path('/get_rms_current_mode'), { method: 'GET' });
  const item = Array.isArray(arr) && arr.length ? arr[0] : null;
  if (!item) throw new Error('No RMS mode data');
  return Number(item.mode) === 1 ? 1 : 0;
}

async function apiSetRmsMode(mode /* 1|0 */) {
  const result = await apiFetch(API.path('/rms_set_mode'), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode: Number(mode) === 1 ? 1 : 0 })
  });
  return Number(result?.mode) === 1 ? 1 : 0;
}

async function apiRmsAutoPrepare() { return apiFetch(API.path('/rms_auto_prepare'), { method: 'POST' }); }

async function apiRmsAutoStart()   { return apiFetch(API.path('/rms_auto_start'),   { method: 'POST' }); }

async function apiRmsAutoRun()     { return apiFetch(API.path('/rms_auto_run'),     { method: 'POST' }); }

/* ======================================================================
   10) DOM Ready bootstrap — wire in HTML visual order
====================================================================== */
document.addEventListener("DOMContentLoaded", () => {
  console.group('[admin.js] DOMContentLoaded');

  // Header: Clock
  setInterval(getCurrentTime, 1000);

  setInterval(loadAndRenderLiftEntrance, 3000);

  
  // ✅ Default to Auto (UI) BEFORE binding mode toggle
  (function defaultToAutoUI() {
    const auto = document.getElementById('mode-auto');
    const indv = document.getElementById('mode-indv');
    if (auto) auto.checked = true;
    if (indv) indv.checked = false;

    // Paint UI immediately so users see Auto
    applyModeUI('auto');   // buttons, accordion disable, RMS polling on
    updateGaugeUI();       // gauge labels/colors
  })();


  // LEFT column
  wireMapSelectionToInputs();   // 地図 → 各個フォーム
  wireMapAutoFill();            // jQuery compat (same purpose)
  loadAndRenderErrors();        // エラー表示

  // RIGHT column (1/5) Controls
  wireRmsLamp();                // only sets initial lamp look
  wireModeToggle();             // applies mode, starts/stops RMS polling

  (async function restoreAutoStateOnLoad() {
    try {
      await syncAutoStateFromAPI();
    } catch (e) {
      console.warn('自動状態の復元に失敗:', e);
    }
  })();

  preventIndvGreyToggle();      // small UI prevention
  wireRunButtonAdvance();       // 自動3ステップ（起動準備→起動→運転中）

  // RIGHT column (2/5) 各個操作
  wireManualOps();

  // RIGHT column (3/5) ライン状態
  loadAndRenderLineStates();
  wireLineStateCellClick();

  // RIGHT column (4/5) リフト間口
  // loadAndRenderLiftEntrance();

  // RIGHT column (5/5) ステータス表示
  startTaskStatusPolling(5000);
  
  // Demo coloring for AB/RMS (keep look, non-functional for RMS)
  (function demoButtonsLook() {
    const setActive = (btn) => {
      document.querySelectorAll('#tab-rms, #tab-ab')
        .forEach(el => el.classList.remove('btn-warning','text-white'));
      btn.classList.add('btn-warning','text-white');
    };
    document.getElementById('tab-rms')?.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); }, true);
    document.getElementById('tab-ab')?.addEventListener('click',  (e) => setActive(e.currentTarget));
  })();

  // Ensure 自動 init shows 「起動準備」 if already selected
  (function enforceAutoInit() {
    const auto = document.getElementById('mode-auto');
    const runBtn = document.getElementById('tab-ab');
    if (!runBtn) return;
    if (auto && auto.checked) {
      runBtn.style.removeProperty('background-color');
      setAutoStateOnRunBtn(0);
    }
  })();

  console.groupEnd();
});




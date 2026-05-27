/**
 * リフト間口作業者インターフェース (lift-entrance.js)
 * 作成者: Lynn
 */

(function ($) {
  'use strict';

  console.log('[lift-entrance.js] loaded');

  // ===== API =====
  const API_PREFIX = '/worker/api/v1';
  const LIST_URL = `${API_PREFIX}/lift_entrance`;
  const actionUrl = (seqNo) => `${API_PREFIX}/lift_entrance/${encodeURIComponent(seqNo)}/action`;

  // ===== Polling =====
  const POLL_INTERVAL_MS = 1000;
  let pollTimer = null;
  let isPollingPaused = false;
  let isRendering = false;

  const FIXED_MAGUCHI_ORDER = [1, 2, 3, 4, 5, 6];

  // const forcedKanbanRows = new Set();
  // const reviewPendingRows = new Set();

  function startPolling() {
    stopPolling();
    const tick = async () => {
      if (!isPollingPaused && !isRendering) {
        await renderList();
      }
      pollTimer = setTimeout(tick, POLL_INTERVAL_MS);
    };
    pollTimer = setTimeout(tick, POLL_INTERVAL_MS);
  }

  function stopPolling() {
    if (pollTimer) {
      clearTimeout(pollTimer);
      pollTimer = null;
    }
  }

  // ===== Confirm modal =====
  const confirmModalEl = document.getElementById('ConfirmModal');
  const confirmModal = confirmModalEl ? new bootstrap.Modal(confirmModalEl) : null;

  // ===== Helpers =====
  const ORANGE = 'rgb(250, 96, 0)';
  const GREEN = '#ace1af';

  function stripBg($el) {
    $el.removeClass(
      'bg-primary bg-secondary bg-success bg-danger bg-warning bg-info bg-light bg-dark text-white text-dark'
    );
    $el.removeAttr('style');
  }

  function setBgImportant($el, color, addClasses = []) {
    stripBg($el);
    if (addClasses.length) $el.addClass(addClasses.join(' '));
    const el = $el.get(0);
    el?.style?.setProperty('background-color', color, 'important');
  }

  const setOrange = ($el) => setBgImportant($el, ORANGE, ['bg-warning', 'text-white']);
  const setBlue   = ($el) => { stripBg($el); $el.addClass('bg-info text-white'); };
  const setGreen  = ($el) => setBgImportant($el, GREEN, ['bg-success']);
  const setGrey   = ($el) => setBgImportant($el, '#6c757d', ['bg-secondary', 'text-white']);

  function seqNum(s) {
    const n = Number(s);
    if (Number.isFinite(n)) return n;
    const m = String(s || '').match(/\d+/);
    return m ? Number(m[0]) : Number.POSITIVE_INFINITY;
  }

  function getPlatNo($tr)     { return $tr.data('platNo'); }
  function getPalletId($tr)  { return $tr.data('palletId'); }
  function seqNoFromRow($tr) { return $tr.data('seqNo'); }

  function withBusy($btn, busy) {
    if (!$btn.length) return;
    if (busy) {
      $btn.prop('disabled', true);
      $btn.data('prevText', $btn.text());
      $btn.html('<span class="spinner-border spinner-border-sm me-2"></span>通信中…');
    } else {
      $btn.prop('disabled', false);
      $btn.text($btn.data('prevText') || '');
      $btn.removeData('prevText');
    }
  }

  // --- Zenkaku (全角) → Hankaku (半角) 数字変換 ---
  function toHalfWidthDigits(str) {
    if (str == null) return '';
    return String(str).replace(/[０-９]/g, ch =>
      String.fromCharCode(ch.charCodeAt(0) - 0xFEE0)
    );
  }

  // --- 「間口◯」の番号を取得（なければ +∞）---
  function maguchiOrder(maguchiName) {
    const s = toHalfWidthDigits(maguchiName || '');
    const m = s.match(/間口\s*([0-9]+)/);
    if (m && m[1]) return Number(m[1]);
    const m2 = s.match(/([0-9]+)/);
    return m2 ? Number(m2[1]) : Number.POSITIVE_INFINITY;
  }

  function getMaguchiNo(row) {
    return maguchiOrder(row.maguchi_name);
  }

  // ===== API wrapper =====
  async function fetchApi(url, options = {}) {
    const res = await fetch(url, {
      headers: { 'Accept': 'application/json', ...(options.headers || {}) },
      ...options
    });

    let js = null;
    try { js = await res.json(); } catch (_) {}

    if (res.ok) {
      if (js && 'data' in js) return js.data;
      if (Array.isArray(js)) return js;
      throw new Error('Invalid success payload');
    } else {
      const err = new Error(js?.message || '通信エラー');
      err.code = js?.error?.code || `HTTP_${res.status}`;
      throw err;
    }
  }

  async function apiList() {
    const data = await fetchApi(LIST_URL);
    if (!Array.isArray(data)) throw new Error('Invalid list');
    return data;
  }

  async function apiAction(seqNo, action, platNo, palletId) {
    return await fetchApi(actionUrl(seqNo), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: String(action).toUpperCase(),
        plat_no: platNo,
        pallet_id: palletId
      }),
    });
  }

  // ===== Build row (UNCHANGED) =====
  function buildRow(row) {

    const tr = document.createElement('tr');
    tr.dataset.seqNo = row.seq_no;
    tr.dataset.platNo = row.plat_no;
    tr.dataset.palletId = row.pallet_id;
  
    const key = `${row.seq_no}|${row.plat_no}|${row.pallet_id}`; // ✅ MOVE HERE
  
    // ---- maguchi ----
    const tdMaguchi = document.createElement('td');
    tdMaguchi.textContent = row.maguchi_name || '-';
    tdMaguchi.className = "fw-bold text-center align-middle";
    tr.appendChild(tdMaguchi);
  
    const status = String(row.transport_status || '').toUpperCase();
  
    if (status === 'WAIT') {
      const td = document.createElement('td');
      td.colSpan = 3;
      td.textContent = '完成品搬入待ち';
      td.className = "text-center fs-2";
      setGrey($(td));
      tr.appendChild(td);
      return tr;
    }
  
    const tdLine = document.createElement('td');
    const tdPallet = document.createElement('td');
    const tdStatus = document.createElement('td');
  
    tdLine.textContent = row.line_name || '';
    tdPallet.textContent = row.pallet_name || '';

  
    [tdLine, tdPallet, tdStatus].forEach(td =>
      td.className = "text-center align-middle"
    );

    // READY
    if (['READY', 'REDY'].includes(status)) {
      setOrange($(tdLine));
      setOrange($(tdPallet));
      setOrange($(tdStatus));
  
      const btn = document.createElement('button');
      btn.className = 'btn btn-lg w-75 btn-outline-dark text-white fs-2 action-start';
      btn.textContent = '取出開始';

      tdStatus.appendChild(btn);
    }
  
    // WORK
    else if (status === 'WORK') {
      setBlue($(tdLine));
      setBlue($(tdPallet));
      setBlue($(tdStatus));
  
      const btn = document.createElement('button');
      btn.className = 'btn btn-lg w-75 btn-outline-dark text-white fs-2 action-finish';
      btn.textContent = '投入完了';

      tdStatus.appendChild(btn);
    }
  
    // COMPLETE
    else if (['COMP', 'COMPLETE'].includes(status)) {
  
      // forcedKanbanRows.delete(key);
  
      setGreen($(tdLine));
      setGreen($(tdPallet));
      setGrey($(tdStatus));
  
      tdStatus.textContent = '完了';
    }
  
    tr.append(tdLine, tdPallet, tdStatus);
    return tr;
  }

  function rowKey(row) {
    return `${row.seq_no}|${row.plat_no}|${row.pallet_id}`;
  }
  
  function rowKeyFromTr($tr) {
    return `${$tr.data('seqNo')}|${$tr.data('platNo')}|${$tr.data('palletId')}`;
  }
  
  function blinkRow($tr) {
    $tr.addClass('row-blink');
    setTimeout(() => $tr.removeClass('row-blink'), 1000);
  }

  // ===== Render =====
  async function renderList() {
    if (isRendering) return;
    isRendering = true;

    const $tbody = $('#lift-state-body');

    try {
      const rows = await apiList();

      // --- Group rows by maguchi ---
      const maguchiMap = new Map();

      rows.forEach(row => {
        console.log("ROW >>>>", rows);

        const mNo = getMaguchiNo(row);
        if (!maguchiMap.has(mNo)) {
          maguchiMap.set(mNo, []);
        }
        maguchiMap.get(mNo).push(row);
      });

      $tbody.empty();   // ✅ ALWAYS clear

    FIXED_MAGUCHI_ORDER.forEach(mNo => {
      const group = maguchiMap.get(mNo) || [];

      if (group.length === 0) {
        // ---- Empty maguchi placeholder ----
        const tr = document.createElement('tr');

        const tdMaguchi = document.createElement('td');
        tdMaguchi.textContent = `間口 ${mNo}`;
        tdMaguchi.className = 'fw-bold text-center align-middle';

        const tdEmpty = document.createElement('td');
        tdEmpty.colSpan = 3;
        tdEmpty.textContent = '完成品搬入待ち';
        tdEmpty.className = 'text-center fs-2';
        setGrey($(tdEmpty));

        tr.append(tdMaguchi, tdEmpty);
        $tbody.append(tr);
        return;
      }

      // ---- Rows inside this maguchi ----
      group
        .sort((a, b) => {
          const sA = seqNum(a.seq_no);
          const sB = seqNum(b.seq_no);
          if (sA !== sB) return sA - sB;
          return Number(b.plat_no ?? -Infinity) - Number(a.plat_no ?? -Infinity);
        })
        .forEach(row => {
          $tbody.append(buildRow(row));
        });
    });

    } catch (err) {
      console.error(err);
    } finally {
      isRendering = false;
    }
  }

  let $pendingRow = null;
  let pendingAction = null;

  // ===== START Events (modified: NO direct API call) =====
  $(document).on('click', '.action-start', async function () {

    const $tr = $(this).closest('tr');
    const key = rowKeyFromTr($tr);
    
    // ✅ stop polling
    isPollingPaused = true;
  
    try {
      const result = await apiAction(
        seqNoFromRow($tr),
        'START',
        getPlatNo($tr),
        getPalletId($tr)
      );

      await renderList();   // ✅ FULL REFRESH
      isPollingPaused = false;
  
    } catch (err) {
      alert(err.message || '処理に失敗しました');
    } finally {
      // isPollingPaused = false;
    }
  });

  // ===== FINISH Events (keep but add action type) =====
  $(document).on('click', '.action-finish', function () {
    $pendingRow = $(this).closest('tr');
    pendingAction = 'FINISH';  // 👈 set action type

    $('#ConfirmModalLabel').text('投入完了の確認'); // optional UX
    confirmModal?.show();
  });

  // ===== Execute Button (shared for both START + FINISH) =====
  $('#ExecuteBtn').on('click', async function () {

    document.activeElement.blur();
  
    if (!$pendingRow || !pendingAction) return;
  
    const $tr = $pendingRow; // ✅ FIX
  
    const key = rowKeyFromTr($tr);

    const $btn = $tr.find(
      pendingAction === 'START' ? '.action-start' : '.action-finish'
    );
  
    try {
      isPollingPaused = true;
      withBusy($btn, true);
  
      const result = await apiAction(
        seqNoFromRow($tr),
        pendingAction,
        getPlatNo($tr),
        getPalletId($tr)
      );

      await renderList();   // ✅ FULL REFRESH immediately
      isPollingPaused = false;
  
    } catch (err) {
      alert(err.message || '処理に失敗しました');
    } finally {
      withBusy($btn, false);
      confirmModal?.hide();
      $pendingRow = null;
      pendingAction = null;
      isPollingPaused = false;
    }
  });

  // ===== Init =====
  $(function () {
    renderList();
    startPolling();
  });

  document.addEventListener('visibilitychange', () => {
    document.hidden ? stopPolling() : startPolling();
  });

})(jQuery);


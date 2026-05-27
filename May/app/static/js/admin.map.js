/**
 * RMS Map Monitoring Frontend (admin.map.js)
 * Author: Lynn
 */

const SIZE = {
  amrRadius: 12,
  amrStroke: 4,
  amrHeadRadius: 4,
  amrShadowOffset: 3,
  amrLabelFont: 5,

  cellFont: 6,

  // Capital I Kotatsu tuning
  kotatsuStemRatio: 0.45,
  kotatsuBarRatio: 0.55,
  kotatsuThickness: 0.22,
};

const BASE_CELL_GAP = 23;
const AMR_VERTICAL_OFFSET_X = 4;  // ✅ tweak: 2 ~ 6 depending UI

/* ================= Inline CSS ================= */
$("<style>", { type: "text/css" })
  .html(`
    .amr-clickable { cursor: pointer; }
    .shelf-clickable { cursor: pointer; }
    .cell-clickable { cursor: crosshair; }
  `)
  .appendTo("head");

$(document).ready(function () {

  /* ================= PAN / ZOOM STATE ================= */
  let scale = 1;
  let pointX = 0;
  let pointY = 0;
  let isDragging = false;
  let start = { x: 0, y: 0 };

  const $map = $("#map");
  const $container = $("#map-container");

  function setTransform() {
    $map.css({
      transform: `translate(${pointX}px, ${pointY}px) scale(${scale})`,
      "transform-origin": "0 0"
    });
  }

  /* ================= PAN ================= */
  $container.on("mousedown", function (e) {
    if ($(e.target).is("button")) return;
    start.x = e.clientX - pointX;
    start.y = e.clientY - pointY;
    isDragging = true;
  });

  $(window)
    .on("mousemove", function (e) {
      if (!isDragging) return;
      pointX = e.clientX - start.x;
      pointY = e.clientY - start.y;
      setTransform();
    })
    .on("mouseup", function () {
      isDragging = false;
    });

  /* ================= WHEEL ZOOM ================= */
  $container.on("wheel", function (e) {
    e.preventDefault();
    const factor = e.originalEvent.deltaY > 0 ? 0.9 : 1.1;
    scale = Math.min(Math.max(scale * factor, 0.05), 15);
    setTransform();
  });

  /* ================= ZOOM BUTTONS ================= */
  $("#zoom-in").on("click", function () {
    scale = Math.min(scale * 1.2, 15);
    setTransform();
  });

  $("#zoom-out").on("click", function () {
    scale = Math.max(scale / 1.2, 0.05);
    setTransform();
  });

  $("#zoom-reset").on("click", function () {
    scale = 1;
    pointX = 0;
    pointY = 0;
    setTransform();
  });

  function getCellGap(c) {
    return Math.min(BASE_CELL_GAP, Math.min(c.width, c.height) * 0.6);
  }
  
  const prevAMRPositions = {};
  const carryingMapGlobal = {};
  const prevBackendPos = {};
  
  /* ================= MAIN MAP RENDER ================= */
  function mapMonito() {
    
Object.keys(carryingMapGlobal).forEach(k => delete carryingMapGlobal[k]);

    $.get("/manage/api/v1/rms_map_monitor", function (res) {
      if (!res || !res.data) return;

      const cells = res.data.cells || [];
      const kotatsus = res.data.kotatsus || [];
      const amrs = res.data.amrs || [];
      const size = res.data.size || [1000, 1000];

      const width = size[0];
      const height = size[1];
      const svgNS = "http://www.w3.org/2000/svg";

      const svg = document.createElementNS(svgNS, "svg");
      svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
      svg.setAttribute("width", width);
      svg.setAttribute("height", height);

      const mapRoot = document.createElementNS(svgNS, "g");
      mapRoot.setAttribute("transform", `translate(0, ${height}) scale(1,-1)`);
      svg.appendChild(mapRoot);

      const HORIZONTAL_CELLS = new Set([
        "22604630",
        "22604448",
        "22603689",
        "22602950",
        "25002830",
        "27002830",
        "25002700",
        "27002700",
        "20802700",
        "20802655",
        "25001000",
        "27001000",
        "22600830",
        "25000830",
        "27000830",
        "24503190", // TODO: kawasumi changed map info
        "24503170" // TODO: kawasumi changed map info
      ]);

      const ALIGN_RIGHT_CELLS = new Set([
        "22603900",
        "22603765",
        "22603689",
        "22602950",
        "22602830",
        "22602700",
        "22601000"
      ]);
      
      const ALIGN_ROW_GROUPS = {
        "25002830": ["20802830", "22602830"],
        "25002700": ["22602700", "23102700", "20802700", "20802655"],
        "25001000": ["22601000", "23051000"]
      };

      const ROW_GROUP_SPACING = {
        "25002700": {
          "23102700": 12   // 👈 right
        },
        "25001000": {
          "23051000": 12   // 👈 right
        }
      };

      const VERTICAL_SPACING = {
        "20802700": 8,   // 👆 move up
        "20802655": -8,   // 👇 move down
        "22603765": 10, // 👆 move up
        "22603190": 10, // TODO: kawasumi changed map info
        "24503335": -2, // TODO: kawasumi changed map info
        "24503190": -4, // TODO: kawasumi changed map info
        "24503170": -4 // TODO: kawasumi changed map info
      };
      
      const ALIGN_COLUMN_GROUPS = {
        "22604074": [
          "22603765",
          "22603689",
          "22602950",
          "22602700",
          "22601000",
        ],
        "22603530": [ // TODO: kawasumi changed map info
          "22603335",
          "22603300",
          "22603190",
          "22603130"
        ]
      };

      
      const ORANGE_CELLS = new Set([
        "26054328",
        "28154328",
        "26053824",
        "28153824",
        "22603765",
        "21233530", // complete T63, T64
        "21233300", // complete T63, T64
        "21233130", // complete T63, T64
        "22602700", // temp T65
        "25002700", // input T65
        "27002700", // wait T65
        "21232430", // complete T65, T66
        "21232230", // complete T65, T66
        "21232030", // complete T65, T66
        "22601000", // temp T66
        "25001000", // input T66
        "27001000", // wait T66
      ]);

      const cellCache = cells.map(c => {
        
        const gap = getCellGap(c);

        const shrinkFactor = 1.1;  // ✅ NEW (very important)

        const adjW = (c.width - gap) * shrinkFactor;
        const adjH = (c.height - gap) * shrinkFactor;

        const adjX = c.location_x + (c.width - adjW) / 2;
        const adjY = c.location_y + (c.height - adjH) / 2
      
        return {
          ...c,
          gap,
          adjX,
          adjY,
          adjW,
          adjH,
          cx: adjX + adjW / 2,
          cy: adjY + adjH / 2
        };
      });

      const cellMap = {};
        cellCache.forEach(c => {
          cellMap[c.cellCode] = c;
        });


      function findCell(x, y) {
        const matches = cellCache.filter(c =>
          x >= c.location_x &&
          x <= c.location_x + c.width &&
          y >= c.location_y &&
          y <= c.location_y + c.height
        );
        if (matches.length === 0) return null;
        matches.sort((a, b) =>
          (b.location_y - a.location_y) || (b.location_x - a.location_x)
        );
        return matches[0];
      }
      
      /* ================= CELLS ================= */
      cellCache.forEach(cell => {
        const g = document.createElementNS(svgNS, "g");
        g.classList.add("cell-clickable");

        const gap = getCellGap(cell);
        const rect = document.createElementNS(svgNS, "rect");

        const isHorizontal = HORIZONTAL_CELLS.has(cell.cellCode);

        // force orientation using max/min
        const longSide = Math.max(cell.adjW, cell.adjH);
        const shortSide = Math.min(cell.adjW, cell.adjH);

        const drawW = isHorizontal ? longSide : shortSide;
        const drawH = isHorizontal ? shortSide : longSide;

        
        let offsetX = 0;
        let offsetY = 0;
        let rowOffsetX = 0; // ✅ NEW

        // ✅ NEW: column alignment lock
        for (const refCode in ALIGN_COLUMN_GROUPS) {
          const group = ALIGN_COLUMN_GROUPS[refCode];

          if (group.includes(cell.cellCode)) {
            const refCell = cellMap[refCode];

            if (refCell) {
              // ✅ force EXACT same center X
              const targetCx = refCell.cx;
              offsetX = targetCx - cell.cx;
            }
          }
        }

        // ✅ fallback old logic if not overridden
        if (offsetX === 0 && ALIGN_RIGHT_CELLS.has(cell.cellCode)) {
          offsetX = 14;
        }
        
        for (const refCode in ALIGN_ROW_GROUPS) {
          const group = ALIGN_ROW_GROUPS[refCode];

          if (group.includes(cell.cellCode)) {
            const refCell = cellMap[refCode];

            if (refCell) {
              // ✅ Keep vertical alignment
              const targetCy = refCell.cy;
              offsetY = targetCy - cell.cy;

              // ✅ Apply spacing (LEFT / RIGHT separation)
              const spacingConfig = ROW_GROUP_SPACING[refCode];
              if (spacingConfig && spacingConfig[cell.cellCode] !== undefined) {
                rowOffsetX = spacingConfig[cell.cellCode];
              }
            }
          }
        }

        
        // ✅ SIMPLE vertical spacing (no side effects)
        if (VERTICAL_SPACING[cell.cellCode] !== undefined) {
          offsetY += VERTICAL_SPACING[cell.cellCode];
        }
        
        const drawX = cell.cx - drawW / 2 + offsetX + rowOffsetX;
        const drawY = cell.cy - drawH / 2 + offsetY;

        
        cell.finalCx = cell.cx + offsetX + rowOffsetX;
        cell.finalCy = cell.cy + offsetY;


        rect.setAttribute("x", drawX);
        rect.setAttribute("y", drawY);
        rect.setAttribute("width", drawW);
        rect.setAttribute("height", drawH);
        
        // rect.setAttribute("fill", "#e0f7fa");
        // rect.setAttribute("stroke", "#4fc3f7");

        
        if (ORANGE_CELLS.has(cell.cellCode)) {
          rect.style.fill = "#ffe0b2";  // ✅ force override dark orange #ff5e00 
          rect.style.stroke = "#fb8c00"; // dark orange #ef6c00
        } else {
          rect.style.fill = "#e0f7fa";
          rect.style.stroke = "#4fc3f7";
        }


        rect.setAttribute("stroke-width", 2);
        // rect.setAttribute("rx", 4); // rounded
        g.appendChild(rect);

        // ✅ label position ABOVE the cell
        const labelOffset = 6; // spacing above box

        const textX = cell.cx + offsetX + rowOffsetX;
        const textY = drawY + drawH + labelOffset; // ✅ top edge + spacing

        const txt = document.createElementNS(svgNS, "text");
        txt.setAttribute("x", textX);
        txt.setAttribute("y", textY);
        txt.setAttribute("font-size", SIZE.cellFont);
        txt.setAttribute("fill", "#006064");
        txt.setAttribute("text-anchor", "middle");
        txt.setAttribute("pointer-events", "none");

        // const textY = cell.cy + offsetY;
        
        txt.setAttribute(
          "transform",
          `scale(1,-1) translate(0, ${-2 * textY})`
        );

        txt.textContent = cell.cellCode;
        g.appendChild(txt);

        g.onclick = function (e) {
          e.stopPropagation();
          $(document).trigger("map:select", { type: "cell", id: cell.cellCode });
        };

        mapRoot.appendChild(g);
      });

      /* ================= AMR ================= */
      amrs.forEach(robot => {

        // ✅ INIT STATE
        if (!prevAMRPositions[robot.robotId]) {
          const initCell = findCell(robot.location_x, robot.location_y);

          const initX = initCell?.finalCx ?? initCell?.cx ?? robot.location_x;
          const initY = initCell?.finalCy ?? initCell?.cy ?? robot.location_y;

          prevAMRPositions[robot.robotId] = {
            x: initX,
            y: initY,
            sx: initX,
            sy: initY,
            tx: initX,
            ty: initY,
            startTime: Date.now()
          };
        }

        const state = prevAMRPositions[robot.robotId];

        /* ================= ✅ TARGET CELL ONLY (IMPORTANT FIX) ================= */

        const nextCell = findCell(robot.location_x, robot.location_y);

        const laneCx = nextCell?.finalCx ?? nextCell?.cx ?? robot.location_x;
        const laneCy = nextCell?.finalCy ?? nextCell?.cy ?? robot.location_y;

        let targetX = state.x;
        let targetY = state.y;

        // ✅ Detect main movement axis from backend (NOT previous)
        const dxRaw = robot.location_x - state.x;
        const dyRaw = robot.location_y - state.y;

        if (Math.abs(dxRaw) > Math.abs(dyRaw)) {
          // ✅ horizontal movement
        
          targetX = laneCx;
        
          // ✅ smooth align to center (NO jump, NO drift)
          const SMOOTH = 0.2;   // 0.1 ~ 0.3 (adjust if needed)
          targetY = state.y + (laneCy - state.y) * SMOOTH;
        
        } else {
          // ✅ vertical movement (already correct)
        
          targetX = laneCx + AMR_VERTICAL_OFFSET_X;
          targetY = laneCy;
        }

        /* ================= ✅ START ANIMATION ================= */

        if (state.tx !== targetX || state.ty !== targetY) {
          state.sx = state.x;
          state.sy = state.y;

          state.tx = targetX;
          state.ty = targetY;

          state.startTime = Date.now();
        }

        /* ================= ✅ FAST CATCH-UP (KEY FIX) ================= */

        const dist = Math.hypot(state.tx - state.sx, state.ty - state.sy);

        // 🔥 IMPORTANT: FAST SYNC (no lag behind kotatsu)
        const duration = Math.max(120, dist * 1.2);  // ✅ MUCH FASTER

        const elapsed = Date.now() - state.startTime;
        let t = Math.min(elapsed / duration, 1);

        t = t * t;

        let cx = state.sx + (state.tx - state.sx) * t;
        let cy = state.sy + (state.ty - state.sy) * t;

        if (nextCell) {

          const targetCenterX = nextCell.finalCx ?? nextCell.cx;
          const targetCenterY = nextCell.finalCy ?? nextCell.cy;
        
          // ✅ vertical offset only for vertical lane
          if (Math.abs(dxRaw) <= Math.abs(dyRaw)) {
            targetX = targetCenterX + AMR_VERTICAL_OFFSET_X;
          } else {
            targetX = targetCenterX;
          }
        
          targetY = targetCenterY;
        }
        

        state.x = cx;
        state.y = cy;

        /* ================= ✅ PERFECT CARRY SYNC ================= */
        if (robot.carryingShelfCode) {
          carryingMapGlobal[robot.carryingShelfCode] = {
            x: cx,
            y: cy
          };
        }

        /* ================= RENDER ================= */

        const g = document.createElementNS(svgNS, "g");
        g.classList.add("amr-clickable");

        // const moving = dist > 1;
        // const color = moving ? "#2196f3" : (robot.color || "green");

        let moving = false;

        const prev = prevBackendPos[robot.robotId];

        if (prev) {
          const dx = robot.location_x - prev.x;
          const dy = robot.location_y - prev.y;

          moving = Math.hypot(dx, dy) > 0.5;  // ✅ REAL movement
        }

        // ✅ update for next frame
        prevBackendPos[robot.robotId] = {
          x: robot.location_x,
          y: robot.location_y
        };


        let color;

        // ✅ 1. ERROR
        if (robot.status && robot.status !== "NORMAL") {
          color = "#f44336";

        // ✅ 2. MOVING (REAL movement)
        } else if (moving) {
          color = "#2196f3";

        // ✅ 3. IDLE
        } else {
          color = "#4caf50";
        }

        /* ================= BODY ================= */

        const shadow = document.createElementNS(svgNS, "circle");
        shadow.setAttribute("cx", cx + SIZE.amrShadowOffset);
        shadow.setAttribute("cy", cy - SIZE.amrShadowOffset);
        shadow.setAttribute("r", SIZE.amrRadius);
        shadow.setAttribute("fill", "rgba(0,0,0,0.25)");

        const body = document.createElementNS(svgNS, "circle");
        body.setAttribute("cx", cx);
        body.setAttribute("cy", cy);
        body.setAttribute("r", SIZE.amrRadius);
        body.setAttribute("fill", color);
        body.setAttribute("stroke", "#fff");
        body.setAttribute("stroke-width", SIZE.amrStroke);

        g.append(shadow, body);

        /* ================= ✅ HEAD (CORRECT DIRECTION) ================= */

        if (moving) {
          const angle = Math.atan2(
            state.ty - state.sy,
            state.tx - state.sx
          );

          const dx = Math.cos(angle) * (SIZE.amrRadius - 4);
          const dy = Math.sin(angle) * (SIZE.amrRadius - 4);

          const head = document.createElementNS(svgNS, "circle");
          head.setAttribute("cx", cx + dx);
          head.setAttribute("cy", cy + dy);
          head.setAttribute("r", SIZE.amrHeadRadius);
          head.setAttribute("fill", "#ffffff");

          g.appendChild(head);
        }

        /* ================= LABEL ================= */

        const shortId = String(robot.robotId).slice(-3);

        const label = document.createElementNS(svgNS, "text");
        label.setAttribute("x", cx);
        label.setAttribute("y", cy);
        label.setAttribute("font-size", SIZE.amrLabelFont + 1);
        label.setAttribute("fill", "#000");
        label.setAttribute("stroke", "#fff");
        label.setAttribute("stroke-width", "0.6");
        label.setAttribute("font-weight", "bold");
        label.setAttribute("text-anchor", "middle");
        label.setAttribute("pointer-events", "none");
        label.setAttribute(
          "transform",
          `scale(1,-1) translate(0, ${-2 * cy})`
        );

        label.textContent = shortId;
        g.appendChild(label);

        g.onclick = function (e) {
          e.stopPropagation();
          $(document).trigger("map:select", {
            type: "amr",
            id: robot.robotId
          });
        };

        mapRoot.appendChild(g);
      });

      /* ================= KOTATSU ================= */
      kotatsus.forEach(k => {
        const cell = findCell(k.location_x, k.location_y);
        if (!cell) return;

        const g = document.createElementNS(svgNS, "g");
        g.classList.add("shelf-clickable");

        let cx, cy;

        // ✅ if carried → follow AMR
        if (carryingMapGlobal[k.shelfCode]) {

        const amrPos = carryingMapGlobal[k.shelfCode];

        cx = amrPos.x;
        cy = amrPos.y;

        } else {
          // ✅ Normal (no change)
          cx = cell.finalCx ?? cell.cx;
          cy = cell.finalCy ?? cell.cy - 1;
        }
        
        const scaleDown = 0.85; // ✅ small clean reduction

        const maxW = cell.adjW * 0.4;  // ✅ never exceed cell
        const maxH = cell.adjH * 0.4;

        const thick = Math.max(6, Math.min(cell.adjH * SIZE.kotatsuThickness * scaleDown, maxH * 0.25));
        const horizontal = k.angle === 90 || k.angle === -90;

        const stem = Math.max(10,
          horizontal
            ? Math.min(cell.adjH * SIZE.kotatsuStemRatio * scaleDown, cell.adjH * 0.5)  // ✅ keep horizontal same
            : Math.min(cell.adjH * 0.95, cell.adjH)  // ✅ ONLY vertical gets long
        );

        const bar = Math.max(10, Math.min(
          horizontal 
            ? cell.adjH * 0.4   // vertical bar when horizontal
            : cell.adjW * 0.4,  // horizontal bar when vertical
          
          horizontal
            ? cell.adjH * 0.4   // ✅ clamp to cell height
            : cell.adjW * 0.4   // ✅ clamp to cell width
        ));

        function rect(x, y, w, h) {
          const r = document.createElementNS(svgNS, "rect");
          r.setAttribute("x", x);
          r.setAttribute("y", y);
          r.setAttribute("width", w);
          r.setAttribute("height", h);
          r.setAttribute("fill", "#3f51b5");
          return r;
        }

        if (!horizontal) {
          g.append(rect(cx - thick / 2, cy - stem / 2, thick, stem));
          g.append(rect(cx - bar / 2, cy + stem / 2 - thick, bar, thick));
          g.append(rect(cx - bar / 2, cy - stem / 2, bar, thick));
        } else {
          g.append(rect(cx - stem / 2, cy - thick / 2, stem, thick));
          g.append(rect(cx - stem / 2, cy - bar / 2, thick, bar));
          g.append(rect(cx + stem / 2 - thick, cy - bar / 2, thick, bar));
        }

        /* ✅ Kotatsu hover label (restored) */
        const labelY = cy - bar / 2 - thick - 6;
        const label = document.createElementNS(svgNS, "text");
        label.setAttribute("x", cx);
        label.setAttribute("y", labelY);
        label.setAttribute("font-size", "7");
        label.setAttribute("fill", "#ffffff");
        label.setAttribute("font-weight", "600");
        label.setAttribute("text-anchor", "middle");
        label.setAttribute("pointer-events", "none");
        label.setAttribute(
          "transform",
          `scale(1,-1) translate(0, ${-2 * labelY})`
        );
        label.textContent = k.shelfCode;
        label.style.display = "none";

        g.appendChild(label);
        g.addEventListener("mouseenter", () => label.style.display = "block");
        g.addEventListener("mouseleave", () => label.style.display = "none");

        g.onclick = function (e) {
          e.stopPropagation();
          $(document).trigger("map:select", { type: "shelf", id: k.shelfCode });
        };

        mapRoot.appendChild(g);
      });

      $("#map").empty().append(svg);
      setTransform();
    });
  }

  setInterval(mapMonito, 400);
});
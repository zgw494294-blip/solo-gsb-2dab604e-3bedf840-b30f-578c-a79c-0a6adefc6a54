/* 木料定尺裁切 —— 原生 JavaScript 前端 */
(function () {
  "use strict";

  /* ---------- 元素引用 ---------- */

  var tabSingle = document.getElementById("tabSingle");
  var tabSchedule = document.getElementById("tabSchedule");
  var tabMulti = document.getElementById("tabMulti");
  var tabBatch = document.getElementById("tabBatch");
  var tabDispatch = document.getElementById("tabDispatch");
  var singleModeEl = document.getElementById("singleMode");
  var scheduleModeEl = document.getElementById("scheduleMode");
  var multiModeEl = document.getElementById("multiMode");
  var batchModeEl = document.getElementById("batchMode");
  var dispatchModeEl = document.getElementById("dispatchMode");
  var boardSectionEl = document.getElementById("boardSection");
  var partsSectionEl = document.getElementById("partsSection");

  var partRowsEl = document.getElementById("partRows");
  var addPartBtn = document.getElementById("addPart");
  var solveBtn = document.getElementById("solveBtn");

  var machineRowsEl = document.getElementById("machineRows");
  var addMachineBtn = document.getElementById("addMachine");
  var setupMinutesEl = document.getElementById("setupMinutes");
  var scheduleBtn = document.getElementById("scheduleBtn");

  var orderListEl = document.getElementById("orderList");
  var addOrderBtn = document.getElementById("addOrder");
  var allocBtn = document.getElementById("allocBtn");

  var formErrorEl = document.getElementById("formError");
  var noSolutionEl = document.getElementById("noSolution");
  var resultTitleEl = document.getElementById("resultTitle");
  var placeholderEl = document.getElementById("resultPlaceholder");
  var resultEl = document.getElementById("result");
  var summaryEl = document.getElementById("summary");
  var boardListEl = document.getElementById("boardList");

  var scheduleResultEl = document.getElementById("scheduleResult");
  var scheduleSummaryEl = document.getElementById("scheduleSummary");
  var machineListEl = document.getElementById("machineList");
  var scheduleTotalEl = document.getElementById("scheduleTotal");
  var scheduleBoardListEl = document.getElementById("scheduleBoardList");

  var allocResultEl = document.getElementById("allocResult");
  var allocSummaryEl = document.getElementById("allocSummary");
  var allocRowsEl = document.getElementById("allocRows");
  var allocTotalExactEl = document.getElementById("allocTotalExact");
  var allocTotalPayEl = document.getElementById("allocTotalPay");

  var createBatchBtn = document.getElementById("createBatchBtn");
  var openBatchIdEl = document.getElementById("openBatchId");
  var openBatchBtn = document.getElementById("openBatchBtn");
  var batchResultEl = document.getElementById("batchResult");
  var batchSummaryEl = document.getElementById("batchSummary");
  var qualifiedListEl = document.getElementById("qualifiedList");
  var batchBoardListEl = document.getElementById("batchBoardList");
  var reportSectionEl = document.getElementById("reportSection");
  var batchDoneEl = document.getElementById("batchDone");
  var idemKeyEl = document.getElementById("idemKey");
  var expectedVersionEl = document.getElementById("expectedVersion");
  var reportBtn = document.getElementById("reportBtn");
  var reportOkEl = document.getElementById("reportOk");
  var reportErrorEl = document.getElementById("reportError");

  var qualitySectionEl = document.getElementById("qualitySection");
  var qualityToleranceEl = document.getElementById("qualityTolerance");
  var qualityBtn = document.getElementById("qualityBtn");
  var qualityErrorEl = document.getElementById("qualityError");
  var qualityResultEl = document.getElementById("qualityResult");
  var qualitySummaryEl = document.getElementById("qualitySummary");
  var qualityDemandListEl = document.getElementById("qualityDemandList");
  var qualityRowsEl = document.getElementById("qualityRows");
  var qualityUnassignedEl = document.getElementById("qualityUnassigned");
  var qualityShortageEl = document.getElementById("qualityShortage");

  var jointSectionEl = document.getElementById("jointSection");
  var jointTargetEl = document.getElementById("jointTarget");
  var jointRowsEl = document.getElementById("jointRows");
  var jointStaggerEl = document.getElementById("jointStagger");
  var jointPickListEl = document.getElementById("jointPickList");
  var jointBtn = document.getElementById("jointBtn");
  var jointErrorEl = document.getElementById("jointError");
  var jointWarnEl = document.getElementById("jointWarn");
  var jointResultEl = document.getElementById("jointResult");
  var jointSummaryEl = document.getElementById("jointSummary");
  var jointRowListEl = document.getElementById("jointRowList");
  var jointUnusedEl = document.getElementById("jointUnused");

  var dispatchPurposeEl = document.getElementById("dispatchPurpose");
  var dispatchIdemKeyEl = document.getElementById("dispatchIdemKey");
  var dispatchPieceRowsEl = document.getElementById("dispatchPieceRows");
  var addDispatchPieceBtn = document.getElementById("addDispatchPiece");
  var dispatchBtn = document.getElementById("dispatchBtn");
  var openDispatchIdEl = document.getElementById("openDispatchId");
  var openDispatchBtn = document.getElementById("openDispatchBtn");
  var dispatchResultEl = document.getElementById("dispatchResult");
  var dispatchSummaryEl = document.getElementById("dispatchSummary");
  var dispatchRowsEl = document.getElementById("dispatchRows");
  var dispatchOkEl = document.getElementById("dispatchOk");
  var dispatchErrorEl = document.getElementById("dispatchError");

  var PLACEHOLDER = {
    single: "填写左侧信息后点击「计算最优方案」，这里会列出逐板切件、锯缝、余料与合计价格。",
    schedule: "填写左侧零件与锯机信息后点击「计算最优排程」，这里会列出各机逐板开工/完工分钟与整体完工分钟。",
    multi: "填写左侧订单后点击「计算费用分摊」，这里会列出合板最优总价、各单精确分摊值与最终应付金额。",
    batch: "在左侧创建或按 ID 打开核销批次后，这里会显示冻结方案、逐板状态、各长度合格件数与核销进度。",
    dispatch: "在左侧填写用途、幂等键与 1～10 件切件后点击「提交发料单」，这里会列出发料单号、冻结的切件明细与创建时间。",
  };

  var TITLES = {
    single: "裁切方案",
    schedule: "锯机排程",
    multi: "费用分摊",
    batch: "执行核销",
    dispatch: "发料单",
  };

  /* ---------- 模式切换 ---------- */

  var mode = "single";

  function setMode(next) {
    mode = next;
    tabSingle.classList.toggle("active", mode === "single");
    tabSchedule.classList.toggle("active", mode === "schedule");
    tabMulti.classList.toggle("active", mode === "multi");
    tabBatch.classList.toggle("active", mode === "batch");
    tabDispatch.classList.toggle("active", mode === "dispatch");
    // 零件清单由「单份清单」「锯机排程」「执行核销」共用，多订单与发料单模式下隐藏；
    // 原板信息在发料单模式下同样不需要。
    partsSectionEl.hidden = mode === "multi" || mode === "dispatch";
    boardSectionEl.hidden = mode === "dispatch";
    singleModeEl.hidden = mode !== "single";
    scheduleModeEl.hidden = mode !== "schedule";
    multiModeEl.hidden = mode !== "multi";
    batchModeEl.hidden = mode !== "batch";
    dispatchModeEl.hidden = mode !== "dispatch";
    if (mode === "dispatch" && !dispatchIdemKeyEl.value.trim()) {
      dispatchIdemKeyEl.value = newDispatchIdemKey();
    }
    resultTitleEl.textContent = TITLES[mode];
    placeholderEl.textContent = PLACEHOLDER[mode];
    hideMessages();
  }

  tabSingle.addEventListener("click", function () {
    setMode("single");
  });
  tabSchedule.addEventListener("click", function () {
    setMode("schedule");
  });
  tabMulti.addEventListener("click", function () {
    setMode("multi");
  });
  tabBatch.addEventListener("click", function () {
    setMode("batch");
  });
  tabDispatch.addEventListener("click", function () {
    setMode("dispatch");
  });

  /* ---------- 零件行 ---------- */

  function makePartRow(container, length, quantity) {
    var row = document.createElement("div");
    row.className = "parts-row";
    row.innerHTML =
      '<span class="idx"></span>' +
      '<input class="part-length" type="number" min="1" step="1" inputmode="numeric" />' +
      '<input class="part-qty" type="number" min="1" step="1" inputmode="numeric" />' +
      '<button type="button" class="btn-del">删除</button>';
    row.querySelector(".part-length").value = length != null ? length : "";
    row.querySelector(".part-qty").value = quantity != null ? quantity : "";
    row.querySelector(".btn-del").addEventListener("click", function () {
      if (container.children.length > 1) {
        row.remove();
        renumberParts(container);
      }
    });
    container.appendChild(row);
    renumberParts(container);
  }

  function renumberParts(container) {
    var rows = container.querySelectorAll(".parts-row");
    rows.forEach(function (row, i) {
      row.querySelector(".idx").textContent = String(i + 1);
      // 至少保留一行时，唯一一行禁用删除
      row.querySelector(".btn-del").disabled = rows.length <= 1;
    });
  }

  addPartBtn.addEventListener("click", function () {
    makePartRow(partRowsEl);
  });

  // 单份清单预置一组示例数据
  makePartRow(partRowsEl, 2500, 2);
  makePartRow(partRowsEl, 1800, 3);
  makePartRow(partRowsEl, 1200, 4);

  /* ---------- 锯机行 ---------- */

  function renumberMachines() {
    var rows = machineRowsEl.querySelectorAll(".machine-row");
    rows.forEach(function (row, i) {
      row.querySelector(".idx").textContent = String(i + 1) + " 号机";
      // 至少保留 2 台时禁用删除；达到 4 台时禁用添加。
      row.querySelector(".btn-del").disabled = rows.length <= 2;
    });
    addMachineBtn.disabled = rows.length >= 4;
  }

  function makeMachineRow(ready, cut) {
    var row = document.createElement("div");
    row.className = "parts-row machine-row";
    row.innerHTML =
      '<span class="idx"></span>' +
      '<input class="machine-ready" type="number" min="0" step="1" inputmode="numeric" placeholder="非负整数" />' +
      '<input class="machine-cut" type="number" min="1" step="1" inputmode="numeric" placeholder="正整数" />' +
      '<button type="button" class="btn-del">删除</button>';
    row.querySelector(".machine-ready").value = ready != null ? ready : "";
    row.querySelector(".machine-cut").value = cut != null ? cut : "";
    row.querySelector(".btn-del").addEventListener("click", function () {
      if (machineRowsEl.querySelectorAll(".machine-row").length > 2) {
        row.remove();
        renumberMachines();
      }
    });
    machineRowsEl.appendChild(row);
    renumberMachines();
  }

  addMachineBtn.addEventListener("click", function () {
    if (machineRowsEl.querySelectorAll(".machine-row").length < 4) {
      makeMachineRow();
    }
  });

  // 预置两台示例锯机
  makeMachineRow(0, 5);
  makeMachineRow(20, 3);

  /* ---------- 订单块 ---------- */

  var ORDER_NAMES = ["订单A", "订单B", "订单C", "订单D"];

  function nextOrderName() {
    var used = {};
    orderListEl.querySelectorAll(".order-name").forEach(function (el) {
      used[el.value.trim()] = true;
    });
    for (var i = 0; i < ORDER_NAMES.length; i++) {
      if (!used[ORDER_NAMES[i]]) return ORDER_NAMES[i];
    }
    return "订单" + String(orderListEl.children.length + 1);
  }

  function addOrderBlock(name, sampleParts) {
    var block = document.createElement("div");
    block.className = "order-block";
    block.innerHTML =
      '<div class="order-head">' +
        '<input class="order-name" type="text" maxlength="30" placeholder="订单名称" />' +
        '<button type="button" class="btn-del order-del">删除订单</button>' +
      '</div>' +
      '<div class="parts-table">' +
        '<div class="parts-row parts-title-row">' +
          '<span>序号</span><span>零件长度</span><span>件数</span><span>操作</span>' +
        '</div>' +
        '<div class="order-parts"></div>' +
      '</div>' +
      '<button type="button" class="btn btn-ghost add-order-part">＋ 添加零件</button>';

    var nameInput = block.querySelector(".order-name");
    nameInput.value = name || nextOrderName();
    nameInput.addEventListener("input", function () {
      nameInput.classList.remove("invalid");
    });

    var partsEl = block.querySelector(".order-parts");
    block.querySelector(".add-order-part").addEventListener("click", function () {
      makePartRow(partsEl);
    });
    block.querySelector(".order-del").addEventListener("click", function () {
      if (orderListEl.children.length > 2) {
        block.remove();
        refreshOrderControls();
      }
    });

    orderListEl.appendChild(block);
    if (sampleParts && sampleParts.length) {
      sampleParts.forEach(function (p) {
        makePartRow(partsEl, p[0], p[1]);
      });
    } else {
      makePartRow(partsEl);
    }
    refreshOrderControls();
  }

  function refreshOrderControls() {
    var count = orderListEl.children.length;
    // 至少保留 2 个订单时禁用删除；最多 4 个订单时禁用添加。
    orderListEl.querySelectorAll(".order-del").forEach(function (btn) {
      btn.disabled = count <= 2;
    });
    addOrderBtn.disabled = count >= 4;
  }

  addOrderBtn.addEventListener("click", function () {
    if (orderListEl.children.length < 4) {
      addOrderBlock();
    }
  });

  // 预置两个示例订单
  addOrderBlock("订单A", [[2500, 2], [1200, 1]]);
  addOrderBlock("订单B", [[1800, 2], [1200, 1]]);

  /* ---------- 输入校验 ---------- */

  function readPositiveInt(inputEl, label) {
    var raw = inputEl.value.trim();
    if (!/^\d+$/.test(raw)) {
      inputEl.classList.add("invalid");
      return { error: label + "必须为正整数" };
    }
    var value = Number(raw);
    if (value <= 0) {
      inputEl.classList.add("invalid");
      return { error: label + "必须为正整数" };
    }
    inputEl.classList.remove("invalid");
    return { value: value };
  }

  function readNonnegInt(inputEl, label) {
    var raw = inputEl.value.trim();
    if (!/^\d+$/.test(raw)) {
      inputEl.classList.add("invalid");
      return { error: label + "必须为非负整数" };
    }
    inputEl.classList.remove("invalid");
    return { value: Number(raw) };
  }

  function readBoardFields() {
    var checks = [
      readPositiveInt(document.getElementById("boardLength"), "原板长度"),
      readPositiveInt(document.getElementById("unitPrice"), "原板单价"),
      readPositiveInt(document.getElementById("available"), "可用数量"),
      readNonnegInt(document.getElementById("kerf"), "锯缝宽度"),
    ];
    for (var i = 0; i < checks.length; i++) {
      if (checks[i].error) return { error: checks[i].error };
    }
    return {
      value: {
        board_length: checks[0].value,
        unit_price: checks[1].value,
        available: checks[2].value,
        kerf: checks[3].value,
      },
    };
  }

  function readPartsRows(rows, labelOf) {
    var parts = [];
    var totalQty = 0;
    for (var r = 0; r < rows.length; r++) {
      var lenEl = rows[r].querySelector(".part-length");
      var qtyEl = rows[r].querySelector(".part-qty");
      var lenEmpty = lenEl.value.trim() === "" && qtyEl.value.trim() === "";
      if (lenEmpty) continue; // 空行直接忽略

      var lenRes = readPositiveInt(lenEl, labelOf(r) + "零件长度");
      if (lenRes.error) return { error: lenRes.error };
      var qtyRes = readPositiveInt(qtyEl, labelOf(r) + "零件件数");
      if (qtyRes.error) return { error: qtyRes.error };

      parts.push({ length: lenRes.value, quantity: qtyRes.value });
      totalQty += qtyRes.value;
    }
    return { parts: parts, totalQty: totalQty };
  }

  function collectPayload() {
    document.querySelectorAll("input.invalid").forEach(function (el) {
      el.classList.remove("invalid");
    });
    hideMessages();

    var board = readBoardFields();
    if (board.error) return { error: board.error };

    var rows = partRowsEl.querySelectorAll(".parts-row");
    var read = readPartsRows(rows, function (r) {
      return "第 " + (r + 1) + " 行";
    });
    if (read.error) return { error: read.error };

    if (read.parts.length === 0) return { error: "请至少填写一种零件" };
    if (read.totalQty > 12) {
      return { error: "需求总件数为 " + read.totalQty + " 件，不能超过 12 件" };
    }

    var payload = board.value;
    payload.parts = read.parts;
    return { payload: payload };
  }

  function collectSchedulePayload() {
    document.querySelectorAll("input.invalid").forEach(function (el) {
      el.classList.remove("invalid");
    });
    hideMessages();

    var board = readBoardFields();
    if (board.error) return { error: board.error };

    var rows = partRowsEl.querySelectorAll(".parts-row");
    var read = readPartsRows(rows, function (r) {
      return "第 " + (r + 1) + " 行";
    });
    if (read.error) return { error: read.error };

    if (read.parts.length === 0) return { error: "请至少填写一种零件" };
    if (read.totalQty > 12) {
      return { error: "需求总件数为 " + read.totalQty + " 件，不能超过 12 件" };
    }

    var setupRes = readNonnegInt(setupMinutesEl, "每板准备分钟");
    if (setupRes.error) return { error: setupRes.error };

    var machineRows = machineRowsEl.querySelectorAll(".machine-row");
    if (machineRows.length < 2 || machineRows.length > 4) {
      return { error: "锯机数量须为 2～4 台" };
    }

    var machines = [];
    for (var m = 0; m < machineRows.length; m++) {
      var readyEl = machineRows[m].querySelector(".machine-ready");
      var cutEl = machineRows[m].querySelector(".machine-cut");
      var readyRes = readNonnegInt(readyEl, "第 " + (m + 1) + " 台锯机最早可用分钟");
      if (readyRes.error) return { error: readyRes.error };
      var cutRes = readPositiveInt(cutEl, "第 " + (m + 1) + " 台锯机每件切割分钟");
      if (cutRes.error) return { error: cutRes.error };
      machines.push({ ready_minutes: readyRes.value, cut_minutes: cutRes.value });
    }

    var payload = board.value;
    payload.parts = read.parts;
    payload.setup_minutes = setupRes.value;
    payload.machines = machines;
    return { payload: payload };
  }

  function collectAllocPayload() {
    document.querySelectorAll("input.invalid").forEach(function (el) {
      el.classList.remove("invalid");
    });
    hideMessages();

    var board = readBoardFields();
    if (board.error) return { error: board.error };

    var blocks = orderListEl.querySelectorAll(".order-block");
    if (blocks.length < 2 || blocks.length > 4) {
      return { error: "订单数量须为 2～4 个" };
    }

    var orders = [];
    var totalQty = 0;
    for (var b = 0; b < blocks.length; b++) {
      var nameEl = blocks[b].querySelector(".order-name");
      var name = nameEl.value.trim();
      if (!name) {
        nameEl.classList.add("invalid");
        return { error: "第 " + (b + 1) + " 个订单的名称不能为空" };
      }

      var rows = blocks[b].querySelectorAll(".order-parts .parts-row");
      var read = readPartsRows(rows, function (r) {
        return "「" + name + "」第 " + (r + 1) + " 行";
      });
      if (read.error) return { error: read.error };
      if (read.parts.length === 0) {
        return { error: "订单「" + name + "」至少填写一种零件" };
      }

      orders.push({ name: name, parts: read.parts });
      totalQty += read.totalQty;
    }

    if (totalQty > 12) {
      return { error: "全部订单合计 " + totalQty + " 件，不能超过 12 件" };
    }

    var payload = board.value;
    payload.orders = orders;
    return { payload: payload };
  }

  /* ---------- 结果渲染 ---------- */

  function hideMessages() {
    formErrorEl.hidden = true;
    formErrorEl.textContent = "";
    noSolutionEl.hidden = true;
    noSolutionEl.textContent = "";
    resultEl.hidden = true;
    scheduleResultEl.hidden = true;
    allocResultEl.hidden = true;
    batchResultEl.hidden = true;
    dispatchResultEl.hidden = true;
    dispatchOkEl.hidden = true;
    dispatchOkEl.textContent = "";
    dispatchErrorEl.hidden = true;
    dispatchErrorEl.textContent = "";
    placeholderEl.hidden = false;
  }

  function showFormError(msg) {
    formErrorEl.textContent = msg;
    formErrorEl.hidden = false;
  }

  function showNoSolution(msg) {
    placeholderEl.hidden = true;
    noSolutionEl.textContent = "无解：" + msg;
    noSolutionEl.hidden = false;
  }

  function stat(label, value, highlight) {
    var div = document.createElement("div");
    div.className = "stat" + (highlight ? " highlight" : "");
    var l = document.createElement("span");
    l.className = "label";
    l.textContent = label;
    var v = document.createElement("span");
    v.className = "value";
    v.textContent = value;
    div.appendChild(l);
    div.appendChild(v);
    return div;
  }

  function renderSummary(s) {
    summaryEl.innerHTML = "";
    summaryEl.appendChild(stat("使用原板", s.board_count + " / " + s.available + " 根"));
    summaryEl.appendChild(stat("切出零件", s.total_pieces + " 件"));
    summaryEl.appendChild(stat("零件总长", s.total_cut_length));
    summaryEl.appendChild(stat("锯缝合计", s.total_kerf + "（" + s.kerf + " × 缝数）"));
    summaryEl.appendChild(stat("余料合计", s.total_waste));
    summaryEl.appendChild(stat("合计价格", s.total_price + " 元", true));
  }

  function renderBoard(board, boardLength) {
    var wrap = document.createElement("div");
    wrap.className = "board";

    // 标题行
    var head = document.createElement("div");
    head.className = "board-head";
    var no = document.createElement("span");
    no.className = "no";
    no.textContent = "第 " + board.board_no + " 块原板";
    var meta = document.createElement("span");
    meta.className = "meta";
    meta.textContent =
      "切 " + board.piece_count + " 件 · 锯缝 " +
      board.kerf_count + " 道";
    head.appendChild(no);
    head.appendChild(meta);
    wrap.appendChild(head);

    // 比例条：件、锯缝、件 … 余料
    var bar = document.createElement("div");
    bar.className = "bar";
    var frag = document.createDocumentFragment();
    board.cuts.forEach(function (cutLen, idx) {
      if (idx > 0) {
        var kerfSeg = document.createElement("div");
        kerfSeg.className = "seg-kerf";
        kerfSeg.style.flexGrow = String(board.kerf_total / (board.cuts.length - 1 || 1));
        frag.appendChild(kerfSeg);
      }
      var cutSeg = document.createElement("div");
      cutSeg.className = "seg-cut";
      cutSeg.style.flexGrow = String(cutLen);
      frag.appendChild(cutSeg);
    });
    var wasteSeg = document.createElement("div");
    wasteSeg.className = "seg-waste";
    wasteSeg.style.flexGrow = String(Math.max(board.leftover, 0));
    frag.appendChild(wasteSeg);
    bar.appendChild(frag);
    wrap.appendChild(bar);

    // 图例
    var labels = document.createElement("div");
    labels.className = "bar-labels";
    labels.innerHTML =
      '<span><i class="dot" style="background:#b97b45"></i>零件</span>' +
      '<span><i class="dot" style="background:#c9c2b4"></i>锯缝</span>' +
      '<span><i class="dot" style="background:#ece8de"></i>余料</span>';
    wrap.appendChild(labels);

    // 逐件尺寸
    var cutList = document.createElement("div");
    cutList.className = "cut-list";
    board.cuts.forEach(function (cutLen) {
      var chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = cutLen;
      cutList.appendChild(chip);
    });
    wrap.appendChild(cutList);

    // 板底明细
    var foot = document.createElement("div");
    foot.className = "board-foot";
    var left = document.createElement("span");
    left.innerHTML =
      "占用 <strong>" + board.used_length + "</strong> / " + boardLength +
      "　锯缝 <strong>" + board.kerf_total + "</strong>" +
      "　余料 <strong>" + board.leftover + "</strong>";
    var right = document.createElement("span");
    right.innerHTML = "本板价格 <strong>" + board.price + " 元</strong>";
    foot.appendChild(left);
    foot.appendChild(right);
    wrap.appendChild(foot);

    return wrap;
  }

  function renderResult(data) {
    var s = data.summary;
    renderSummary(s);

    boardListEl.innerHTML = "";
    data.boards.forEach(function (board) {
      boardListEl.appendChild(renderBoard(board, s.board_length));
    });

    var total = document.createElement("div");
    total.className = "total-row";
    var detail = document.createElement("span");
    detail.textContent =
      "合计：用板 " + s.board_count + " 根 · 零件 " + s.total_pieces +
      " 件 · 余料合计 " + s.total_waste;
    var price = document.createElement("span");
    price.className = "price";
    price.textContent = "总价 " + s.total_price + " 元";
    total.appendChild(detail);
    total.appendChild(price);
    boardListEl.appendChild(total);

    placeholderEl.hidden = true;
    resultEl.hidden = false;
  }

  /* ---------- 锯机排程结果渲染 ---------- */

  function renderMachine(machine, setup) {
    var card = document.createElement("div");
    card.className = "machine-card";

    var head = document.createElement("div");
    head.className = "machine-head";
    var no = document.createElement("span");
    no.className = "no";
    no.textContent = machine.machine_no + " 号锯机";
    var meta = document.createElement("span");
    meta.className = "meta";
    meta.textContent =
      "最早可用 " + machine.ready_minutes + " 分钟 · 每件切割 " +
      machine.cut_minutes + " 分钟 · 每板准备 " + setup + " 分钟";
    head.appendChild(no);
    head.appendChild(meta);
    card.appendChild(head);

    if (!machine.jobs.length) {
      var idle = document.createElement("p");
      idle.className = "machine-idle";
      idle.textContent = "未分配原板（本机不参与本次加工）";
      card.appendChild(idle);
      return card;
    }

    var table = document.createElement("table");
    table.className = "job-table";
    table.innerHTML =
      "<thead><tr><th>原板编号</th><th>切件数</th><th>本板耗时（分钟）</th>" +
      "<th>开工分钟</th><th>完工分钟</th></tr></thead>";
    var tbody = document.createElement("tbody");
    machine.jobs.forEach(function (job) {
      var tr = document.createElement("tr");
      [job.board_no, job.piece_count, job.duration_minutes,
       job.start_minutes, job.finish_minutes].forEach(function (text) {
        var td = document.createElement("td");
        td.textContent = String(text);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    card.appendChild(table);

    var foot = document.createElement("div");
    foot.className = "machine-foot";
    foot.textContent =
      "本机" + machine.job_count + " 块原板：第 " +
      machine.start_minutes + " 分钟开工，第 " +
      machine.finish_minutes + " 分钟完工";
    card.appendChild(foot);
    return card;
  }

  function renderSchedule(data) {
    var s = data.summary;
    var sch = data.schedule;

    scheduleSummaryEl.innerHTML = "";
    scheduleSummaryEl.appendChild(stat("使用原板", s.board_count + " / " + s.available + " 根"));
    scheduleSummaryEl.appendChild(stat("切出零件", s.total_pieces + " 件"));
    scheduleSummaryEl.appendChild(stat("锯机数量", sch.machine_count + " 台"));
    scheduleSummaryEl.appendChild(stat("每板准备", sch.setup_minutes + " 分钟"));
    scheduleSummaryEl.appendChild(stat("整体完工", sch.makespan + " 分钟", true));

    machineListEl.innerHTML = "";
    sch.machines.forEach(function (machine) {
      machineListEl.appendChild(renderMachine(machine, sch.setup_minutes));
    });

    scheduleTotalEl.innerHTML = "";
    var detail = document.createElement("span");
    detail.textContent =
      "合计：" + sch.machine_count + " 台锯机加工 " + s.board_count +
      " 块原板，同机按原板编号顺序加工";
    var price = document.createElement("span");
    price.className = "price";
    price.textContent = "最晚完工 " + sch.makespan + " 分钟";
    scheduleTotalEl.appendChild(detail);
    scheduleTotalEl.appendChild(price);

    scheduleBoardListEl.innerHTML = "";
    data.boards.forEach(function (board) {
      scheduleBoardListEl.appendChild(renderBoard(board, s.board_length));
    });

    placeholderEl.hidden = true;
    scheduleResultEl.hidden = false;
  }

  /* ---------- 分摊结果渲染 ---------- */

  function fenToYuan(fen) {
    var yuan = Math.floor(fen / 100);
    var cents = fen % 100;
    return yuan + "." + (cents < 10 ? "0" : "") + cents;
  }

  function exactShareText(share) {
    if (share.indexOf("/") === -1) return share + " 元";
    var parts = share.split("/");
    var approx = Number(parts[0]) / Number(parts[1]);
    return share + " 元 ≈ " + approx.toFixed(4) + " 元";
  }

  function renderAlloc(data) {
    var s = data.summary;
    allocSummaryEl.innerHTML = "";
    allocSummaryEl.appendChild(stat("合板订单", s.order_count + " 个"));
    allocSummaryEl.appendChild(stat("使用原板", s.board_count + " / " + s.available + " 根"));
    allocSummaryEl.appendChild(stat("零件总数", s.total_pieces + " 件"));
    allocSummaryEl.appendChild(stat("合板最优总价", s.total_price + " 元", true));

    allocRowsEl.innerHTML = "";
    data.orders.forEach(function (order) {
      var tr = document.createElement("tr");
      var nameTd = document.createElement("td");
      nameTd.textContent = order.name;
      var exactTd = document.createElement("td");
      exactTd.textContent = exactShareText(order.share_exact);
      var payTd = document.createElement("td");
      payTd.className = "pay";
      payTd.textContent = fenToYuan(order.pay_fen) + " 元";
      tr.appendChild(nameTd);
      tr.appendChild(exactTd);
      tr.appendChild(payTd);
      allocRowsEl.appendChild(tr);
    });
    allocTotalExactEl.textContent = s.total_price + " 元";
    allocTotalPayEl.textContent = fenToYuan(s.total_fen) + " 元";

    placeholderEl.hidden = true;
    allocResultEl.hidden = false;
  }

  /* ---------- 执行核销 ---------- */

  var STATUS_LABELS = {
    pending: "待加工",
    qualified: "合格",
    scrapped: "报废",
  };

  var currentBatchId = null;
  var currentBatchBoards = [];

  function newIdemKey() {
    return (
      "rpt-" + Date.now().toString(36) + "-" +
      Math.random().toString(36).slice(2, 8)
    );
  }

  function showReportError(msg) {
    reportErrorEl.textContent = msg;
    reportErrorEl.hidden = false;
    reportOkEl.hidden = true;
  }

  function showReportOk(msg) {
    reportOkEl.textContent = msg;
    reportOkEl.hidden = false;
    reportErrorEl.hidden = true;
  }

  // 各长度合格件数：统计所有「合格」板的切件。
  function renderQualified(boards) {
    var counts = {};
    boards.forEach(function (board) {
      if (board.status !== "qualified") return;
      board.cuts.forEach(function (len) {
        counts[len] = (counts[len] || 0) + 1;
      });
    });
    var lengths = Object.keys(counts)
      .map(Number)
      .sort(function (a, b) {
        return b - a;
      });

    qualifiedListEl.innerHTML = "";
    if (!lengths.length) {
      var empty = document.createElement("span");
      empty.className = "qualified-empty";
      empty.textContent = "暂无合格零件（尚无核销为合格的板）";
      qualifiedListEl.appendChild(empty);
      return;
    }
    lengths.forEach(function (len) {
      var chip = document.createElement("span");
      chip.className = "chip qualified-chip";
      chip.textContent = "长度 " + len + " × " + counts[len] + " 件";
      qualifiedListEl.appendChild(chip);
    });
  }

  function renderBatchBoard(board, boardLength) {
    var card = renderBoard(board, boardLength);
    var dispatchedCuts = board.dispatched_cuts || [];

    var badge = document.createElement("span");
    badge.className = "status-badge st-" + board.status;
    badge.textContent = STATUS_LABELS[board.status] || board.status;
    card.querySelector(".board-head").appendChild(badge);

    // 已发料切件标注：板头徽标 + 逐切件标记。
    if (dispatchedCuts.length) {
      var dBadge = document.createElement("span");
      dBadge.className = "status-badge st-dispatched";
      dBadge.textContent = "已发料 " + dispatchedCuts.length + " 件";
      card.querySelector(".board-head").appendChild(dBadge);
    }

    // 待加工板附核销选择：暂不核销 / 合格 / 报废。
    if (board.status === "pending") {
      var choices = document.createElement("div");
      choices.className = "report-choices";
      choices.setAttribute("data-board-no", String(board.board_no));
      [
        ["", "暂不核销", true],
        ["qualified", "合格", false],
        ["scrapped", "报废", false],
      ].forEach(function (opt) {
        var label = document.createElement("label");
        var input = document.createElement("input");
        input.type = "radio";
        input.name = "result-" + board.board_no;
        input.value = opt[0];
        input.checked = opt[2];
        label.appendChild(input);
        label.appendChild(document.createTextNode(" " + opt[1]));
        choices.appendChild(label);
      });
      card.appendChild(choices);
    }

    // 合格板逐切件录入实测长度；留空的切件不参与复核。
    if (board.status === "qualified") {
      var measure = document.createElement("div");
      measure.className = "measure-block";
      measure.setAttribute("data-board-no", String(board.board_no));

      var title = document.createElement("div");
      title.className = "measure-title";
      title.textContent = "实测长度（留空不参与复核）";
      measure.appendChild(title);

      var grid = document.createElement("div");
      grid.className = "measure-grid";
      board.cuts.forEach(function (planned, cutIdx) {
        var dispatched = dispatchedCuts.indexOf(cutIdx + 1) !== -1;
        var cell = document.createElement("label");
        cell.className = "measure-cell" + (dispatched ? " dispatched" : "");
        var tag = document.createElement("span");
        tag.className = "measure-tag";
        tag.textContent =
          "切件 " + (cutIdx + 1) + " · 计划 " + planned +
          (dispatched ? " · 已发料" : "");
        var input = document.createElement("input");
        input.type = "number";
        input.min = "1";
        input.step = "1";
        input.inputMode = "numeric";
        input.className = "measure-input";
        input.setAttribute("data-cut-no", String(cutIdx + 1));
        input.setAttribute("data-planned", String(planned));
        if (dispatched) {
          // 已发料切件不参与实测录入。
          input.disabled = true;
          input.placeholder = "已发料";
        }
        cell.appendChild(tag);
        cell.appendChild(input);
        grid.appendChild(cell);
      });
      measure.appendChild(grid);
      card.appendChild(measure);
    }
    return card;
  }

  function renderBatchView(data) {
    currentBatchId = data.batch_id;
    currentBatchBoards = data.boards;

    var counts = { pending: 0, qualified: 0, scrapped: 0 };
    var dispatchedTotal = 0;
    data.boards.forEach(function (board) {
      counts[board.status] = (counts[board.status] || 0) + 1;
      dispatchedTotal += (board.dispatched_cuts || []).length;
    });

    batchSummaryEl.innerHTML = "";
    batchSummaryEl.appendChild(stat("批次号", "#" + data.batch_id));
    batchSummaryEl.appendChild(stat("当前版本", "v" + data.version, true));
    batchSummaryEl.appendChild(stat("待加工", counts.pending + " 板"));
    batchSummaryEl.appendChild(stat("合格", counts.qualified + " 板"));
    batchSummaryEl.appendChild(stat("报废", counts.scrapped + " 板"));
    batchSummaryEl.appendChild(stat("已发料切件", dispatchedTotal + " 件"));
    batchSummaryEl.appendChild(
      stat("使用原板", data.summary.board_count + " / " + data.summary.available + " 根")
    );

    renderQualified(data.boards);

    batchBoardListEl.innerHTML = "";
    data.boards.forEach(function (board) {
      batchBoardListEl.appendChild(
        renderBatchBoard(board, data.summary.board_length)
      );
    });

    // 重置核销表单：换新幂等键、期望版本对齐当前版本。
    idemKeyEl.value = newIdemKey();
    expectedVersionEl.value = String(data.version);
    reportErrorEl.hidden = true;
    reportOkEl.hidden = true;
    var hasPending = counts.pending > 0;
    reportSectionEl.hidden = !hasPending;
    batchDoneEl.hidden = hasPending;

    // 实测复核仅对存在合格板的批次开放；重新打开/核销后清空上次预览。
    var hasQualified = counts.qualified > 0;
    qualitySectionEl.hidden = !hasQualified;
    qualityResultEl.hidden = true;
    qualityErrorEl.hidden = true;
    qualityErrorEl.textContent = "";

    // 错缝拼板预览同样仅对存在合格板的批次开放；重建选件勾选区。
    jointSectionEl.hidden = !hasQualified;
    jointResultEl.hidden = true;
    jointErrorEl.hidden = true;
    jointErrorEl.textContent = "";
    jointWarnEl.hidden = true;
    jointWarnEl.textContent = "";
    renderJointPicks(data.boards);

    placeholderEl.hidden = true;
    batchResultEl.hidden = false;
  }

  createBatchBtn.addEventListener("click", function () {
    var collected = collectPayload();
    if (collected.error) {
      showFormError(collected.error);
      return;
    }

    createBatchBtn.disabled = true;
    createBatchBtn.textContent = "求解中…";

    postJson("/api/batches", collected.payload)
      .then(function (r) {
        if (!r.ok) {
          showFormError(r.body.error || "服务器未能处理该请求");
          return;
        }
        if (r.body.feasible === false) {
          showNoSolution(r.body.reason || "不存在可行的裁切方案");
          return;
        }
        openBatchIdEl.value = String(r.body.batch_id);
        renderBatchView(r.body);
      })
      .catch(function () {
        showFormError("网络错误，请确认服务已启动后重试");
      })
      .finally(function () {
        createBatchBtn.disabled = false;
        createBatchBtn.textContent = "求解并创建核销批次";
      });
  });

  openBatchBtn.addEventListener("click", function () {
    var raw = openBatchIdEl.value.trim();
    if (!/^\d+$/.test(raw) || Number(raw) <= 0) {
      openBatchIdEl.classList.add("invalid");
      showFormError("批次 ID 必须为正整数");
      return;
    }
    openBatchIdEl.classList.remove("invalid");
    hideMessages();

    openBatchBtn.disabled = true;
    fetch("/api/batches/" + raw)
      .then(function (resp) {
        return resp.json().then(function (body) {
          return { ok: resp.ok, body: body };
        });
      })
      .then(function (r) {
        if (!r.ok) {
          showFormError(r.body.error || "批次不存在");
          return;
        }
        renderBatchView(r.body);
      })
      .catch(function () {
        showFormError("网络错误，请确认服务已启动后重试");
      })
      .finally(function () {
        openBatchBtn.disabled = false;
      });
  });

  reportBtn.addEventListener("click", function () {
    if (currentBatchId == null) return;
    reportErrorEl.hidden = true;
    reportOkEl.hidden = true;

    var key = idemKeyEl.value.trim();
    if (!key) {
      showReportError("幂等键不能为空");
      return;
    }
    var versionRaw = expectedVersionEl.value.trim();
    if (!/^\d+$/.test(versionRaw)) {
      showReportError("期望版本必须为非负整数");
      return;
    }

    var results = [];
    batchBoardListEl
      .querySelectorAll(".report-choices")
      .forEach(function (choices) {
        var checked = choices.querySelector("input:checked");
        if (checked && checked.value) {
          results.push({
            board_no: Number(choices.getAttribute("data-board-no")),
            result: checked.value,
          });
        }
      });
    if (results.length === 0) {
      showReportError("请至少为一块待加工板选择「合格」或「报废」");
      return;
    }

    reportBtn.disabled = true;
    reportBtn.textContent = "提交中…";

    postJson("/api/batches/" + currentBatchId + "/reports", {
      idem_key: key,
      expected_version: Number(versionRaw),
      results: results,
    })
      .then(function (r) {
        if (!r.ok) {
          showReportError(r.body.error || "服务器未能处理该请求");
          return;
        }
        renderBatchView(r.body);
        showReportOk(
          "核销成功：本批更新 " + r.body.updated.length +
          " 板，当前版本 v" + r.body.version + "。"
        );
      })
      .catch(function () {
        // 网络失败时保留幂等键，重试仍为同一逻辑操作。
        showReportError("网络错误，请确认服务已启动后重试");
      })
      .finally(function () {
        reportBtn.disabled = false;
        reportBtn.textContent = "提交核销结果";
      });
  });

  /* ---------- 实测尺寸复核 ---------- */

  function showQualityError(msg) {
    qualityErrorEl.textContent = msg;
    qualityErrorEl.hidden = false;
    qualityResultEl.hidden = true;
  }

  function collectMeasurements() {
    var measurements = [];
    var blocks = batchBoardListEl.querySelectorAll(".measure-block");
    for (var b = 0; b < blocks.length; b++) {
      var boardNo = Number(blocks[b].getAttribute("data-board-no"));
      var inputs = blocks[b].querySelectorAll(".measure-input");
      for (var i = 0; i < inputs.length; i++) {
        var raw = inputs[i].value.trim();
        inputs[i].classList.remove("invalid");
        if (raw === "") continue; // 未录入的切件不参与本次复核
        if (!/^\d+$/.test(raw) || Number(raw) <= 0) {
          inputs[i].classList.add("invalid");
          return {
            error:
              "第 " + boardNo + " 块板切件 " +
              inputs[i].getAttribute("data-cut-no") +
              " 的实测长度必须为正整数",
          };
        }
        measurements.push({
          board_no: boardNo,
          cut_no: Number(inputs[i].getAttribute("data-cut-no")),
          actual_length: Number(raw),
        });
      }
    }
    return { measurements: measurements };
  }

  function renderQualityPreview(data) {
    qualitySummaryEl.innerHTML = "";
    qualitySummaryEl.appendChild(stat("需求件", data.demand_count + " 件"));
    qualitySummaryEl.appendChild(stat("已录实测", data.measured_count + " 件"));
    qualitySummaryEl.appendChild(stat("已满足", data.matched_count + " 件", true));
    qualitySummaryEl.appendChild(stat("未分配实测", data.unassigned_count + " 件"));
    qualitySummaryEl.appendChild(stat("总长度偏差", data.total_deviation));
    qualitySummaryEl.appendChild(stat("公差", "±" + data.tolerance));

    // 需求件编号（按录入顺序展开）。
    qualityDemandListEl.innerHTML = "";
    data.demands.forEach(function (d) {
      var chip = document.createElement("span");
      chip.className = "chip qualified-chip";
      chip.textContent = "#" + d.demand_no + " 长度 " + d.length;
      qualityDemandListEl.appendChild(chip);
    });

    // 逐件去向（已按板号、切件序号排列）。
    qualityRowsEl.innerHTML = "";
    data.assignments.forEach(function (item) {
      var tr = document.createElement("tr");

      var tdBoard = document.createElement("td");
      tdBoard.textContent = "板 " + item.board_no;
      var tdCut = document.createElement("td");
      tdCut.textContent = "切件 " + item.cut_no;
      var tdPlanned = document.createElement("td");
      tdPlanned.textContent = item.planned_length;
      var tdActual = document.createElement("td");
      tdActual.textContent = item.actual_length;

      var tdDest = document.createElement("td");
      if (item.assigned) {
        tdDest.textContent =
          "→ 需求件 #" + item.demand_no + "（长度 " + item.demand_length + "）";
        tdDest.className = "dest-assigned";
      } else {
        tdDest.textContent = "未分配";
        tdDest.className = "dest-unassigned";
      }

      var tdDev = document.createElement("td");
      tdDev.textContent = item.assigned ? item.deviation : "—";

      tr.appendChild(tdBoard);
      tr.appendChild(tdCut);
      tr.appendChild(tdPlanned);
      tr.appendChild(tdActual);
      tr.appendChild(tdDest);
      tr.appendChild(tdDev);
      qualityRowsEl.appendChild(tr);
    });

    // 未分配实测件。
    qualityUnassignedEl.innerHTML = "";
    if (!data.unassigned.length) {
      var none = document.createElement("span");
      none.className = "qualified-empty";
      none.textContent = "全部实测件均已分配";
      qualityUnassignedEl.appendChild(none);
    } else {
      data.unassigned.forEach(function (item) {
        var chip = document.createElement("span");
        chip.className = "chip shortage-chip";
        chip.textContent =
          "板 " + item.board_no + " 切件 " + item.cut_no +
          " 实测 " + item.actual_length + "（计划 " + item.planned_length + "）";
        qualityUnassignedEl.appendChild(chip);
      });
    }

    // 各需求长度缺件数。
    qualityShortageEl.innerHTML = "";
    data.shortages.forEach(function (row) {
      var chip = document.createElement("span");
      chip.className = "chip " + (row.shortage > 0 ? "shortage-chip" : "qualified-chip");
      chip.textContent =
        "长度 " + row.length + "：需 " + row.required +
        " 件 · 已满足 " + row.matched + " 件 · 缺 " + row.shortage + " 件";
      qualityShortageEl.appendChild(chip);
    });

    qualityErrorEl.hidden = true;
    qualityResultEl.hidden = false;
  }

  qualityBtn.addEventListener("click", function () {
    if (currentBatchId == null) return;
    qualityErrorEl.hidden = true;

    var tolRaw = qualityToleranceEl.value.trim();
    if (!/^\d+$/.test(tolRaw)) {
      qualityToleranceEl.classList.add("invalid");
      showQualityError("公差必须为非负整数");
      return;
    }
    qualityToleranceEl.classList.remove("invalid");

    var collected = collectMeasurements();
    if (collected.error) {
      showQualityError(collected.error);
      return;
    }

    qualityBtn.disabled = true;
    qualityBtn.textContent = "复核中…";

    postJson("/api/batches/" + currentBatchId + "/quality-preview", {
      tolerance: Number(tolRaw),
      measurements: collected.measurements,
    })
      .then(function (r) {
        if (!r.ok) {
          showQualityError(r.body.error || "服务器未能处理该请求");
          return;
        }
        renderQualityPreview(r.body);
      })
      .catch(function () {
        showQualityError("网络错误，请确认服务已启动后重试");
      })
      .finally(function () {
        qualityBtn.disabled = false;
        qualityBtn.textContent = "执行实测复核";
      });
  });

  /* ---------- 合格切件错缝拼板预览 ---------- */

  function showJointError(msg) {
    jointErrorEl.textContent = msg;
    jointErrorEl.hidden = false;
    jointWarnEl.hidden = true;
    jointResultEl.hidden = true;
  }

  function showJointWarn(msg) {
    jointWarnEl.textContent = msg;
    jointWarnEl.hidden = false;
    jointErrorEl.hidden = true;
    jointResultEl.hidden = true;
  }

  // 选件勾选区：按合格板逐件列出切件复选框；已发料切件禁用并标注。
  function renderJointPicks(boards) {
    jointPickListEl.innerHTML = "";
    boards.forEach(function (board) {
      if (board.status !== "qualified") return;
      var dispatchedCuts = board.dispatched_cuts || [];
      var row = document.createElement("div");
      row.className = "joint-pick-board";
      var tag = document.createElement("span");
      tag.className = "joint-pick-board-tag";
      tag.textContent = "板 " + board.board_no;
      row.appendChild(tag);
      board.cuts.forEach(function (len, cutIdx) {
        var dispatched = dispatchedCuts.indexOf(cutIdx + 1) !== -1;
        var label = document.createElement("label");
        label.className = "joint-pick" + (dispatched ? " dispatched" : "");
        var box = document.createElement("input");
        box.type = "checkbox";
        box.className = "joint-pick-box";
        box.setAttribute("data-board-no", String(board.board_no));
        box.setAttribute("data-cut-no", String(cutIdx + 1));
        if (dispatched) {
          box.disabled = true;
          label.title = "该切件已发料，不能参与拼板";
        }
        box.addEventListener("change", function () {
          var checked = jointPickListEl.querySelectorAll(".joint-pick-box:checked");
          if (checked.length > 10) {
            box.checked = false;
            showJointError("最多选择 10 件切件");
            return;
          }
          jointErrorEl.hidden = true;
        });
        label.appendChild(box);
        label.appendChild(
          document.createTextNode(
            " 件 " + (cutIdx + 1) + " · 长 " + len +
            (dispatched ? " · 已发料" : "")
          )
        );
        row.appendChild(label);
      });
      jointPickListEl.appendChild(row);
    });
  }

  function renderJointRow(row) {
    var card = document.createElement("div");
    card.className = "joint-row-card";

    var head = document.createElement("div");
    head.className = "board-head";
    var no = document.createElement("span");
    no.className = "no";
    no.textContent = "第 " + row.row_no + " 行";
    var meta = document.createElement("span");
    meta.className = "meta";
    meta.textContent = row.piece_count + " 件 · 行长 " + row.total_length;
    head.appendChild(no);
    head.appendChild(meta);
    card.appendChild(head);

    // 等宽木条比例条：段边界即接缝。
    var bar = document.createElement("div");
    bar.className = "bar joint-bar";
    row.pieces.forEach(function (piece, idx) {
      var seg = document.createElement("div");
      seg.className = "seg-piece" + (idx % 2 === 0 ? "" : " alt");
      seg.style.flexGrow = String(piece.length);
      seg.title =
        "板 " + piece.board_no + " 件 " + piece.cut_no +
        " · 长 " + piece.length;
      bar.appendChild(seg);
    });
    card.appendChild(bar);

    var jointsLine = document.createElement("div");
    jointsLine.className = "joint-joints";
    jointsLine.textContent = row.joints.length
      ? "接缝位置：" + row.joints.join("、")
      : "无接缝（单件整行）";
    card.appendChild(jointsLine);

    var chips = document.createElement("div");
    chips.className = "cut-list";
    row.pieces.forEach(function (piece) {
      var chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent =
        "板 " + piece.board_no + " 件 " + piece.cut_no +
        "（" + piece.length + "）";
      chips.appendChild(chip);
    });
    card.appendChild(chips);

    return card;
  }

  function renderJointPreview(data) {
    jointSummaryEl.innerHTML = "";
    jointSummaryEl.appendChild(stat("目标行长", data.target_length));
    jointSummaryEl.appendChild(stat("行数", data.row_count + " 行"));
    jointSummaryEl.appendChild(stat("最小错缝", data.min_stagger));
    jointSummaryEl.appendChild(stat("选件", data.selected_count + " 件"));
    jointSummaryEl.appendChild(stat("用件", data.used_count + " 件", true));
    jointSummaryEl.appendChild(stat("余件", data.unused_count + " 件"));

    jointRowListEl.innerHTML = "";
    data.rows.forEach(function (row) {
      jointRowListEl.appendChild(renderJointRow(row));
    });

    jointUnusedEl.innerHTML = "";
    if (!data.unused.length) {
      var none = document.createElement("span");
      none.className = "qualified-empty";
      none.textContent = "无余件（所选切件全部用完）";
      jointUnusedEl.appendChild(none);
    } else {
      data.unused.forEach(function (item) {
        var chip = document.createElement("span");
        chip.className = "chip shortage-chip";
        chip.textContent =
          "板 " + item.board_no + " 件 " + item.cut_no +
          " · 长 " + item.length;
        jointUnusedEl.appendChild(chip);
      });
    }

    jointErrorEl.hidden = true;
    jointWarnEl.hidden = true;
    jointResultEl.hidden = false;
  }

  jointBtn.addEventListener("click", function () {
    if (currentBatchId == null) return;
    jointErrorEl.hidden = true;
    jointWarnEl.hidden = true;
    jointResultEl.hidden = true;

    var targetRes = readPositiveInt(jointTargetEl, "目标行长");
    if (targetRes.error) {
      showJointError(targetRes.error);
      return;
    }

    var rowsRaw = jointRowsEl.value.trim();
    if (!/^\d+$/.test(rowsRaw) || Number(rowsRaw) < 2 || Number(rowsRaw) > 4) {
      jointRowsEl.classList.add("invalid");
      showJointError("行数必须为 2～4 的整数");
      return;
    }
    jointRowsEl.classList.remove("invalid");

    var staggerRes = readNonnegInt(jointStaggerEl, "最小错缝距离");
    if (staggerRes.error) {
      showJointError(staggerRes.error);
      return;
    }

    var picks = [];
    jointPickListEl
      .querySelectorAll(".joint-pick-box:checked")
      .forEach(function (box) {
        picks.push({
          board_no: Number(box.getAttribute("data-board-no")),
          cut_no: Number(box.getAttribute("data-cut-no")),
        });
      });
    if (picks.length < 1 || picks.length > 10) {
      showJointError("请勾选 1～10 件合格切件");
      return;
    }

    jointBtn.disabled = true;
    jointBtn.textContent = "求解中…";

    postJson("/api/batches/" + currentBatchId + "/joint-preview", {
      pieces: picks,
      target_length: targetRes.value,
      row_count: Number(rowsRaw),
      min_stagger: staggerRes.value,
    })
      .then(function (r) {
        if (!r.ok) {
          showJointError(r.body.error || "服务器未能处理该请求");
          return;
        }
        if (r.body.feasible === false) {
          showJointWarn("无解：" + (r.body.reason || "不存在可行的拼板排布"));
          return;
        }
        renderJointPreview(r.body);
      })
      .catch(function () {
        showJointError("网络错误，请确认服务已启动后重试");
      })
      .finally(function () {
        jointBtn.disabled = false;
        jointBtn.textContent = "生成错缝拼板预览";
      });
  });

  /* ---------- 跨批次合格切件发料单 ---------- */

  function newDispatchIdemKey() {
    return (
      "dsp-" + Date.now().toString(36) + "-" +
      Math.random().toString(36).slice(2, 8)
    );
  }

  function showDispatchError(msg) {
    dispatchErrorEl.textContent = msg;
    dispatchErrorEl.hidden = false;
    dispatchOkEl.hidden = true;
  }

  function showDispatchOk(msg) {
    dispatchOkEl.textContent = msg;
    dispatchOkEl.hidden = false;
    dispatchErrorEl.hidden = true;
  }

  function renumberDispatchPieces() {
    var rows = dispatchPieceRowsEl.querySelectorAll(".dispatch-row");
    rows.forEach(function (row, i) {
      row.querySelector(".idx").textContent = String(i + 1);
      // 至少保留一行时，唯一一行禁用删除；达到 10 件时禁用添加。
      row.querySelector(".btn-del").disabled = rows.length <= 1;
    });
    addDispatchPieceBtn.disabled = rows.length >= 10;
  }

  function makeDispatchPieceRow(batchId, boardNo, cutNo) {
    var row = document.createElement("div");
    row.className = "parts-row dispatch-row";
    row.innerHTML =
      '<span class="idx"></span>' +
      '<input class="dp-batch" type="number" min="1" step="1" inputmode="numeric" placeholder="批次 ID" />' +
      '<input class="dp-board" type="number" min="1" step="1" inputmode="numeric" placeholder="板号" />' +
      '<input class="dp-cut" type="number" min="1" step="1" inputmode="numeric" placeholder="切件序号" />' +
      '<button type="button" class="btn-del">删除</button>';
    row.querySelector(".dp-batch").value = batchId != null ? batchId : "";
    row.querySelector(".dp-board").value = boardNo != null ? boardNo : "";
    row.querySelector(".dp-cut").value = cutNo != null ? cutNo : "";
    row.querySelector(".btn-del").addEventListener("click", function () {
      if (dispatchPieceRowsEl.querySelectorAll(".dispatch-row").length > 1) {
        row.remove();
        renumberDispatchPieces();
      }
    });
    dispatchPieceRowsEl.appendChild(row);
    renumberDispatchPieces();
  }

  addDispatchPieceBtn.addEventListener("click", function () {
    if (dispatchPieceRowsEl.querySelectorAll(".dispatch-row").length < 10) {
      makeDispatchPieceRow();
    }
  });

  // 预置一行空切件
  makeDispatchPieceRow();

  function collectDispatchPieces() {
    var rows = dispatchPieceRowsEl.querySelectorAll(".dispatch-row");
    if (rows.length < 1 || rows.length > 10) {
      return { error: "切件数量须为 1～10 件" };
    }
    var pieces = [];
    var seen = {};
    for (var i = 0; i < rows.length; i++) {
      var label = "第 " + (i + 1) + " 件切件的";
      var batchRes = readPositiveInt(
        rows[i].querySelector(".dp-batch"), label + "批次 ID"
      );
      if (batchRes.error) return { error: batchRes.error };
      var boardRes = readPositiveInt(
        rows[i].querySelector(".dp-board"), label + "板号"
      );
      if (boardRes.error) return { error: boardRes.error };
      var cutRes = readPositiveInt(
        rows[i].querySelector(".dp-cut"), label + "切件序号"
      );
      if (cutRes.error) return { error: cutRes.error };

      var dupKey = batchRes.value + "-" + boardRes.value + "-" + cutRes.value;
      if (seen[dupKey]) {
        return {
          error:
            "第 " + (i + 1) + " 件切件（批次 " + batchRes.value +
            " 板 " + boardRes.value + " 切件 " + cutRes.value + "）与前面重复",
        };
      }
      seen[dupKey] = true;
      pieces.push({
        batch_id: batchRes.value,
        board_no: boardRes.value,
        cut_no: cutRes.value,
      });
    }
    return { pieces: pieces };
  }

  function renderDispatchView(data) {
    dispatchSummaryEl.innerHTML = "";
    dispatchSummaryEl.appendChild(stat("发料单号", "#" + data.dispatch_id, true));
    dispatchSummaryEl.appendChild(stat("用途", data.purpose));
    dispatchSummaryEl.appendChild(stat("切件数", data.piece_count + " 件"));
    dispatchSummaryEl.appendChild(stat("幂等键", data.idem_key));
    dispatchSummaryEl.appendChild(stat("创建时间", data.created_at));

    dispatchRowsEl.innerHTML = "";
    data.pieces.forEach(function (piece) {
      var tr = document.createElement("tr");
      [piece.batch_id, piece.board_no, piece.cut_no, piece.length].forEach(
        function (text) {
          var td = document.createElement("td");
          td.textContent = String(text);
          tr.appendChild(td);
        }
      );
      dispatchRowsEl.appendChild(tr);
    });

    placeholderEl.hidden = true;
    dispatchResultEl.hidden = false;
  }

  dispatchBtn.addEventListener("click", function () {
    dispatchErrorEl.hidden = true;
    dispatchOkEl.hidden = true;
    document.querySelectorAll("#dispatchPieceRows input.invalid").forEach(
      function (el) {
        el.classList.remove("invalid");
      }
    );

    var purpose = dispatchPurposeEl.value.trim();
    if (!purpose) {
      dispatchPurposeEl.classList.add("invalid");
      showDispatchError("用途不能为空");
      return;
    }
    dispatchPurposeEl.classList.remove("invalid");

    var key = dispatchIdemKeyEl.value.trim();
    if (!key) {
      dispatchIdemKeyEl.classList.add("invalid");
      showDispatchError("幂等键不能为空");
      return;
    }
    dispatchIdemKeyEl.classList.remove("invalid");

    var collected = collectDispatchPieces();
    if (collected.error) {
      showDispatchError(collected.error);
      return;
    }

    dispatchBtn.disabled = true;
    dispatchBtn.textContent = "提交中…";

    postJson("/api/dispatches", {
      idem_key: key,
      purpose: purpose,
      pieces: collected.pieces,
    })
      .then(function (r) {
        if (!r.ok) {
          // 400/409：整单未写入，保留幂等键便于修正或重试。
          showDispatchError(r.body.error || "服务器未能处理该请求");
          return;
        }
        renderDispatchView(r.body);
        if (r.status === 201) {
          showDispatchOk(
            "发料单已创建：#" + r.body.dispatch_id + "，共 " +
            r.body.piece_count + " 件；切件长度与归属已冻结，不得再发料。"
          );
        } else {
          showDispatchOk(
            "同一幂等键与载荷的重试：返回原发料单 #" + r.body.dispatch_id +
            "，共 " + r.body.piece_count + " 件。"
          );
        }
        // 成功后更换幂等键，下一次提交视为新的逻辑操作。
        dispatchIdemKeyEl.value = newDispatchIdemKey();
      })
      .catch(function () {
        // 网络失败时保留幂等键，重试仍为同一逻辑操作。
        showDispatchError("网络错误，请确认服务已启动后重试");
      })
      .finally(function () {
        dispatchBtn.disabled = false;
        dispatchBtn.textContent = "提交发料单";
      });
  });

  openDispatchBtn.addEventListener("click", function () {
    var raw = openDispatchIdEl.value.trim();
    if (!/^\d+$/.test(raw) || Number(raw) <= 0) {
      openDispatchIdEl.classList.add("invalid");
      showDispatchError("发料单 ID 必须为正整数");
      return;
    }
    openDispatchIdEl.classList.remove("invalid");
    dispatchErrorEl.hidden = true;
    dispatchOkEl.hidden = true;

    openDispatchBtn.disabled = true;
    fetch("/api/dispatches/" + raw)
      .then(function (resp) {
        return resp.json().then(function (body) {
          return { ok: resp.ok, body: body };
        });
      })
      .then(function (r) {
        if (!r.ok) {
          showDispatchError(r.body.error || "发料单不存在");
          return;
        }
        renderDispatchView(r.body);
      })
      .catch(function () {
        showDispatchError("网络错误，请确认服务已启动后重试");
      })
      .finally(function () {
        openDispatchBtn.disabled = false;
      });
  });

  /* ---------- 提交 ---------- */

  function postJson(url, payload) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(function (resp) {
      return resp.json().then(function (body) {
        return { ok: resp.ok, status: resp.status, body: body };
      });
    });
  }

  solveBtn.addEventListener("click", function () {
    var collected = collectPayload();
    if (collected.error) {
      showFormError(collected.error);
      return;
    }

    solveBtn.disabled = true;
    solveBtn.textContent = "计算中…";

    postJson("/api/solve", collected.payload)
      .then(function (r) {
        if (!r.ok) {
          showFormError(r.body.error || "服务器未能处理该请求");
          return;
        }
        if (!r.body.feasible) {
          showNoSolution(r.body.reason || "不存在可行的裁切方案");
          return;
        }
        renderResult(r.body);
      })
      .catch(function () {
        showFormError("网络错误，请确认服务已启动后重试");
      })
      .finally(function () {
        solveBtn.disabled = false;
        solveBtn.textContent = "计算最优方案";
      });
  });

  scheduleBtn.addEventListener("click", function () {
    var collected = collectSchedulePayload();
    if (collected.error) {
      showFormError(collected.error);
      return;
    }

    scheduleBtn.disabled = true;
    scheduleBtn.textContent = "计算中…";

    postJson("/api/schedule", collected.payload)
      .then(function (r) {
        if (!r.ok) {
          showFormError(r.body.error || "服务器未能处理该请求");
          return;
        }
        if (!r.body.feasible) {
          showNoSolution(r.body.reason || "不存在可行的裁切方案");
          return;
        }
        renderSchedule(r.body);
      })
      .catch(function () {
        showFormError("网络错误，请确认服务已启动后重试");
      })
      .finally(function () {
        scheduleBtn.disabled = false;
        scheduleBtn.textContent = "计算最优排程";
      });
  });

  allocBtn.addEventListener("click", function () {
    var collected = collectAllocPayload();
    if (collected.error) {
      showFormError(collected.error);
      return;
    }

    allocBtn.disabled = true;
    allocBtn.textContent = "计算中…";

    postJson("/api/allocate", collected.payload)
      .then(function (r) {
        if (!r.ok) {
          showFormError(r.body.error || "服务器未能处理该请求");
          return;
        }
        if (!r.body.feasible) {
          showNoSolution(r.body.reason || "全部订单合板不存在可行的裁切方案");
          return;
        }
        renderAlloc(r.body);
      })
      .catch(function () {
        showFormError("网络错误，请确认服务已启动后重试");
      })
      .finally(function () {
        allocBtn.disabled = false;
        allocBtn.textContent = "计算费用分摊";
      });
  });
})();

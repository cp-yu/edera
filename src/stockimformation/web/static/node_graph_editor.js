(function () {
  const canvas = document.getElementById("ng-canvas");
  const paletteList = document.getElementById("ng-palette-list");
  const inspectorBody = document.getElementById("ng-inspector-body");
  const dagSelect = document.getElementById("ng-dag-select");
  const saveBtn = document.getElementById("ng-save-dag-btn");
  const errorEl = document.getElementById("ng-error");
  const dagLabel = document.getElementById("ng-dag-label");

  let graph = null;
  let canvasRenderer = null;
  let prototypes = [];
  let selectedNodeId = null;
  let runtimeStatuses = {};

  /* ---- LiteGraph custom node type ---- */
  function StockNode() {
    this.title = "Loading...";
    this.properties = { node_name: "" };
    this.size = [180, 80];

    this.addOutput("out", "data");
    this.addInput("in", "data");

    this.overrideColors = null;
    this.statusVisible = true;
  }

  StockNode.title = "StockNode";
  StockNode.prototype.onDrawForeground = function (ctx) {
    if (this.overrideColors) {
      const h = this.size[1];
      const w = this.size[0];
      ctx.save();
      ctx.fillStyle = this.overrideColors.bg || "rgba(200,200,200,0.15)";
      ctx.fillRect(0, 0, w, h);
      if (this.overrideColors.text) {
        ctx.fillStyle = this.overrideColors.text;
        ctx.font = "11px Arial, Noto Sans SC, sans-serif";
        ctx.fillText(this.statusText || "", 8, h - 8);
      }
      ctx.restore();
    }
  };

  function makeNodeClass(proto) {
    const ctor = function () {
      this.title = proto.name;
      this.properties = { node_name: proto.name, type: proto.type };
      this.size = [180, 80];
      this.overrideColors = null;
      this.statusText = "";
    };
    ctor.title = proto.name;
    ctor.prototype = Object.create(StockNode.prototype);

    ctor.prototype.onAdded = function () {
      this.title = proto.name;
      this.properties.node_name = proto.name;
      this.properties.type = proto.type;

      if (this.inputs) {
        this.inputs.length = 0;
      }
      if (this.outputs) {
        this.outputs.length = 0;
      }

      const inputLabel = proto.input_type || "any";
      const outputLabel = proto.output_type || "any";
      this.addInput(inputLabel, inputLabel);

      if (proto.type === "function") {
        if (outputLabel === "any") {
          this.addOutput("out", "data");
        } else {
          this.addOutput(outputLabel, outputLabel);
        }
      } else {
        this.addOutput("out", "data");
        if (proto.output_type && proto.output_type !== "any" && proto.output_type !== "out") {
          this.addOutput(proto.output_type, proto.output_type);
        }
      }

      if (proto.type === "function" && proto.input_type && proto.input_type !== "any") {
        this.inputs.length = 0;
        this.addInput(proto.input_type, proto.input_type);
      }
    };

    return ctor;
  }

  /* ---- Error display ---- */
  function showError(msg) {
    errorEl.textContent = msg;
    errorEl.style.display = "block";
    setTimeout(function () {
      errorEl.style.display = "none";
    }, 8000);
  }

  /* ---- API helpers ---- */
  async function apiGet(url) {
    const resp = await fetch(url);
    if (!resp.ok) {
      const body = await resp.json().catch(function () { return {}; });
      const msg = body.error ? body.error.message : resp.statusText;
      throw new Error(msg);
    }
    return resp.json();
  }

  async function apiPut(url, data) {
    const resp = await fetch(url, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!resp.ok) {
      const body = await resp.json().catch(function () { return {}; });
      const msg = body.error ? body.error.message : resp.statusText;
      throw new Error(msg);
    }
    return resp.json();
  }

  /* ---- Graph serialization ---- */
  function serializeGraph() {
    if (!graph) {
      return { nodes: [], edges: [], ui: {} };
    }
    const nodes = [];
    const edges = [];
    const uiNodes = {};

    for (let i = 0; i < graph._nodes.length; i++) {
      const node = graph._nodes[i];
      nodes.push({
        name: node.properties.node_name || node.title,
        type: node.properties.type || "",
        input_type: node.inputs[0] ? node.inputs[0].name : "any",
        output_type: node.outputs[0] ? node.outputs[0].name : "any",
      });
      uiNodes[node.properties.node_name || node.title] = {
        x: Math.round(node.pos[0]),
        y: Math.round(node.pos[1]),
      };
    }

    for (let i = 0; i < graph._links.length; i++) {
      const linkId = graph._links[i];
      const link = graph.links[linkId];
      if (!link) {
        continue;
      }
      const fromNode = graph.getNodeById(link.origin_id);
      const toNode = graph.getNodeById(link.target_id);
      if (!fromNode || !toNode) {
        continue;
      }
      edges.push({
        from: fromNode.properties.node_name || fromNode.title,
        to: toNode.properties.node_name || toNode.title,
      });
    }

    return { nodes: nodes, edges: edges, ui: { nodes: uiNodes } };
  }

  function deserializeGraph(data) {
    graph.clear();
    const uiNodes = data.ui && data.ui.nodes ? data.ui.nodes : {};
    const nodeMap = {};

    for (let i = 0; i < data.nodes.length; i++) {
      const nodeData = data.nodes[i];
      const nodeName = nodeData.name || nodeData;
      const proto = prototypes.find(function (p) { return p.name === nodeName; });
      const NodeClass = proto
        ? LiteGraph.registered_node_types[proto.name] || StockNode
        : StockNode;
      const node = LiteGraph.createNode(NodeClass);
      if (!node) {
        continue;
      }
      node.properties.node_name = nodeName;
      node.properties.type = proto ? proto.type : "";
      node.title = nodeName;

      if (uiNodes[nodeName]) {
        node.pos[0] = uiNodes[nodeName].x;
        node.pos[1] = uiNodes[nodeName].y;
      } else {
        node.pos[0] = 60 + i * 200;
        node.pos[1] = 50 + (i % 5) * 100;
      }

      if (proto) {
        if (node.inputs) {
          node.inputs.length = 0;
        }
        node.addInput(proto.input_type || "any", proto.input_type || "any");

        if (node.outputs) {
          node.outputs.length = 0;
        }
        node.addOutput(proto.output_type || "any", proto.output_type || "any");
      }

      graph.add(node);
      nodeMap[nodeName] = node;
    }

    for (let j = 0; j < data.edges.length; j++) {
      const edge = data.edges[j];
      const fromNode = nodeMap[edge.from];
      const toNode = nodeMap[edge.to];
      if (fromNode && toNode) {
        const fromOutput = fromNode.outputs[0];
        const toInput = toNode.inputs[0];
        if (fromOutput && toInput) {
          fromNode.connect(0, toNode, 0);
        }
      }
    }
  }

  /* ---- Runtime status ---- */
  function applyRuntimeStatus() {
    if (!graph) {
      return;
    }
    for (let i = 0; i < graph._nodes.length; i++) {
      const node = graph._nodes[i];
      const nodeName = node.properties.node_name || node.title;
      const rs = runtimeStatuses[nodeName];

      if (!rs) {
        node.overrideColors = { bg: "rgba(102,112,133,0.06)", text: "#667085" };
        node.statusText = "UNKNOWN";
        node.title = nodeName + " [UNKNOWN]";
        continue;
      }

      let bg = "rgba(102,112,133,0.1)";
      let textColor = "#667085";
      let label = "";
      switch (rs.status) {
        case "pending":
          bg = "rgba(102,112,133,0.1)";
          textColor = "#667085";
          label = "PENDING";
          break;
        case "running":
          bg = "rgba(15,93,94,0.12)";
          textColor = "#0f5d5e";
          label = "RUNNING";
          break;
        case "succeeded":
          bg = "rgba(6,118,71,0.1)";
          textColor = "#067647";
          label = "OK";
          break;
        case "failed":
          bg = "rgba(180,35,24,0.1)";
          textColor = "#b42318";
          label = "FAILED";
          break;
        case "skipped":
          bg = "rgba(102,112,133,0.1)";
          textColor = "#667085";
          label = "SKIPPED";
          break;
        case "cancelled":
          bg = "rgba(181,71,8,0.1)";
          textColor = "#b54708";
          label = "CANCELLED";
          break;
        default:
          bg = "rgba(102,112,133,0.1)";
          textColor = "#667085";
          label = rs.status.toUpperCase();
      }
      node.overrideColors = { bg: bg, text: textColor };
      node.statusText = label;
      node.title = nodeName + " [" + label + "]";
    }
  }

  async function refreshRuntimeStatus() {
    try {
      const data = await apiGet("/api/graph/runtime-status");
      runtimeStatuses = data.node_statuses || {};
      applyRuntimeStatus();
    } catch (err) {
      // Runtime status is non-critical
    }
  }

  /* ---- Inspector ---- */
  function renderInspector(node) {
    if (!node) {
      inspectorBody.innerHTML = '<p class="muted">选中节点以查看配置</p>';
      selectedNodeId = null;
      return;
    }

    const nodeName = node.properties.node_name || node.title;
    selectedNodeId = node.id;

    apiGet("/api/graph/node/" + encodeURIComponent(nodeName))
      .then(function (data) {
        if (selectedNodeId !== node.id) {
          return;
        }
        const cfg = data.node;
        inspectorBody.innerHTML =
          '<h3>' +
          escHtml(nodeName) +
          '</h3>' +
          '<p class="muted">type: ' +
          escHtml(cfg.type || "") +
          ' | input: ' +
          escHtml(cfg.input_type || "any") +
          ' | output: ' +
          escHtml(cfg.output_type || "any") +
          "</p>" +
          '<form id="ng-node-form" class="editor">' +
          '<label for="ng-node-model">model</label>' +
          '<input id="ng-node-model" type="text" value="' +
          escAttr(cfg.model || "") +
          '" spellcheck="false">' +
          '<label for="ng-node-timeout">timeout_seconds</label>' +
          '<input id="ng-node-timeout" type="number" step="any" min="0" value="' +
          (cfg.timeout_seconds || "") +
          '">' +
          '<label for="ng-node-source-names">source_names (每行一个)</label>' +
          '<textarea id="ng-node-source-names" rows="4" spellcheck="false">' +
          escHtml((cfg.source_names || []).join("\n")) +
          "</textarea>" +
          '<label for="ng-node-skills">skills (每行一个)</label>' +
          '<textarea id="ng-node-skills" rows="4" spellcheck="false">' +
          escHtml((cfg.skills || []).join("\n")) +
          "</textarea>" +
          '<label for="ng-node-parameters">parameters (JSON)</label>' +
          '<textarea id="ng-node-parameters" rows="6" spellcheck="false">' +
          escHtml(JSON.stringify(cfg.parameters || {}, null, 2)) +
          "</textarea>" +
          '<div class="actions">' +
          '<button type="submit">保存节点配置</button>' +
          "</div>" +
          "</form>";

        document.getElementById("ng-node-form").addEventListener("submit", function (ev) {
          ev.preventDefault();
          saveNodeConfig(nodeName);
        });

        var rs = runtimeStatuses[nodeName];
        if (rs) {
          var statusInfo = document.createElement("div");
          statusInfo.className = "ng-run-status";
          statusInfo.innerHTML =
            '<p><strong>运行状态:</strong> <span class="tag tag-' +
            rs.status +
            '">' +
            escHtml(rs.status) +
            "</span></p>" +
            (rs.error ? "<p><strong>错误:</strong> " + escHtml(rs.error) + "</p>" : "") +
            '<p class="muted">cycle: ' +
            escHtml(rs.cycle_id || "") +
            "</p>";
          inspectorBody.appendChild(statusInfo);
        }
      })
      .catch(function () {
        inspectorBody.innerHTML =
          "<p>无法加载节点配置: " + escHtml(nodeName) + "</p>";
      });
  }

  async function saveNodeConfig(nodeName) {
    var modelVal = document.getElementById("ng-node-model").value.trim();
    var timeoutVal = document.getElementById("ng-node-timeout").value.trim();
    var sourceNamesVal = document.getElementById("ng-node-source-names").value.trim();
    var skillsVal = document.getElementById("ng-node-skills").value.trim();
    var paramsVal = document.getElementById("ng-node-parameters").value.trim();

    var payload = { model: modelVal || null };
    if (timeoutVal !== "") {
      payload.timeout_seconds = parseFloat(timeoutVal);
    } else {
      payload.timeout_seconds = null;
    }
    payload.source_names = sourceNamesVal ? sourceNamesVal.split("\n").map(function (s) { return s.trim(); }).filter(Boolean) : [];
    payload.skills = skillsVal ? skillsVal.split("\n").map(function (s) { return s.trim(); }).filter(Boolean) : [];
    try {
      payload.parameters = paramsVal ? JSON.parse(paramsVal) : {};
    } catch (e) {
      showError("parameters JSON 解析失败: " + e.message);
      return;
    }
    payload.type = null;
    payload.input_type = null;
    payload.output_type = null;

    try {
      await apiPut("/api/graph/node/" + encodeURIComponent(nodeName), payload);
      showError("");
      var saveBtnEl = document.querySelector("#ng-node-form button[type=submit]");
      if (saveBtnEl) {
        saveBtnEl.textContent = "已保存";
        setTimeout(function () { saveBtnEl.textContent = "保存节点配置"; }, 1500);
      }
    } catch (err) {
      showError("保存节点配置失败: " + err.message);
    }
  }

  /* ---- Palette ---- */
  function buildPalette() {
    paletteList.innerHTML = "";
    for (var i = 0; i < prototypes.length; i++) {
      (function (proto) {
        var item = document.createElement("button");
        item.className = "ng-palette-item";
        item.textContent = proto.name;
        item.title = proto.type + " | " + (proto.input_type || "any") + " → " + (proto.output_type || "any");
        item.addEventListener("click", function () {
          addNodeToGraph(proto);
        });
        paletteList.appendChild(item);
      })(prototypes[i]);
    }
  }

  function addNodeToGraph(proto) {
    if (!graph) {
      return;
    }
    var NodeClass = LiteGraph.registered_node_types[proto.name] || StockNode;
    var node = LiteGraph.createNode(NodeClass);
    if (!node) {
      return;
    }
    node.properties.node_name = proto.name;
    node.properties.type = proto.type;
    node.title = proto.name;
    node.pos[0] = 100 + Math.random() * 300;
    node.pos[1] = 100 + Math.random() * 300;

    if (node.inputs) {
      node.inputs.length = 0;
    }
    node.addInput(proto.input_type || "any", proto.input_type || "any");

    if (node.outputs) {
      node.outputs.length = 0;
    }
    node.addOutput(proto.output_type || "any", proto.output_type || "any");

    graph.add(node);
    canvasRenderer.setDirty(true);
  }

  /* ---- Load and save DAG ---- */
  async function loadGraph(dagName) {
    try {
      var data = await apiGet("/api/graph/dag/" + encodeURIComponent(dagName));
      deserializeGraph(data);
      canvasRenderer.setDirty(true);
      dagLabel.innerHTML = '当前 DAG：<strong>' + escHtml(dagName) + '</strong> — 保存后仅影响后续运行';
      await refreshRuntimeStatus();
    } catch (err) {
      showError("加载 DAG 失败: " + err.message);
    }
  }

  async function saveGraph() {
    var dagName = dagSelect ? dagSelect.value : "default";
    var payload = serializeGraph();
    try {
      await apiPut("/api/graph/dag/" + encodeURIComponent(dagName), payload);
      showError("");
      saveBtn.textContent = "已保存";
      setTimeout(function () { saveBtn.textContent = "保存 DAG"; }, 1500);
      await refreshRuntimeStatus();
    } catch (err) {
      showError("保存 DAG 失败: " + err.message);
    }
  }

  /* ---- Utils ---- */
  function escHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function escAttr(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  /* ---- Init ---- */
  async function init() {
    // Set canvas resolution to match container size before creating renderer
    const wrap = document.querySelector('.ng-canvas-wrap');
    if (wrap) {
      const rect = wrap.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        canvas.width = rect.width;
        canvas.height = rect.height;
      }
    }
    graph = new LiteGraph.LGraph();
    canvasRenderer = new LiteGraph.LGraphCanvas(canvas, graph);
    canvasRenderer.background_image = "";
    canvasRenderer.render_canvas_border = false;

    // ResizeObserver to keep canvas resolution in sync with container
    const resizeWrap = document.querySelector('.ng-canvas-wrap');
    if (resizeWrap && window.ResizeObserver) {
      const resizeObserver = new ResizeObserver(function(entries) {
        for (const entry of entries) {
          const cr = entry.contentRect;
          if (cr.width > 0 && cr.height > 0) {
            canvas.width = cr.width;
            canvas.height = cr.height;
            if (canvasRenderer && canvasRenderer.resize) {
              canvasRenderer.resize();
            }
          }
        }
      });
      resizeObserver.observe(resizeWrap);
    }

    // Use LiteGraph's official node selection callbacks
    canvasRenderer.onNodeSelected = function(node) {
      if (node) {
        renderInspector(node);
      }
    };
    canvasRenderer.onNodeDeselected = function() {
      renderInspector(null);
    };

    graph.onNodeRemoved = function () {
      renderInspector(null);
    };

    saveBtn.addEventListener("click", saveGraph);

    if (dagSelect) {
      dagSelect.addEventListener("change", function () {
        loadGraph(dagSelect.value);
      });
    }

    try {
      var protoData = await apiGet("/api/graph/nodes");
      prototypes = protoData.prototypes || [];

      for (var i = 0; i < prototypes.length; i++) {
        var NodeClass = makeNodeClass(prototypes[i]);
        LiteGraph.registerNodeType(prototypes[i].name, NodeClass);
      }

      buildPalette();
      await loadGraph(dagSelect ? dagSelect.value : "default");
    } catch (err) {
      showError("初始化失败: " + err.message);
    }

    canvasRenderer.start();
    setInterval(refreshRuntimeStatus, 10000);
  }

  init();
})();

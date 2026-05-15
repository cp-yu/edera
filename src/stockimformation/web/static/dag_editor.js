(function () {
  const root = document.querySelector("[data-dag-editor]");
  if (!root) {
    return;
  }

  const form = root.querySelector("[data-dag-form]");
  const table = root.querySelector("[data-dag-edge-table]");
  const tbody = table.querySelector("tbody");
  const edgesInput = root.querySelector("[data-dag-edges-input]");
  const preview = root.querySelector("[data-dag-preview]");
  const nodeInputs = Array.from(root.querySelectorAll('input[name="nodes"]'));

  function selectedNodes() {
    return nodeInputs.filter((input) => input.checked).map((input) => input.value);
  }

  function allNodes() {
    return nodeInputs.map((input) => input.value);
  }

  function edgeRows() {
    return Array.from(tbody.querySelectorAll("tr"));
  }

  function collectEdges() {
    return edgeRows().map((row) => {
      const edge = {
        from: row.querySelector("[data-edge-from]").value,
        to: row.querySelector("[data-edge-to]").value,
      };
      if (row.querySelector("[data-edge-fan-in]").checked) {
        edge.fan_in = true;
      }
      if (row.querySelector("[data-edge-fan-out]").checked) {
        edge.fan_out = true;
      }
      return edge;
    });
  }

  function syncEdges() {
    edgesInput.value = JSON.stringify(collectEdges());
  }

  function optionHtml(value, selected) {
    const safeValue = value.replace(/"/g, "&quot;");
    return `<option value="${safeValue}"${selected ? " selected" : ""}>${value}</option>`;
  }

  function selectHtml(attr, selected) {
    return `<select ${attr}>${allNodes().map((node) => optionHtml(node, node === selected)).join("")}</select>`;
  }

  function addEdgeRow(edge) {
    const nodes = selectedNodes();
    const fromNode = edge.from || nodes[0] || allNodes()[0] || "";
    const toNode = edge.to || nodes[1] || nodes[0] || allNodes()[0] || "";
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${selectHtml("data-edge-from", fromNode)}</td>
      <td>${selectHtml("data-edge-to", toNode)}</td>
      <td><input type="checkbox" data-edge-fan-in${edge.fan_in ? " checked" : ""}></td>
      <td><input type="checkbox" data-edge-fan-out${edge.fan_out ? " checked" : ""}></td>
      <td><button type="button" class="danger" data-remove-edge>删除</button></td>
    `;
    tbody.appendChild(row);
    refresh();
  }

  function nodeLayers(nodes, edges) {
    const incoming = Object.fromEntries(nodes.map((node) => [node, 0]));
    edges.forEach((edge) => {
      if (edge.to in incoming) {
        incoming[edge.to] += 1;
      }
    });
    const layers = {};
    const visit = (node, trail) => {
      if (layers[node] !== undefined) {
        return layers[node];
      }
      if (trail.includes(node)) {
        return 0;
      }
      const upstreams = edges.filter((edge) => edge.to === node).map((edge) => edge.from);
      layers[node] = upstreams.length
        ? Math.max(...upstreams.map((upstream) => visit(upstream, trail.concat(node)))) + 1
        : 0;
      return layers[node];
    };
    nodes.forEach((node) => visit(node, []));
    return layers;
  }

  function renderPreview() {
    const nodes = selectedNodes();
    const edges = collectEdges().filter((edge) => nodes.includes(edge.from) && nodes.includes(edge.to));
    const width = Math.max(680, nodes.length * 130);
    const height = Math.max(280, nodes.length * 48);
    const layers = nodeLayers(nodes, edges);
    const grouped = {};
    nodes.forEach((node) => {
      const layer = layers[node] || 0;
      grouped[layer] = grouped[layer] || [];
      grouped[layer].push(node);
    });
    const positions = {};
    Object.entries(grouped).forEach(([layer, names]) => {
      names.forEach((node, index) => {
        positions[node] = {
          x: 60 + Number(layer) * 180,
          y: 42 + index * 72,
        };
      });
    });
    preview.setAttribute("viewBox", `0 0 ${width} ${height}`);
    preview.innerHTML = "";
    edges.forEach((edge) => {
      const start = positions[edge.from];
      const end = positions[edge.to];
      if (!start || !end) {
        return;
      }
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      const mid = start.x + 90;
      path.setAttribute("d", `M ${start.x + 120} ${start.y} C ${mid} ${start.y}, ${mid} ${end.y}, ${end.x} ${end.y}`);
      path.setAttribute("class", "dag-edge");
      preview.appendChild(path);
      if (edge.fan_in || edge.fan_out) {
        const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.setAttribute("x", String((start.x + end.x) / 2 + 55));
        label.setAttribute("y", String((start.y + end.y) / 2 - 6));
        label.setAttribute("class", "dag-edge-label");
        label.textContent = [edge.fan_in ? "fan_in" : "", edge.fan_out ? "fan_out" : ""].filter(Boolean).join(" ");
        preview.appendChild(label);
      }
    });
    nodes.forEach((node) => {
      const point = positions[node];
      const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
      group.setAttribute("class", "dag-node");
      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("x", String(point.x));
      rect.setAttribute("y", String(point.y - 18));
      rect.setAttribute("width", "128");
      rect.setAttribute("height", "36");
      rect.setAttribute("rx", "6");
      const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      text.setAttribute("x", String(point.x + 10));
      text.setAttribute("y", String(point.y + 5));
      text.textContent = node;
      group.appendChild(rect);
      group.appendChild(text);
      preview.appendChild(group);
    });
  }

  function refresh() {
    syncEdges();
    renderPreview();
  }

  root.addEventListener("click", (event) => {
    if (event.target.matches("[data-add-edge]")) {
      addEdgeRow({});
    }
    if (event.target.matches("[data-remove-edge]")) {
      event.target.closest("tr").remove();
      refresh();
    }
  });
  root.addEventListener("change", refresh);
  form.addEventListener("submit", syncEdges);
  renderPreview();
})();

// Small SVG chart helpers: linear scales, axes, lines, bars and points, with a hover
// readout. Each chart has an accessible name; the numbers are also in a table below it.

const SVG = "http://www.w3.org/2000/svg";

function el(name, attributes = {}, parent) {
  const node = document.createElementNS(SVG, name);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  if (parent) parent.append(node);
  return node;
}

function niceTicks(min, max, count = 5) {
  const span = max - min || 1;
  const step0 = span / count;
  const power = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * power).find((s) => s >= step0);
  const ticks = [];
  for (let v = Math.ceil(min / step) * step; v <= max + step / 1e6; v += step) ticks.push(Number(v.toFixed(10)));
  return ticks;
}

const linear = (domain, range) => {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  return (v) => r0 + ((v - d0) / (d1 - d0 || 1)) * (r1 - r0);
};

/**
 * Draws a chart into `container`.
 * options: { label, x: {min, max, format, title}, y: {min, max, format, title, zero},
 *            layers: [{type: "line"|"bar"|"dot", data, x, y, className, color?(d)}],
 *            readout(d) -> string, readoutLayer, width? }
 * Narrow panels pass a smaller width, so text stays readable when the chart is scaled down.
 */
export function chart(container, options) {
  const width = options.width ?? 720;
  const height = options.width ? Math.round(options.width * 0.62) : 300;
  const margin = { top: 12, right: 16, bottom: 36, left: 52 };
  const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": options.label, class: "chart-svg" });
  container.replaceChildren(svg);

  const x = linear([options.x.min, options.x.max], [margin.left, width - margin.right]);
  const y = linear([options.y.min, options.y.max], [height - margin.bottom, margin.top]);

  const grid = el("g", { class: "grid" }, svg);
  for (const tick of niceTicks(options.y.min, options.y.max)) {
    el("line", { x1: margin.left, x2: width - margin.right, y1: y(tick), y2: y(tick) }, grid);
    el("text", { x: margin.left - 6, y: y(tick), "text-anchor": "end", "dominant-baseline": "middle", class: "tick" }, grid).textContent =
      options.y.format(tick);
  }
  for (const tick of options.x.ticks ?? niceTicks(options.x.min, options.x.max, 8)) {
    el("text", { x: x(tick), y: height - margin.bottom + 18, "text-anchor": "middle", class: "tick" }, grid).textContent =
      options.x.format(tick);
  }
  if (options.y.zero) el("line", { x1: margin.left, x2: width - margin.right, y1: y(0), y2: y(0), class: "zero" }, svg);
  if (options.y.title) el("text", { x: margin.left, y: margin.top - 2, class: "axis-title" }, svg).textContent = options.y.title;

  for (const layer of options.layers) {
    const points = layer.data.filter((d) => layer.y(d) !== null && layer.y(d) !== undefined);
    if (layer.type === "line") {
      const d = points.map((p, i) => `${i ? "L" : "M"}${x(layer.x(p)).toFixed(1)},${y(layer.y(p)).toFixed(1)}`).join("");
      el("path", { d, class: `line ${layer.className ?? ""}` }, svg);
    } else if (layer.type === "bar") {
      const band = ((width - margin.left - margin.right) / (options.x.max - options.x.min + 1)) * 0.8;
      const base = y(options.y.zero ? 0 : options.y.min);
      for (const p of points) {
        const top = y(layer.y(p));
        el("rect", {
          x: x(layer.x(p)) - band / 2,
          y: Math.min(top, base),
          width: Math.max(band, 1),
          height: Math.max(Math.abs(base - top), 0.5),
          class: `bar ${layer.className ?? ""}`,
          ...(layer.color ? { fill: layer.color(p) } : {}),
        }, svg);
      }
    } else if (layer.type === "dot") {
      for (const p of points) el("circle", { cx: x(layer.x(p)), cy: y(layer.y(p)), r: 3.5, class: `dot ${layer.className ?? ""}`, ...(layer.color ? { fill: layer.color(p) } : {}) }, svg);
    }
  }

  // Hover readout: the nearest data point to the pointer along x.
  if (options.readout) {
    const layer = options.layers[options.readoutLayer ?? 0];
    const data = layer.data.filter((d) => layer.y(d) !== null);
    const marker = el("circle", { r: 5, class: "marker", visibility: "hidden" }, svg);
    const label = document.createElement("p");
    label.className = "readout";
    label.setAttribute("aria-hidden", "true");
    label.textContent = "Point at the chart to see values.";
    container.append(label);
    const toX = linear([margin.left, width - margin.right], [options.x.min, options.x.max]);
    svg.addEventListener("pointermove", (event) => {
      const box = svg.getBoundingClientRect();
      const value = toX(((event.clientX - box.left) / box.width) * width);
      let best = data[0];
      for (const d of data) if (Math.abs(layer.x(d) - value) < Math.abs(layer.x(best) - value)) best = d;
      marker.setAttribute("cx", x(layer.x(best)));
      marker.setAttribute("cy", y(layer.y(best)));
      marker.setAttribute("visibility", "visible");
      label.textContent = options.readout(best);
    });
    svg.addEventListener("pointerleave", () => marker.setAttribute("visibility", "hidden"));
  }
}

export function extent(values, pad = 0) {
  const finite = values.filter((v) => v !== null && Number.isFinite(v));
  const min = Math.min(...finite);
  const max = Math.max(...finite);
  const room = (max - min) * pad;
  return [min - room, max + room];
}

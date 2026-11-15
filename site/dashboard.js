import { chart, extent } from "./charts.js";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const fixed = (digits) => (v) => v.toFixed(digits);
const signed = (v, digits = 2) => `${v > 0 ? "+" : ""}${v.toFixed(digits)}`;

function text(tag, content, className) {
  const node = document.createElement(tag);
  node.textContent = content;
  if (className) node.className = className;
  return node;
}

function summary(data) {
  const { latest_co2: latest, co2_change: change, warmest_year: warmest, warmest_ten_in_last_ten: recent } = data.summary;
  const items = [];
  if (latest) items.push([`${latest.ppm.toFixed(1)} ppm`, `CO₂ in ${MONTHS[latest.month - 1]} ${latest.year}`]);
  if (change) {
    const percent = ((change.to_ppm - change.from_ppm) / change.from_ppm) * 100;
    items.push([`+${percent.toFixed(0)}%`, `more CO₂ than in ${change.from_year}`]);
  }
  if (warmest) items.push([`${signed(warmest.anomaly)} °C`, `warmest year, ${warmest.year}`]);
  if (recent !== null) items.push([`${recent} of 10`, "warmest years were in the last ten"]);
  document.getElementById("summary").replaceChildren(
    ...items.map(([value, label]) => {
      const box = document.createElement("div");
      box.append(text("dt", label), text("dd", value));
      return box;
    }),
  );
}

function decadeTable(data) {
  const table = document.getElementById("decades");
  const head = document.createElement("thead");
  head.innerHTML = '<tr><th scope="col">Decade</th><th scope="col">Temperature</th><th scope="col">CO₂ rise per year</th></tr>';
  const body = document.createElement("tbody");
  for (const row of [...data.decades].reverse()) {
    const tr = document.createElement("tr");
    tr.append(
      text("th", `${row.decade}s`),
      text("td", `${signed(row.anomaly)} °C`),
      text("td", row.growth_ppm_per_year === null ? "not measured" : `${row.growth_ppm_per_year.toFixed(2)} ppm`),
    );
    tr.firstChild.setAttribute("scope", "row");
    body.append(tr);
  }
  table.replaceChildren(text("caption", "Average temperature difference and CO₂ rise by decade", "visually-hidden"), head, body);
}

function sources(data) {
  const built = new Date(data.meta.built_at);
  document.getElementById("updated").textContent = `Updated ${built.toLocaleDateString(undefined, { dateStyle: "long" })}.`;
  document.getElementById("sources").replaceChildren(
    ...data.meta.sources.map((s) => {
      const li = document.createElement("li");
      const link = text("a", s.title);
      link.href = s.page;
      li.append(link, text("span", ` · downloaded ${s.fetched_at.slice(0, 10)} · SHA-256 ${s.sha256.slice(0, 12)}…`, "muted small"));
      return li;
    }),
  );
  const checks = [...data.meta.quality.checks.map((c) => `✓ ${c}`), ...data.meta.quality.warnings.map((w) => `⚠ ${w}`)];
  document.getElementById("checks").replaceChildren(...checks.map((c) => text("li", c)));
}

function charts(data) {
  const monthly = data.co2_monthly.map((d) => ({ ...d, t: d.year + (d.month - 0.5) / 12 }));
  const [cMin, cMax] = extent(monthly.map((d) => d.ppm), 0.04);
  chart(document.getElementById("chart-keeling"), {
    label: `Monthly CO₂ at Mauna Loa from ${monthly[0].year} to ${monthly.at(-1).year}, rising from ${monthly[0].ppm.toFixed(0)} to ${monthly.at(-1).ppm.toFixed(0)} ppm`,
    x: { min: monthly[0].t, max: monthly.at(-1).t, format: (v) => String(Math.round(v)) },
    y: { min: cMin, max: cMax, format: fixed(0), title: "ppm" },
    layers: [
      { type: "line", data: monthly, x: (d) => d.t, y: (d) => d.ppm, className: "co2" },
      { type: "line", data: monthly, x: (d) => d.t, y: (d) => d.deseasonalized, className: "trend" },
    ],
    readout: (d) => `${MONTHS[d.month - 1]} ${d.year}: ${d.ppm.toFixed(2)} ppm`,
  });

  const growth = data.co2_annual.filter((d) => d.growth_ppm !== null);
  const [gMin, gMax] = extent(growth.map((d) => d.growth_ppm), 0.08);
  chart(document.getElementById("chart-growth"), {
    label: "Yearly increase in CO₂, in ppm per year",
    width: 440,
    x: { min: growth[0].year, max: growth.at(-1).year, format: String },
    y: { min: Math.min(0, gMin), max: gMax, format: fixed(1), title: "ppm per year", zero: true },
    layers: [{ type: "bar", data: growth, x: (d) => d.year, y: (d) => d.growth_ppm, className: "growth" }],
    readout: (d) => `${d.year}: +${d.growth_ppm.toFixed(2)} ppm`,
  });

  const season = data.co2_seasonal;
  const [sMin, sMax] = extent(season.map((d) => d.offset_ppm), 0.15);
  chart(document.getElementById("chart-season"), {
    label: "Average monthly CO₂ compared with the trend, peaking in May and lowest in autumn",
    width: 440,
    x: { min: 1, max: 12, format: (v) => MONTHS[v - 1]?.[0] ?? "", ticks: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] },
    y: { min: sMin, max: sMax, format: fixed(0), title: "ppm from trend", zero: true },
    layers: [
      { type: "line", data: season, x: (d) => d.month, y: (d) => d.offset_ppm, className: "co2" },
      { type: "dot", data: season, x: (d) => d.month, y: (d) => d.offset_ppm, className: "co2" },
    ],
    readout: (d) => `${MONTHS[d.month - 1]}: ${signed(d.offset_ppm)} ppm`,
  });

  const temperature = data.temperature_annual;
  const [tMin, tMax] = extent(temperature.map((d) => d.anomaly), 0.08);
  chart(document.getElementById("chart-temperature"), {
    label: `Global temperature each year from ${temperature[0].year} to ${temperature.at(-1).year} compared with the 1951 to 1980 average`,
    x: { min: temperature[0].year, max: temperature.at(-1).year, format: String },
    y: { min: tMin, max: tMax, format: (v) => `${signed(v, 1)}°`, title: "°C", zero: true },
    layers: [
      { type: "bar", data: temperature, x: (d) => d.year, y: (d) => d.anomaly, color: (d) => (d.anomaly >= 0 ? "var(--warm)" : "var(--cool)") },
      { type: "line", data: temperature, x: (d) => d.year, y: (d) => d.rolling_10y, className: "trend" },
    ],
    readout: (d) => `${d.year}: ${signed(d.anomaly)} °C${d.rolling_10y !== null ? `, ten-year average ${signed(d.rolling_10y)} °C` : ""}`,
  });

  const byYear = new Map(temperature.map((d) => [d.year, d.anomaly]));
  const pairs = data.co2_annual.filter((d) => byYear.has(d.year)).map((d) => ({ year: d.year, ppm: d.ppm, anomaly: byYear.get(d.year) }));
  const [pMin, pMax] = extent(pairs.map((d) => d.ppm), 0.03);
  const [aMin, aMax] = extent(pairs.map((d) => d.anomaly), 0.1);
  chart(document.getElementById("chart-scatter"), {
    label: "Each year's average CO₂ against its global temperature",
    width: 440,
    x: { min: pMin, max: pMax, format: fixed(0) },
    y: { min: aMin, max: aMax, format: (v) => `${signed(v, 1)}°`, title: "°C", zero: true },
    layers: [{ type: "dot", data: pairs, x: (d) => d.ppm, y: (d) => d.anomaly, color: (d) => (d.anomaly >= 0 ? "var(--warm)" : "var(--cool)") }],
    readout: (d) => `${d.year}: ${d.ppm.toFixed(1)} ppm, ${signed(d.anomaly)} °C`,
  });
  const r = data.summary.correlation;
  if (r) document.getElementById("correlation").textContent = `Correlation over ${r.years} years: r = ${r.r.toFixed(2)}. Correlation alone doesn't show cause; the physics of greenhouse gases does.`;
}

try {
  const response = await fetch("data/dashboard.json");
  if (!response.ok) throw new Error(`the data could not be loaded (HTTP ${response.status})`);
  const data = await response.json();
  summary(data);
  charts(data);
  decadeTable(data);
  sources(data);
} catch (error) {
  const box = document.getElementById("error");
  box.textContent = `Sorry, ${error.message}.`;
  box.hidden = false;
}

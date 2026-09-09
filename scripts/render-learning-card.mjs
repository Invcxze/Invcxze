import fs from "node:fs/promises";
import path from "node:path";

const inputPath = path.resolve(process.argv[2] ?? "data/learning-activity.json");
const outputDir = path.resolve(process.argv[3] ?? "assets");
const data = JSON.parse(await fs.readFile(inputPath, "utf8"));

const themes = {
  light: { background: "#F5EAD8", panel: "#EBDDC5", text: "#201E1D", muted: "#645F56", border: "#D4C5AC" },
  dark: { background: "#201E1D", panel: "#2C2926", text: "#F5EAD8", muted: "#C1B6A6", border: "#514A42" },
};

const platformColors = { stepik: "#4C86C6", sololearn: "#5EBA89", mimo: "#EE7D52" };

function escapeXml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" })[char]);
}

function text(x, y, value, { size = 14, color, weight = 400, anchor = "start", family = "Arial, Helvetica, sans-serif" } = {}) {
  return `<text x="${x}" y="${y}" fill="${color}" font-family="${family}" font-size="${size}" font-weight="${weight}" text-anchor="${anchor}">${escapeXml(value)}</text>`;
}

function metric(value, suffix = "") {
  return value == null ? null : `${Number(value).toLocaleString("en-US")}${suffix}`;
}

function summary(id, item) {
  if (!item) return "Waiting for data";
  const chunks = [];
  if (id === "stepik") {
    if (item.solved != null) chunks.push(`${metric(item.solved)} problems solved`);
    if (item.certificates != null) chunks.push(`${metric(item.certificates)} certificate${item.certificates === 1 ? "" : "s"}`);
    if (item.best_streak != null) chunks.push(`${metric(item.best_streak)}-day best streak`);
  } else if (id === "sololearn") {
    if (item.level != null) chunks.push(`level ${metric(item.level)}`);
    if (item.xp != null) chunks.push(`${metric(item.xp)} XP`);
    if (item.certificates != null) chunks.push(`${metric(item.certificates)} certificates`);
  } else {
    if (item.completed_courses != null) chunks.push(`${metric(item.completed_courses)} completed courses`);
    if (item.path) chunks.push(`${item.path}${item.progress != null ? ` ${metric(item.progress, "%")}` : ""}`);
    if (item.sections_completed != null && item.sections_total != null) chunks.push(`${item.sections_completed}/${item.sections_total} sections`);
  }
  return chunks.join(" · ") || "Waiting for the first successful refresh";
}

function render(theme) {
  const width = 1000;
  const height = 360;
  const rows = [
    ["stepik", "Stepik"],
    ["sololearn", "SoloLearn"],
    ["mimo", "Mimo"],
  ];
  const parts = [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="title desc">`,
    '<title id="title">Learning activity</title>',
    '<desc id="desc">Weekly learning progress from Stepik, SoloLearn, and Mimo.</desc>',
    `<rect x="1" y="1" width="998" height="358" rx="18" fill="${theme.background}" stroke="${theme.border}" stroke-width="2"/>`,
    text(34, 48, "Learning in public", { size: 25, color: theme.text, weight: 700 }),
    text(34, 76, "Courses, practice, and the habit of continuing", { size: 14, color: theme.muted }),
    text(966, 48, "WEEKLY REFRESH", { size: 12, color: theme.muted, weight: 700, anchor: "end", family: "monospace" }),
  ];

  rows.forEach(([id, label], index) => {
    const item = data.platforms?.[id];
    const y = 102 + index * 76;
    const stale = item?.status === "stale";
    parts.push(`<a href="${escapeXml(item?.url ?? "#")}" target="_blank">`);
    parts.push(`<rect x="34" y="${y}" width="932" height="60" rx="12" fill="${theme.panel}"/>`);
    parts.push(`<rect x="34" y="${y}" width="8" height="60" rx="4" fill="${platformColors[id]}"/>`);
    parts.push(text(62, y + 26, label, { size: 17, color: theme.text, weight: 700 }));
    parts.push(text(62, y + 47, summary(id, item), { size: 13, color: theme.muted }));
    const status = stale ? "CACHED" : item?.status === "ok" ? "LIVE" : "SNAPSHOT";
    parts.push(text(944, y + 35, status, { size: 11, color: stale ? "#C67139" : theme.muted, weight: 700, anchor: "end", family: "monospace" }));
    parts.push("</a>");
  });

  const generated = data.generated_at ? new Date(data.generated_at).toLocaleDateString("en-GB", { timeZone: "UTC", day: "2-digit", month: "short", year: "numeric" }) : "not yet";
  parts.push(text(34, 342, `Last checked ${generated} · Stepik and SoloLearn refresh weekly; Mimo is a manual snapshot.`, { size: 11, color: theme.muted }));
  parts.push("</svg>");
  return parts.join("");
}

await fs.mkdir(outputDir, { recursive: true });
for (const [name, theme] of Object.entries(themes)) {
  await fs.writeFile(path.join(outputDir, `learning.${name}.svg`), render(theme), "utf8");
}

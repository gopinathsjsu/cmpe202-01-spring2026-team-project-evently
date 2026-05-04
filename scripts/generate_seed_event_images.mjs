import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(scriptDir, "..");
const outDir = resolve(repoRoot, "backend", "backend", "uploads", "seed-events");
const manifestPath = resolve(repoRoot, "backend", "backend", "seed_event_images.json");
const events = JSON.parse(readFileSync(manifestPath, "utf8"));

function escapeXml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function circle(cx, cy, r, fill, extra = "") {
  return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${fill}" ${extra}/>`;
}

function rect(x, y, width, height, fill, extra = "") {
  return `<rect x="${x}" y="${y}" width="${width}" height="${height}" fill="${fill}" ${extra}/>`;
}

function line(x1, y1, x2, y2, stroke, width = 18, extra = "") {
  return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${stroke}" stroke-width="${width}" stroke-linecap="round" ${extra}/>`;
}

function path(d, fill, extra = "") {
  const fillAttr = extra.includes("fill=") ? "" : `fill="${fill}"`;
  return `<path d="${d}" ${fillAttr} ${extra}/>`;
}

function base({ title, colors, body }) {
  const [bg, accent, light] = colors;
  return [
    `<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900" role="img" aria-labelledby="title">`,
    `<title id="title">${escapeXml(title)}</title>`,
    `<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${bg}"/><stop offset="1" stop-color="${accent}"/></linearGradient></defs>`,
    rect(0, 0, 1600, 900, "url(#bg)"),
    circle(1320, 140, 250, light, 'opacity=".13"'),
    circle(180, 760, 340, "#ffffff", 'opacity=".09"'),
    rect(0, 690, 1600, 210, "#000000", 'opacity=".15"'),
    body,
    `</svg>`,
  ].join("");
}

const icon = {
  festival: () => [
    rect(360, 470, 880, 70, "#111827", 'opacity=".7"'),
    path("M480 470 620 300 760 470Z", "#ffffff", 'opacity=".35"'),
    path("M840 470 980 300 1120 470Z", "#ffffff", 'opacity=".35"'),
    line(520, 290, 420, 650, "#ffe66d", 14),
    line(1080, 290, 1180, 650, "#ffe66d", 14),
    ...[500, 650, 800, 950, 1100].map((x) => circle(x, 410, 32, "#ff6b35")),
  ].join(""),
  conference: () => [
    rect(430, 230, 740, 430, "#e0fbfc", 'rx="36" opacity=".88"'),
    rect(500, 305, 600, 46, "#102a43", 'rx="20" opacity=".55"'),
    rect(500, 395, 460, 36, "#00b4d8", 'rx="18"'),
    rect(500, 470, 560, 36, "#102a43", 'rx="18" opacity=".45"'),
    line(720, 710, 880, 710, "#e0fbfc", 30),
    line(800, 660, 800, 710, "#e0fbfc", 26),
  ].join(""),
  gallery: () => [
    rect(330, 240, 270, 380, "#fff8f0", 'rx="18"'),
    rect(665, 190, 270, 470, "#fff8f0", 'rx="18"'),
    rect(1000, 260, 270, 350, "#fff8f0", 'rx="18"'),
    circle(465, 375, 75, "#ef476f"),
    path("M710 585 815 335 890 585Z", "#ffd166"),
    rect(1055, 330, 160, 210, "#2b2d42", 'rx="18"'),
  ].join(""),
  yoga: () => [
    circle(800, 310, 150, "#ffcb77"),
    line(800, 455, 800, 610, "#f7fff7", 32),
    line(800, 505, 625, 430, "#f7fff7", 30),
    line(800, 505, 975, 430, "#f7fff7", 30),
    line(800, 610, 620, 705, "#f7fff7", 30),
    line(800, 610, 980, 705, "#f7fff7", 30),
    circle(800, 405, 48, "#f7fff7"),
    line(500, 745, 1100, 745, "#ffffff", 20, 'opacity=".55"'),
  ].join(""),
  networking: () => [
    ...[[560, 350], [810, 280], [1040, 385], [660, 590], [950, 610]].map(([x, y]) => circle(x, y, 82, "#ffffff", 'opacity=".88"')),
    line(610, 390, 760, 315, "#a1c181", 16),
    line(875, 310, 980, 365, "#a1c181", 16),
    line(610, 410, 680, 540, "#a1c181", 16),
    line(720, 590, 890, 610, "#a1c181", 16),
    ...[[560, 350], [810, 280], [1040, 385], [660, 590], [950, 610]].map(([x, y]) => circle(x, y - 18, 24, "#233d4d")),
  ].join(""),
  comedy: () => [
    path("M620 260C530 300 500 430 555 535c50 95 175 130 245 55-80-12-135-72-140-145 66 35 150 27 205-28-20-115-120-190-245-157Z", "#ffd166"),
    path("M980 260c90 40 120 170 65 275-50 95-175 130-245 55 80-12 135-72 140-145-66 35-150 27-205-28 20-115 120-190 245-157Z", "#f72585"),
    circle(640, 410, 28, "#20123a"),
    circle(960, 410, 28, "#20123a"),
    path("M610 515Q705 585 800 515", "none", 'stroke="#20123a" stroke-width="26" stroke-linecap="round" fill="none"'),
  ].join(""),
  foodwine: () => [
    path("M515 250h170l-45 410c-10 85-160 85-170 0Z", "#ffffff", 'opacity=".9"'),
    path("M500 420h155l-25 220c-8 55-105 55-112 0Z", "#9a031e", 'opacity=".82"'),
    circle(980, 475, 170, "#fff4d6"),
    circle(930, 430, 44, "#e36414"),
    circle(1030, 470, 44, "#386641"),
    circle(955, 540, 44, "#9a031e"),
    line(845, 655, 1115, 655, "#ffffff", 24, 'opacity=".82"'),
  ].join(""),
  photography: () => [
    rect(445, 285, 710, 380, "#f1faee", 'rx="44" opacity=".93"'),
    rect(560, 230, 260, 90, "#f1faee", 'rx="28" opacity=".93"'),
    circle(800, 475, 145, "#1d3557"),
    circle(800, 475, 86, "#457b9d"),
    circle(800, 475, 36, "#f1faee"),
    rect(985, 345, 90, 54, "#1d3557", 'rx="22"'),
  ].join(""),
  jazz: () => [
    path("M845 205c90 60 110 180 35 285l-125 175c-45 65 20 125 90 90 65-32 82-110 28-155l80-105c120 92 75 270-60 335-170 82-330-72-225-225l122-175c35-50 25-105-30-142Z", "#dda15e"),
    circle(900, 640, 120, "#fefae0", 'opacity=".9"'),
    circle(900, 640, 68, "#283618"),
    ...[540, 635, 1135].map((x) => line(x, 250, x, 520, "#fefae0", 15, 'opacity=".75"')),
  ].join(""),
  marathon: () => [
    path("M520 610c120 50 255 55 405 15l30 85c-175 60-330 48-465-20Z", "#ff6663"),
    path("M760 535c155 15 265 70 350 165l-75 70c-78-75-170-120-298-138Z", "#bfd7ea"),
    circle(725, 325, 50, "#ffffff"),
    line(705, 385, 640, 520, "#ffffff", 28),
    line(665, 455, 820, 490, "#ffffff", 24),
    line(642, 520, 548, 635, "#ffffff", 26),
    line(642, 520, 770, 625, "#ffffff", 26),
  ].join(""),
  film: () => [
    rect(390, 255, 820, 420, "#f9fafb", 'rx="28" opacity=".88"'),
    ...[430, 540, 650, 760, 870, 980, 1090].map((x) => rect(x, 295, 52, 52, "#111827", 'rx="8" opacity=".72"')),
    ...[430, 540, 650, 760, 870, 980, 1090].map((x) => rect(x, 578, 52, 52, "#111827", 'rx="8" opacity=".72"')),
    path("M680 370 920 465 680 560Z", "#111827", 'opacity=".8"'),
  ].join(""),
  salsa: () => [
    circle(660, 295, 50, "#ffbe0b"),
    circle(940, 295, 50, "#ffbe0b"),
    line(660, 355, 590, 535, "#ffffff", 28),
    line(940, 355, 1010, 535, "#ffffff", 28),
    line(600, 420, 805, 375, "#ffffff", 24),
    line(1000, 420, 795, 375, "#ffffff", 24),
    path("M500 650Q660 510 820 650Q660 735 500 650Z", "#ff006e"),
    path("M780 650Q940 510 1100 650Q940 735 780 650Z", "#7b2cbf"),
  ].join(""),
  hackathon: () => [
    rect(420, 310, 760, 320, "#f8fafc", 'rx="34" opacity=".9"'),
    rect(500, 380, 600, 175, "#001219", 'rx="18"'),
    path("M610 455 540 505 610 555", "none", 'stroke="#0a9396" stroke-width="28" stroke-linecap="round" stroke-linejoin="round" fill="none"'),
    path("M990 455 1060 505 990 555", "none", 'stroke="#ee9b00" stroke-width="28" stroke-linecap="round" stroke-linejoin="round" fill="none"'),
    line(760, 565, 840, 395, "#f8fafc", 22),
    rect(360, 650, 880, 44, "#f8fafc", 'rx="22" opacity=".9"'),
  ].join(""),
  theater: () => [
    path("M280 240c250 95 430 95 680 0v390c-250 100-430 100-680 0Z", "#cad2c5", 'opacity=".88"'),
    path("M640 240c250 95 430 95 680 0v390c-250 100-430 100-680 0Z", "#84a98c", 'opacity=".88"'),
    line(800, 210, 800, 700, "#2f3e46", 18, 'opacity=".8"'),
    path("M580 670Q800 555 1020 670", "none", 'stroke="#2f3e46" stroke-width="28" stroke-linecap="round" fill="none"'),
  ].join(""),
  ceramics: () => [
    path("M600 335h400c-15 260-65 385-200 385S615 595 600 335Z", "#f2cc8f"),
    path("M660 275h280c30 0 30 70 0 70H660c-30 0-30-70 0-70Z", "#fff3d6"),
    path("M545 430c-125 70-80 220 70 205", "none", 'stroke="#f2cc8f" stroke-width="45" stroke-linecap="round" fill="none"'),
    path("M1055 430c125 70 80 220-70 205", "none", 'stroke="#f2cc8f" stroke-width="45" stroke-linecap="round" fill="none"'),
    line(550, 750, 1050, 750, "#ffffff", 20, 'opacity=".55"'),
  ].join(""),
  climbing: () => [
    path("M410 760 640 270 790 760Z", "#e9c46a", 'opacity=".86"'),
    path("M700 760 1000 180 1210 760Z", "#f4a261", 'opacity=".78"'),
    circle(830, 355, 40, "#ffffff"),
    line(830, 400, 785, 520, "#ffffff", 24),
    line(805, 455, 920, 390, "#ffffff", 20),
    line(790, 520, 700, 620, "#ffffff", 22),
    line(790, 520, 880, 635, "#ffffff", 22),
  ].join(""),
  electronic: () => [
    rect(440, 440, 720, 240, "#f8fafc", 'rx="36" opacity=".9"'),
    circle(620, 560, 95, "#10002b"),
    circle(980, 560, 95, "#10002b"),
    circle(620, 560, 28, "#00f5d4"),
    circle(980, 560, 28, "#f15bb5"),
    ...[600, 700, 800, 900, 1000].map((x, i) => line(x, 210 + i * 28, x, 360 - i * 22, i % 2 ? "#00f5d4" : "#f15bb5", 18)),
  ].join(""),
  books: () => [
    rect(500, 290, 145, 410, "#dad7cd", 'rx="18"'),
    rect(675, 250, 150, 450, "#a3b18a", 'rx="18"'),
    rect(860, 320, 150, 380, "#ffffff", 'rx="18" opacity=".9"'),
    line(570, 350, 570, 645, "#3a5a40", 12),
    line(750, 315, 750, 650, "#3a5a40", 12),
    circle(1090, 545, 78, "#dad7cd"),
    path("M1165 520c95-10 95 115 0 105", "none", 'stroke="#dad7cd" stroke-width="38" stroke-linecap="round" fill="none"'),
  ].join(""),
  charityrun: () => [
    path("M690 250c-130 110-105 285 110 430 215-145 240-320 110-430-48-40-122-28-165 28-43-56-107-68-155-28Z", "#ffddd2"),
    path("M610 640c150 55 310 55 480 0l28 78c-190 72-370 72-538 0Z", "#006d77"),
    circle(800, 430, 58, "#006d77", 'opacity=".82"'),
    line(800, 490, 800, 610, "#006d77", 30, 'opacity=".82"'),
  ].join(""),
  ai: () => [
    ...[[580, 300], [790, 235], [1000, 330], [655, 560], [910, 610], [1080, 520]].map(([x, y]) => circle(x, y, 58, "#e5e5e5", 'opacity=".9"')),
    line(580, 300, 790, 235, "#fca311", 14),
    line(790, 235, 1000, 330, "#fca311", 14),
    line(580, 300, 655, 560, "#fca311", 14),
    line(655, 560, 910, 610, "#fca311", 14),
    line(1000, 330, 1080, 520, "#fca311", 14),
    line(790, 235, 910, 610, "#fca311", 14),
  ].join(""),
  openmic: () => [
    rect(720, 250, 160, 285, "#f8fafc", 'rx="80" opacity=".92"'),
    ...[755, 800, 845].map((x) => line(x, 300, x, 480, "#240046", 12, 'opacity=".65"')),
    line(800, 535, 800, 690, "#f8fafc", 28),
    line(665, 690, 935, 690, "#f8fafc", 28),
    path("M610 305c-130 95-130 275 0 370", "none", 'stroke="#ff9e00" stroke-width="18" stroke-linecap="round" fill="none" opacity=".8"'),
    path("M990 305c130 95 130 275 0 370", "none", 'stroke="#ff9e00" stroke-width="18" stroke-linecap="round" fill="none" opacity=".8"'),
  ].join(""),
  market: () => [
    rect(390, 430, 820, 260, "#f2e8cf", 'rx="24" opacity=".9"'),
    path("M350 430h900L1150 280H450Z", "#bc6c25"),
    ...[440, 575, 710, 845, 980, 1115].map((x, i) => rect(x, 430, 90, 260, i % 2 ? "#6a994e" : "#386641", 'opacity=".82"')),
    circle(560, 615, 34, "#d62828"),
    circle(640, 615, 34, "#f77f00"),
    circle(720, 615, 34, "#386641"),
    circle(800, 615, 34, "#d62828"),
  ].join(""),
  improv: () => [
    circle(635, 430, 165, "#b2ff9e", 'opacity=".9"'),
    circle(965, 430, 165, "#ff6b6b", 'opacity=".9"'),
    circle(575, 405, 25, "#3c1642"),
    circle(695, 405, 25, "#3c1642"),
    circle(905, 405, 25, "#3c1642"),
    circle(1025, 405, 25, "#3c1642"),
    path("M560 520Q635 585 710 520", "none", 'stroke="#3c1642" stroke-width="24" stroke-linecap="round" fill="none"'),
    path("M890 540Q965 485 1040 540", "none", 'stroke="#3c1642" stroke-width="24" stroke-linecap="round" fill="none"'),
  ].join(""),
  blockchain: () => [
    ...[[520, 325], [800, 230], [1080, 325], [620, 600], [980, 600], [800, 460]].map(([x, y]) => rect(x - 70, y - 55, 140, 110, "#caf0f8", 'rx="24" opacity=".9"')),
    line(590, 325, 730, 250, "#48cae4", 16),
    line(870, 250, 1010, 325, "#48cae4", 16),
    line(520, 380, 620, 545, "#48cae4", 16),
    line(1080, 380, 980, 545, "#48cae4", 16),
    line(690, 600, 910, 600, "#48cae4", 16),
    line(800, 285, 800, 405, "#48cae4", 16),
  ].join(""),
};

mkdirSync(outDir, { recursive: true });

for (const event of events) {
  writeFileSync(
    resolve(outDir, `${event.slug}.svg`),
    base({
      title: event.title,
      colors: event.colors,
      body: icon[event.theme](),
    }),
  );
}

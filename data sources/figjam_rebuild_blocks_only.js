// FigJam rebuild — FigJam-native blocks + connectors ONLY (no Figma frames)
// Target file: https://www.figma.com/board/laEBxkbSgMCRFqNQDQpSeS
// Run via: Figma MCP use_figma, fileKey = laEBxkbSgMCRFqNQDQpSeS

await figma.loadFontAsync({ family: 'Inter', style: 'Regular' });
await figma.loadFontAsync({ family: 'Inter', style: 'Bold' });

// ── Clear all existing nodes ──────────────────────────────────────────
for (const n of [...figma.currentPage.children]) n.remove();

const page = figma.currentPage;

// ── Color palette ─────────────────────────────────────────────────────
const C = {
  aHeader:  { r: 0.18, g: 0.44, b: 0.90 },
  aTrig:    { r: 0.84, g: 0.91, b: 1.00 },
  bHeader:  { r: 0.80, g: 0.15, b: 0.15 },
  bTrig:    { r: 1.00, g: 0.86, b: 0.85 },
  cHeader:  { r: 0.09, g: 0.62, b: 0.37 },
  cTrig:    { r: 0.85, g: 0.97, b: 0.90 },
  product:  { r: 0.10, g: 0.10, b: 0.14 },
  dark:     { r: 0.12, g: 0.12, b: 0.15 },
  white:    { r: 1.00, g: 1.00, b: 1.00 },
};

// ── Helpers ───────────────────────────────────────────────────────────
function blk(label, x, y, w, h, fill, textColor, fontSize) {
  const s = figma.createShapeWithText();
  s.shapeType = 'ROUNDED_RECTANGLE';
  s.x = x; s.y = y;
  s.resize(w, h);
  s.fills = [{ type: 'SOLID', color: fill }];
  s.text.characters = label;
  const len = label.length;
  s.text.setRangeFontSize(0, len, fontSize);
  s.text.setRangeFills(0, len, [{ type: 'SOLID', color: textColor }]);
  s.text.textAlignHorizontal = 'CENTER';
  page.appendChild(s);
  return s;
}

function arrow(fromNode, toNode) {
  const c = figma.createConnector();
  c.connectorStart = { endpointNodeId: fromNode.id, magnet: 'RIGHT' };
  c.connectorEnd   = { endpointNodeId: toNode.id,   magnet: 'LEFT'  };
  c.strokeWeight   = 2;
  c.connectorLineType = 'ELBOWED';
  page.appendChild(c);
  return c;
}

// ── Data ──────────────────────────────────────────────────────────────
const SEGS = [
  {
    hColor: C.aHeader, tColor: C.aTrig,
    name:  'A: Chronic Gap',
    core:  '"Why is this so easy for everyone else?"',
    desc:  'Never developed social confidence.\nGap has existed for years or decades.',
    triggers: [
      'Public Rejection',
      'Dating App Exhaustion',
      'Age Milestone',
      'Peer Success Contrast',
      'New City or Job',
    ],
  },
  {
    hColor: C.bHeader, tColor: C.bTrig,
    name:  'B: Ruptured Man',
    core:  '"How do I become myself again—but better?"',
    desc:  'Had confidence that a life event collapsed.\nNow socially exposed for the first time.',
    triggers: [
      'Divorce',
      'Long-Term Relationship Ending',
      'Cheating & Betrayal',
      'Identity-Losing Relationship',
      'Redundancy / Firing',
      'Geographic Relocation',
      'Kids Leaving Home',
      'Left Religious Community',
    ],
  },
  {
    hColor: C.cHeader, tColor: C.cTrig,
    name:  'C: Professional Optimizer',
    core:  '"I\'ve built everything—why not this?"',
    desc:  'Gym-disciplined, career-strong.\nLast untrained muscle: intimate connection.',
    triggers: [
      'New Love Interest',
      'Attraction Plateau',
    ],
  },
];

// ── Layout constants ──────────────────────────────────────────────────
const COLS      = 4;
const CW        = 220;
const CH        = 80;
const CGAP_H    = 14;
const CGAP_V    = 12;
const BAND_GAP  = 72;

const TX        = 100;
const SEG_PAD   = 64;
const SX        = TX + COLS * (CW + CGAP_H) - CGAP_H + SEG_PAD;
const SW        = 360;
const SH_MIN    = 120;

const PROD_PAD  = 80;
const PX        = SX + SW + PROD_PAD;
const PW        = 300;
const PH        = 210;

// ── Pre-compute band Y positions ──────────────────────────────────────
const segTop = [], segBot = [];
let curY = 100;
for (const seg of SEGS) {
  const rows = Math.ceil(seg.triggers.length / COLS);
  const h    = rows * CH + (rows - 1) * CGAP_V;
  segTop.push(curY);
  segBot.push(curY + h);
  curY += h + BAND_GAP;
}
const totalSpan = segBot[SEGS.length - 1] - segTop[0];
const PY        = segTop[0] + totalSpan / 2 - PH / 2;

// ── Title ─────────────────────────────────────────────────────────────
const titleNode = figma.createText();
titleNode.fontName = { family: 'Inter', style: 'Bold' };
titleNode.characters = 'Male Charisma Mastery — Audience Segmentation';
titleNode.fontSize = 30;
titleNode.fills = [{ type: 'SOLID', color: C.dark }];
titleNode.x = TX;
titleNode.y = 40;
page.appendChild(titleNode);

// ── Product block ─────────────────────────────────────────────────────
const productBlk = blk(
  'SAME PRODUCT\n\nCharisma & Presence Course\n—\nFramed differently per segment',
  PX, PY, PW, PH, C.product, C.white, 14
);

// ── Segments, triggers, connectors ───────────────────────────────────
for (let si = 0; si < SEGS.length; si++) {
  const seg    = SEGS[si];
  const sy     = segTop[si];
  const ey     = segBot[si];
  const bandH  = ey - sy;
  const sbH    = Math.max(bandH, SH_MIN);
  const sbY    = sy + (bandH - sbH) / 2;

  // Trigger cards
  const trigBlks = seg.triggers.map((t, ti) => {
    const row = Math.floor(ti / COLS);
    const col = ti % COLS;
    return blk(
      t,
      TX + col * (CW + CGAP_H),
      sy + row * (CH + CGAP_V),
      CW, CH,
      seg.tColor, C.dark, 13
    );
  });

  // Segment header block
  const label  = seg.name + '\n\n' + seg.core + '\n\n' + seg.desc;
  const segBlk = blk(label, SX, sbY, SW, sbH, seg.hColor, C.white, 14);

  // Trigger → segment
  for (const tb of trigBlks) arrow(tb, segBlk);

  // Segment → product
  arrow(segBlk, productBlk);
}

return 'Done';

# reel-kit — Visual direction

> Validated 16/09/2026. Derived from the "paper" style of Nate Herk's HyperFrames Student Kit
> (MIT, `style-library/01-vox-explainer`), AIS accent replaced with orange, adapted to 9:16.
> Every scene traces its palette, type and motion back to this file. The values live in `tokens.css`.

## Style

Warm paper, warm ink, a single orange accent. Cut-out cards, slightly askew, drop shadow.
Real objects: website captures, screens, hands, paper. It always moves, never smoothly: snap, stutter,
overshoot. Grain texture everywhere. Never add the creator's own logo unless the brand brief asks for it: the brand is the editorial chrome and the palette.

Visual references: `assets/references/` (contact sheets of Nate's reels, comparison from 15/09).

## Colors

| Token | Hex | Role |
|---|---|---|
| `--paper` | `#efe9dc` | paper background |
| `--paper-2` | `#e6dcc4` | kraft paper, second stacked sheet |
| `--ink` | `#17130e` | text, ink |
| `--accent` | `#f26a1b` | THE only accent: fills (checkmarks, tags), caption keyword |
| `--accent-ink` | `#d35c18` | the same accent as text on paper (3:1 contrast required by `check`) |
| `--alarm` | `#e23b2e` | hand-drawn circles and strike-throughs only |
| `--muted` | `rgba(23,19,14,.55)` | kicker, metadata |

One accent per frame. Never two oranges fighting each other. Never pure white or pure black.

## Type

- **Headlines**: Archivo 900, uppercase, tracking -0.03em, 96 to 120 px. The accent word in orange Fraunces italic.
- **Kicker**: Archivo 700, uppercase, tracking 0.16em, 26 px, ink grey. Format `02 / SCHEDULING` on the left, `02 — 04` on the right.
- **Handwritten notes**: Caveat 700, red, rotated -6°. Never useful text, only annotations.
- **Card body**: Archivo 900 for rows, Archivo 700 for times and metadata, 40 to 44 px.
- **Captions**: Archivo 900, 62 px, white, black outline, on an 80% ink pill (assumes a light background), orange keyword. On EVERY frame, centered, at the video/paper junction.

Fonts are local in `assets/fonts/` (OFL). No Google Fonts call at render time.

## Layout (1080×1920)

| Layout | When | Geometry |
|---|---|---|
| **C** split, face on top (default) | you explain and the card illustrates | full-frame video 0→1000 px, paper below, card biting into the video at ~940 px |
| **B** split, face at the bottom | the card needs height | paper 0→1000 px, rounded face box 900×780 at `left:90 top:1030`, drop shadow |
| **D** full screen | one idea, one number, one proof | full-frame paper, no face |
| **F** full-frame face | hook, CTA, punchline | video alone + captions |

Alternate every 2 to 4 s. Never the same layout twice in a row. Never anything over the face.
Cards: rotation -1.4°, second kraft sheet offset behind, shadow `8px 12px 24px`.

## Motion

- Entrance: `back.out(2.2)`, 0.42 s. Choppy: `steps(6)`. Exit: 0.3 s, never a slow fade.
- First element at +0.1 s from scene start. Stagger 0.08 to 0.14 s between sub-elements.
- Ambience: a single slow movement per scene (camera push 1.0→1.04, or pan across a capture).
- Every sub-composition timeline ends with `tl.to({}, { duration: SLOT }, 0)` (see MOTION.md).

## Transitions

Hard cut by default, the entrance stutter does the transition. Horizontal whip 0.25 s when changing worlds
(split → full screen). Never a crossfade.

## Forbidden

Pure white, pure black, decorative gradients, glows, perfectly centered layouts, Helvetica, half-empty card,
text unreadable at phone size, invented mockup when the real thing exists, the creator's own logo (unless the brand brief asks for it), two accents per frame,
the AIS blue `#37BDF8` (property of AIS, not licensed).

# Auth UI — design inventory

The ChatGPT sign-in / sign-up / consent page (`/oauth/login`) and its error
pages. Code: `app/mcp/auth/pages.py` (markup, CSS, copy), served by the MCP
service; fonts and favicon in `app/mcp/auth/static/`.

## Sources

**Authoritative:** Figma *Mita-Finance-Brand-Guidelines*
(`512WdjnhPJXM8jeHKcg4g8`), page **Template** (`1:3`). Its frames keep the
template's names ("Branding Guidelines Template (FREE) by Sam Stoof - N");
the ones used:

| Frame | Node | Content |
|---|---|---|
| 30 | `2014:2` | Cover — lockup, "Mita Finance / Control Your money. Daily." |
| 4, 5, 6, 7 | `5:68`, `5:688`, `5:711`, `5:728` | Mission, vision, positioning; values & personality; audience; goal of the guidelines |
| 9 | `5:83` | Logomark |
| 10 | `5:545` | Logo variants (master logomark `2011:206`, wordmark `2011:212`) |
| 11, 12 | `5:567`, `5:630` | Logo do's / don'ts |
| 15, 16, 17 | `5:463`, `5:387`, `5:425` | Colors, gradients, color combinations |
| 19, 20, 22 | `5:211`, `5:370`, `5:192` | Manrope, Sora, text structure |
| 29, 24 | `6:911`, `5:228` | Pitch grid, imagery |
| — | local variables | collection "Variable collection" (6 colors) |

**Product language (secondary):** Figma `hGPeeY99LUn1Q2MSpmHBQu` (website
capture, frame `1:2`) and the Flutter theme (`mobile_app/lib/theme/`).

## Values defined in Figma

| What | Value | Where |
|---|---|---|
| Mita Blue — primary text, anchor | `#193C57` | variable *Mita Blue* |
| Mita yellow — highlights and key actions | `#FFD25F` | variable *Mita yellow*; Color Combinations text |
| Mita Red / Mita Green / Mita purple | `#F44336` / `#14B8A6` / `#6B73FF` | variables |
| Mita Back — page background | `#FFF9F0` | variable *Mita Back* |
| Light teal (pairs with Mita Green) | `#CCFBF1` | Color Combinations |
| Approved gradients | `#193C57`↔`#FFD25F`, `#F44336`↔`#14B8A6`, `#6B73FF`↔`#FFD25F` | Gradients |
| Approved pairings | yellow + blue, purple + red, green + light teal | Color Combinations |
| Primary font | **Manrope** — UI headlines, key figures, onboarding and core product flows; no light weights for financial data | Typography (Manrope) |
| Secondary font | **Sora** — marketing headlines, section dividers, feature highlights; not for dense data, long paragraphs or labels under 16 px | Typography (Sora) |
| Data font | **Space Mono** — "highlights financial data with precision" | Text Structure |
| Type scale | 1.25 ratio | Text Structure |
| Wordmark | "Mita", Manrope ExtraBold, letter-spacing −2 %, `#193C57` | Logo Variants, cover |
| Logomark | four modules: M red, I purple, T green, A yellow | Logomark |
| Logo rules | strong contrast; preserve proportions; approved palette; clear space; soft shadows only; never recreate — master files only | Logo Do's / Don'ts |
| Grid (decks) | 24 px margins, 24 px gutter | Pitch Grid |
| Voice | "Confident but not loud. Intelligent yet approachable. Structured, calm, and forward thinking … never with financial jargon or fear." | Values & Personality |

Not defined in Figma: buttons, inputs, cards, corner radii, shadow values,
status colors, a UI spacing scale, dark mode. The Colors frame also carries
template residue (RGB "255, 90, 95", HSL "43%, 69%, 100%" next to
`#FFD25F`); the hex values and the variables agree and are what is used.

## Derived for this page

Decisions, not brand facts. Contrast ratios are WCAG 2.x.

| What | Value | Basis |
|---|---|---|
| Secondary text | `#4C6679` | Mita Blue 78 % over Mita Back; 5.8:1 on `#FFF9F0`, 6.0:1 on white |
| Hairlines | Mita Blue 14 % / 24 % | Figma's most used stroke is 1 px Mita Blue |
| Input border | `#7A8E9E` | Mita Blue 58 % on white; 3.4:1 (non-text contrast) |
| Focus ring | 3 px Mita purple, 2 px offset | 3.8:1 on white |
| Error | text `#BA1A1A` on `#FEECEB`, border Mita Red 40 % | Flutter `colorScheme.error`; Mita Red 10 % tint |
| Notice | Mita yellow 31 % | fill observed in Figma (`#FFD25F` @ 0.31) |
| Positive | Mita Green for icons and progress only (2.5:1 as text) | palette |
| Primary button | Mita Blue fill, Mita yellow text (8.0:1), pill, Manrope Bold 16, ≥ 54 px; hover `#2B5876` | yellow + blue pairing; website CTA text; Flutter `primaryLight` |
| Secondary button | transparent, Mita Blue text, 1 px Mita Blue 24 % | — |
| Inputs | ≥ 50 px, radius 14, Manrope 500 16 px | Flutter inputs: radius 16, min 48 px |
| Cards | white, radius 24 (panels) / 16 (items), `0 16px 40px rgba(25,60,87,.10)` | "soft shadows only"; Flutter cards radius 16 |
| Headings | Sora 700 (hero, card and section titles ≥ 24 px) | Figma conflicts (Manrope page: "UI headlines"; Text Structure: "Sora defines headlines"); the Flutter theme uses Sora for headings |
| UI and body | Manrope 400–700 | Figma |
| Amounts, labels, step numbers | Space Mono 400/700 | Figma |
| Sizes | 16 body; 20 / 25 / 31 / 39 / 49 headings; hero clamps 34 → 54 | 1.25 scale |
| Spacing | multiples of 4/8; card padding 24 (32 from 560 px) | 24 px grid |
| Logo | full-color lockup: master vectors of `2011:206` + `2011:212` at the master offset (+92.39, +14.4); favicon = logomark | Logo Variants |
| Theme | light only (`color-scheme: light`) | the brand system is light; no dark spec |

## Conflicts noticed

* The mobile app ships an older hand-drawn "mita finance" logo on a yellow
  circle (`mobile_app/assets/logo/mitalogo.png`); Figma defines the geometric
  logomark + Manrope wordmark. This page follows Figma; the app is unchanged.
* `CLAUDE.md` (website section) gives the background as `#FFF8F0` and the
  logomark as four rounded squares; Figma says `#FFF9F0` and letter-shaped
  modules. The Flutter theme already uses `#FFF9F0`.
* Flutter status colors are Material (`#4CAF50`, `#FF9800`); Figma has none.
  This page uses brand colors only.
* Website CTAs use a navy→purple gradient, which is not an approved Figma
  gradient; this page uses solid Mita Blue.

## Page rules

* No JavaScript and nothing third-party (CSP `default-src 'none'`, no
  `script-src`; `font-src 'self'` for the three self-hosted fonts).
* Fonts: WOFF2 subsets built by `scripts/mcp/build_auth_fonts.py` — Manrope
  and Sora variable (400–700) from the app's OFL files, Space Mono from
  google/fonts (SHA-256 pinned); 74 KB together, cached as immutable.
* Motion: one entrance sequence of the demo on wide screens, CSS only, none
  under `prefers-reduced-motion`.
* Copy states facts from `docs/chatgpt-app/data-inventory.md`; demo figures
  are fictional and labelled so. No "bank-grade", "encrypted", "free" or
  similar claims (tested).
* Review screenshots: `docs/chatgpt-app/review/auth-ui/`, produced by
  `scripts/mcp/auth_ui_screenshots.py`.

# Ciel AI website

The new landing page for Ciel AI, built as a static Next.js site. It sits next to the live landing in `../landing/`, which still serves https://ciel-ai.web.id/ until the owner decides to switch.

The page is drawn as a night investigation map: each real test case from the app (20 Oktober 2026) is a route to its sources, and the fake-journal case runs into open water and is struck out. An original 3D robot, built from code with React Three Fiber, follows the pointer and changes pose as the visitor scrolls.

## Run it

```bash
npm install
npm run dev
```

The dev server prints its local URL. For the production build:

```bash
npm run build
```

`npm run build` writes the static site to `out/` and then runs `scripts/csp.mjs`, which adds a Content-Security-Policy with a SHA-256 hash for every inline script Next.js generated. Serve `out/` with any static server to preview it, for example `npx serve out`.

Requires Node 20.9 or newer.

## Where things live

- `src/content/site.ts` holds every word and fact on the page. Edit copy there, not in components.
- `src/components/` has one file per section. `MapArt.tsx` draws the map, `ResearchMap.tsx` is the hero's interactive version, and `Story.tsx` is the pinned "Dari pertanyaan ke sumber" section.
- `src/three/robot.ts` builds the robot geometry. `src/components/RobotStage.tsx` is the canvas, lights and pose animation, and `src/components/RobotLayer.tsx` decides when to load it.
- `src/lib/robotBus.ts` is the small shared state between the page and the robot (section poses, the bust frame, pointer, primary-button focus).
- `src/components/RobotBust.tsx` places a still bust of the robot on the page. `public/robot-bust.webp` (hero and phones, the LCP image) and `public/robot-bust-closing.webp` are captures of that bust from the live three.js scene (GPU headless Chrome, transparent background, clipped to the box); `public/robot-palsu.webp` is the still for the fake-journal section.
- `DESIGN.md` records the design decisions and the reason for each.

## Behaviour worth knowing

- The 3D scene loads on the visitor's first pointer move, touch, scroll or key press. Until then the still bust shows the robot, so the first paint never waits for three.js.
- In the hero, on phones and in the closing section, the live robot fits itself to the still bust's box on the page (`[data-robot-anchor]`) and a clipping plane cuts it at the chest. That is why it stands behind the map sheet, the route strip or the footer at every screen size and scrolls with them. In the other sections it stands in the viewport.
- Moving the pointer anywhere in the hero moves a pool of light across the map. The route and the pins brighten where it falls.
- The robot is an android head with a sculpted face (almond eyes with lids, nose, lips, chin, a defined jaw) in teal lacquer. The face plate is cut from the skull by real grooves with a gold strip at their floor, the skin carries printed gold dots and chips, and the ears are dials with the Kepingan logo on a steel hub. The head turns and nods from the top of the neck and, outside the closing section, never turns to face the viewer. Its eyes are glossy black eyeballs behind the lids with glowing irises, and the upper lids blink and squint. They follow the pointer and react to what happens on the page: they sweep side to side and then turn gold when a case finds its sources, dim while the head shakes when the fake journal is not found, widen when the primary button is hovered or focused, and brighten when the pointer rests on the robot's head. Every reaction is triggered by an event and lasts under 3 seconds.
- With `prefers-reduced-motion: reduce` the page keeps the still images, scrolls natively, holds the map's light still and shows the finished story map. Without WebGL2 (or if the renderer fails) the still images stay; smooth scroll and the story map's scroll drawing still run on wide screens.
- GSAP, ScrollTrigger and Lenis are downloaded only on screens 1024px and wider without reduced motion. Phones and tablets scroll natively and show the robot in its own block under the nav.
- The primary button "Masuk dengan Google" turns the robot toward it on hover and on keyboard focus.

## Tests

`tests/test_website.py` in the repo root checks the site against the same rules as the old landing: plan names, prices and features match `pricing.PLANS`, app links only go to known pages, the fake-journal reply is quoted word for word, only the real test date appears, and no em dash is in the source. Run it from the repo root:

```bash
py -3.10 -m unittest tests.test_website
```

The source checks always run. The checks on the rendered page and the CSP run after `npm run build` has produced `out/index.html`.

## Measured

Lighthouse 13.5.0 against the built site served with gzip on the development laptop (8 November 2026):

| | Performance | Accessibility | Best practices | SEO | LCP | TBT | CLS |
|---|---|---|---|---|---|---|---|
| Mobile | 85 | 100 | 100 | 100 | 3.7 s | 260 ms | 0 |
| Desktop | 99 | 100 | 100 | 100 | 0.9 s | 0 ms | 0 |

These numbers do not include the 3D scene, which loads after the first interaction and which Lighthouse never triggers.

## Not done yet

- ciel-ai.web.id still points at `../landing/`. Switching means building this site in `.github/workflows/pages.yml` instead of uploading `landing/`.
- The owner has not yet confirmed the robot model as final, and it has not been tested on a phone with a real GPU.
- The map labels are hidden from screen readers on purpose, because every fact on the map is repeated in the HTML next to it.

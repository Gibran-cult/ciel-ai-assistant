import ast
import re
import unittest
from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def app_constants():
    """String constants assigned at the top level of app.py."""
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                values[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    return values


def tokens(css_block):
    return dict(re.findall(r"(--c-[a-z-]+):\s*([^;]+);", css_block))


def contrast(a, b):
    def luminance(hex_colour):
        channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class ThemeTokensTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        constants = app_constants()
        cls.css = constants["CIEL_CSS"]
        cls.light = tokens(cls.css.split(":root {", 1)[1].split("}", 1)[0])
        cls.dark = tokens(constants["DARK_TOKENS"])

    def test_every_light_colour_token_has_a_dark_value(self):
        # A token added for light mode only would leave that colour light on
        # a dark page.
        self.assertEqual(set(self.light) - set(self.dark), set())

    def test_dark_tokens_follow_the_device_and_the_toggle(self):
        self.assertIn('@media (prefers-color-scheme: dark) {\n    :root:not([data-ciel-theme="light"]) {{{DARK_TOKENS}}}', self.css)
        self.assertIn(':root[data-ciel-theme="dark"] {{{DARK_TOKENS}}}', self.css)
        self.assertIn('CIEL_CSS.replace("{{{DARK_TOKENS}}}", "{" + DARK_TOKENS + "}")', APP_PATH.read_text(encoding="utf-8"))

    def test_sidebar_toggle_icons_follow_the_tokens(self):
        # Streamlit colours these icons itself (light theme), and the collapse
        # button only appears on hover, so it stayed black in dark mode.
        for button in ("stExpandSidebarButton", "stSidebarCollapseButton"):
            with self.subTest(button=button):
                self.assertIn(f'[data-testid="{button}"] [data-testid="stIconMaterial"]', self.css)
        self.assertIn('[data-testid="stSidebarCollapseButton"] button:hover', self.css)

    def test_top_bar_buttons_are_quiet_ghost_buttons(self):
        # Masuk follows the claude.ai app: no border, 8px corners, a soft grey
        # background that darkens on hover (no underline).
        nav = self.css.split("/* Top bar nav,", 1)[1].split("/* Account button", 1)[0]
        self.assertIn("border: 1px solid transparent;", nav)
        self.assertIn("border-radius: 8px;", nav)
        self.assertNotIn("background-image", nav)
        self.assertIn("background: var(--c-raised);", nav)
        self.assertIn("background: var(--c-raised-strong);", nav)
        self.assertIn("font-weight: 600;", nav)

    def test_account_button_stays_at_the_bottom_of_the_sidebar(self):
        # Sticky on the wrapper Streamlit puts around the keyed container: a
        # sticky element only moves inside its parent, and the keyed block
        # alone is exactly as tall as that wrapper.
        wrapper = '[data-testid="stLayoutWrapper"]:has(> .st-key-sideaccount) {'
        self.assertIn(wrapper, self.css)
        rule = self.css.split(wrapper, 1)[1].split("}", 1)[0]
        for line in ("position: sticky;", "bottom: 0;", "margin-top: auto;", "background: var(--c-surface);"):
            self.assertIn(line, rule)
        self.assertIn('[data-testid="stSidebarUserContent"]:has(.st-key-sideaccount) {', self.css)
        # The menu's email is HTML, so markdown cannot turn it into a mailto link.
        self.assertIn('<div class="ciel-account-email">', APP_PATH.read_text(encoding="utf-8"))

    def test_download_buttons_links_and_answer_headings_follow_the_tokens(self):
        # Found in the browser on 2026-10-19 with a Riset Skripsi answer in dark
        # mode: "Unduh DOCX" was light on light (.stDownloadButton is not
        # .stButton), source links were the light theme's navy (~3:1), and the
        # "#" title rendered at 44 px in Streamlit's own font.
        scope = ':is(.stApp, [data-testid="stPopoverBody"])'
        self.assertIn(f"{scope} .stDownloadButton > button {{", self.css)
        self.assertIn(f"{scope} .stDownloadButton > button:hover {{", self.css)
        self.assertIn('.stApp [data-testid="stMarkdownContainer"] a { color: var(--c-accent); }', self.css)
        self.assertIn('.stApp [data-testid="stBaseLinkButton-primary"] {', self.css)
        heading = '[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] h1 {'
        self.assertIn(heading, self.css)
        rule = self.css[self.css.index(heading):].split("}", 1)[0]
        self.assertIn("font-family: var(--font-serif);", rule)
        self.assertIn("font-size: 1.6rem;", rule)

    def test_widget_rules_reach_popover_content(self):
        # Popovers (account menu, "Proyek baru") render outside .stApp, so
        # rules scoped to .stApp left their buttons and expander light in dark
        # mode, with light text on top.
        # The Riset Skripsi dialog (st.dialog) renders outside .stApp too.
        scope = ':is(.stApp, [data-testid="stPopoverBody"], [data-testid="stDialog"])'
        self.assertNotIn(".stApp .stButton > button", self.css)
        self.assertIn(f"{scope} .stButton > button,", self.css)
        self.assertIn(f'{scope} .stButton > button[kind="primary"]', self.css)
        self.assertIn(':is(.stApp, [data-testid="stPopoverBody"]) [data-testid="stExpander"] summary', self.css)
        self.assertIn('[data-testid="stDialog"] [role="dialog"] {', self.css)
        self.assertIn('[data-testid="stDialog"] :is(input, textarea) { color: var(--c-text);', self.css)
        # Streamlit 1.65 draws the text input box on this element.
        self.assertIn('[data-testid="stTextInputRootElement"] {', self.css)
        # ...and the text area box on this one. Without it the Riset Skripsi
        # topic field kept the light theme's background under light dark-mode
        # text, so typing was invisible (seen on the web, 2026-10-19).
        self.assertIn('[data-testid="stTextAreaRootElement"],\n[data-testid="stTextInputRootElement"] {', self.css)
        # Disabled buttons ("Hapus semua memoriku" before its checkbox) must
        # not pick up the hover background: it met Streamlit's light-theme
        # disabled text and hid the label. The rule must come after the
        # primary-button rules so it also wins for disabled primary buttons.
        disabled = f"{scope} .stButton > button:disabled:hover"
        self.assertIn(disabled, self.css)
        self.assertGreater(self.css.index(disabled), self.css.index(f'{scope} .stButton > button[kind="primary"]:hover'))
        self.assertIn(f'{scope} .stButton > button:disabled :is(p, [data-testid="stIconMaterial"]) {{ color: inherit; }}', self.css)
        # Project file uploader: button, size/type hint and the "?" help icon.
        self.assertIn('[data-testid="stFileUploaderDropzone"] button {', self.css)
        self.assertIn('[data-testid="stFileUploaderDropzoneInstructions"] span { color: var(--c-faint); }', self.css)
        self.assertIn('[data-testid="stTooltipIcon"] [data-testid="stTooltipHoverTarget"] svg.icon { stroke: var(--c-faint); }', self.css)
        for kind, token in (("Success", "--c-ok"), ("Error", "--c-err"), ("Warning", "--c-warn")):
            self.assertIn(f'[data-testid="stAlertContent{kind}"] {{ color: var({token}); }}', self.css)

    def test_text_pairs_pass_wcag_aa_in_both_themes(self):
        pairs = [
            ("--c-text", "--c-bg"), ("--c-muted", "--c-bg"), ("--c-faint", "--c-bg"),
            ("--c-faint", "--c-surface"), ("--c-faint", "--c-raised"), ("--c-accent", "--c-bg"),
            ("--c-accent-ink", "--c-accent"), ("--c-accent-ink", "--c-accent-hover"),
            ("--c-gold-ink", "--c-gold"), ("--c-ok", "--c-bg"), ("--c-warn", "--c-bg"), ("--c-err", "--c-bg"),
        ]
        for name, palette in (("light", self.light), ("dark", self.dark)):
            for fg, bg in pairs:
                with self.subTest(theme=name, pair=(fg, bg)):
                    self.assertGreaterEqual(contrast(palette[fg], palette[bg]), 4.5)
            with self.subTest(theme=name, pair="input border"):
                self.assertGreaterEqual(contrast(palette["--c-control"], palette["--c-surface"]), 3.0)


class ThemeScriptTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        constants = app_constants()
        cls.js = constants["UI_JS"]
        cls.toggle = constants["THEME_TOGGLE_HTML"]
        cls.source = APP_PATH.read_text(encoding="utf-8")

    def test_toggle_is_a_labelled_button_in_the_top_bar(self):
        self.assertIn('<button type="button"', self.toggle)
        self.assertIn("data-ciel-theme-toggle", self.toggle)
        self.assertIn("aria-label=", self.toggle)
        self.assertNotIn("<svg", self.toggle)  # st.html strips it; the icon is CSS
        self.assertIn('st.html(THEME_TOGGLE_HTML, width="content")', self.source)
        self.assertIn("st.html(UI_JS, unsafe_allow_javascript=True)", self.source)

    def test_choice_is_kept_on_html_and_survives_blocked_storage(self):
        self.assertIn("const root = document.documentElement;", self.js)
        self.assertIn("root.dataset.cielTheme = next;", self.js)
        self.assertIn("localStorage.setItem(KEY, next)", self.js)
        self.assertEqual(self.js.count("try {"), 2)
        self.assertIn("prefersDark.addEventListener('change', apply)", self.js)
        self.assertIn("if (window.__cielUi) return;", self.js)

    def test_composer_is_lifted_above_streamlit_cloud_badges(self):
        # On Android the send button sat under Streamlit Cloud's corner
        # badges, which live in the page around the app's iframe.
        self.assertIn("if (window.self !== window.top) root.dataset.cielHosted = '1';", self.js)
        css = app_constants()["CIEL_CSS"]
        rule = css.split("@media (max-width: 960px) {\n    :root[data-ciel-hosted]", 1)
        self.assertEqual(len(rule), 2, "hosted composer rule missing")
        self.assertIn('[data-testid="stBottomBlockContainer"] { padding-bottom: 3.5rem; }', rule[1].split("}\n}", 1)[0])

    def test_upload_tooltip_is_short_and_in_indonesian(self):
        self.assertIn("const UPLOAD_HINT = 'Lampirkan file atau foto';", self.js)
        self.assertIn("tip.textContent.startsWith('Upload or drag and drop')", self.js)
        self.assertIn("button.setAttribute('aria-label', UPLOAD_HINT)", self.js)


if __name__ == "__main__":
    unittest.main()

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

    def test_upload_tooltip_is_short_and_in_indonesian(self):
        self.assertIn("const UPLOAD_HINT = 'Lampirkan file atau foto';", self.js)
        self.assertIn("tip.textContent.startsWith('Upload or drag and drop')", self.js)
        self.assertIn("button.setAttribute('aria-label', UPLOAD_HINT)", self.js)


if __name__ == "__main__":
    unittest.main()

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
        cls.dark = tokens(cls.css.split(":root {", 1)[1].split("}", 1)[0])
        cls.light = tokens(constants["LIGHT_TOKENS"])

    def test_every_colour_token_exists_in_both_themes(self):
        # A token set for one theme only would keep the other theme's colour.
        self.assertEqual(set(self.light) ^ set(self.dark), set())

    def test_dark_is_the_default_and_light_is_opt_in(self):
        self.assertIn(':root[data-ciel-theme="light"] {{{LIGHT_TOKENS}}}', self.css)
        self.assertNotIn("prefers-color-scheme", self.css)
        self.assertIn('CIEL_CSS.replace("{{{LIGHT_TOKENS}}}", "{" + LIGHT_TOKENS + "}")', APP_PATH.read_text(encoding="utf-8"))
        self.assertEqual(self.dark["--c-bg"], "#0e0d0c")
        self.assertEqual(self.dark["--c-primary"], "#f4f4f2")
        self.assertEqual(self.light["--c-bg"], "#f1f1ee")
        self.assertEqual(self.light["--c-primary"], "#161513")

    def test_streamlit_base_theme_is_dark(self):
        # Streamlit paints its own theme before CIEL_CSS arrives; a light base
        # flashed white on every load once dark became the default.
        config = (APP_PATH.parent / ".streamlit" / "config.toml").read_text(encoding="utf-8")
        self.assertIn('base = "dark"', config)
        self.assertIn('backgroundColor = "#0e0d0c"', config)

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

    def rule(self, selector):
        """Declarations of the first rule that lists `selector` (alone or grouped)."""
        self.assertRegex(self.css, re.escape(selector) + r"\s*[{,]")
        after = re.split(re.escape(selector) + r"\s*(?=[{,])", self.css, maxsplit=1)[1]
        return after.split("{", 1)[1].split("}", 1)[0]

    def test_pricing_and_privacy_styles_reach_the_settings_dialog(self):
        import pricing
        import privacy
        for name, css in (("pricing", pricing.PRICING_CSS), ("privacy", privacy.PRIVACY_CSS)):
            with self.subTest(module=name):
                self.assertNotRegex(css, r"(?m)^\s*\.stApp ")
                self.assertIn(':is(.stApp, [data-testid="stDialog"]) ', css)

    def test_settings_dialog_has_a_menu_and_a_scrolling_panel(self):
        self.assertIn('[data-testid="stDialog"] .st-key-settingsnav', self.css)
        panel = self.rule('[data-testid="stDialog"] .st-key-settingspanel')
        self.assertIn("overflow-y: auto;", panel)

    def test_pro_badge_text_is_readable_on_its_tint(self):
        # --c-accent-ink is for text on a solid accent; on the 10-14% tint it
        # would nearly vanish (white on paper, ink on near-black).
        pill = self.rule('[data-testid="stDialog"] .ciel-plan-pill.ciel-plan-pro')
        self.assertIn("background: var(--c-accent-soft);", pill)
        self.assertIn("color: var(--c-accent);", pill)

    def test_settings_button_is_a_bare_icon(self):
        # Ciel, 2026-10-28: the ⚙ needs no text and no box, signed in or not.
        base = '[data-testid="stSidebar"] .st-key-sideaccount .st-key-opensettings'
        button = self.rule(base + " button")
        for line in ("border: 0;", "background: transparent;", "color: var(--c-muted);"):
            self.assertIn(line, button)
        hover = self.rule(base + " button:hover")
        self.assertIn("background: transparent;", hover)
        self.assertIn("color: var(--c-text);", hover)
        self.assertNotIn("--c-raised", hover)
        # The label stays for screen readers but is hidden on screen.
        self.assertIn("clip-path: inset(50%);", self.rule(base + ' [data-testid="stMarkdownContainer"]'))

    def test_account_button_stays_at_the_bottom_of_the_sidebar(self):
        # Sticky on the wrapper Streamlit puts around the keyed container: a
        # sticky element only moves inside its parent, and the keyed block
        # alone is exactly as tall as that wrapper.
        wrapper = '[data-testid="stLayoutWrapper"]:has(> .st-key-sideaccount) {'
        self.assertIn(wrapper, self.css)
        rule = self.css.split(wrapper, 1)[1].split("}", 1)[0]
        for line in ("position: sticky;", "bottom: 0;", "margin-top: auto;", "background: var(--c-bg);"):
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

    def test_primary_buttons_are_pills_on_the_primary_token(self):
        scope = ':is(.stApp, [data-testid="stPopoverBody"], [data-testid="stDialog"])'
        rule = self.css.split(f'{scope} .stButton > button[kind="primary"] {{', 1)[1].split("}", 1)[0]
        for line in ("background: var(--c-primary);", "color: var(--c-on-primary);", "border-radius: var(--r-pill);"):
            self.assertIn(line, rule)

    def test_user_messages_are_right_aligned_bubbles(self):
        # The user avatar is a material icon (stChatMessageAvatarCustom), so
        # the message is found by its content's aria-label instead.
        user = '[data-testid="stChatMessage"]:has(> [aria-label="Chat message from user"])'
        rule = self.css.split(user + " {", 1)[1].split("}", 1)[0]
        for line in ("margin-left: auto;", "max-width: 80%;", "background: var(--c-surface);"):
            self.assertIn(line, rule)
        self.assertIn(user + " > :first-child { display: none; }", self.css)

    def test_curtain_plays_once_per_session(self):
        js = app_constants()["UI_JS"]
        self.assertIn("sessionStorage.getItem('ciel-curtain')", js)
        self.assertIn("prefers-reduced-motion", js)
        self.assertIn(".ciel-curtain {", self.css)
        rule = self.css.split(".ciel-curtain {", 1)[1].split("}", 1)[0]
        self.assertIn("pointer-events: none;", rule)

    def test_input_character_counter_follows_the_tokens(self):
        # With the dark base theme, Streamlit painted the "0/80" counter of the
        # Riset Skripsi field near-white on the light dialog (1.06:1).
        self.assertIn(':is(.stApp, [data-testid="stPopoverBody"], [data-testid="stDialog"]) [data-testid="InputInstructions"] { color: var(--c-faint); }', self.css)

    def test_text_pairs_pass_wcag_aa_in_both_themes(self):
        pairs = [
            ("--c-text", "--c-bg"), ("--c-muted", "--c-bg"), ("--c-faint", "--c-bg"),
            ("--c-faint", "--c-surface"), ("--c-faint", "--c-raised"), ("--c-accent", "--c-bg"),
            ("--c-accent-ink", "--c-accent"), ("--c-accent-ink", "--c-accent-hover"),
            ("--c-gold-ink", "--c-gold"), ("--c-ok", "--c-bg"), ("--c-warn", "--c-bg"), ("--c-err", "--c-bg"),
            ("--c-on-primary", "--c-primary"), ("--c-text", "--c-gap-bg"), ("--c-faint", "--c-raised-strong"),
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
        cls.choice = constants["THEME_CHOICE_HTML"]
        cls.css = constants["CIEL_CSS"]
        cls.source = APP_PATH.read_text(encoding="utf-8")

    def test_theme_is_chosen_in_settings_not_the_top_bar(self):
        self.assertNotIn("data-ciel-theme-toggle", self.source)
        self.assertNotIn("THEME_TOGGLE_HTML", self.source)
        self.assertIn('data-ciel-theme-set="dark" aria-pressed="true"', self.choice)
        self.assertIn('data-ciel-theme-set="light" aria-pressed="false"', self.choice)
        self.assertIn('st.html(THEME_CHOICE_HTML, width="content")', self.source)
        self.assertIn("st.html(UI_JS, unsafe_allow_javascript=True)", self.source)

    def test_choice_buttons_set_the_theme_and_report_it(self):
        self.assertIn("closest('[data-ciel-theme-set]')", self.js)
        self.assertIn("if (next !== 'light' && next !== 'dark') return;", self.js)
        self.assertIn("button.setAttribute('aria-pressed', pressed)", self.js)

    def test_choice_buttons_follow_the_tokens(self):
        self.assertIn('.ciel-theme-choice[aria-pressed="true"]', self.css)
        # Keyboard focus comes from the app-wide rule for buttons in .stApp.
        self.assertIn('.stApp :is(button, a, textarea, input, summary, [role="button"]):focus-visible', self.css)

    def test_choice_is_kept_on_html_and_survives_blocked_storage(self):
        self.assertIn("const root = document.documentElement;", self.js)
        self.assertIn("root.dataset.cielTheme = next;", self.js)
        self.assertIn("localStorage.setItem(KEY, next)", self.js)
        self.assertIn("if (window.__cielUi) return;", self.js)

    def test_saved_light_choice_survives_and_default_is_dark(self):
        self.assertIn("root.dataset.cielTheme = saved === 'light' ? 'light' : 'dark';", self.js)
        self.assertNotIn("prefers-color-scheme", self.js)
        self.assertIn("localStorage.setItem(KEY, next)", self.js)
        # Theme storage read and write, plus the curtain's sessionStorage.
        self.assertEqual(self.js.count("try {"), 3)

    def test_composer_is_lifted_above_streamlit_cloud_badges(self):
        # On Android the send button sat under Streamlit Cloud's corner
        # badges, which live in the page around the app's iframe.
        self.assertIn("if (window.self !== window.top) root.dataset.cielHosted = '1';", self.js)
        css = app_constants()["CIEL_CSS"]
        rule = css.split("@media (max-width: 960px) {\n    :root[data-ciel-hosted]", 1)
        self.assertEqual(len(rule), 2, "hosted composer rule missing")
        self.assertIn('[data-testid="stBottomBlockContainer"] { padding-bottom: 3.5rem; }', rule[1].split("}\n}", 1)[0])

    def test_rail_stays_in_view_on_wide_screens(self):
        css = app_constants()["CIEL_CSS"]
        # Sticky on Streamlit's wrapper: the keyed block alone is exactly as
        # tall as its wrapper and could not stick (checked in the browser).
        wrapper = css.split('[data-testid="stLayoutWrapper"]:has(> .st-key-rail) {', 1)[1].split("}", 1)[0]
        self.assertIn("position: sticky;", wrapper)
        rail = css.split(".st-key-rail {", 1)[1].split("}", 1)[0]
        self.assertIn("overflow-y: auto;", rail)
        self.assertIn('[data-testid="stColumn"]:has(.st-key-rail) { align-self: stretch; }', css)

    def test_copy_button_announces_and_leaves_error_cards(self):
        self.assertIn("button.setAttribute('aria-live', 'polite')", self.js)
        self.assertIn("stale.remove()", self.js)

    def test_template_click_focuses_the_composer_on_the_first_blank(self):
        # Spec 3: after a template fills the composer it gets focus, with the
        # first [...] selected so typing replaces it.
        self.assertIn(".st-key-templates button", self.js)
        self.assertIn("setSelectionRange(start, end + 1)", self.js)

    def test_page_scripts_are_valid_javascript(self):
        # UI_JS lives in a Python string: a "\n" meant for JavaScript became a
        # real line break inside a JS string and the whole script stopped
        # (found in the final review of the redesign).
        import shutil
        import subprocess
        import tempfile
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        for name in ("UI_JS", "NAV_SCROLL_JS"):
            script = app_constants()[name].split("<script>", 1)[1].split("</script>", 1)[0]
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
                handle.write(script)
            result = subprocess.run([node, "--check", handle.name], capture_output=True, text=True)
            Path(handle.name).unlink()
            with self.subTest(script=name):
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_upload_tooltip_is_short_and_in_indonesian(self):
        self.assertIn("const UPLOAD_HINT = 'Lampirkan file atau foto';", self.js)
        self.assertIn("tip.textContent.startsWith('Upload or drag and drop')", self.js)
        self.assertIn("button.setAttribute('aria-label', UPLOAD_HINT)", self.js)


if __name__ == "__main__":
    unittest.main()

"""guard/scope.py: lingkup tugas dan pemeriksa jalur file."""

import unittest

from guard.risk import Action
from guard.scope import ScopeVerdict, TaskScope, contains_path, in_scope

SKRIPSI = "C:/Users/nadia/Dokumen/Skripsi"


class ContainsPathTest(unittest.TestCase):
    def test_inside(self):
        self.assertTrue(contains_path(SKRIPSI, "C:/Users/nadia/Dokumen/Skripsi/bab1/draf.docx"))
        self.assertTrue(contains_path(SKRIPSI, "c:\\users\\NADIA\\dokumen\\skripsi\\a.txt"))
        self.assertTrue(contains_path("/home/nadia/skripsi", "/home/nadia/skripsi/bab1.md"))

    def test_the_folder_itself_and_a_trailing_slash(self):
        self.assertTrue(contains_path(SKRIPSI, SKRIPSI))
        self.assertTrue(contains_path(SKRIPSI + "/", SKRIPSI + "/bab1"))

    def test_escapes(self):
        for path in (
            "C:/Users/nadia/Dokumen/Skripsi/../../.ssh/id_rsa",
            "C:/Users/nadia/Dokumen/Skripsi2/a.docx",
            "D:/Users/nadia/Dokumen/Skripsi/a.docx",
            "bab1/draf.docx",
            "/home/nadia/skripsi/../.ssh/id_rsa",
            "/Users/nadia/Dokumen/Skripsi/a.docx",
            "", None, 7,
        ):
            with self.subTest(path=path):
                self.assertFalse(contains_path(SKRIPSI, path))

    def test_posix_folder_rejects_windows_and_relative_paths(self):
        self.assertFalse(contains_path("/home/nadia/skripsi", "C:/home/nadia/skripsi/a.md"))
        self.assertFalse(contains_path("/home/nadia/skripsi", "/home/nadia/skripsi2/a.md"))
        self.assertFalse(contains_path("/home/nadia/skripsi", "skripsi/a.md"))

    def test_broken_folder(self):
        self.assertFalse(contains_path(None, SKRIPSI + "/a.txt"))
        self.assertFalse(contains_path("Skripsi", "Skripsi/a.txt"))


SCOPE = TaskScope(
    hosts=frozenset({"shopee.co.id"}), apps=frozenset({"winword"}),
    folders=(SKRIPSI,), writable_folders=(SKRIPSI + "/rapi",),
    kinds=frozenset({"tab_read", "tab_click", "file_list", "file_move", "ui_click"}),
)

WIDE = TaskScope(
    hosts=frozenset({"shopee.co.id"}), apps=frozenset({"winword"}),
    folders=(SKRIPSI, "/home/nadia/skripsi"), writable_folders=(SKRIPSI + "/rapi",),
    kinds=frozenset({"file_read", "file_delete", "file_list", "search", "message_send", "tab_read"}),
)


class InScopeTest(unittest.TestCase):
    def test_inside(self):
        for action in (
            Action(kind="tab_read", host="mall.shopee.co.id"),
            Action(kind="file_list", path=SKRIPSI + "/bab1"),
            Action(kind="file_move", path=SKRIPSI + "/rapi/bab1.docx", dest=SKRIPSI + "/rapi/bab1/bab1.docx"),
            Action(kind="ui_click", app="WINWORD"),
            Action(kind="ask_user"), Action(kind="finish"),
        ):
            with self.subTest(action=action):
                self.assertEqual(in_scope(action, SCOPE), ScopeVerdict(True, None))

    def test_outside(self):
        cases = [
            (Action(kind="tab_type", host="shopee.co.id"), "kind"),
            (Action(kind="tab_read", host="example.org"), "host"),
            (Action(kind="tab_read"), "host"),
            (Action(kind="ui_click", app="excel"), "app"),
            (Action(kind="file_list", path="C:/Users/nadia/Unduhan"), "path"),
            (Action(kind="file_move", path=SKRIPSI + "/bab1/a.docx"), "path"),
            (Action(kind="file_list", path="C:/Users/nadia/.ssh"), "path_denied"),
            (Action(kind="file_list", path=SKRIPSI + "/../../AppData/Roaming"), "path_denied"),
        ]
        for action, reason in cases:
            with self.subTest(action=action):
                self.assertEqual(in_scope(action, SCOPE), ScopeVerdict(False, reason))

    def test_reading_is_allowed_in_writable_folders_but_writing_needs_them(self):
        self.assertTrue(in_scope(Action(kind="file_read", path=SKRIPSI + "/rapi/a.txt"), WIDE).inside)
        self.assertTrue(in_scope(Action(kind="file_delete", path=SKRIPSI + "/rapi/a.txt"), WIDE).inside)
        self.assertEqual(in_scope(Action(kind="file_delete", path=SKRIPSI + "/a.txt"), WIDE), ScopeVerdict(False, "path"))

    def test_kinds_without_a_target_only_need_to_be_in_the_plan(self):
        self.assertTrue(in_scope(Action(kind="search"), WIDE).inside)
        self.assertTrue(in_scope(Action(kind="message_send"), WIDE).inside)
        self.assertEqual(in_scope(Action(kind="search"), SCOPE), ScopeVerdict(False, "kind"))

    def test_denied_folders_on_posix_and_in_relative_paths(self):
        self.assertEqual(in_scope(Action(kind="file_list", path="/home/nadia/.ssh/config"), WIDE), ScopeVerdict(False, "path_denied"))
        self.assertEqual(in_scope(Action(kind="file_read", path="../.aws/credentials"), WIDE), ScopeVerdict(False, "path_denied"))

    def test_wrong_typed_fields_do_not_raise(self):
        self.assertEqual(in_scope(Action(kind="tab_read", host=7), WIDE), ScopeVerdict(False, "host"))
        self.assertEqual(in_scope(Action(kind="file_list", path=7), WIDE), ScopeVerdict(False, "path"))
        self.assertEqual(in_scope(Action(kind=["tab_read"]), WIDE), ScopeVerdict(False, "kind"))
        self.assertEqual(in_scope(Action(kind="ui_click", app=None), SCOPE), ScopeVerdict(False, "app"))

    def test_empty_scope_allows_only_asking_and_finishing(self):
        empty = TaskScope()
        self.assertEqual(empty.spend_cap, 0)
        self.assertTrue(in_scope(Action(kind="ask_user"), empty).inside)
        self.assertEqual(in_scope(Action(kind="tab_read", host="shopee.co.id"), empty), ScopeVerdict(False, "kind"))


HOME = TaskScope(
    hosts=frozenset({"shopee.co.id"}), writable_folders=("C:/Users/nadia",),
    kinds=frozenset({"tab_read", "tab_open", "file_read", "file_write"}),
)


class FinalReviewTest(unittest.TestCase):
    """Uji untuk temuan tinjauan akhir C2 dan I1."""

    def test_host_forms_a_browser_reports_are_inside(self):
        for host in ("shopee.co.id.", "Mall.Shopee.co.id", "shopee.co.id:443"):
            with self.subTest(host=host):
                self.assertTrue(in_scope(Action(kind="tab_read", host=host), HOME).inside)

    def test_hosts_that_only_end_with_an_allowed_domain_are_outside(self):
        for host in ("evil.com/.shopee.co.id", "evil.com\\.shopee.co.id", "evil.com#.shopee.co.id",
                     "user@evil.com/a.shopee.co.id", "https://evil.com/?.shopee.co.id"):
            with self.subTest(host=host):
                self.assertEqual(in_scope(Action(kind="tab_open", host=host), HOME), ScopeVerdict(False, "host"))

    def test_windows_spellings_of_denied_folders(self):
        for path in (
            "C:/Users/nadia/.ssh./id_rsa", "C:/Users/nadia/.ssh /id_rsa", "C:/Users/nadia/SSH~1/id_rsa",
            "C:/Users/nadia/.ssh::$INDEX_ALLOCATION/id_rsa", "C:/Users/nadia/AppData./Local/x",
            "C:/Users/nadia/APPDAT~1/Local/x", "C:/Users/nadia/a.txt::$DATA", "C:/Users/nadia/Dokumen/.. /x",
        ):
            for kind in ("file_read", "file_write"):
                with self.subTest(path=path, kind=kind):
                    self.assertEqual(in_scope(Action(kind=kind, path=path), HOME), ScopeVerdict(False, "path_denied"))

    def test_ordinary_paths_still_pass(self):
        for path in ("C:/Users/nadia/Dokumen/a.txt", "C:/Users/nadia/Dokumen/Bab 1/draf v1.0.docx", "C:/Users/nadia/~$draf.docx"):
            with self.subTest(path=path):
                self.assertTrue(in_scope(Action(kind="file_write", path=path), HOME).inside)


MOVES = TaskScope(
    hosts=frozenset({"shopee.co.id"}), folders=(SKRIPSI,), writable_folders=(SKRIPSI + "/rapi",),
    kinds=frozenset({"file_move", "download", "file_read", "tab_click"}),
)
STARTUP = "C:/Users/nadia/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/mulai.bat"
ANYWHERE = TaskScope(
    writable_folders=("C:/", "/"), kinds=frozenset({"file_read", "file_write"}),
)


class DeferredMinorsTest(unittest.TestCase):
    """Temuan minor tinjauan akhir: tujuan pindah file, daftar folder terlarang, efek, tipe lingkup."""

    def test_move_needs_a_destination_inside_writable_folders(self):
        source = SKRIPSI + "/rapi/a.docx"
        good = Action(kind="file_move", path=source, dest=SKRIPSI + "/rapi/bab1/a.docx")
        self.assertEqual(in_scope(good, MOVES), ScopeVerdict(True, None))

        for dest in (None, 7, SKRIPSI + "/a.docx", "C:/Users/nadia/Unduhan/a.docx", "a.docx"):
            with self.subTest(dest=dest):
                self.assertEqual(in_scope(Action(kind="file_move", path=source, dest=dest), MOVES), ScopeVerdict(False, "path"))

        for dest in (STARTUP, SKRIPSI + "/rapi/.ssh./a.docx"):
            with self.subTest(dest=dest):
                moved = Action(kind="file_move", path=source, dest=dest)
                self.assertEqual(in_scope(moved, MOVES), ScopeVerdict(False, "path_denied"))

    def test_download_destination_is_checked_when_given(self):
        self.assertTrue(in_scope(Action(kind="download"), MOVES).inside)
        self.assertTrue(in_scope(Action(kind="download", dest=SKRIPSI + "/rapi/berkas.pdf"), MOVES).inside)
        outside = Action(kind="download", dest="C:/Users/nadia/Unduhan/berkas.pdf")
        self.assertEqual(in_scope(outside, MOVES), ScopeVerdict(False, "path"))
        self.assertEqual(in_scope(Action(kind="download", dest=STARTUP), MOVES), ScopeVerdict(False, "path_denied"))

    def test_ordinary_folder_names_are_not_denied(self):
        for path in ("C:/Users/nadia/Dokumen/Skripsi/Library/zotero.pdf", "C:/Users/nadia/Dokumen/Skripsi/windows/layar.png",
                     "/home/nadia/skripsi/etc/catatan.md", "/home/nadia/skripsi/library/buku.pdf",
                     "/Users/nadia/Documents/Library/buku.pdf"):
            with self.subTest(path=path):
                self.assertTrue(in_scope(Action(kind="file_write", path=path), ANYWHERE).inside)

    def test_more_credential_and_system_folders_are_denied(self):
        for path in ("/home/nadia/.kube/config", "/home/nadia/.docker/config.json", "/home/nadia/.config/gh/hosts.yml",
                     "/home/nadia/.netrc", "/home/nadia/.mozilla/firefox/profil", "/home/nadia/.git-credentials",
                     "C:/ProgramData/aplikasi/x", "C:/Users/nadia/NTUSER.DAT", "/etc/passwd",
                     "/Users/nadia/Library/Keychains/login.keychain-db", "/Library/Preferences/x",
                     "/Users/nadia/Library/Application Support/Google/Chrome/Default/Login Data",
                     "C:/Windows/win.ini", "C:/Program Files/aplikasi/x", "C:/Users/nadia/AppData/Local/x"):
            with self.subTest(path=path):
                self.assertEqual(in_scope(Action(kind="file_read", path=path), ANYWHERE), ScopeVerdict(False, "path_denied"))

    def test_effect_must_be_in_the_plan(self):
        click = Action(kind="tab_click", host="shopee.co.id", effect="cart_add")
        self.assertEqual(in_scope(click, MOVES), ScopeVerdict(False, "kind"))
        planned = TaskScope(hosts=frozenset({"shopee.co.id"}), kinds=frozenset({"tab_click", "cart_add"}))
        self.assertTrue(in_scope(click, planned).inside)
        self.assertEqual(in_scope(Action(kind="tab_click", host="shopee.co.id", effect=7), planned), ScopeVerdict(False, "kind"))

    def test_scope_rejects_wrong_types(self):
        for kwargs in ({"kinds": "tab_read"}, {"hosts": ["shopee.co.id"]}, {"apps": frozenset({7})}, {"folders": "C:/x"},
                       {"writable_folders": ["C:/x"]}, {"folders": (7,)}, {"spend_cap": "500000"}, {"spend_cap": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(TypeError):
                TaskScope(**kwargs)


if __name__ == "__main__":
    unittest.main()

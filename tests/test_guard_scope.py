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
            Action(kind="file_move", path=SKRIPSI + "/rapi/bab1.docx"),
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


if __name__ == "__main__":
    unittest.main()

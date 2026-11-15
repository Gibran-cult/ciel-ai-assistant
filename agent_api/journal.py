"""Penulis log aksi berantai untuk satu tugas (docs/security.md bagian 3).

Setiap keputusan loop ditulis sebagai satu baris agent_actions. Baris
memuat hash baris sebelumnya, dihitung dengan kunci rahasia server, dan hash
baris terakhir disimpan di tugasnya. Jadi baris yang diubah, dihapus di
tengah, atau dipotong dari ujung akan ketahuan saat rantainya diperiksa.

Yang dicatat hanya jenis aksi dan targetnya. Teks yang diketik dan isi
halaman tidak pernah masuk log.
"""

from dataclasses import asdict

from guard.audit import MIN_KEY, AuditEvent, chain_hash, target_of

MAX_KIND = 40


class Journal:

    def __init__(self, store, key, owner, device, task):
        if not isinstance(key, bytes) or len(key) < MIN_KEY:
            raise ValueError("kunci rantai log harus bytes, minimal 16 byte")

        self.store = store
        self.key = key
        self.owner = owner
        self.device = device
        self.task = task
        self.seq = 0
        self.head = ""

    def record(self, action, decision, now, approved_by=None, result=None):
        """Tulis satu baris. True hanya kalau baris dan hash kepala tersimpan."""

        kind = action.kind[:MAX_KIND] if isinstance(action.kind, str) and action.kind else "unknown"
        event = AuditEvent(
            owner=self.owner, device=self.device, task=self.task, seq=self.seq + 1, kind=kind,
            target=target_of(action), level=decision.level, decision=decision.outcome, reason=decision.reason,
            approved_by=approved_by, result=result, at=now.isoformat(),
        )
        row_hash = chain_hash(self.head, event, self.key)

        if not self.store.append_action({**asdict(event), "prev_hash": self.head, "hash": row_hash}):
            return False

        if not self.store.update_task(self.owner, self.task, head_hash=row_hash):
            return False

        self.seq += 1
        self.head = row_hash
        return True

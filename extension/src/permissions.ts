// Izin situs. Ekstensi tidak punya izin tetap untuk situs mana pun; izin
// diminta per situs saat pengguna mengklik tombol di panel. Chrome hanya
// mengizinkan permissions.request dari gerakan pengguna, jadi fungsi ini
// dipanggil langsung dari handler klik di panel.

function origin(host: string): string {
  return `https://${host}/*`;
}

export async function hasPermission(host: string): Promise<boolean> {
  try {
    return await chrome.permissions.contains({ origins: [origin(host)] });
  } catch {
    return false;
  }
}

// Langsung meminta, tanpa menunggu apa pun lebih dulu: Chrome menolak
// permintaan yang tidak lagi dianggap bagian dari klik pengguna. Kalau izinnya
// sudah ada, Chrome menjawab true tanpa bertanya lagi.
export async function ensurePermission(host: string): Promise<boolean> {
  try {
    return await chrome.permissions.request({ origins: [origin(host)] });
  } catch {
    return false;
  }
}

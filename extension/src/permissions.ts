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

export async function ensurePermission(host: string): Promise<boolean> {
  if (await hasPermission(host)) return true;

  try {
    return await chrome.permissions.request({ origins: [origin(host)] });
  } catch {
    return false;
  }
}

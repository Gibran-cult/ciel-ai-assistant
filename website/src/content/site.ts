// Every word and fact on the page lives here, so the truth tests and the copy checks read one file.
// Facts come from the live landing, pricing.PLANS and the app test on 20 Oktober 2026. Nothing here is invented.

export const APP = "https://app.ciel-ai.web.id/";

export const links = {
  login: `${APP}?page=login`,
  app: APP,
  pricing: `${APP}?page=pricing`,
  privacy: `${APP}?page=privacy`,
  terms: `${APP}?page=terms`,
  instagram: "https://www.instagram.com/ciel_ai.1/",
  tiktok: "https://www.tiktok.com/@ciel_ai.1",
};

export const contactEmail = "gibranahmadn6@gmail.com";
export const testDate = "20 Oktober 2026";

export const nav = [
  { href: "#cara-kerja", label: "Cara kerja" },
  { href: "#uji-jurnal-palsu", label: "Uji jurnal palsu" },
  { href: "#harga", label: "Harga" },
  { href: "#tanya-jawab", label: "Tanya jawab" },
] as const;

export const hero = {
  titleLines: ["Riset yang", "nggak ngarang."],
  lede: "Ciel nyari sumber dulu sebelum jawab, lalu nulis daftar sumbernya supaya bisa kamu cek. Kalau nggak nemu, Ciel bilang jujur.",
  cta: "Masuk dengan Google",
  alt: "Coba tanpa masuk",
  note: "Gratis untuk mulai.",
  mapPrompt: "Coba lihat: pilih satu referensi.",
  mapCaption: `Rute asli dari uji di aplikasi Ciel, ${testDate}. Jejak yang dicoret berasal dari uji jurnal palsu. Jawaban Ciel diringkas.`,
};

export type Source = { n: number; domain: string; title: string; url: string };
export type Case = {
  id: "vaswani" | "palsu" | "koto";
  chip: string;
  question: string;
  found: boolean;
  sources: Source[];
  answer: string;
  note?: string;
};

// The three real cases from the 20 Oktober test. Koto's answer also gave a name for IndoLEM's
// sentiment data that is likely wrong (see PRODUCT.md), so that line is left out on purpose.
export const cases: Case[] = [
  {
    id: "vaswani",
    chip: "Vaswani dkk. (2017)",
    question: "Ringkas paper ini dong, buat bahan presentasi: Vaswani dkk. (2017).",
    found: true,
    sources: [
      { n: 1, domain: "arxiv.org", title: "Attention Is All You Need", url: "https://arxiv.org/abs/1706.03762" },
      { n: 2, domain: "arxiv.org", title: "Teks lengkap, versi 3", url: "https://arxiv.org/html/1706.03762v3" },
      { n: 3, domain: "arxiv.org", title: "Bagian 3.2, 3.5, dan Tabel 3", url: "https://arxiv.org/html/1706.03762v4" },
      {
        n: 4,
        domain: "proceedings.neurips.cc",
        title: "Attention is All you Need",
        url: "https://proceedings.neurips.cc/paper/2017/hash/3f5ee243547dee91fbd053c1c4a845aa-Abstract.html",
      },
    ],
    answer:
      "Paper ini memperkenalkan Transformer: model yang membuang rekurensi dan konvolusi, lalu mengandalkan attention saja, jadi jauh lebih mudah diparalelkan. Ciel menyusunnya jadi 12 slide, dari masalah yang dipecahkan sampai hasilnya di terjemahan mesin.",
  },
  {
    id: "palsu",
    chip: "Hendrawan & Sulistyo (2019)",
    question: "Tolong ringkas jurnal Hendrawan & Sulistyo (2019), Jurnal Psikologi Pendidikan Nusantara Vol. 7 No. 2.",
    found: false,
    sources: [],
    answer: "Aku nggak bisa meringkas jurnal itu, karena sejauh pencarianku, jurnal tersebut tidak ada.",
    note: "Ciel nyebut apa aja yang sudah dicari: judul persisnya, lalu nama jurnal beserta volume dan nomornya. Nggak ada yang cocok, jadi Ciel nggak bikin ringkasan.",
  },
  {
    id: "koto",
    chip: "Koto dkk. (2020)",
    question: "Paper ini relevan nggak buat skripsi analisis sentimen? Koto dkk. (2020).",
    found: true,
    sources: [
      { n: 1, domain: "aclanthology.org", title: "IndoLEM and IndoBERT", url: "https://aclanthology.org/2020.coling-main.66/" },
      { n: 2, domain: "arxiv.org", title: "IndoLEM and IndoBERT", url: "https://arxiv.org/abs/2011.00677" },
      { n: 3, domain: "aclanthology.org", title: "Versi PDF", url: "https://aclanthology.org/2020.coling-main.66.pdf" },
      { n: 4, domain: "doi.org", title: "IndoLEM and IndoBERT", url: "https://doi.org/10.18653/v1/2020.coling-main.66" },
    ],
    answer:
      "Relevan, sebagai fondasi: paper ini memperkenalkan IndoBERT dan benchmark IndoLEM, yang salah satu tugasnya analisis sentimen. Ciel juga ngingetin supaya paper ini nggak dijadiin rujukan utama untuk metode klasifikasinya.",
  },
];

export const story = {
  heading: "Dari pertanyaan ke sumber",
  steps: [
    {
      id: "tanya",
      text: "Pertama, kamu nanya kayak ngobrol biasa. Boleh sambil lampirkan PDF, file teks, CSV, atau foto materi kuliah.",
      sample: "Bandingin regresi logistik sama random forest buat data beasiswa angkatan 2023",
    },
    {
      id: "cari",
      text: "Lalu, Ciel nyari dan baca sumber dulu sebelum nulis. Di uji kami, chat biasa selesai kurang dari semenit. Riset Skripsi bisa beberapa menit.",
      sample: "Ciel sedang mencari dan memeriksa",
    },
    {
      id: "jawab",
      text: "Setelah itu, jawaban muncul dengan daftar sumber bernomor di akhir. Buka satu-satu sebelum dipakai di tugas.",
      sample:
        "Random forest biasanya lebih kuat buat pola yang nggak linear [1], tapi regresi logistik lebih gampang dijelasin ke penguji [2].",
    },
    {
      id: "jujur",
      text: "Kalau nggak nemu, Ciel nggak nebak angka atau ngarang judul jurnal. Ciel bilang terus terang dan nyaranin tempat lain buat nyari, kayak Google Scholar, Garuda, atau perpustakaan kampus.",
      sample: "Aku nggak bisa meringkas jurnal itu, karena sejauh pencarianku, jurnal tersebut tidak ada.",
    },
  ],
  sampleSources: [
    { n: 1, domain: "scikit-learn.org", title: "Ensembles", url: "https://scikit-learn.org/stable/modules/ensemble.html" },
    { n: 2, domain: "openstax.org", title: "Introductory Statistics", url: "https://openstax.org/details/books/introductory-statistics" },
  ] as Source[],
  footnote: `Dari uji di aplikasi Ciel, ${testDate}, chat biasa. Jawaban di langkah ketiga adalah contoh tampilan.`,
  elsewhere: ["Google Scholar", "Garuda", "Perpustakaan kampus"],
};

export const fakeJournal = {
  heading: "Kami tes pakai jurnal palsu.",
  lede: "Kami minta Ciel ngeringkas jurnal yang nggak pernah ada, lengkap dengan nama penulis, tahun, dan nomor volume.",
  request:
    "Tolong ringkas jurnal \"Pengaruh Konsumsi Kopi Robusta terhadap IPK Mahasiswa Teknik di Yogyakarta\" karya Hendrawan & Sulistyo (2019), Jurnal Psikologi Pendidikan Nusantara Vol. 7 No. 2.",
  reply: "Aku nggak bisa meringkas jurnal itu, karena sejauh pencarianku, jurnal tersebut tidak ada.",
  followUp: "Mau aku lanjut cari penelitian asli yang paling dekat dengan topik ini?",
  explain:
    "Ciel ngecek judulnya dan bilang jurnal itu nggak ada. Habis itu Ciel nawarin nyari penelitian asli yang topiknya mirip, biar kamu tetap bisa lanjut.",
  caption: `Dari uji di aplikasi Ciel, ${testDate}, chat biasa. Jawaban Ciel diringkas.`,
  facts: [
    { k: "Chat biasa", v: "Di bawah semenit di uji kami" },
    { k: "Bahasa", v: "Indonesia" },
    { k: "Masuk pakai", v: "Akun Google, opsional" },
    { k: "Mulai dari", v: "Gratis" },
  ],
};

export const legend = {
  heading: "Satu layar, enam hal",
  lede: "Tanya apa aja soal tugas atau skripsimu.",
  // In reading order of the sample screen: the key numbers point at its parts.
  items: [
    { id: "proyek", term: "Proyek", text: "Tiap skripsi atau tugas punya ruangnya sendiri, lengkap dengan file konteksnya." },
    { id: "template", term: "Template", text: "Pertanyaan bisa mulai dari template, kayak Analisis metode di contoh ini. Tinggal ganti bagian dalam kurung." },
    { id: "dugaan", term: "Label dugaan", text: "Di mode analisis, poin yang belum ada dasarnya ditandai kuning sebagai dugaan." },
    { id: "sumber", term: "Sumber bernomor", text: "Jawaban yang pakai pencarian ditutup daftar sumber bernomor yang bisa diklik." },
    { id: "panel", term: "Panel sumber", text: "Semua sumber di satu chat dikumpulkan di panel kanan, jadi gampang dicek." },
    { id: "ingatan", term: "Ingatan", text: "Setelah masuk, Ciel ingat hal penting lintas chat. Kamu bisa hapus kapan aja." },
  ],
  sample: {
    label: "Contoh",
    project: "Skripsi sentimen ojol",
    // The "Analisis metode" template from beranda.py, filled in: "Analisis: [metode] cocok nggak buat data [jenis data]-ku?"
    question: "Analisis: IndoBERT cocok nggak buat data ulasan ojol-ku?",
    answer: "Cocok buat mulai, karena IndoBERT dilatih pakai teks bahasa Indonesia [1]. Buat ngetes, pakai data sentimen dari IndoNLU [2].",
    guess: "Ulasan ojol yang campur bahasa Jawa belum ada sumbernya.",
    sources: [
      { n: 1, domain: "arxiv.org", title: "IndoLEM and IndoBERT", url: "https://arxiv.org/abs/2011.00677" },
      { n: 2, domain: "arxiv.org", title: "IndoNLU", url: "https://arxiv.org/abs/2009.05387" },
    ] as Source[],
    // Section titles of the app's right-hand panel, as render_rail() in app.py writes them.
    railSources: "Sumber di chat ini",
    railGaps: "Belum ketemu",
    railMemory: "Yang Ciel ingat",
    // The composer's placeholder inside a project chat (composer() in app.py).
    composer: "Tanya soal skripsimu",
    memory: "Format sitasi APA 7",
  },
};

// Mirrors pricing.PLANS word for word; tests/test_website.py fails the build if they drift apart.
export const pricing = {
  heading: "Mulai gratis, upgrade kalau butuh",
  lede: "Fitur inti gratis dengan batas pesan per jam. Pro buat kamu yang lagi nyusun skripsi.",
  detailLink: "Lihat detail paket",
  plans: [
    {
      id: "free",
      name: "Gratis",
      price: "Rp0",
      tag: "Tersedia sekarang",
      features: [
        "Chat, riset web dengan sumber, dan matematika",
        "Analisis angka dari file CSV/TSV",
        "Lampiran foto, PDF, dan file teks",
        "Proyek dengan file konteks bersama",
        "Edit gambar",
        "Long-term memory pribadi (perlu login)",
        "Riwayat chat tersimpan di akun setelah masuk",
      ],
      limit: "Dengan batas pesan per jam",
      cta: "Mulai gratis",
      href: APP,
    },
    {
      id: "pro",
      name: "Pro",
      price: "Rp79.000",
      period: "per 30 hari",
      features: [
        "Semua di paket Gratis",
        "Riset Skripsi: peta sumber per tema, celah riset, dan daftar pustaka APA 7",
        "Kerangka Bab 1–3 dari peta sumber, dengan pertanyaan pemandu",
        "Cek kutipan & kemiripan draf terhadap peta sumber",
        "Unduh hasil Riset Skripsi sebagai DOCX",
        "Edit gambar dengan AI & ilustrasi (3 per hari)",
        "Batas pesan per jam lebih tinggi",
      ],
      note: "Sekali bayar, tanpa tagihan otomatis.",
      cta: "Lihat paket Pro",
      href: `${APP}?page=pricing`,
    },
  ],
};

export const faq = {
  heading: "Yang sering ditanya",
  items: [
    {
      q: "Ciel buat nyontek?",
      a: "Nggak. Ciel bantu kamu ngerti materi dan nemu sumber. Tulisannya tetap kamu yang bikin, dan sumbernya bisa kamu buka sendiri.",
    },
    {
      q: "Bedanya sama chatbot biasa?",
      a: "Ciel nyari sumber dulu, baru jawab, lalu nulis daftar sumbernya. Kalau nggak nemu, Ciel bilang terus terang dan nggak nebak-nebak.",
    },
    {
      q: "Kenapa jawabannya kadang agak lama?",
      a: "Karena Ciel nyari dan baca sumber dulu. Di uji kami chat biasa selesai di bawah semenit. Riset Skripsi bisa beberapa menit karena sumber yang dibaca lebih banyak.",
    },
    {
      q: "Ciel ingat apa aja?",
      a: "Setelah kamu masuk, hal penting dari obrolanmu, kayak topik skripsi atau format sitasi dari dosen. Ingatannya milik akunmu, bisa kamu lihat dan hapus di menu akun.",
    },
    {
      q: "Harus masuk pakai Google?",
      a: "Nggak wajib. Tanpa masuk kamu tetap bisa chat dengan batas pesan per jam. Setelah masuk, riwayat chat dan proyek tersimpan di akunmu dan Ciel bisa ingat konteks penting.",
    },
    {
      q: "Ciel bikin nilaiku naik?",
      a: "Kami belum punya data soal itu, jadi kami nggak janji. Ciel tetap nyari sumber dulu dan bilang terus terang kalau nggak nemu.",
    },
  ],
};

export const closing = {
  heading: "Riset yang bisa dicek.",
  lede: "Mulai gratis. Masuk pakai Google, dan pertanyaan pertamamu langsung dicariin sumbernya.",
  cta: "Masuk dengan Google",
  alt: "Atau coba dulu tanpa masuk",
};

export type FooterLink = { label: string; handle?: string; href: string; external?: boolean; strong?: boolean };

// The footer is the bottom margin of the chart: its key (links set like the map's Keterangan) and
// a note on where the first map's routes come from, built from the real test cases.
export const footer = {
  tagline: "Teman riset dan belajar buat mahasiswa Indonesia.",
  key: [
    {
      term: "Mulai",
      links: [
        { label: "Buka aplikasi Ciel", href: links.app, strong: true },
        { label: "Masuk", href: links.login },
      ],
    },
    {
      term: "Ikuti",
      links: [
        { label: "Instagram", handle: "@ciel_ai.1", href: links.instagram, external: true },
        { label: "TikTok", handle: "@ciel_ai.1", href: links.tiktok, external: true },
      ],
    },
    { term: "Hubungi", links: [{ label: contactEmail, href: `mailto:${contactEmail}` }] },
    {
      term: "Lihat",
      links: [
        { label: "Paket", href: links.pricing },
        { label: "Privasi", href: links.privacy },
        { label: "Ketentuan", href: links.terms },
      ],
    },
  ] as Array<{ term: string; links: FooterLink[] }>,
  sourcesTitle: "Sumber data peta",
  sourcesNote: `Rute di peta paling atas berasal dari uji di aplikasi Ciel, ${testDate}. Jurnal yang dicoret sengaja kami karang untuk menguji Ciel.`,
  found: (n: number) => `${n} sumber`,
  notFound: "tidak ada",
  copyright: "© 2026 Ciel AI",
  domain: "ciel-ai.web.id",
  backToTop: "Kembali ke atas",
};

export const meta = {
  title: "Ciel AI: riset yang nggak ngarang",
  description:
    `Ciel nyari sumber dulu sebelum jawab, dan bilang terus terang kalau nggak nemu. ${footer.tagline}`,
  url: "https://ciel-ai.web.id/",
};

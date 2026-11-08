import type { Metadata, Viewport } from "next";
import { Alegreya, Alegreya_Sans, Fraunces } from "next/font/google";
import { meta } from "@/content/site";
import "./globals.css";

// next/font downloads these at build time and serves them from this site, so no request
// goes to a font host when the page opens.
const alegreya = Alegreya({
  subsets: ["latin"],
  style: ["normal", "italic"],
  variable: "--font-alegreya",
  display: "swap",
});

const alegreyaSans = Alegreya_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-alegreya-sans",
  display: "swap",
});

// Only the wordmark uses Fraunces (brand commitment from the 2026-10-20 redesign spec).
const fraunces = Fraunces({
  subsets: ["latin"],
  weight: "500",
  variable: "--font-fraunces",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(meta.url),
  title: meta.title,
  description: meta.description,
  alternates: { canonical: "/" },
  referrer: "strict-origin-when-cross-origin",
  icons: {
    icon: [{ url: "/ciel-icon.svg", type: "image/svg+xml" }, { url: "/ciel-icon-192.png", sizes: "192x192" }],
    apple: "/ciel-icon-192.png",
  },
  openGraph: {
    type: "website",
    url: meta.url,
    siteName: "Ciel AI",
    locale: "id_ID",
    title: meta.title,
    description: meta.description,
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "Ciel AI: riset yang nggak ngarang" }],
  },
  twitter: { card: "summary_large_image", title: meta.title, description: meta.description, images: ["/og.png"] },
};

export const viewport: Viewport = {
  themeColor: "#141311",
  colorScheme: "dark",
};

const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    { "@type": "WebSite", name: "Ciel AI", alternateName: ["Ciel"], url: meta.url, inLanguage: "id" },
    {
      "@type": "Organization",
      name: "Ciel AI",
      url: meta.url,
      logo: `${meta.url}ciel-icon-512.png`,
      sameAs: ["https://www.instagram.com/ciel_ai.1/", "https://www.tiktok.com/@ciel_ai.1"],
    },
    {
      "@type": "WebApplication",
      name: "Ciel AI",
      url: meta.url,
      description: meta.description,
      applicationCategory: "EducationalApplication",
      operatingSystem: "Web",
      inLanguage: "id",
      offers: [
        { "@type": "Offer", name: "Gratis", price: "0", priceCurrency: "IDR" },
        {
          "@type": "Offer",
          name: "Pro",
          price: "79000",
          priceCurrency: "IDR",
          eligibleDuration: { "@type": "QuantitativeValue", value: 30, unitCode: "DAY" },
        },
      ],
    },
  ],
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="id" className={`${alegreya.variable} ${alegreyaSans.variable} ${fraunces.variable}`}>
      <body>
        {children}
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      </body>
    </html>
  );
}

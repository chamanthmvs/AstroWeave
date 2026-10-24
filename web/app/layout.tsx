import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import Sky from "@/components/Sky";

export const metadata: Metadata = {
  title: "AstroWeave — Vedic astrology, read clearly",
  description:
    "Specialist Vedic & KP astrology, coordinated into one clear answer. Factual, honest, easy to understand.",
};

// Apply the saved theme before first paint so there is no light/dark flash.
const themeScript = `(function(){try{var t=localStorage.getItem('astroweave:theme');if(t==='light'||t==='dark'){document.documentElement.setAttribute('data-theme',t);}}catch(e){}})();`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Sora:wght@300;400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <Sky />
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}

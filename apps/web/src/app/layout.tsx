import type { Metadata, Viewport } from "next";
import "@fontsource-variable/vazirmatn";
import "./globals.css";

import { AuthProvider } from "@/components/auth/AuthProvider";
import { ServiceWorkerRegister } from "@/components/pwa/ServiceWorkerRegister";
import { ToastProvider } from "@/components/ui/Toast";

export const metadata: Metadata = {
  title: {
    default: "NetNova Notify",
    template: "%s | NetNova Notify",
  },
  description: "سامانه مدیریت اطلاع رسانی پروژه های نت نووا از طریق تلگرام",
  applicationName: "NetNova Notify",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "NetNova Notify",
  },
  icons: {
    icon: [{ url: "/favicon.png", type: "image/png" }],
    apple: [{ url: "/icons/apple-touch-icon.png", sizes: "180x180" }],
  },
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#070c18",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fa" dir="rtl">
      <body>
        <ToastProvider>
          <AuthProvider>{children}</AuthProvider>
        </ToastProvider>
        <ServiceWorkerRegister />
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import { Geist } from "next/font/google";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import "./globals.css";

const geist = Geist({
  subsets: ["latin"],
  variable: "--font-geist-sans",
});

export const metadata: Metadata = {
  title: {
    default: "HospitalCompare — Quality & Price Transparency",
    template: "%s | HospitalCompare",
  },
  description:
    "Free tool for U.S. patients to compare hospital CMS quality ratings and shoppable procedure prices by ZIP code.",
  metadataBase: new URL("https://opensourcemed.info/hospital-ranking"),
  openGraph: {
    title: "HospitalCompare",
    description: "Compare hospital quality and procedure prices near you.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geist.variable} flex min-h-screen flex-col antialiased`}>
        <SiteHeader />
        <main className="flex-1">{children}</main>
        <SiteFooter />
      </body>
    </html>
  );
}
import "./globals.css";
import { LocaleProvider } from "../lib/i18n";

export const metadata = {
  title: "CityScope · AI routes for city explorers",
  description: "Plan memorable city runs and rides through interesting places with Gemini, Google Maps, and Google Routes.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><LocaleProvider><a className="skip-link" href="#main-content">Skip to main content</a>{children}</LocaleProvider></body></html>;
}

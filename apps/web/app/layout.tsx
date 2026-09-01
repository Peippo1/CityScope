import "./globals.css";

export const metadata = {
  title: "CityScope · AI routes for city explorers",
  description: "Plan memorable city runs and rides through interesting places with Gemini, Google Maps, and Google Routes.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><a className="skip-link" href="#main-content">Skip to main content</a>{children}</body></html>;
}

import "./globals.css";

export const metadata = {
  title: "CityScope · Cross-city mobility intelligence",
  description: "Compare historical bike-share activity across cities, nearby places, and bicycle routes with grounded evidence.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><a className="skip-link" href="#main-content">Skip to main content</a>{children}</body></html>;
}

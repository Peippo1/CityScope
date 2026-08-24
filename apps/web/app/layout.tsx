import "./globals.css";

export const metadata = {
  title: "CityScope · London mobility explorer",
  description: "Explore historical London cycling activity, nearby places, and bicycle routes with grounded evidence.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><a className="skip-link" href="#main-content">Skip to main content</a>{children}</body></html>;
}

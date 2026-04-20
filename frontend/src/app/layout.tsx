import type { Metadata } from "next";
import "~/styles/globals.css";
import { CartProvider } from "~/contexts/CartContext";

export const metadata: Metadata = {
  title: "Ecommerce Demo",
  description: "A simple ecommerce demo with Next.js and FastAPI",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-gray-50 text-gray-900 antialiased">
        <CartProvider>{children}</CartProvider>
      </body>
    </html>
  );
}

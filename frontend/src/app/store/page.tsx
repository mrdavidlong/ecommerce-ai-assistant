"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import ProductCard, { type Product } from "~/components/ProductCard";
import CartSidebar from "~/components/CartSidebar";
import { getCurrentUser, clearCurrentUser } from "~/lib/auth";
import { formatCurrency } from "~/lib/formatters";

interface UserDetail {
  id: string;
  name: string;
  email: string;
  balance: number;
}

export default function StorePage() {
  const router = useRouter();
  const [userId, setUserId] = useState<string | null>(null);
  const [user, setUser] = useState<UserDetail | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchUser = useCallback(async (id: string) => {
    const res = await fetch(`http://localhost:8000/users/${id}`);
    if (!res.ok) throw new Error("Failed to load user");
    const data = (await res.json()) as UserDetail;
    setUser(data);
  }, []);

  const fetchProducts = useCallback(async () => {
    const res = await fetch("http://localhost:8000/products/");
    if (!res.ok) throw new Error("Failed to load products");
    const data = (await res.json()) as Product[];
    setProducts(data);
  }, []);

  useEffect(() => {
    const session = getCurrentUser();
    if (!session) {
      router.replace("/");
      return;
    }
    setUserId(session.id);
    const load = async () => {
      try {
        await Promise.all([fetchUser(session.id), fetchProducts()]);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load page");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [fetchUser, fetchProducts, router]);

  useEffect(() => {
    if (!userId) return;
    const handler = () => { void fetchUser(userId); };
    window.addEventListener("ai-response", handler);
    return () => window.removeEventListener("ai-response", handler);
  }, [userId, fetchUser]);

  function handleLogout() {
    clearCurrentUser();
    router.replace("/");
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">Loading...</div>
    );
  }

  if (error || !user || !userId) {
    return (
      <div className="min-h-screen p-6">
        <div className="bg-red-100 border border-red-400 text-red-700 p-4 rounded-md max-w-2xl mx-auto">
          {error ?? "Could not load store"}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{user.name}</h1>
            <p className="text-gray-600">{user.email}</p>
          </div>
          <div className="flex items-center gap-4">
            <p className="text-2xl font-bold text-green-700">
              {formatCurrency(user.balance)}
            </p>
            <button
              type="button"
              onClick={handleLogout}
              className="text-sm text-gray-500 hover:text-gray-900 underline"
            >
              Log out
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
            {products.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
          <div>
            <CartSidebar
              userId={userId}
              userBalance={user.balance}
              onOrderSuccess={() => { void fetchUser(userId); void fetchProducts(); }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

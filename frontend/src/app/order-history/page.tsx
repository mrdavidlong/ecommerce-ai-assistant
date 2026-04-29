"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import OrderHistory, { type Order } from "~/components/OrderHistory";
import { getCurrentUser } from "~/lib/auth";

export default function HistoryPage() {
  const router = useRouter();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [session, setSession] = useState<{ id: string } | null>(null);

  const fetchOrders = async (userId: string) => {
    try {
      const res = await fetch(
        `http://localhost:8000/orders/?user_id=${userId}`,
      );
      if (!res.ok) throw new Error("Failed to load orders");
      const data = (await res.json()) as Order[];
      setOrders(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load orders");
    }
  };

  useEffect(() => {
    const currentSession = getCurrentUser();
    if (!currentSession) {
      router.replace("/");
      return;
    }
    setSession(currentSession);
    const load = async () => {
      try {
        await fetchOrders(currentSession.id);
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [router]);

  useEffect(() => {
    if (!session) return;
    const handler = () => { void fetchOrders(session.id); };
    window.addEventListener("ai-response", handler);
    return () => window.removeEventListener("ai-response", handler);
  }, [session]);

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-3xl mx-auto">
        <Link href="/store" className="text-blue-600 hover:underline text-sm">
          &larr; Back to store
        </Link>
        <h1 className="text-3xl font-bold text-gray-900 mt-2 mb-6">
          Order History
        </h1>

        {loading && <p className="text-gray-500">Loading orders...</p>}
        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 p-4 rounded-md">
            {error}
          </div>
        )}
        {!loading && !error && <OrderHistory orders={orders} />}
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import Link from "next/link";
import { useCart } from "~/contexts/CartContext";
import { formatCurrency } from "~/lib/formatters";

interface CartSidebarProps {
  userId: string;
  userBalance: number;
  onOrderSuccess: () => void;
}


export default function CartSidebar({
  userId,
  userBalance,
  onOrderSuccess,
}: CartSidebarProps) {
  const { items, total, updateQuantity, removeItem, clearCart } = useCart();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const insufficient = total > userBalance;
  const isValid = items.length > 0 && !insufficient && !submitting;

  const handleBuy = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("http://localhost:8000/orders/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          items: items.map((i) => ({ product_id: i.productId, quantity: i.quantity })),
        }),
      });
      if (!res.ok) {
        const body = (await res.json()) as { detail?: string };
        throw new Error(body.detail ?? "Order failed");
      }
      clearCart();
      onOrderSuccess();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Order failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <aside className="bg-white rounded-lg shadow-md border border-gray-200 p-6 sticky top-6">
      <h2 className="text-xl font-semibold text-gray-900 mb-4">Cart</h2>

      {items.length === 0 ? (
        <p className="text-gray-500 text-sm">Your cart is empty.</p>
      ) : (
        <div className="space-y-3 mb-4">
          {items.map((item) => (
            <div
              key={item.productId}
              className="flex flex-col gap-1 pb-3 border-b border-gray-100 last:border-b-0"
            >
              <div className="flex justify-between items-start">
                <span className="font-medium text-gray-900 text-sm">{item.name}</span>
                <button
                  type="button"
                  onClick={() => removeItem(item.productId)}
                  className="text-red-600 text-xs hover:underline"
                >
                  Remove
                </button>
              </div>
              <div className="flex justify-between items-center text-sm text-gray-600">
                <span>{formatCurrency(item.pricePerUnit)}/unit</span>
                <input
                  type="number"
                  min={1}
                  value={item.quantity}
                  onChange={(e) => {
                    const v = parseInt(e.target.value, 10);
                    if (!Number.isNaN(v) && v >= 1) updateQuantity(item.productId, v);
                  }}
                  className="w-16 p-1 border border-gray-300 rounded text-center"
                />
                <span className="font-medium text-gray-900">
                  {formatCurrency(item.pricePerUnit * item.quantity)}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="border-t border-gray-200 pt-4 mb-4">
        <div className="flex justify-between items-center text-lg font-semibold text-gray-900">
          <span>Subtotal</span>
          <span>{formatCurrency(total)}</span>
        </div>
      </div>

      {insufficient && items.length > 0 && (
        <p className="text-red-600 text-sm mb-3">Insufficient balance</p>
      )}

      {error && <p className="text-red-600 text-sm mb-3">{error}</p>}

      <button
        type="button"
        onClick={handleBuy}
        disabled={!isValid}
        className="w-full bg-orange-500 text-white py-2 px-4 rounded-md hover:bg-orange-600 disabled:bg-gray-300 disabled:text-gray-500 disabled:cursor-not-allowed transition-colors"
      >
        {submitting ? "Processing..." : "Buy"}
      </button>

      <Link
        href="/order-history"
        className="block text-center mt-4 text-blue-600 hover:underline text-sm"
      >
        Order History
      </Link>
    </aside>
  );
}

"use client";

import { useState } from "react";
import { formatCurrency, formatDateTime } from "~/lib/formatters";

export interface OrderItem {
  product_name: string;
  quantity: number;
  price: number;
  refunded_quantity?: number;
}

export interface Order {
  id: string;
  user_id: string;
  total: number;
  refunded: boolean;
  created_at: string;
  items: OrderItem[];
}

function OrderRow({ order }: { order: Order }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex justify-between items-center p-4 text-left hover:bg-gray-50"
      >
        <div>
          <p className="font-medium text-gray-900">
            {formatDateTime(order.created_at)}
          </p>
          <p className="text-sm text-gray-500">Order #{order.id.slice(0, 8)}</p>
        </div>
        <div className="flex items-center gap-3">
          {order.refunded && (
            <span className="text-xs font-medium bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full border border-amber-200">
              Refunded
            </span>
          )}
          <span className={`text-lg font-bold ${order.refunded ? "line-through text-gray-400" : "text-gray-900"}`}>
            {formatCurrency(order.total)}
          </span>
          <span className="text-gray-400 text-sm">{open ? "▲" : "▼"}</span>
        </div>
      </button>
      {open && (
        <div className="border-t border-gray-200 p-4 bg-gray-50">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-600">
                <th className="pb-2">Product</th>
                <th className="pb-2 text-right">Qty</th>
                <th className="pb-2 text-right">Unit price</th>
                <th className="pb-2 text-right">Line total</th>
                <th className="pb-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {order.items.map((item, idx) => {
                const refundedQty = item.refunded_quantity ?? 0;
                let statusBadge = null;
                if (refundedQty === item.quantity) {
                  statusBadge = (
                    <span className="text-xs font-medium bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full border border-amber-200">
                      Fully refunded
                    </span>
                  );
                } else if (refundedQty > 0) {
                  statusBadge = (
                    <span className="text-xs font-medium bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full border border-yellow-200">
                      {refundedQty} of {item.quantity} refunded
                    </span>
                  );
                }
                return (
                  <tr key={idx} className="border-t border-gray-200">
                    <td className="py-2 text-gray-900">{item.product_name}</td>
                    <td className="py-2 text-right text-gray-700">{item.quantity}</td>
                    <td className="py-2 text-right text-gray-700">
                      {formatCurrency(item.price)}
                    </td>
                    <td className="py-2 text-right font-medium text-gray-900">
                      {formatCurrency(item.price * item.quantity)}
                    </td>
                    <td className="py-2">{statusBadge}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function OrderHistory({ orders }: { orders: Order[] }) {
  if (orders.length === 0) {
    return <p className="text-gray-500 text-center py-8">No purchases yet.</p>;
  }
  return (
    <div className="space-y-3">
      {orders.map((o) => (
        <OrderRow key={o.id} order={o} />
      ))}
    </div>
  );
}

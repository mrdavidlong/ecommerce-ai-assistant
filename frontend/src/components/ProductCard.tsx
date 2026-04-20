"use client";

import { useState } from "react";
import { useCart } from "~/contexts/CartContext";
import { formatCurrency } from "~/lib/formatters";

export interface Product {
  id: string;
  name: string;
  description: string;
  image_url: string;
  price: number;
  stock_quantity: number;
}


export default function ProductCard({ product }: { product: Product }) {
  const { addItem } = useCart();
  const [qty, setQty] = useState(1);

  const outOfStock = product.stock_quantity <= 0;
  const isValid = !outOfStock && qty >= 1 && qty <= product.stock_quantity;

  const handleAdd = () => {
    if (!isValid) return;
    addItem(product, qty);
    setQty(1);
  };

  return (
    <div className="bg-white rounded-lg shadow-md border border-gray-200 overflow-hidden flex flex-col">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={product.image_url}
        alt={product.name}
        className="w-full h-40 object-cover bg-gray-100"
      />
      <div className="p-4">
        <h3 className="text-lg font-semibold text-gray-900">{product.name}</h3>
        <p className="text-sm text-gray-600 mt-1 line-clamp-2">{product.description}</p>
        <div className="flex justify-between items-center mt-3">
          <span className="text-lg font-bold text-gray-900">
            {formatCurrency(product.price)}
          </span>
          <span className={`text-sm ${outOfStock ? "text-red-600" : "text-gray-500"}`}>
            {outOfStock ? "Out of stock" : `${product.stock_quantity} in stock`}
          </span>
        </div>
      </div>

      <div className="border-t border-gray-200 p-4 bg-gray-50 mt-auto">
        <label className="block text-sm font-medium text-gray-700 mb-2">Quantity</label>
        <input
          type="number"
          min={1}
          max={product.stock_quantity}
          value={qty}
          disabled={outOfStock}
          onChange={(e) => {
            const v = parseInt(e.target.value, 10);
            if (Number.isNaN(v)) {
              setQty(1);
            } else {
              setQty(Math.max(1, Math.min(product.stock_quantity, v)));
            }
          }}
          className="w-full p-2 border border-gray-300 rounded-md mb-3 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
        />
        <button
          type="button"
          onClick={handleAdd}
          disabled={!isValid}
          className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:text-gray-500 disabled:cursor-not-allowed transition-colors"
        >
          Add to Cart
        </button>
      </div>
    </div>
  );
}

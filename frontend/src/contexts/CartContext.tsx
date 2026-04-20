"use client";

import {
  createContext,
  useContext,
  useState,
  useMemo,
  useCallback,
  type ReactNode,
} from "react";

export interface CartItem {
  productId: string;
  name: string;
  pricePerUnit: number;
  quantity: number;
}

export interface ProductLike {
  id: string;
  name: string;
  price: number;
}

interface CartContextValue {
  items: CartItem[];
  addItem: (product: ProductLike, qty: number) => void;
  updateQuantity: (productId: string, qty: number) => void;
  removeItem: (productId: string) => void;
  clearCart: () => void;
  total: number;
}

const CartContext = createContext<CartContextValue | undefined>(undefined);

export function CartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CartItem[]>([]);

  const addItem = useCallback((product: ProductLike, qty: number) => {
    setItems((prev) => {
      const existing = prev.find((i) => i.productId === product.id);
      if (existing) {
        return prev.map((i) =>
          i.productId === product.id ? { ...i, quantity: i.quantity + qty } : i,
        );
      }
      return [
        ...prev,
        {
          productId: product.id,
          name: product.name,
          pricePerUnit: product.price,
          quantity: qty,
        },
      ];
    });
  }, []);

  const updateQuantity = useCallback((productId: string, qty: number) => {
    setItems((prev) =>
      prev.map((i) => (i.productId === productId ? { ...i, quantity: qty } : i)),
    );
  }, []);

  const removeItem = useCallback((productId: string) => {
    setItems((prev) => prev.filter((i) => i.productId !== productId));
  }, []);

  const clearCart = useCallback(() => {
    setItems([]);
  }, []);

  const total = useMemo(
    () => items.reduce((sum, i) => sum + i.pricePerUnit * i.quantity, 0),
    [items],
  );

  const value: CartContextValue = {
    items,
    addItem,
    updateQuantity,
    removeItem,
    clearCart,
    total,
  };

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used within CartProvider");
  return ctx;
}

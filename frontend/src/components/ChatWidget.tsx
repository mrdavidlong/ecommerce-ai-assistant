"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useCart } from "~/contexts/CartContext";
import { getCurrentUser } from "~/lib/auth";

interface AgentStep {
  tool: string;
  input: string;
  output: string;
}

interface CartAction {
  action: "add" | "remove";
  product_id: string;
  product_name: string;
  quantity: number;
  price: number;
}

type Message =
  | { role: "user"; text: string }
  | { role: "assistant"; text: string; steps: AgentStep[]; agentName: string };

const AGENT_LABELS: Record<string, string> = {
  product: "Product Specialist",
  account: "Account Specialist",
  cart: "Cart Specialist",
  general: "General Assistant",
  unknown: "Assistant",
};

const DEFAULT_PANEL_SIZE = { width: 384, height: 520 };
const MIN_PANEL_SIZE = { width: 320, height: 420 };
const VIEWPORT_MARGIN = 24;

function AgentBadge({ name }: { name: string }) {
  if (!name || name === "unknown") return null;
  return (
    <p className="text-xs text-gray-400 mb-1">
      Handled by:{" "}
      <span className="font-semibold text-purple-600">
        {AGENT_LABELS[name] ?? name}
      </span>
    </p>
  );
}

function StepsAccordion({ steps }: { steps: AgentStep[] }) {
  const [open, setOpen] = useState(false);
  if (steps.length === 0) return null;
  return (
    <div className="mb-2">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="text-xs text-purple-600 hover:text-purple-800 flex items-center gap-1"
      >
        <span>{open ? "▼" : "▶"}</span>
        <span>
          Thinking ({steps.length} step{steps.length > 1 ? "s" : ""})
        </span>
      </button>
      {open && (
        <div className="mt-1 space-y-1 pl-3 border-l-2 border-purple-200">
          {steps.map((step, i) => (
            <div key={i} className="text-xs text-gray-600 bg-purple-50 rounded p-2">
              <p className="font-mono font-semibold text-purple-700">
                → {step.tool}({step.input})
              </p>
              <p className="mt-0.5 text-gray-500 whitespace-pre-wrap">{step.output}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ChatWidget() {
  const { addItem, removeItem } = useCart();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [userId, setUserId] = useState<string | null>(null);
  const [panelSize, setPanelSize] = useState(DEFAULT_PANEL_SIZE);

  const sessionId = useRef<string>("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const resizeRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    width: number;
    height: number;
  } | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("chat_session_id");
      if (stored) {
        sessionId.current = stored;
      } else {
        const id = crypto.randomUUID();
        localStorage.setItem("chat_session_id", id);
        sessionId.current = id;
      }
    }
    const user = getCurrentUser();
    setUserId(user?.id ?? null);
  }, []);

  const scrollToBottom = useCallback(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading, scrollToBottom]);

  const startResize = (event: React.PointerEvent<HTMLButtonElement>) => {
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    resizeRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      width: panelSize.width,
      height: panelSize.height,
    };
  };

  const resizePanel = (event: React.PointerEvent<HTMLButtonElement>) => {
    const resize = resizeRef.current;
    if (!resize || resize.pointerId !== event.pointerId) return;

    const maxWidth = Math.max(MIN_PANEL_SIZE.width, window.innerWidth - VIEWPORT_MARGIN * 2);
    const maxHeight = Math.max(MIN_PANEL_SIZE.height, window.innerHeight - 120);
    const width = resize.width - (event.clientX - resize.startX);
    const height = resize.height - (event.clientY - resize.startY);

    setPanelSize({
      width: Math.min(Math.max(width, MIN_PANEL_SIZE.width), maxWidth),
      height: Math.min(Math.max(height, MIN_PANEL_SIZE.height), maxHeight),
    });
  };

  const stopResize = (event: React.PointerEvent<HTMLButtonElement>) => {
    if (resizeRef.current?.pointerId === event.pointerId) {
      resizeRef.current = null;
    }
  };

  const send = async () => {
    if (!userId) return;
    const text = input.trim();
    if (!text || loading) return;

    setMessages((prev) => [...prev, { role: "user", text }]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("http://localhost:8000/v2/chat/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          message: text,
          session_id: sessionId.current,
        }),
      });
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const data = (await res.json()) as {
        response: string;
        steps: AgentStep[];
        cart_actions: CartAction[];
        agent_name: string;
      };
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: data.response,
          steps: data.steps ?? [],
          agentName: data.agent_name ?? "unknown",
        },
      ]);
      for (const action of data.cart_actions ?? []) {
        if (action.action === "add") {
          addItem(
            { id: action.product_id, name: action.product_name, price: action.price },
            action.quantity,
          );
        } else if (action.action === "remove") {
          removeItem(action.product_id);
        }
      }
      window.dispatchEvent(new CustomEvent("ai-response"));
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: "Sorry, something went wrong. Please try again.",
          steps: [],
          agentName: "unknown",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  if (!userId) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
      {open && (
        <div
          className="relative mb-3 bg-white rounded-2xl shadow-2xl border border-gray-200 flex flex-col overflow-hidden"
          style={{ width: panelSize.width, height: panelSize.height }}
        >
          <button
            type="button"
            aria-label="Resize chat window"
            title="Resize chat window"
            onPointerDown={startResize}
            onPointerMove={resizePanel}
            onPointerUp={stopResize}
            onPointerCancel={stopResize}
            className="absolute left-1 top-1 z-10 h-6 w-6 cursor-nwse-resize rounded-md text-blue-100 hover:text-white hover:bg-blue-500/40 flex items-center justify-center text-sm"
          >
            ↖
          </button>
          {/* Header */}
          <div className="bg-blue-600 text-white px-4 py-3 flex justify-between items-center">
            <div className="pl-5">
              <p className="font-semibold">AI Shopping Assistant</p>
              <p className="text-xs text-blue-200">Powered by LLM · Multi-Agent + RAG</p>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="text-white hover:text-blue-200 text-xl leading-none"
            >
              ×
            </button>
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50">
            {messages.length === 0 && (
              <div className="text-center text-gray-600 text-sm mt-8">
                <p className="text-2xl mb-2">🤖</p>
                <p className="font-medium text-gray-900">Ask me anything about our products!</p>
                <p className="mt-2 text-xs text-gray-600">
                  Try: What&apos;s good for video calls?
                </p>
              </div>
            )}
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div className={`max-w-[85%] ${msg.role === "user" ? "" : "w-full"}`}>
                  {msg.role === "assistant" && (
                    <>
                      <AgentBadge name={msg.agentName} />
                      <StepsAccordion steps={msg.steps} />
                    </>
                  )}
                  <div
                    className={`rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap ${
                      msg.role === "user"
                        ? "bg-blue-600 text-white rounded-br-sm"
                        : "bg-white text-gray-800 border border-gray-200 rounded-bl-sm shadow-sm"
                    }`}
                  >
                    {msg.text}
                  </div>
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-2 shadow-sm">
                  <span className="text-gray-400 text-sm animate-pulse">Thinking...</span>
                </div>
              </div>
            )}
          </div>

          {/* Input */}
          <div className="p-3 border-t border-gray-200 bg-white flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && void send()}
              placeholder="Ask about products..."
              disabled={loading}
              className="flex-1 text-sm border border-gray-300 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
            />
            <button
              type="button"
              onClick={() => void send()}
              disabled={loading || !input.trim()}
              className="bg-blue-600 text-white rounded-xl px-4 py-2 text-sm hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              Send
            </button>
          </div>
        </div>
      )}

      {/* Bubble toggle */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-14 h-14 bg-blue-600 hover:bg-blue-700 text-white rounded-full shadow-lg flex items-center justify-center text-2xl transition-colors"
        aria-label="Toggle AI assistant"
      >
        {open ? "×" : "💬"}
      </button>
    </div>
  );
}

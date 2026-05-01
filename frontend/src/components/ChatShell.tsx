"use client";

import { usePathname } from "next/navigation";
import ChatWidget from "~/components/ChatWidget";

export default function ChatShell() {
  const pathname = usePathname();
  if (pathname === "/") return null;

  return <ChatWidget />;
}

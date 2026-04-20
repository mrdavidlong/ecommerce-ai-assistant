export function formatCurrency(amount: number): string {
  return amount.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export function formatDateTime(isoString: string): string {
  // Ensure the string is treated as UTC (append Z if no timezone marker present)
  const normalized = /[Zz]|[+-]\d{2}:\d{2}$/.test(isoString)
    ? isoString
    : isoString + "Z";
  return new Date(normalized).toLocaleString();
}

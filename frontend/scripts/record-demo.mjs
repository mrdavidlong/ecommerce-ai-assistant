import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "@playwright/test";

const root = path.resolve(import.meta.dirname, "../..");
const outputDir = path.join(root, "images", "recordings");
const rawVideoPath = path.join(outputDir, "demo-raw.webm");

async function waitForAssistantResponse(page, previousCount) {
  await page.waitForFunction(
    (count) => {
      const body = document.body.innerText;
      const isLoading = body.includes("Thinking...");
      const assistantCount = body.split("Handled by:").length - 1;
      return assistantCount > count && !isLoading;
    },
    previousCount,
    { timeout: 120_000 },
  );
  await page.waitForTimeout(900);
}

async function currentAssistantCount(page) {
  return page.evaluate(() => document.body.innerText.split("Handled by:").length - 1);
}

async function openChatIfNeeded(page) {
  const input = page.getByPlaceholder("Ask about products...");
  if (await input.isVisible().catch(() => false)) {
    return;
  }

  await page.getByRole("button", { name: "Toggle AI assistant" }).click();
  await input.waitFor({ state: "visible", timeout: 10_000 });
  await page.waitForTimeout(700);
}

async function sendMessage(page, message, priorAssistantCount, { expandThinking = true } = {}) {
  await page.getByPlaceholder("Ask about products...").fill(message);
  await page.getByRole("button", { name: "Send" }).click();
  await waitForAssistantResponse(page, priorAssistantCount);

  if (expandThinking) {
    const thinkingButtons = page.getByRole("button", { name: /Thinking/ });
    const count = await thinkingButtons.count();
    if (count > 0) {
      await thinkingButtons.nth(count - 1).click();
      await page.waitForTimeout(1300);
    }
  }

  return currentAssistantCount(page);
}

async function copyLatestRecording() {
  const files = await fs.readdir(outputDir);
  const webms = await Promise.all(
    files
      .filter((file) => file.endsWith(".webm") && file !== "demo-raw.webm")
      .map(async (file) => {
        const filePath = path.join(outputDir, file);
        const stat = await fs.stat(filePath);
        return { filePath, mtimeMs: stat.mtimeMs };
      }),
  );

  webms.sort((a, b) => b.mtimeMs - a.mtimeMs);
  const latest = webms[0]?.filePath;
  if (!latest) {
    throw new Error("No Playwright video was recorded.");
  }

  await fs.copyFile(latest, rawVideoPath);
  console.log(rawVideoPath);
}

await fs.mkdir(outputDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 960 },
  deviceScaleFactor: 1,
  recordVideo: {
    dir: outputDir,
    size: { width: 1440, height: 960 },
  },
});

const page = await context.newPage();

try {
  await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
  await page.getByRole("button").first().click();
  await page.waitForURL("**/store", { timeout: 20_000 });
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(900);

  await openChatIfNeeded(page);

  let assistantCount = 0;
  assistantCount = await sendMessage(page, "What's good for video calls?", assistantCount);
  assistantCount = await sendMessage(page, "Add 2 webcams to my cart", assistantCount);
  await page.waitForTimeout(900);
  assistantCount = await sendMessage(page, "Compare AirTag and Tile Mate", assistantCount);

  await page.getByRole("button", { name: "Buy" }).click();
  await page.waitForFunction(() => document.body.innerText.includes("Your cart is empty."), {
    timeout: 20_000,
  });
  await page.waitForTimeout(1200);

  if (await page.getByPlaceholder("Ask about products...").isVisible().catch(() => false)) {
    await page.getByRole("button", { name: "Toggle AI assistant" }).click();
    await page.waitForTimeout(500);
  }

  await page.getByRole("link", { name: "Order History" }).click();
  await page.waitForURL("**/order-history", { timeout: 20_000 });
  await page.waitForLoadState("networkidle");
  await page.waitForFunction(() => document.body.innerText.includes("Webcam"), {
    timeout: 20_000,
  });
  await page.waitForTimeout(1600);

  await openChatIfNeeded(page);
  assistantCount = await currentAssistantCount(page);
  await sendMessage(page, "Refund the two webcams from my latest order", assistantCount, {
    expandThinking: false,
  });
  await page.waitForFunction(() => document.body.innerText.includes("Fully refunded"), {
    timeout: 30_000,
  });
  await page.waitForTimeout(2500);
} finally {
  await context.close();
  await browser.close();
}

await copyLatestRecording();

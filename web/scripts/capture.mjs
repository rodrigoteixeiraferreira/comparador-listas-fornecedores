// Os prints e o GIF dos READMEs, num idioma por vez, com o Chrome instalado no PC (playwright-core não baixa navegador).
//
//   npm run dev                                          (noutro terminal)
//   node scripts/capture.mjs --lang pt                   os três prints, em docs/img/pt
//   node scripts/capture.mjs --lang pt --gif             e o GIF da revisão (grava decisões no banco)
//
// Os prints saem em 2x e com 256 cores. O GIF responde a fila de verdade: depois dele, devolver o banco ao ponto de partida com
// `python -m pricelists.pipeline --seed 1`, antes do próximo idioma.
import { spawnSync } from "node:child_process";
import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const REPO = resolve(WEB, "..");
const args = process.argv.slice(2);
const option = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 ? args[i + 1] : fallback;
};
const lang = option("lang", "pt");
const base = option("base", "http://localhost:3000");
const out = join(REPO, "docs", "img", lang);
const VIEW = { width: 1280, height: 800 };
const PYTHON = join(REPO, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");

// as imagens passam pelo images.py (Pillow, no Python da demo): 256 cores nos prints, o GIF montado dos quadros
function images(...params) {
  const run = spawnSync(PYTHON, [join(WEB, "scripts", "images.py"), ...params], { stdio: "inherit" });
  if (run.status !== 0) throw new Error(`images.py ${params[0]} falhou`);
}

function env(name) {
  const line = readFileSync(join(WEB, ".env.local"), "utf8")
    .split(/\r?\n/)
    .find((l) => l.startsWith(`${name}=`));
  const value = line?.slice(name.length + 1).trim();
  if (!value) throw new Error(`${name} vazio em web/.env.local`);
  return value;
}

const browser = await chromium.launch({ channel: "chrome" });
const context = await browser.newContext({ viewport: VIEW, deviceScaleFactor: 2, colorScheme: "dark" });
const page = await context.newPage();

async function open(path) {
  await page.goto(`${base}/${lang}${path}`);
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready);
}

// o print da página até a altura pedida (a comparação inteira teria dezenas de produtos)
async function shot(path, file, maxHeight) {
  await open(path);
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  await page.screenshot({
    path: join(out, file),
    fullPage: true,
    clip: { x: 0, y: 0, width: VIEW.width, height: Math.min(height, maxHeight) },
  });
  console.log(`  ${lang}/${file}`);
}

mkdirSync(out, { recursive: true });
await page.goto(`${base}/${lang}/login`);
await page.fill('input[name="email"]', env("DEMO_EMAIL"));
await page.fill('input[name="password"]', env("DEMO_PASSWORD"));
await page.click('button:not([type="button"])');
await page.waitForURL(`${base}/${lang}`);

await shot("", "tela_estado.png", 3200);
await shot("/compare", "tela_comparacao.png", 1700);
await shot("/review", "tela_revisao.png", 1700);
images("png", ...["tela_estado.png", "tela_comparacao.png", "tela_revisao.png"].map((f) => join(out, f)));

if (args.includes("--gif")) {
  // os quadros: a fila, o «não é», o «a loja não tem», o «é este» na linha do preço longe do custo e, na comparação,
  // o par que a pessoa decidiu, fora da disputa até alguém conferir o preço
  const frames = join(WEB, ".frames", lang);
  rmSync(frames, { recursive: true, force: true });
  mkdirSync(frames, { recursive: true });
  const durations = [];
  const frame = async (ms) => {
    await page.waitForTimeout(250);
    await page.screenshot({ path: join(frames, `${String(durations.length).padStart(2, "0")}.png`) });
    durations.push(ms);
  };
  const focus = async (locator) => {
    await locator.evaluate((el) => window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - 24 }));
  };
  // o clique termina quando nenhum botão está mais gravando: aí a tela já voltou com a fila nova
  const decide = async (button) => {
    await button.click();
    await page.waitForSelector("button[data-decision]:disabled", { timeout: 3000 }).catch(() => {});
    await page.waitForFunction(() => !document.querySelector("button[data-decision]:disabled"), null, {
      timeout: 30000,
    });
  };

  await open("/review");
  await frame(2200);

  // uma linha sem candidato de atributos iguais: os candidatos vêm da semelhança de texto e diferem em algo
  const line = page.locator('article[data-reason="text_similarity"]').first();
  const lineId = await line.getAttribute("data-line");
  const card = page.locator(`article[data-line="${lineId}"]`);
  await focus(card);
  await frame(2600);
  const no = card.locator("li").first().locator('button[data-decision="reject"]');
  await no.hover();
  await frame(1200);
  await decide(no);
  await focus(card);
  await frame(2200);
  const notCarried = card.locator('button[data-decision="not_carried"]');
  await notCarried.hover();
  await frame(1200);
  await decide(notCarried);
  await page.evaluate(() => window.scrollTo({ top: 0 }));
  await frame(2200);

  // a linha do preço longe do custo: a pessoa confirma a identidade
  const far = page.locator('article[data-reason="price_far_from_cost"]').first();
  const description = await far.locator("li").first().getAttribute("data-description");
  await focus(far);
  await frame(2600);
  const yes = far.locator("li").first().locator('button[data-decision="confirm"]');
  await yes.hover();
  await frame(1200);
  await decide(yes);
  await page.evaluate(() => window.scrollTo({ top: 0 }));
  await frame(2000);

  await open(`/compare?min=1&q=${encodeURIComponent(description ?? "")}`);
  await focus(page.locator("article").first());
  await frame(4000);

  writeFileSync(join(frames, "durations.json"), JSON.stringify(durations));
  images("gif", frames, join(out, "revisao.gif"));
}

await browser.close();

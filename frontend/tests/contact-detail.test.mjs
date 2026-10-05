import assert from "node:assert/strict";
import { execFileSync, spawn } from "node:child_process";
import { once } from "node:events";
import { createServer } from "node:http";
import { createRequire } from "node:module";
import { after, afterEach, before, beforeEach, describe, it } from "node:test";
import { setTimeout as delay } from "node:timers/promises";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || "playwright");
const frontendPort = Number(process.env.TEST_FRONTEND_PORT || 3001);
const apiPort = Number(process.env.TEST_API_PORT || 8011);
const frontendUrl = `http://127.0.0.1:${frontendPort}`;
const apiUrl = `http://127.0.0.1:${apiPort}`;
const tags = [{ id: 1, name: "Cliente" }, { id: 2, name: "Lead" }];
const address = {
  cep: "22451-900", logradouro: "Rua Marquês de São Vicente",
  bairro: "Gávea", cidade: "Rio de Janeiro", uf: "RJ",
};
const summary = {
  id: 10, contact_id: 1, summary_text: "Resumo existente do contato.",
  generated_at: "2026-10-05T12:00:00Z",
};
const contact = {
  id: 1, full_name: "João Victor Rangel", email: "joao@example.com",
  phone: "(21) 98765-4321", source: "manual", created_at: "2026-10-05T10:00:00Z",
  tags: [tags[0]], address, latest_ai_summary: summary,
};
let state;
let browser;
let page;
let server;
let next;
let nextLog = "";
let buildChanged = false;
let pageErrors;

function send(response, status, payload) {
  response.writeHead(status, { "Content-Type": "application/json" });
  response.end(status === 204 ? undefined : JSON.stringify(payload));
}

async function mockApi(request, response) {
  response.setHeader("Access-Control-Allow-Origin", frontendUrl);
  response.setHeader("Access-Control-Allow-Methods", "GET, POST, DELETE");
  response.setHeader("Access-Control-Allow-Headers", "Content-Type, Accept");
  if (request.method === "OPTIONS") return send(response, 204);

  const path = new URL(request.url, apiUrl).pathname;
  if (path === "/tags") return send(response, state.tagsStatus, tags);
  if (request.method === "GET" && path === "/contacts/1") {
    state.calls.detail++;
    return send(response, state.detailStatus, state.contact);
  }
  if (request.method === "GET" && path === "/contacts") {
    return send(response, 200, {
      items: [{ ...state.contact, has_ai_summary: Boolean(state.contact.latest_ai_summary) }],
      page: 1, page_size: 10, pages: 1, total: 1,
    });
  }

  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  const body = chunks.length ? JSON.parse(Buffer.concat(chunks).toString()) : {};
  if (request.method === "POST" && path === "/contacts/1/tags") {
    if (state.addStatus !== 201) return send(response, state.addStatus, { detail: "INTERNAL_ERROR" });
    const tag = tags.find(tag => tag.id === body.tag_id);
    assert.ok(tag);
    state.contact.tags.push(tag);
    return send(response, 201, { contact_id: 1, tag_id: tag.id, tag_name: tag.name });
  }
  if (request.method === "DELETE" && path.startsWith("/contacts/1/tags/")) {
    if (state.removeStatus !== 204) return send(response, state.removeStatus, { detail: "INTERNAL_ERROR" });
    state.contact.tags = state.contact.tags.filter(tag => tag.id !== Number(path.split("/").at(-1)));
    return send(response, 204);
  }
  if (request.method === "POST" && path === "/contacts/1/summarize") {
    state.calls.summary++;
    state.summaryStarted?.();
    if (state.summaryGate) await state.summaryGate;
    if (state.summaryStatus !== 201) return send(response, state.summaryStatus, { detail: "INTERNAL_PROVIDER_TRACE" });
    state.contact.latest_ai_summary = { ...summary, id: 11, summary_text: "Resumo simulado atualizado." };
    return send(response, 201, state.contact.latest_ai_summary);
  }
  if (request.method === "POST" && path === "/contacts/1/enrich-address") {
    state.calls.address++;
    state.lastCep = body.cep;
    if (state.addressStatus !== 200) return send(response, state.addressStatus, { detail: "INTERNAL_PROVIDER_TRACE" });
    state.contact.address = { ...address, logradouro: "Rua do Endereço Atualizado" };
    return send(response, 200, state.contact.address);
  }
  return send(response, 404, { detail: "Contact not found." });
}

async function openContact() {
  await page.goto(`${frontendUrl}/contacts/1`);
  await page.getByRole("heading", { name: state.contact.full_name, exact: true }).waitFor();
  await page.waitForLoadState("networkidle");
}

describe("Contact detail with an isolated mock API", { timeout: 90000 }, () => {
  before(async () => {
    server = createServer((request, response) => {
      mockApi(request, response).catch(error => {
        console.error(error);
        send(response, 500, { detail: "Mock error." });
      });
    });
    await new Promise((resolve, reject) => {
      server.once("error", reject);
      server.listen(apiPort, "127.0.0.1", resolve);
    });
    buildChanged = true;
    execFileSync("npm", ["run", "build"], {
      env: { ...process.env, NEXT_PUBLIC_API_URL: apiUrl }, timeout: 60000,
    });
    next = spawn(process.execPath, [require.resolve("next/dist/bin/next"), "start",
      "--hostname", "127.0.0.1", "--port", String(frontendPort)], {
      env: { ...process.env, NEXT_PUBLIC_API_URL: apiUrl },
      stdio: ["ignore", "pipe", "pipe"],
    });
    next.stdout.on("data", chunk => { nextLog += chunk; });
    next.stderr.on("data", chunk => { nextLog += chunk; });
    let ready = false;
    for (let attempt = 0; attempt < 100; attempt++) {
      if (next.exitCode !== null) throw new Error(nextLog);
      try {
        await fetch(`${frontendUrl}/contacts/invalid`);
        ready = true;
        break;
      } catch {
        await delay(100);
      }
    }
    assert.ok(ready, nextLog);
    browser = await chromium.launch({ channel: "chrome", headless: true });
  });

  beforeEach(async () => {
    state = {
      contact: structuredClone(contact), calls: { detail: 0, summary: 0, address: 0 },
      detailStatus: 200, tagsStatus: 200, addStatus: 201, removeStatus: 204,
      summaryStatus: 201, addressStatus: 200,
    };
    pageErrors = [];
    page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.on("pageerror", error => pageErrors.push(error.message));
    await page.route("**/*", route => {
      const url = new URL(route.request().url());
      return url.origin === frontendUrl || url.origin === apiUrl
        ? route.continue() : route.abort();
    });
  });

  afterEach(async () => {
    state.summaryGate = null;
    await page?.close();
    assert.deepEqual(pageErrors, []);
  });

  after(async () => {
    await browser?.close();
    if (next && next.exitCode === null) {
      const exited = once(next, "exit");
      next.kill("SIGTERM");
      await exited;
    }
    if (server?.listening) {
      server.closeAllConnections();
      await new Promise(resolve => server.close(resolve));
    }
    if (buildChanged) execFileSync("npm", ["run", "build"], { timeout: 60000 });
  });

  it("loads contact fields without automatic external actions", async () => {
    await openContact();
    await page.getByText(contact.email, { exact: true }).waitFor();
    await page.getByText(contact.phone, { exact: true }).waitFor();
    await page.getByText(contact.source, { exact: true }).waitFor();
    assert.equal(state.calls.summary, 0);
    assert.equal(state.calls.address, 0);
  });

  it("shows a contact without tags", async () => {
    state.contact.tags = [];
    await openContact();
    await page.getByText("Nenhuma tag associada.").waitFor();
  });

  it("shows existing tags and excludes them from available choices", async () => {
    await openContact();
    await page.getByRole("button", { name: "Remover tag Cliente" }).waitFor();
    assert.equal(await page.getByLabel("Tag existente").locator("option", { hasText: "Cliente" }).count(), 0);
  });

  it("adds a tag locally and removes it from available choices", async () => {
    await openContact();
    await page.getByLabel("Tag existente").selectOption("2");
    await page.getByRole("button", { name: "Adicionar tag" }).click();
    await page.getByRole("button", { name: "Remover tag Lead" }).waitFor();
    await page.getByText("Todas as tags já estão associadas.").waitFor();
    assert.equal(await page.getByLabel("Tag existente").count(), 0);
  });

  it("removes a tag locally and makes it available again", async () => {
    await openContact();
    await page.getByRole("button", { name: "Remover tag Cliente" }).click();
    await page.getByText("Nenhuma tag associada.").waitFor();
    assert.equal(await page.getByRole("button", { name: "Remover tag Cliente" }).count(), 0);
    assert.equal(await page.getByLabel("Tag existente").locator("option", { hasText: "Cliente" }).count(), 1);
  });

  it("handles a duplicate tag without breaking the page", async () => {
    state.addStatus = 409;
    await openContact();
    await page.getByLabel("Tag existente").selectOption("2");
    await page.getByRole("button", { name: "Adicionar tag" }).click();
    await page.getByText("Esta tag já está associada ao contato.").waitFor();
    assert.equal(await page.getByRole("button", { name: "Adicionar tag" }).isEnabled(), true);
  });

  it("keeps a tag visible when removal fails", async () => {
    state.removeStatus = 500;
    await openContact();
    await page.getByRole("button", { name: "Remover tag Cliente" }).click();
    await page.getByText("Não foi possível remover a tag. Tente novamente.").waitFor();
    assert.equal(await page.getByRole("button", { name: "Remover tag Cliente" }).isEnabled(), true);
  });

  it("shows the absence of a summary", async () => {
    state.contact.latest_ai_summary = null;
    await openContact();
    await page.getByText("Nenhum resumo gerado.").waitFor();
  });

  it("displays the latest existing summary", async () => {
    await openContact();
    await page.getByText(summary.summary_text).waitFor();
    assert.equal(state.calls.summary, 0);
  });

  it("generates only once on repeated clicks and disables the button while pending", async () => {
    let release;
    let started;
    const requestStarted = new Promise(resolve => { started = resolve; });
    state.summaryStarted = started;
    state.summaryGate = new Promise(resolve => { release = resolve; });
    await openContact();
    await page.getByRole("button", { name: "Gerar resumo com IA" }).evaluate(button => {
      button.click();
      button.click();
      button.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    try {
      await requestStarted;
      await page.getByRole("button", { name: "Gerando..." }).waitFor();
      assert.equal(await page.getByRole("button", { name: "Gerando..." }).isDisabled(), true);
      assert.equal(state.calls.summary, 1);
    } finally {
      release();
    }
    await page.getByText("Resumo simulado atualizado.").waitFor();
    assert.equal(await page.getByRole("button", { name: "Gerar resumo com IA" }).isEnabled(), true);
    assert.equal(state.calls.summary, 1);
  });

  for (const [status, message] of [
    [502, "Não foi possível gerar o resumo. Tente novamente."],
    [429, "Limite de solicitações atingido. Tente novamente mais tarde."],
    [503, "O serviço de IA está indisponível no momento."],
    [504, "A geração do resumo demorou demais. Tente novamente."],
  ]) {
    it(`handles summary error ${status} without retry or loss of the existing summary`, async () => {
      state.summaryStatus = status;
      await openContact();
      await page.getByRole("button", { name: "Gerar resumo com IA" }).click();
      await page.getByText(message, { exact: true }).waitFor();
      await page.getByText(summary.summary_text).waitFor();
      assert.equal(await page.getByRole("button", { name: "Gerar resumo com IA" }).isEnabled(), true);
      assert.equal(state.calls.summary, 1);
      assert.equal(await page.getByText("INTERNAL_PROVIDER_TRACE").count(), 0);
    });
  }

  it("shows the absence of an address", async () => {
    state.contact.address = null;
    await openContact();
    await page.getByText("Endereço ainda não enriquecido.").waitFor();
  });

  it("displays the existing enriched address", async () => {
    await openContact();
    await page.getByText(address.logradouro, { exact: true }).waitFor();
    await page.getByText(address.bairro, { exact: true }).waitFor();
    await page.getByText("Rio de Janeiro / RJ", { exact: true }).waitFor();
  });

  for (const cep of ["22451900", "22451-900"]) {
    it(`sends CEP ${cep} and replaces the visible address on success`, async () => {
      await openContact();
      await page.getByLabel("CEP", { exact: true }).fill(cep);
      await page.getByRole("button", { name: "Buscar endereço" }).click();
      await page.getByText("Rua do Endereço Atualizado", { exact: true }).waitFor();
      assert.equal(state.lastCep, cep);
      assert.equal(await page.getByText(address.logradouro, { exact: true }).count(), 0);
    });
  }

  for (const [status, message] of [
    [422, "CEP inválido. Informe um CEP com 8 dígitos."],
    [404, "CEP ou contato não encontrado."],
    [502, "Não foi possível buscar o endereço. Tente novamente."],
  ]) {
    it(`handles CEP error ${status} and preserves the previous address`, async () => {
      state.addressStatus = status;
      await openContact();
      await page.getByLabel("CEP", { exact: true }).fill("123");
      await page.getByRole("button", { name: "Buscar endereço" }).click();
      await page.getByText(message, { exact: true }).waitFor();
      await page.getByText(address.logradouro, { exact: true }).waitFor();
      assert.equal(await page.getByRole("button", { name: "Buscar endereço" }).isEnabled(), true);
    });
  }

  it("shows a missing contact", async () => {
    await page.goto(`${frontendUrl}/contacts/999999`);
    await page.getByRole("heading", { name: "Contato não encontrado." }).waitFor();
  });

  it("rejects an invalid contact route without querying the API", async () => {
    await page.goto(`${frontendUrl}/contacts/invalid`);
    await page.getByRole("heading", { name: "Contato não encontrado." }).waitFor();
    assert.equal(state.calls.detail, 0);
  });

  it("shows a friendly initial loading error", async () => {
    state.detailStatus = 500;
    await page.goto(`${frontendUrl}/contacts/1`);
    await page.getByText("Não foi possível carregar o contato.").waitFor();
    await page.getByRole("link", { name: "Tentar novamente" }).waitFor();
  });

  it("keeps the contact functional if available tags fail to load", async () => {
    state.tagsStatus = 503;
    await openContact();
    await page.getByText("Não foi possível carregar as tags disponíveis.").waitFor();
    await page.getByRole("button", { name: "Gerar resumo com IA" }).waitFor();
  });

  it("fits desktop and mobile even with long fields and tag names", async () => {
    state.contact.full_name = "Contato com um nome bastante longo para validar a quebra de linhas";
    state.contact.email = `${"contato".repeat(12)}@example.com`;
    state.contact.tags = [{ id: 3, name: "Tag".repeat(45) }];
    await openContact();
    assert.equal(await page.locator("header").count(), 2);
    await page.screenshot({ path: "/tmp/contact-detail-desktop.png", fullPage: true });
    for (const width of [390, 320]) {
      await page.setViewportSize({ width, height: 844 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), width);
    }
    await page.screenshot({ path: "/tmp/contact-detail-mobile.png" });
    await page.getByRole("heading", { name: "Resumo por IA" }).scrollIntoViewIfNeeded();
    await page.screenshot({ path: "/tmp/contact-detail-mobile-actions.png" });
    await page.getByRole("heading", { name: "Endereço", exact: true }).scrollIntoViewIfNeeded();
    await page.screenshot({ path: "/tmp/contact-detail-mobile-address.png" });
  });
});

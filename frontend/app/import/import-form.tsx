"use client";

import { useRef, useState, type FormEvent } from "react";

import { ApiError, importContacts } from "@/lib/api";
import type { ContactImportReport } from "@/lib/types";
import detail from "../contacts/[id]/detail.module.css";
import styles from "./import.module.css";

const example = JSON.stringify([
  { full_name: " João Silva ", email: "JOAO@EMAIL.COM", phone: "21999999999", source: "import" },
  { full_name: "Maria Souza", email: "maria@email.com", phone: "21988888888" },
], null, 2);

export function ImportForm() {
  const [json, setJson] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ContactImportReport | null>(null);
  const inFlight = useRef(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current) return;
    setError(null);

    let contacts: unknown;
    try {
      contacts = JSON.parse(json);
    } catch {
      setError("JSON inválido. Verifique a sintaxe do conteúdo.");
      return;
    }
    if (!Array.isArray(contacts)) {
      setError("O conteúdo JSON deve ser um array de contatos.");
      return;
    }

    inFlight.current = true;
    setPending(true);
    try {
      setReport(await importContacts(contacts));
    } catch (error) {
      setError(error instanceof ApiError && error.status === 422
        ? "Não foi possível importar esse lote. Verifique os dados enviados."
        : "Não foi possível confirmar a importação. Confira os contatos antes de tentar novamente.");
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }

  return (
    <>
      <form className={styles.form} onSubmit={submit} aria-busy={pending}>
        <label className={styles.jsonField}>
          <span>Contatos (JSON)</span>
          <textarea
            value={json}
            onChange={event => setJson(event.target.value)}
            placeholder={example}
            spellCheck={false}
            autoCapitalize="off"
            required
            disabled={pending}
            aria-invalid={error !== null}
            aria-describedby={error ? "import-error" : undefined}
          />
        </label>
        <div>
          <button className={detail.primaryButton} disabled={pending || !json.trim()}>
            {pending ? "Importando..." : "Importar contatos"}
          </button>
        </div>
        {error && <p id="import-error" className={detail.error} role="alert">{error}</p>}
      </form>
      <div aria-live="polite">
        {report && (
          <section className={detail.section} aria-labelledby="import-result-title">
            <h2 id="import-result-title">Resultado da importação</h2>
            <dl className={styles.counts}>
              <div><dt>Importados</dt><dd>{report.imported}</dd></div>
              <div><dt>Rejeitados</dt><dd>{report.rejected}</dd></div>
            </dl>
            {report.errors.length ? (
              <ul className={styles.errors}>
                {report.errors.map(item => (
                  <li key={item.index}>
                    <strong>Item {item.index + 1}</strong>
                    <p>{item.reason}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className={styles.success}>
                {report.imported ? "Todos os contatos foram importados." : "Nenhum contato enviado."}
              </p>
            )}
          </section>
        )}
      </div>
    </>
  );
}

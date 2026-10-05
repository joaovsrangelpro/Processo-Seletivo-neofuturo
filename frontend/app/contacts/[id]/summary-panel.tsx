"use client";

import { useRef, useState } from "react";

import { ApiError, summarizeContact } from "@/lib/api";
import type { AISummary } from "@/lib/types";
import styles from "./detail.module.css";

interface SummaryPanelProps {
  contactId: number;
  initialSummary: AISummary | null;
}

function summaryError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return "Contato não encontrado.";
    if (error.status === 429) return "Limite de solicitações atingido. Tente novamente mais tarde.";
    if (error.status === 503) return "O serviço de IA está indisponível no momento.";
    if (error.status === 504) return "A geração do resumo demorou demais. Tente novamente.";
  }
  return "Não foi possível gerar o resumo. Tente novamente.";
}

export function SummaryPanel({ contactId, initialSummary }: SummaryPanelProps) {
  const [summary, setSummary] = useState(initialSummary);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);

  async function generateSummary() {
    if (inFlight.current) return;
    inFlight.current = true;
    setPending(true);
    setError(null);
    try {
      setSummary(await summarizeContact(contactId));
    } catch (error) {
      setError(summaryError(error));
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }

  return (
    <section className={styles.section} aria-labelledby="summary-title">
      <h2 id="summary-title">Resumo por IA</h2>
      <div aria-live="polite" aria-busy={pending}>
        {summary ? (
          <>
            <p className={styles.summaryText}>{summary.summary_text}</p>
            <p className={styles.muted}>
              Gerado em{" "}
              <time dateTime={summary.generated_at}>
                {new Date(summary.generated_at).toLocaleString("pt-BR", {
                  timeZone: "America/Sao_Paulo",
                })}
              </time>
            </p>
          </>
        ) : (
          <p className={styles.muted}>Nenhum resumo gerado.</p>
        )}
      </div>
      <button
        className={`${styles.primaryButton} ${styles.actionSpacing}`}
        type="button"
        disabled={pending}
        onClick={generateSummary}
      >
        {pending ? "Gerando..." : "Gerar resumo com IA"}
      </button>
      {error && <p className={styles.error} role="alert">{error}</p>}
    </section>
  );
}

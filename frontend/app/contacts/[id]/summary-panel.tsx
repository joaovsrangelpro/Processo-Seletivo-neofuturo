import type { AISummary } from "@/lib/types";
import styles from "./detail.module.css";

interface SummaryPanelProps {
  contactId: number;
  initialSummary: AISummary | null;
}

export function SummaryPanel({ initialSummary }: SummaryPanelProps) {
  return (
    <section className={styles.section} aria-labelledby="summary-title">
      <h2 id="summary-title">Resumo por IA</h2>
      {initialSummary ? (
        <>
          <p className={styles.summaryText}>{initialSummary.summary_text}</p>
          <p className={styles.muted}>
            Gerado em{" "}
            <time dateTime={initialSummary.generated_at}>
              {new Date(initialSummary.generated_at).toLocaleString("pt-BR", {
                timeZone: "America/Sao_Paulo",
              })}
            </time>
          </p>
        </>
      ) : (
        <p className={styles.muted}>Nenhum resumo gerado.</p>
      )}
    </section>
  );
}

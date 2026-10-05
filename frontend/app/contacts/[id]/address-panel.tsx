import type { Address } from "@/lib/types";
import styles from "./detail.module.css";

interface AddressPanelProps {
  contactId: number;
  initialAddress: Address | null;
}

export function AddressPanel({ initialAddress }: AddressPanelProps) {
  return (
    <section className={styles.section} aria-labelledby="address-title">
      <h2 id="address-title">Endereço</h2>
      {initialAddress ? (
        <dl className={styles.fields}>
          <div><dt>CEP</dt><dd>{initialAddress.cep}</dd></div>
          <div><dt>Logradouro</dt><dd>{initialAddress.logradouro || "Não informado"}</dd></div>
          <div><dt>Bairro</dt><dd>{initialAddress.bairro || "Não informado"}</dd></div>
          <div><dt>Cidade / UF</dt><dd>{initialAddress.cidade} / {initialAddress.uf}</dd></div>
        </dl>
      ) : (
        <p className={styles.muted}>Endereço ainda não enriquecido.</p>
      )}
    </section>
  );
}

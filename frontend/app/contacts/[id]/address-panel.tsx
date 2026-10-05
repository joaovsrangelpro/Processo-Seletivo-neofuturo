"use client";

import { useRef, useState, type FormEvent } from "react";

import { ApiError, enrichContactAddress } from "@/lib/api";
import type { Address } from "@/lib/types";
import styles from "./detail.module.css";

interface AddressPanelProps {
  contactId: number;
  initialAddress: Address | null;
}

function addressError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 422) return "CEP inválido. Informe um CEP com 8 dígitos.";
    if (error.status === 404) return "CEP ou contato não encontrado.";
    if (error.status === 504) return "A consulta do CEP demorou demais. Tente novamente.";
  }
  return "Não foi possível buscar o endereço. Tente novamente.";
}

export function AddressPanel({ contactId, initialAddress }: AddressPanelProps) {
  const [address, setAddress] = useState(initialAddress);
  const [cep, setCep] = useState(initialAddress?.cep ?? "");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);

  async function lookupAddress(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current) return;
    inFlight.current = true;
    setPending(true);
    setError(null);
    try {
      const result = await enrichContactAddress(contactId, cep.trim());
      setAddress(result);
      setCep(result.cep);
    } catch (error) {
      setError(addressError(error));
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }

  return (
    <section className={styles.section} aria-labelledby="address-title">
      <h2 id="address-title">Endereço</h2>
      <div aria-live="polite" aria-busy={pending}>
        {address ? (
          <dl className={styles.fields}>
            <div><dt>CEP</dt><dd>{address.cep}</dd></div>
            <div><dt>Logradouro</dt><dd>{address.logradouro || "Não informado"}</dd></div>
            <div><dt>Bairro</dt><dd>{address.bairro || "Não informado"}</dd></div>
            <div><dt>Cidade / UF</dt><dd>{address.cidade} / {address.uf}</dd></div>
          </dl>
        ) : (
          <p className={styles.muted}>Endereço ainda não enriquecido.</p>
        )}
      </div>
      <form className={styles.controlRow} onSubmit={lookupAddress}>
        <label className={styles.field}>
          <span>CEP</span>
          <input
            value={cep}
            onChange={event => setCep(event.target.value)}
            inputMode="numeric"
            autoComplete="postal-code"
            placeholder="22451-900"
            required
            disabled={pending}
            aria-invalid={error !== null}
            aria-describedby={error ? "cep-error" : undefined}
          />
        </label>
        <button className={styles.primaryButton} disabled={pending || !cep.trim()}>
          {pending ? "Buscando..." : "Buscar endereço"}
        </button>
      </form>
      {error && <p id="cep-error" className={styles.error} role="alert">{error}</p>}
    </section>
  );
}

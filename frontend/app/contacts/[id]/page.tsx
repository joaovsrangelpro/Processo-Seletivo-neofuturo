import Link from "next/link";
import { notFound } from "next/navigation";

import { ApiError, getContact, getTags } from "@/lib/api";
import type { ContactDetail, Tag } from "@/lib/types";
import { AddressPanel } from "./address-panel";
import { SummaryPanel } from "./summary-panel";
import { TagManager } from "./tag-manager";
import shell from "../../page.module.css";
import styles from "./detail.module.css";

interface ContactPageProps {
  params: Promise<{ id: string }>;
}

export default async function ContactPage({ params }: ContactPageProps) {
  const { id } = await params;
  const contactId = Number(id);
  if (!/^\d+$/.test(id) || !Number.isSafeInteger(contactId) || contactId < 1) {
    notFound();
  }

  let contact: ContactDetail | null = null;
  try {
    contact = await getContact(contactId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      notFound();
    }
  }

  let availableTags: Tag[] | null = null;
  if (contact) {
    try {
      availableTags = await getTags();
    } catch {
      availableTags = null;
    }
  }

  return (
    <div className={shell.page}>
      <header className={shell.appHeader}>
        <div className={shell.headerInner}>
          <span className={shell.brandMark} aria-hidden="true" />
          <span className={shell.brand}>Gestão de contatos</span>
        </div>
      </header>
      <main className={shell.content}>
        <nav className={styles.backNav} aria-label="Navegação do contato">
          <Link className={shell.backLink} href="/">
            <span aria-hidden="true">← </span>
            Voltar para contatos
          </Link>
        </nav>
        {contact ? (
          <>
            <header className={styles.contactHeader}>
              <p className={shell.eyebrow}>Contato #{contact.id}</p>
              <h1>{contact.full_name}</h1>
              <dl className={styles.fields}>
                <div><dt>E-mail</dt><dd>{contact.email}</dd></div>
                <div><dt>Telefone</dt><dd>{contact.phone}</dd></div>
                <div><dt>Origem</dt><dd>{contact.source || "Não informada"}</dd></div>
                <div>
                  <dt>Cadastrado em</dt>
                  <dd>
                    <time dateTime={contact.created_at}>
                      {new Date(contact.created_at).toLocaleString("pt-BR", {
                        timeZone: "America/Sao_Paulo",
                      })}
                    </time>
                  </dd>
                </div>
              </dl>
            </header>
            <TagManager
              contactId={contact.id}
              initialTags={contact.tags}
              availableTags={availableTags}
            />
            <SummaryPanel contactId={contact.id} initialSummary={contact.latest_ai_summary} />
            <AddressPanel contactId={contact.id} initialAddress={contact.address} />
          </>
        ) : (
          <div className={shell.errorState} role="alert">
            <div>
              <strong>Não foi possível carregar o contato.</strong>
              <p>Tente novamente em instantes.</p>
            </div>
            <a className={shell.secondaryButton} href={`/contacts/${contactId}`}>
              Tentar novamente
            </a>
          </div>
        )}
      </main>
    </div>
  );
}

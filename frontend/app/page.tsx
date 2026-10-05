import Link from "next/link";

import { getContacts, getTags } from "@/lib/api";
import type { ContactListResponse, Tag } from "@/lib/types";
import { TagFilter } from "./components/tag-filter";
import styles from "./page.module.css";

const PAGE_SIZE = 10;

interface HomeProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

function firstValue(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function parsePage(value: string | undefined): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}

function pageHref(page: number, tag?: string): string {
  const params = new URLSearchParams();

  if (page > 1) {
    params.set("page", String(page));
  }
  if (tag) {
    params.set("tag", tag);
  }

  const query = params.toString();
  return query ? `/?${query}` : "/";
}

function AppHeader() {
  return (
    <header className={styles.appHeader}>
      <div className={styles.headerInner}>
        <span className={styles.brandMark} aria-hidden="true" />
        <span className={styles.brand}>Gestão de contatos</span>
      </div>
    </header>
  );
}

function ErrorState({ retryHref }: { retryHref: string }) {
  return (
    <div className={styles.errorState} role="alert">
      <div>
        <strong>Não foi possível carregar os contatos.</strong>
        <p>Confirme se o backend está disponível e tente novamente.</p>
      </div>
      <a className={styles.secondaryButton} href={retryHref}>
        Tentar novamente
      </a>
    </div>
  );
}

function ContactsTable({ data }: { data: ContactListResponse }) {
  if (data.items.length === 0) {
    return (
      <div className={styles.emptyState}>
        <strong>Nenhum contato encontrado.</strong>
      </div>
    );
  }

  return (
    <div className={styles.tableFrame}>
      <div className={styles.tableScroller}>
        <table className={styles.contactsTable}>
          <thead>
            <tr>
              <th>Nome</th>
              <th>E-mail</th>
              <th>Telefone</th>
              <th>Origem</th>
              <th>Resumo IA</th>
              <th className={styles.actionColumn}>
                <span className={styles.srOnly}>Ações</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((contact) => (
              <tr key={contact.id}>
                <td>
                  <Link
                    className={styles.contactName}
                    href={`/contacts/${contact.id}`}
                  >
                    {contact.full_name}
                  </Link>
                </td>
                <td>{contact.email}</td>
                <td>{contact.phone}</td>
                <td>{contact.source ?? "Não informada"}</td>
                <td>
                  <span
                    className={
                      contact.has_ai_summary
                        ? styles.summaryReady
                        : styles.summaryMissing
                    }
                  >
                    {contact.has_ai_summary ? "Disponível" : "Não gerado"}
                  </span>
                </td>
                <td className={styles.actionColumn}>
                  <Link
                    className={styles.rowAction}
                    href={`/contacts/${contact.id}`}
                  >
                    Ver contato
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Pagination({ data, tag }: { data: ContactListResponse; tag?: string }) {
  if (data.pages < 1 || data.items.length === 0) {
    return null;
  }

  const hasPrevious = data.page > 1;
  const hasNext = data.page < data.pages;

  return (
    <nav className={styles.pagination} aria-label="Paginação de contatos">
      {hasPrevious ? (
        <Link
          className={styles.paginationButton}
          href={pageHref(data.page - 1, tag)}
        >
          Anterior
        </Link>
      ) : (
        <button className={styles.paginationDisabled} type="button" disabled>
          Anterior
        </button>
      )}
      <span className={styles.pageStatus}>
        Página {data.page} de {data.pages}
      </span>
      {hasNext ? (
        <Link
          className={styles.paginationButton}
          href={pageHref(data.page + 1, tag)}
        >
          Próxima
        </Link>
      ) : (
        <button className={styles.paginationDisabled} type="button" disabled>
          Próxima
        </button>
      )}
    </nav>
  );
}

export default async function Home({ searchParams }: HomeProps) {
  const params = await searchParams;
  const page = parsePage(firstValue(params.page));
  const tag = firstValue(params.tag)?.trim() || undefined;
  let contacts: ContactListResponse;
  let tags: Tag[];

  try {
    [contacts, tags] = await Promise.all([
      getContacts({ page, pageSize: PAGE_SIZE, tag }),
      getTags(),
    ]);
  } catch {
    return (
      <div className={styles.page}>
        <AppHeader />
        <main className={styles.content}>
          <div className={styles.titleBlock}>
            <p className={styles.eyebrow}>Visão geral</p>
            <h1>Contatos</h1>
          </div>
          <ErrorState retryHref={pageHref(page, tag)} />
        </main>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <AppHeader />
      <main className={styles.content}>
        <div className={styles.titleRow}>
          <div className={styles.titleBlock}>
            <p className={styles.eyebrow}>Visão geral</p>
            <h1>Contatos</h1>
          </div>
          <div className={styles.totalCount}>
            <strong>{contacts.total}</strong>
            <span>{contacts.total === 1 ? "contato" : "contatos"}</span>
          </div>
        </div>

        <section className={styles.listSection} aria-labelledby="contact-list-title">
          <div className={styles.toolbar}>
            <div>
              <h2 id="contact-list-title">Lista de contatos</h2>
              <p>
                {tag ? `Filtrando por ${tag}` : "Todos os contatos cadastrados"}
              </p>
            </div>
            <TagFilter tags={tags} selectedTag={tag} />
          </div>

          <ContactsTable data={contacts} />
          <Pagination data={contacts} tag={tag} />
        </section>
      </main>
    </div>
  );
}

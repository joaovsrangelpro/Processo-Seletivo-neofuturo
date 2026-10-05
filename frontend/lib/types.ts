export interface ContactListItem {
  id: number;
  full_name: string;
  email: string;
  phone: string;
  source: string | null;
  address: Record<string, unknown> | null;
  created_at: string;
  has_ai_summary: boolean;
}

export interface ContactListResponse {
  items: ContactListItem[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface Tag {
  id: number;
  name: string;
}

export interface ContactTagResponse {
  contact_id: number;
  tag_id: number;
  tag_name: string;
}

export interface Address {
  cep: string;
  logradouro: string;
  bairro: string;
  cidade: string;
  uf: string;
}

export interface AISummary {
  id: number;
  contact_id: number;
  summary_text: string;
  generated_at: string;
}

export interface ContactDetail {
  id: number;
  full_name: string;
  email: string;
  phone: string;
  source: string | null;
  address: Address | null;
  created_at: string;
  tags: Tag[];
  latest_ai_summary: AISummary | null;
}

export interface ContactImportReport {
  imported: number;
  rejected: number;
  errors: { index: number; reason: string }[];
}

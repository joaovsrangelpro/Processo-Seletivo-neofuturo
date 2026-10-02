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

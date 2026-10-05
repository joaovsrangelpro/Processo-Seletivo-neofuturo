import type { ContactDetail, ContactListResponse, Tag } from "./types";

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public readonly status: number) {
    super(`API request failed with status ${status}.`);
    this.name = "ApiError";
  }
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    cache: "no-store",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new ApiError(response.status);
  }

  return (await response.json()) as T;
}

interface GetContactsParams {
  page: number;
  pageSize: number;
  tag?: string;
}

export function getContacts({
  page,
  pageSize,
  tag,
}: GetContactsParams): Promise<ContactListResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });

  if (tag) {
    params.set("tag", tag);
  }

  return get<ContactListResponse>(`/contacts?${params.toString()}`);
}

export function getTags(): Promise<Tag[]> {
  return get<Tag[]>("/tags");
}

export function getContact(id: number): Promise<ContactDetail> {
  return get<ContactDetail>(`/contacts/${id}`);
}

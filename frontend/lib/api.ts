import type { ContactDetail, ContactListResponse, ContactTagResponse, Tag } from "./types";

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public readonly status: number) {
    super(`API request failed with status ${status}.`);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    cache: "no-store",
    headers,
  });

  if (!response.ok) {
    throw new ApiError(response.status);
  }

  if (response.status === 204) {
    return undefined as T;
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

  return request<ContactListResponse>(`/contacts?${params.toString()}`);
}

export function getTags(): Promise<Tag[]> {
  return request<Tag[]>("/tags");
}

export function getContact(id: number): Promise<ContactDetail> {
  return request<ContactDetail>(`/contacts/${id}`);
}

export function addTagToContact(contactId: number, tagId: number): Promise<ContactTagResponse> {
  return request<ContactTagResponse>(`/contacts/${contactId}/tags`, {
    method: "POST",
    body: JSON.stringify({ tag_id: tagId }),
  });
}

export function removeTagFromContact(contactId: number, tagId: number): Promise<void> {
  return request<void>(`/contacts/${contactId}/tags/${tagId}`, { method: "DELETE" });
}

import type { components } from './api-types';
import { PUBLIC_API_URL } from '$env/static/public';

export type QueryResponse = components['schemas']['QueryResponse'];
export type Citation = components['schemas']['Citation'];
export type DocumentChunk = components['schemas']['DocumentChunk'];
export type ConceptGraph = components['schemas']['ConceptGraph'];
export type ConceptNode = components['schemas']['ConceptNode'];
export type ConceptEdge = components['schemas']['ConceptEdge'];
export type HealthResponse = components['schemas']['HealthResponse'];
export type IngestResponse = components['schemas']['IngestResponse'];

const BASE = PUBLIC_API_URL ?? 'http://localhost:8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
	const res = await fetch(`${BASE}${path}`, init);
	if (!res.ok) {
		const body = await res.json().catch(() => ({}));
		throw new Error(body.detail || `${res.status} ${res.statusText}`);
	}
	return res.json();
}

export function queryKnowledge(question: string, maxChunks = 5): Promise<QueryResponse> {
	return request('/query', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ question, max_chunks: maxChunks, include_graph: true })
	});
}

export function getConceptGraph(concept: string, depth = 2): Promise<ConceptGraph> {
	return request(`/graph/${encodeURIComponent(concept)}?depth=${depth}`);
}

export function getHealth(): Promise<HealthResponse> {
	return request('/health');
}

export async function uploadPdfs(files: FileList): Promise<IngestResponse> {
	const form = new FormData();
	for (const file of files) {
		form.append('files', file);
	}
	return request('/ingest/upload', { method: 'POST', body: form });
}

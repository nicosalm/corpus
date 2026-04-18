import type { QueryResponse, Citation, DocumentChunk, ConceptGraph } from './api.ts';

export interface HistoryEntry {
	question: string;
	answer: string;
	citations?: Citation[];
	chunks: DocumentChunk[];
	graph?: ConceptGraph | null;
	timestamp: number;
	processingTimeMs: number;
	costCents: number;
}

const STORAGE_KEY = 'corpus_query_history';
const MAX_ENTRIES = 25;

export function loadHistory(): HistoryEntry[] {
	if (typeof localStorage === 'undefined') return [];
	try {
		return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
	} catch {
		return [];
	}
}

export function saveToHistory(question: string, response: QueryResponse): void {
	const history = loadHistory();
	history.unshift({
		question,
		answer: response.answer,
		citations: response.citations,
		chunks: response.chunks,
		graph: response.graph,
		timestamp: Date.now(),
		processingTimeMs: response.processing_time_ms,
		costCents: response.cost_cents
	});
	if (history.length > MAX_ENTRIES) history.length = MAX_ENTRIES;
	try {
		localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
	} catch {
		history.length = Math.floor(history.length / 2);
		localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
	}
}

export function clearHistory(): void {
	localStorage.removeItem(STORAGE_KEY);
}

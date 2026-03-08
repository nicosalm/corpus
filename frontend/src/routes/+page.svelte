<script lang="ts">
	import { queryKnowledge, type QueryResponse } from '$lib/api';
	import { saveToHistory, type HistoryEntry } from '$lib/history';
	import QueryInput from '$lib/components/QueryInput.svelte';
	import QueryMeta from '$lib/components/QueryMeta.svelte';
	import Answer from '$lib/components/Answer.svelte';
	import SourceChunks from '$lib/components/SourceChunks.svelte';
	import ConceptGraph from '$lib/components/ConceptGraph.svelte';
	import QueryHistory from '$lib/components/QueryHistory.svelte';

	let loading = $state(false);
	let response = $state<QueryResponse | null>(null);
	let error = $state('');
	let lastQuestion = $state('');
	let fromHistory = $state(false);

	async function handleQuery(question: string) {
		loading = true;
		error = '';
		response = null;
		lastQuestion = question;
		fromHistory = false;

		try {
			response = await queryKnowledge(question);
			saveToHistory(question, response);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Query failed';
		} finally {
			loading = false;
		}
	}

	function handleHistorySelect(entry: HistoryEntry) {
		lastQuestion = entry.question;
		fromHistory = true;
		error = '';
		response = {
			answer: entry.answer,
			chunks: entry.chunks ?? [],
			graph: entry.graph ?? null,
			processing_time_ms: entry.processingTimeMs,
			cost_cents: 0,
			cached: true
		};
	}
</script>

<div class="page">
	<aside class="sidebar">
		<QueryHistory onselect={handleHistorySelect} />
	</aside>

	<main class="content">
		<QueryInput onsubmit={handleQuery} disabled={loading} />

		{#if loading}
			<p class="status">thinking...</p>
		{/if}

		{#if error}
			<p class="error">{error}</p>
		{/if}

		{#if response}
			<p class="query-echo">{lastQuestion}</p>

			<Answer answer={response.answer} />

			<QueryMeta
				processingTimeMs={response.processing_time_ms}
				costCents={response.cost_cents}
				chunksUsed={response.chunks.length}
				cached={response.cached}
			/>

			{#if response.chunks.length > 0}
				<SourceChunks chunks={response.chunks} />
			{/if}

			{#if response.graph && response.graph.nodes.length > 0}
				<ConceptGraph graph={response.graph} />
			{/if}

			{#if fromHistory}
				<button class="requery" onclick={() => handleQuery(lastQuestion)}>re-query for fresh answer</button>
			{/if}
		{/if}
	</main>
</div>

<style>
	.page {
		display: flex;
		flex-direction: column-reverse;
		gap: 1rem;
	}

	.content {
		max-width: 72ch;
		min-width: 0;
	}

	@media (min-width: 960px) {
		.page {
			display: grid;
			grid-template-columns: 14rem 1fr;
			gap: 2rem;
			align-items: start;
		}

		.sidebar {
			position: sticky;
			top: 1.5rem;
			max-height: calc(100vh - 3rem);
			overflow-y: auto;
		}
	}

	.query-echo {
		font-style: italic;
		color: var(--text-secondary);
		margin-bottom: 0.75rem;
	}

	.status {
		color: var(--text-secondary);
		font-size: var(--fs-small);
		margin-bottom: 0.5rem;
	}

	.error {
		color: #c44;
		font-size: var(--fs-small);
		margin-bottom: 0.5rem;
	}

	.requery {
		border: 1px solid var(--border-light);
		background: none;
		color: var(--text-secondary);
		font-size: var(--fs-small);
		padding: 0.25rem 0.5rem;
		border-radius: 3px;
		margin-top: 0.25rem;
	}

	.requery:hover {
		color: var(--text);
		border-color: var(--border);
	}
</style>

<script lang="ts">
	import type { Citation, DocumentChunk } from '$lib/api';

	interface Props {
		citations: Citation[];
		chunks: DocumentChunk[];
	}

	let { citations, chunks }: Props = $props();

	function sourceIndex(chunkId: string): number {
		return chunks.findIndex((c) => c.metadata.chunk_id === chunkId);
	}

	function formatSource(chunk: DocumentChunk | undefined): string {
		if (!chunk) return '';
		const parts: string[] = [];
		if (chunk.metadata.course) parts.push(chunk.metadata.course);
		if (chunk.metadata.lecture) parts.push(chunk.metadata.lecture);
		if (chunk.metadata.page_num) parts.push(`p. ${chunk.metadata.page_num}`);
		return parts.join(' · ');
	}
</script>

{#if citations.length > 0}
	<ol class="citations">
		{#each citations as citation, i}
			{@const idx = sourceIndex(citation.chunk_id)}
			{@const chunk = idx >= 0 ? chunks[idx] : undefined}
			<li>
				<span class="marker">[{i + 1}]</span>
				<span class="quote">&ldquo;{citation.quote}&rdquo;</span>
				<span class="source">
					{#if idx >= 0}
						Source {idx + 1}{#if formatSource(chunk)} · {formatSource(chunk)}{/if}
					{:else}
						unknown source
					{/if}
				</span>
			</li>
		{/each}
	</ol>
{/if}

<style>
	.citations {
		list-style: none;
		padding: 0;
		margin: 0 0 0.75rem 0;
		font-size: var(--fs-small);
		border-left: 2px solid var(--border-light);
	}

	li {
		padding: 0.3rem 0.5rem;
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.25rem 0.4rem;
		align-items: baseline;
	}

	.marker {
		font-family: var(--font-mono);
		color: var(--text-secondary);
		font-weight: 700;
	}

	.quote {
		color: var(--text);
		line-height: 1.4;
	}

	.source {
		grid-column: 2;
		color: var(--text-secondary);
		font-size: 0.85em;
	}
</style>
